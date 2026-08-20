"""Data encryption/decryption utilities for sensitive files."""

import os
from pathlib import Path
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


def get_or_create_key(key_file: Path = Path(".encryption_key")) -> bytes:
    """
    Get or create the encryption master key.
    
    ⚠️ IMPORTANT: In production, store this key in:
    - Azure Key Vault
    - AWS Secrets Manager
    - Environment variable (encrypted)
    - Hardware security module
    
    NEVER commit this key to Git!
    """
    if key_file.exists():
        with open(key_file, "rb") as f:
            return f.read()
    
    # Generate new key
    key = Fernet.generate_key()
    
    # Save it locally (with restricted permissions)
    key_file.write_bytes(key)
    # Set file permissions to 600 (owner read/write only) on Unix
    if hasattr(os, 'chmod'):
        os.chmod(key_file, 0o600)
    
    logger.warning(f"Generated new encryption key at {key_file}")
    logger.warning("⚠️ BACKUP THIS KEY - losing it means losing access to encrypted data!")
    
    return key


def encrypt_file(input_path: Path, output_path: Path = None, key: bytes = None):
    """Encrypt a file."""
    if key is None:
        key = get_or_create_key()
    
    if output_path is None:
        output_path = Path(str(input_path) + ".encrypted")
    
    cipher = Fernet(key)
    
    with open(input_path, "rb") as f:
        data = f.read()
    
    encrypted_data = cipher.encrypt(data)
    
    with open(output_path, "wb") as f:
        f.write(encrypted_data)
    
    logger.info(f"Encrypted {input_path} → {output_path}")
    return output_path


def decrypt_file(input_path: Path, output_path: Path = None, key: bytes = None) -> Path:
    """Decrypt a file."""
    if key is None:
        key = get_or_create_key()
    
    if output_path is None:
        output_path = Path(str(input_path).replace(".encrypted", ""))
    
    cipher = Fernet(key)
    
    try:
        with open(input_path, "rb") as f:
            encrypted_data = f.read()
        
        decrypted_data = cipher.decrypt(encrypted_data)
        
        with open(output_path, "wb") as f:
            f.write(decrypted_data)
        
        logger.info(f"Decrypted {input_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to decrypt {input_path}: {e}")
        raise


def encrypt_bytes(data: bytes, key: bytes = None) -> bytes:
    """Encrypt bytes in memory."""
    if key is None:
        key = get_or_create_key()
    
    cipher = Fernet(key)
    return cipher.encrypt(data)


def decrypt_bytes(encrypted_data: bytes, key: bytes = None) -> bytes:
    """Decrypt bytes in memory."""
    if key is None:
        key = get_or_create_key()
    
    cipher = Fernet(key)
    return cipher.decrypt(encrypted_data)
