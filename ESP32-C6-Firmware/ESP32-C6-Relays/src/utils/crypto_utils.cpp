#include "crypto_utils.h"
#include <mbedtls/aes.h>
#include "logging.h"

const byte aes_key[16] = { 0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6, 0xA7, 0xB8, 0xC9, 0xD0, 0xE1, 0xF2, 0xA3, 0xB4, 0xC5 };

void encryptAES(const char* input, char* output, int length) {
    mbedtls_aes_context aes;
    mbedtls_aes_init(&aes);
    mbedtls_aes_setkey_enc(&aes, aes_key, 128);

    mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_ENCRYPT, (unsigned char*)input, (unsigned char*)output);
    mbedtls_aes_free(&aes);

    LOG_INFO("Wi-Fi credentials encrypted.");
}

void decryptAES(const char* input, char* output, int length) {
    mbedtls_aes_context aes;
    mbedtls_aes_init(&aes);
    mbedtls_aes_setkey_dec(&aes, aes_key, 128);

    mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_DECRYPT, (unsigned char*)input, (unsigned char*)output);
    mbedtls_aes_free(&aes);

    LOG_INFO("Wi-Fi credentials decrypted.");
}
