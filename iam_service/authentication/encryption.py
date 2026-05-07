"""
encryption.py - Utilidades de Cifrado para Campos Sensibles

Este modulo proporciona funciones para cifrar y descifrar campos sensibles
en el modelo de Usuario, como email y telefono, utilizando AES-256-GCM.

El cifrado de campos sensibles es un requisito de seguridad para proteger
la informacion personal identificable (PII) de los usuarios.

Autor: Equipo de Desarrollo LegalFlow
"""

import os
import base64
import hashlib
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from django.conf import settings


# Salt fijo para derivacion de clave (debe ser consistente entre reinicios)
# En produccion, esto deberia almacenarse de forma segura
ENCRYPTION_SALT = b'legalflow_iam_field_encryption_v1'


def get_encryption_key() -> bytes:
    """
    Obtiene la clave de cifrado para campos sensibles.

    Deriva una clave AES-256 a partir de la SECRET_KEY de Django
    usando PBKDF2 con SHA256.

    Returns:
        bytes: Clave de 32 bytes para AES-256
    """
    # Obtener la clave base desde settings
    secret_key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if not secret_key:
        secret_key = settings.SECRET_KEY

    # Convertir a bytes si es string
    if isinstance(secret_key, str):
        secret_key = secret_key.encode('utf-8')

    # Derivar clave usando PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits para AES-256
        salt=ENCRYPTION_SALT,
        iterations=100000,
        backend=default_backend()
    )

    return kdf.derive(secret_key)


def encrypt_field(value: str) -> str:
    """
    Cifra un valor de campo usando AES-256-GCM.

    Args:
        value: Valor en texto plano a cifrar

    Returns:
        str: Valor cifrado codificado en base64 (formato: nonce:ciphertext)
    """
    if not value:
        return value

    # Obtener clave de cifrado
    key = get_encryption_key()

    # Crear instancia AESGCM
    aesgcm = AESGCM(key)

    # Generar nonce aleatorio (12 bytes para GCM)
    nonce = os.urandom(12)

    # Cifrar el valor
    plaintext = value.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Combinar nonce + ciphertext y codificar en base64
    encrypted_data = nonce + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8')


def decrypt_field(encrypted_value: str) -> str:
    """
    Descifra un valor de campo cifrado con AES-256-GCM.

    Args:
        encrypted_value: Valor cifrado en base64

    Returns:
        str: Valor descifrado en texto plano
    """
    if not encrypted_value:
        return encrypted_value

    try:
        # Decodificar de base64
        encrypted_data = base64.b64decode(encrypted_value.encode('utf-8'))

        # Extraer nonce (primeros 12 bytes) y ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]

        # Obtener clave de cifrado
        key = get_encryption_key()

        # Crear instancia AESGCM y descifrar
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode('utf-8')
    except Exception:
        # Si falla el descifrado, devolver el valor original
        # (puede ser un valor sin cifrar o corrupto)
        return encrypted_value


def hash_for_lookup(value: str) -> str:
    """
    Genera un hash determinista de un valor para busquedas.

    Como los valores cifrados incluyen nonces aleatorios, no se pueden
    usar directamente para busquedas. Este hash permite buscar por
    valores exactos sin revelar el valor real.

    Args:
        value: Valor a hashear

    Returns:
        str: Hash SHA256 del valor normalizado
    """
    if not value:
        return ''

    # Normalizar el valor (minusculas, sin espacios)
    normalized = value.lower().strip()

    # Agregar salt del proyecto para evitar rainbow tables
    salted = f"legalflow:{normalized}".encode('utf-8')

    # Generar hash SHA256
    return hashlib.sha256(salted).hexdigest()


class EncryptedFieldMixin:
    """
    Mixin para modelos que requieren campos cifrados.

    Proporciona metodos para acceder a valores cifrados/descifrados
    de forma transparente.
    """

    # Lista de campos que deben ser cifrados
    ENCRYPTED_FIELDS = []

    def get_decrypted_value(self, field_name: str) -> Optional[str]:
        """
        Obtiene el valor descifrado de un campo.

        Args:
            field_name: Nombre del campo cifrado

        Returns:
            str: Valor descifrado o None
        """
        encrypted_field = f"{field_name}_encrypted"
        encrypted_value = getattr(self, encrypted_field, None)

        if encrypted_value:
            return decrypt_field(encrypted_value)
        return None

    def set_encrypted_value(self, field_name: str, value: str):
        """
        Establece un valor cifrado para un campo.

        Args:
            field_name: Nombre del campo
            value: Valor en texto plano a cifrar
        """
        encrypted_field = f"{field_name}_encrypted"
        hash_field = f"{field_name}_hash"

        if value:
            setattr(self, encrypted_field, encrypt_field(value))
            # Tambien guardar hash para busquedas
            if hasattr(self, hash_field):
                setattr(self, hash_field, hash_for_lookup(value))
        else:
            setattr(self, encrypted_field, None)
            if hasattr(self, hash_field):
                setattr(self, hash_field, None)
