from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

AES_KEY = b'\xA1\xB2\xC3\xD4\xE5\xF6\xA7\xB8\xC9\xD0\xE1\xF2\xA3\xB4\xC5\xD6'


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
