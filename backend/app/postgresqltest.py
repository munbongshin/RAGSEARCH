from sshtunnel import SSHTunnelForwarder
import psycopg2
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

def connect_to_postgresql():
    try:
        with SSHTunnelForwarder(
            (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", "22"))),  # 여기 콤마 누락됨
            ssh_username=os.getenv("SSH_USER"),
            ssh_password=os.getenv("SSH_PASSWORD"),
            remote_bind_address=(os.getenv("GPOSTGRES_HOST"), int(os.getenv("GPOSTGRES_PORT", "5432"))),
            local_bind_address=('127.0.0.1', 0)
        ) as tunnel:
            print("SSH 터널링 연결 성공")
            print(f"로컬에서 사용할 포트: {tunnel.local_bind_host}:{tunnel.local_bind_port}")

            # SSH 터널링을 통한 PostgreSQL 연결
            conn = psycopg2.connect(
                dbname=os.getenv("GPOSTGRES_DB"),
                user=os.getenv("GPOSGITTGRES_USER"),
                password=os.getenv("GPOSTGRES_PASSWORD"),
                host=tunnel.local_bind_host,
                port=tunnel.local_bind_port
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            print(f"PostgreSQL 버전: {cursor.fetchone()[0]}")

            # 연결 종료
            cursor.close()
            conn.close()
            print("PostgreSQL 연결 종료")

    except Exception as e:
        print(f"PostgreSQL 연결 실패: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    connect_to_postgresql()