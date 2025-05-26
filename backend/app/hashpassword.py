
import bcrypt

# 비밀번호를 바이트로 인코딩
password_bytes = "admin7749!".encode('utf-8')
# salt 생성 및 해시화
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password_bytes, salt)
# 해시된 비밀번호를 문자열로 디코딩
print(f"{hashed.decode('utf-8')}")
