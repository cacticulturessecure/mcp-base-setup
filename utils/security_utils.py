#!/usr/bin/env python3
"""
Security utilities for SimpleAnthropicCLI
"""

import os
import json
import base64
import logging
from typing import Dict, Any, Optional, Union

# We're implementing a basic encryption mechanism here
# For production code, consider using the `cryptography` package
# or the system's keyring service

def encrypt_simple(data: str, key: str) -> str:
    """Basic XOR-based encryption (NOT for production use).
    
    Args:
        data: String to encrypt
        key: Encryption key
        
    Returns:
        Base64-encoded encrypted string
    """
    # Extend the key to match the data length
    extended_key = key * (len(data) // len(key) + 1)
    extended_key = extended_key[:len(data)]
    
    # XOR operation
    encrypted_bytes = bytes([ord(d) ^ ord(k) for d, k in zip(data, extended_key)])
    
    # Return base64 encoded string
    return base64.b64encode(encrypted_bytes).decode('utf-8')

def decrypt_simple(encrypted: str, key: str) -> str:
    """Basic XOR-based decryption (NOT for production use).
    
    Args:
        encrypted: Base64-encoded encrypted string
        key: Encryption key
        
    Returns:
        Decrypted string
    """
    try:
        # Decode base64
        encrypted_bytes = base64.b64decode(encrypted)
        
        # Extend the key to match the data length
        extended_key = key * (len(encrypted_bytes) // len(key) + 1)
        extended_key = extended_key[:len(encrypted_bytes)]
        
        # XOR operation (same as encryption)
        decrypted = ''.join([chr(b ^ ord(k)) for b, k in zip(encrypted_bytes, extended_key)])
        
        return decrypted
    except Exception as e:
        logging.error(f"Decryption error: {e}")
        return ""

def get_encryption_key() -> str:
    """Get or create an encryption key.
    
    Returns:
        Encryption key
    """
    # In a real implementation, this should use system keyring or another secure method
    # This is a simplified version that uses a device-specific value
    
    # Combine username and hostname for a device-specific value
    import getpass
    import socket
    
    username = getpass.getuser()
    hostname = socket.gethostname()
    
    # Create a basic key - NOT suitable for production
    key = f"{username}:{hostname}:SimpleAnthropicCLI_SECRET_KEY"
    return key

def secure_store(data: Dict[str, Any], filename: str) -> bool:
    """Store data securely.
    
    Args:
        data: Dictionary to store
        filename: Filename to store data in
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert dict to JSON string
        json_data = json.dumps(data)
        
        # Encrypt
        key = get_encryption_key()
        encrypted = encrypt_simple(json_data, key)
        
        # Store
        with open(filename, 'w') as f:
            f.write(encrypted)
            
        return True
    except Exception as e:
        logging.error(f"Error in secure_store: {e}")
        return False

def secure_load(filename: str) -> Optional[Dict[str, Any]]:
    """Load data securely.
    
    Args:
        filename: Filename to load data from
        
    Returns:
        Dictionary of loaded data, or None if error
    """
    if not os.path.exists(filename):
        return None
        
    try:
        # Read encrypted data
        with open(filename, 'r') as f:
            encrypted = f.read()
            
        # Decrypt
        key = get_encryption_key()
        json_data = decrypt_simple(encrypted, key)
        
        # Parse JSON
        data = json.loads(json_data)
        
        return data
    except Exception as e:
        logging.error(f"Error in secure_load: {e}")
        return None

def mask_api_key(api_key: str) -> str:
    """Mask an API key for display purposes.
    
    Args:
        api_key: API key to mask
        
    Returns:
        Masked API key (e.g. "sk_...1234")
    """
    if not api_key or len(api_key) < 8:
        return "Not set"
        
    # Show first 3 and last 4 characters
    return f"{api_key[:3]}...{api_key[-4:]}"