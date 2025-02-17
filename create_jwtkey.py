import secrets

# 32바이트(256비트) 랜덤 문자열 생성
secret_key = secrets.token_hex(32)
print(secret_key)
