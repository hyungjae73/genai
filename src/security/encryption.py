"""
Encryption utilities for sensitive data.

This module provides AES-256-GCM encryption/decryption for sensitive contract data.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Union


def generate_key() -> bytes:
    """
    Generate a new 256-bit encryption key.
    
    Returns:
        32-byte encryption key
    """
    return AESGCM.generate_key(bit_length=256)


def _get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable.
    
    Returns:
        32-byte encryption key
        
    Raises:
        ValueError: If ENCRYPTION_KEY is not set or invalid
    """
    key_b64 = os.getenv('ENCRYPTION_KEY')
    
    if not key_b64:
        raise ValueError(
            "ENCRYPTION_KEY environment variable not set. "
            "Generate a key using: python -c 'from src.security.encryption import generate_key; "
            "import base64; print(base64.b64encode(generate_key()).decode())'"
        )
    
    try:
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            raise ValueError(f"Encryption key must be 32 bytes, got {len(key)}")
        return key
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")


def encrypt_data(plaintext: Union[str, bytes]) -> str:
    """
    Encrypt data using AES-256-GCM.
    
    Args:
        plaintext: Data to encrypt (string or bytes)
        
    Returns:
        Base64-encoded encrypted data with nonce prepended
        Format: base64(nonce + ciphertext + tag)
        
    Example:
        >>> encrypted = encrypt_data("sensitive data")
        >>> decrypted = decrypt_data(encrypted)
        >>> assert decrypted == "sensitive data"
    """
    # Convert string to bytes if necessary
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    
    # Get encryption key
    key = _get_encryption_key()
    
    # Create AESGCM cipher
    aesgcm = AESGCM(key)
    
    # Generate random nonce (96 bits / 12 bytes recommended for GCM)
    nonce = os.urandom(12)
    
    # Encrypt data (GCM automatically adds authentication tag)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # Combine nonce + ciphertext and encode as base64
    encrypted_data = nonce + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8')


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt data using AES-256-GCM.
    
    Args:
        encrypted_data: Base64-encoded encrypted data with nonce prepended
        
    Returns:
        Decrypted plaintext as string
        
    Raises:
        ValueError: If decryption fails (wrong key, corrupted data, or tampered data)
        
    Example:
        >>> encrypted = encrypt_data("sensitive data")
        >>> decrypted = decrypt_data(encrypted)
        >>> assert decrypted == "sensitive data"
    """
    try:
        # Decode base64
        encrypted_bytes = base64.b64decode(encrypted_data)
        
        # Extract nonce (first 12 bytes) and ciphertext (remaining bytes)
        nonce = encrypted_bytes[:12]
        ciphertext = encrypted_bytes[12:]
        
        # Get encryption key
        key = _get_encryption_key()
        
        # Create AESGCM cipher
        aesgcm = AESGCM(key)
        
        # Decrypt data (GCM automatically verifies authentication tag)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext.decode('utf-8')
        
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


def encrypt_dict(data: dict) -> dict:
    """
    Encrypt all string values in a dictionary.
    
    Args:
        data: Dictionary with string values to encrypt
        
    Returns:
        Dictionary with encrypted values
    """
    encrypted = {}
    for key, value in data.items():
        if isinstance(value, str):
            encrypted[key] = encrypt_data(value)
        elif isinstance(value, dict):
            encrypted[key] = encrypt_dict(value)
        elif isinstance(value, list):
            encrypted[key] = [
                encrypt_data(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            encrypted[key] = value
    return encrypted


def decrypt_dict(data: dict) -> dict:
    """
    Decrypt all encrypted string values in a dictionary.
    
    Args:
        data: Dictionary with encrypted values
        
    Returns:
        Dictionary with decrypted values
    """
    decrypted = {}
    for key, value in data.items():
        if isinstance(value, str):
            try:
                decrypted[key] = decrypt_data(value)
            except ValueError:
                # Not encrypted, keep as is
                decrypted[key] = value
        elif isinstance(value, dict):
            decrypted[key] = decrypt_dict(value)
        elif isinstance(value, list):
            decrypted[key] = [
                decrypt_data(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            decrypted[key] = value
    return decrypted
