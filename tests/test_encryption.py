"""
Tests for encryption utilities.
"""

import os
import base64
import pytest
from unittest.mock import patch

from src.security.encryption import (
    generate_key,
    encrypt_data,
    decrypt_data,
    encrypt_dict,
    decrypt_dict,
)


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    key = generate_key()
    key_b64 = base64.b64encode(key).decode()
    with patch.dict(os.environ, {'ENCRYPTION_KEY': key_b64}):
        yield key_b64


def test_generate_key():
    """Test key generation."""
    key = generate_key()
    assert len(key) == 32  # 256 bits
    
    # Generate another key and verify it's different
    key2 = generate_key()
    assert key != key2


def test_encrypt_decrypt_string(encryption_key):
    """Test encryption and decryption of string data."""
    plaintext = "sensitive payment information"
    
    # Encrypt
    encrypted = encrypt_data(plaintext)
    assert encrypted != plaintext
    assert isinstance(encrypted, str)
    
    # Decrypt
    decrypted = decrypt_data(encrypted)
    assert decrypted == plaintext


def test_encrypt_decrypt_bytes(encryption_key):
    """Test encryption and decryption of bytes data."""
    plaintext = b"sensitive binary data"
    
    # Encrypt
    encrypted = encrypt_data(plaintext)
    assert isinstance(encrypted, str)
    
    # Decrypt
    decrypted = decrypt_data(encrypted)
    assert decrypted == plaintext.decode('utf-8')


def test_encrypt_decrypt_unicode(encryption_key):
    """Test encryption and decryption of unicode data."""
    plaintext = "機密データ 🔒"
    
    # Encrypt
    encrypted = encrypt_data(plaintext)
    
    # Decrypt
    decrypted = decrypt_data(encrypted)
    assert decrypted == plaintext


def test_encryption_produces_different_ciphertext(encryption_key):
    """Test that encrypting the same data twice produces different ciphertext."""
    plaintext = "test data"
    
    encrypted1 = encrypt_data(plaintext)
    encrypted2 = encrypt_data(plaintext)
    
    # Different nonces should produce different ciphertext
    assert encrypted1 != encrypted2
    
    # But both should decrypt to the same plaintext
    assert decrypt_data(encrypted1) == plaintext
    assert decrypt_data(encrypted2) == plaintext


def test_decrypt_with_wrong_key():
    """Test that decryption fails with wrong key."""
    # Encrypt with one key
    key1 = generate_key()
    key1_b64 = base64.b64encode(key1).decode()
    
    with patch.dict(os.environ, {'ENCRYPTION_KEY': key1_b64}):
        encrypted = encrypt_data("secret")
    
    # Try to decrypt with different key
    key2 = generate_key()
    key2_b64 = base64.b64encode(key2).decode()
    
    with patch.dict(os.environ, {'ENCRYPTION_KEY': key2_b64}):
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_data(encrypted)


def test_decrypt_corrupted_data(encryption_key):
    """Test that decryption fails with corrupted data."""
    plaintext = "test data"
    encrypted = encrypt_data(plaintext)
    
    # Corrupt the encrypted data
    corrupted = encrypted[:-5] + "XXXXX"
    
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_data(corrupted)


def test_decrypt_invalid_base64(encryption_key):
    """Test that decryption fails with invalid base64."""
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_data("not-valid-base64!!!")


def test_missing_encryption_key():
    """Test that encryption fails without ENCRYPTION_KEY."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="ENCRYPTION_KEY environment variable not set"):
            encrypt_data("test")


def test_invalid_encryption_key():
    """Test that encryption fails with invalid key."""
    # Key too short
    with patch.dict(os.environ, {'ENCRYPTION_KEY': base64.b64encode(b'short').decode()}):
        with pytest.raises(ValueError, match="Encryption key must be 32 bytes"):
            encrypt_data("test")


def test_encrypt_dict(encryption_key):
    """Test encryption of dictionary values."""
    data = {
        'username': 'admin',
        'password': 'secret123',
        'api_key': 'key-12345',
        'number': 42,
        'nested': {
            'token': 'token-abc'
        }
    }
    
    encrypted = encrypt_dict(data)
    
    # String values should be encrypted
    assert encrypted['username'] != data['username']
    assert encrypted['password'] != data['password']
    assert encrypted['api_key'] != data['api_key']
    assert encrypted['nested']['token'] != data['nested']['token']
    
    # Non-string values should remain unchanged
    assert encrypted['number'] == data['number']


def test_decrypt_dict(encryption_key):
    """Test decryption of dictionary values."""
    data = {
        'username': 'admin',
        'password': 'secret123',
        'number': 42,
    }
    
    # Encrypt then decrypt
    encrypted = encrypt_dict(data)
    decrypted = decrypt_dict(encrypted)
    
    # Should match original
    assert decrypted == data


def test_encrypt_decrypt_list_in_dict(encryption_key):
    """Test encryption of lists within dictionaries."""
    data = {
        'tags': ['secret1', 'secret2', 'secret3'],
        'count': 3
    }
    
    encrypted = encrypt_dict(data)
    
    # List items should be encrypted
    assert encrypted['tags'][0] != data['tags'][0]
    assert encrypted['tags'][1] != data['tags'][1]
    
    # Decrypt and verify
    decrypted = decrypt_dict(encrypted)
    assert decrypted == data


def test_decrypt_dict_with_non_encrypted_values(encryption_key):
    """Test that decrypt_dict handles non-encrypted values gracefully."""
    data = {
        'plain_text': 'not encrypted',
        'number': 123
    }
    
    # Should not raise error
    decrypted = decrypt_dict(data)
    assert decrypted == data
