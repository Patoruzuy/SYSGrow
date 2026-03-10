"""
WiFi Credential Encryption for ESP32 Devices
=============================================

Uses **AES-256-GCM** (authenticated encryption with associated data).

Output format (base64-encoded)::

    nonce (12 bytes) || ciphertext || auth-tag (16 bytes)

The ESP32 firmware must decode in the same order.

SECURITY NOTE
-------------
* The AES key **must** be configured via the ``SYSGROW_AES_KEY``
  environment variable in production.
* Key format: **64 hex characters** (32 bytes = 256-bit).
* The default key is *INSECURE* — development only.
* Both backend and ESP32 firmware must share the same key.
"""

from __future__ import annotations

import base64
import json
import logging
import os

from Crypto.Cipher import AES  # nosec B413 - using pycryptodome (maintained fork of pyCrypto)
from Crypto.Random import get_random_bytes  # nosec B413

logger = logging.getLogger(__name__)

# Default key for development ONLY — INSECURE
_DEFAULT_KEY_HEX = "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6"
_NONCE_BYTES = 12  # recommended nonce length for GCM
_USING_DEFAULT_KEY = False


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------


def _get_aes_key() -> bytes:
    """Load the 256-bit AES key from the environment (or fall back to the
    insecure default for development).

    Returns
    -------
    bytes
        32-byte AES key.
    """
    global _USING_DEFAULT_KEY

    key_hex = os.getenv("SYSGROW_AES_KEY", "").strip()

    if not key_hex:
        _USING_DEFAULT_KEY = True
        key_hex = _DEFAULT_KEY_HEX
        logger.warning(
            "SECURITY WARNING: Using default AES key. Set SYSGROW_AES_KEY environment variable for production!"
        )
    else:
        _USING_DEFAULT_KEY = False
        # Accept the old 128-bit (32 hex) key with a deprecation warning
        if len(key_hex) == 32:
            logger.warning("SYSGROW_AES_KEY is 128-bit (32 hex chars). Please upgrade to a 256-bit key (64 hex chars).")
            # Pad by repeating to get 256-bit — ensures old setups still boot.
            key_hex = key_hex + key_hex

    if len(key_hex) != 64:
        raise ValueError(f"SYSGROW_AES_KEY must be 64 hex characters (256-bit). Got {len(key_hex)} characters.")

    try:
        return bytes.fromhex(key_hex)
    except ValueError as exc:
        raise ValueError(f"SYSGROW_AES_KEY contains invalid hex characters: {exc}") from exc


def is_using_default_key() -> bool:
    """Return ``True`` if the system is using the insecure default key."""
    return _USING_DEFAULT_KEY


# Initialise key once at module import
AES_KEY: bytes = _get_aes_key()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _encrypt_bytes(plaintext: bytes) -> str:
    """Encrypt *plaintext* with AES-256-GCM.

    Returns a **base64-encoded** string whose decoded form is::

        nonce (12 B) || ciphertext || tag (16 B)
    """
    nonce = get_random_bytes(_NONCE_BYTES)
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    # Pack: nonce + ciphertext + tag
    return base64.b64encode(nonce + ciphertext + tag).decode()


def encrypt_wifi_payload(ssid: str, password: str) -> str:
    """Encrypt Wi-Fi credentials for delivery to an ESP32.

    Parameters
    ----------
    ssid : str
        The Wi-Fi SSID.
    password : str
        The Wi-Fi password.

    Returns
    -------
    str
        Base64-encoded ``nonce || ciphertext || tag``.
    """
    data = json.dumps({"ssid": ssid, "password": password}).encode()
    return _encrypt_bytes(data)


def encrypt_json_payload(json_data: dict) -> str:
    """Encrypt an arbitrary JSON-serialisable dictionary.

    Parameters
    ----------
    json_data : dict
        Data to encrypt.

    Returns
    -------
    str
        Base64-encoded ``nonce || ciphertext || tag``.
    """
    raw = json.dumps(json_data).encode()
    return _encrypt_bytes(raw)
