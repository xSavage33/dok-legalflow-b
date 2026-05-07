"""
encryption.py - Modulo de cifrado para documentos

Este modulo implementa el cifrado y descifrado de archivos usando AES-256-GCM,
un algoritmo de cifrado simetrico autenticado que proporciona confidencialidad
e integridad de los datos.

Caracteristicas:
- Cifrado AES-256-GCM (Galois/Counter Mode)
- Derivacion de clave usando PBKDF2
- Nonce unico por archivo
- Verificacion de integridad (authentication tag)

Autor: Equipo de Desarrollo LegalFlow
"""

import os
import base64
import hashlib
from typing import Tuple, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from django.conf import settings


# Constantes de configuracion
NONCE_SIZE = 12  # Tamano del nonce para AES-GCM (96 bits)
KEY_SIZE = 32    # Tamano de la clave AES-256 (256 bits)
SALT_SIZE = 16   # Tamano del salt para derivacion de clave


def get_encryption_key() -> bytes:
    """
    Obtiene la clave maestra de cifrado desde la configuracion.

    La clave se deriva usando PBKDF2 a partir de una clave secreta
    almacenada en las variables de entorno.

    Returns:
        bytes: Clave de cifrado de 256 bits

    Raises:
        ValueError: Si no hay clave de cifrado configurada
    """
    # Obtener la clave secreta desde settings o variable de entorno
    secret_key = getattr(settings, 'DOCUMENT_ENCRYPTION_KEY', None)
    if not secret_key:
        secret_key = os.environ.get('DOCUMENT_ENCRYPTION_KEY')

    if not secret_key:
        # Si no hay clave configurada, usar SECRET_KEY como fallback
        # En produccion, se debe configurar DOCUMENT_ENCRYPTION_KEY
        secret_key = settings.SECRET_KEY

    # Usar un salt fijo derivado del secret para consistencia
    # En una implementacion mas robusta, el salt seria unico por archivo
    salt = hashlib.sha256(secret_key.encode()).digest()[:SALT_SIZE]

    # Derivar la clave usando PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )

    return kdf.derive(secret_key.encode())


def encrypt_file(file_content: bytes) -> Tuple[bytes, str]:
    """
    Cifra el contenido de un archivo usando AES-256-GCM.

    El formato del archivo cifrado es:
    [nonce (12 bytes)][ciphertext + tag]

    Args:
        file_content: Contenido del archivo en bytes

    Returns:
        Tuple[bytes, str]:
            - Contenido cifrado (nonce + ciphertext + tag)
            - Metadatos de cifrado en base64 (para almacenamiento)
    """
    # Obtener la clave de cifrado
    key = get_encryption_key()

    # Generar un nonce aleatorio unico
    nonce = os.urandom(NONCE_SIZE)

    # Crear el cifrador AES-GCM
    aesgcm = AESGCM(key)

    # Cifrar el contenido
    # AES-GCM automaticamente genera y adjunta el authentication tag
    ciphertext = aesgcm.encrypt(nonce, file_content, None)

    # Concatenar nonce + ciphertext para almacenamiento
    encrypted_data = nonce + ciphertext

    # Crear metadatos de cifrado
    metadata = {
        'algorithm': 'AES-256-GCM',
        'nonce_size': NONCE_SIZE,
        'key_derivation': 'PBKDF2-SHA256'
    }

    # Codificar metadatos en base64
    import json
    metadata_b64 = base64.b64encode(json.dumps(metadata).encode()).decode()

    return encrypted_data, metadata_b64


def decrypt_file(encrypted_content: bytes) -> bytes:
    """
    Descifra el contenido de un archivo cifrado con AES-256-GCM.

    Extrae el nonce del inicio del contenido cifrado y usa
    la clave derivada para descifrar.

    Args:
        encrypted_content: Contenido cifrado (nonce + ciphertext + tag)

    Returns:
        bytes: Contenido descifrado del archivo

    Raises:
        cryptography.exceptions.InvalidTag: Si el archivo fue manipulado
        ValueError: Si el contenido esta corrupto o es invalido
    """
    if len(encrypted_content) < NONCE_SIZE + 16:  # minimo nonce + tag
        raise ValueError("Contenido cifrado invalido o corrupto")

    # Obtener la clave de cifrado
    key = get_encryption_key()

    # Extraer el nonce del inicio
    nonce = encrypted_content[:NONCE_SIZE]
    ciphertext = encrypted_content[NONCE_SIZE:]

    # Crear el descifrador AES-GCM
    aesgcm = AESGCM(key)

    # Descifrar y verificar integridad
    # Esto lanzara InvalidTag si el archivo fue modificado
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext


def encrypt_file_stream(file_obj) -> Tuple[bytes, str]:
    """
    Cifra un archivo desde un objeto de archivo Django.

    Lee el contenido del archivo, lo cifra y retorna los datos cifrados.

    Args:
        file_obj: Objeto de archivo Django (InMemoryUploadedFile o similar)

    Returns:
        Tuple[bytes, str]: Datos cifrados y metadatos
    """
    # Asegurar que estamos al inicio del archivo
    file_obj.seek(0)

    # Leer todo el contenido
    content = file_obj.read()

    # Volver al inicio para uso posterior
    file_obj.seek(0)

    # Cifrar y retornar
    return encrypt_file(content)


def is_file_encrypted(file_content: bytes) -> bool:
    """
    Intenta determinar si un archivo ya esta cifrado.

    Verifica si el contenido parece ser datos cifrados validos
    intentando descifrarlos.

    Args:
        file_content: Contenido del archivo

    Returns:
        bool: True si el archivo parece estar cifrado, False si no
    """
    if len(file_content) < NONCE_SIZE + 16:
        return False

    try:
        # Intentar descifrar
        decrypt_file(file_content)
        return True
    except Exception:
        return False


def calculate_encrypted_checksum(encrypted_content: bytes) -> str:
    """
    Calcula el checksum SHA-256 del contenido cifrado.

    Args:
        encrypted_content: Contenido cifrado

    Returns:
        str: Hash SHA-256 en hexadecimal
    """
    return hashlib.sha256(encrypted_content).hexdigest()
