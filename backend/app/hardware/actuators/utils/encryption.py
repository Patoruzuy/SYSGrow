"""
WiFi Credential Encryption for ESP32 Devices

SECURITY NOTE: The AES key must be configured via environment variable
SYSGROW_AES_KEY in production. The default key is INSECURE and should
only be used for development. Both the backend and ESP32 firmware must
use the same key.

Key format: 32 hex characters (16 bytes) e.g., "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6"
"""
import os
import logging
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

logger = logging.getLogger(__name__)

# Default key for development ONLY - INSECURE
_DEFAULT_KEY_HEX = "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6"
_USING_DEFAULT_KEY = False


def _get_aes_key() -> bytes:
    """
    Get the AES key from environment variable or use default.

    In production, set SYSGROW_AES_KEY to a 32-character hex string.
    The same key must be configured in ESP32 firmware.

    Returns:
        16-byte AES key
    """
    global _USING_DEFAULT_KEY

    key_hex = os.getenv("SYSGROW_AES_KEY", "").strip()

    if not key_hex:
        _USING_DEFAULT_KEY = True
        key_hex = _DEFAULT_KEY_HEX
        logger.warning(
            "SECURITY WARNING: Using default AES key. "
            "Set SYSGROW_AES_KEY environment variable for production!"
        )
    else:
        _USING_DEFAULT_KEY = False

    # Validate key format
    if len(key_hex) != 32:
        raise ValueError(
            f"SYSGROW_AES_KEY must be exactly 32 hex characters (16 bytes), "
            f"got {len(key_hex)} characters"
        )

    try:
        return bytes.fromhex(key_hex)
    except ValueError as e:
        raise ValueError(f"SYSGROW_AES_KEY contains invalid hex characters: {e}")


def is_using_default_key() -> bool:
    """Check if the system is using the default (insecure) AES key."""
    return _USING_DEFAULT_KEY


# Initialize key on module load
AES_KEY = _get_aes_key()


def encrypt_wifi_payload(ssid: str, password: str) -> str:
    """
    Encrypts Wi-Fi credentials using AES ECB mode.

    Args:
        ssid (str): The Wi-Fi SSID.
        password (str): The Wi-Fi password.

    Returns:
        str: Base64-encoded encrypted payload.
    """
    data = f'{{"ssid":"{ssid}", "password":"{password}"}}'.encode()
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(data, AES.block_size))
    return base64.b64encode(encrypted).decode()


def encrypt_json_payload(json_data: dict) -> str:
    """
    Encrypts an entire JSON dictionary payload.

    Args:
        json_data (dict): JSON data to encrypt.

    Returns:
        str: Base64-encoded encrypted string.
    """
    import json
    raw = json.dumps(json_data).encode()
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(raw, AES.block_size))
    return base64.b64encode(encrypted).decode()
