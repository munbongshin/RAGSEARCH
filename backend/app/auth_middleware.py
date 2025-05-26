import sys
import os
from functools import wraps
from flask import request, redirect, url_for, current_app
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from contextlib import contextmanager
import logging
from typing import Optional
from backend.app.auth_session_service import SessionService
from dotenv import load_dotenv
from pathlib import Path
from sshtunnel import SSHTunnelForwarder

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabasePool:
    _instance = None
    _pool = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        project_root = Path(__file__).parent
        env_path = project_root / '.env'
        load_dotenv(dotenv_path=env_path)
        self.db_type = int(os.getenv('POSTGRES_Db_Type', '0'))
        
        try:
            # db_type에 따라 다른 설정 적용
            if self.db_type == 0:
                self.db_settings = {
                    'host': os.getenv('POSTGRES_HOST'),
                    'port': int(os.getenv('POSTGRES_PORT')),
                    'database': os.getenv('POSTGRES_DB'),
                    'user': os.getenv('POSTGRES_USER'),
                    'password': os.getenv('POSTGRES_PASSWORD')
                }
                
                # 타입 0일 때만 연결 풀 생성
                self._pool = SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dbname=self.db_settings['database'],
                    user=self.db_settings['user'],
                    password=self.db_settings['password'],
                    host=self.db_settings['host'],
                    port=self.db_settings['port'],
                    client_encoding='utf8'  # 명시적으로 인코딩 지정
                )
                logger.info("Database connection pool created successfully")
                
            elif self.db_type == 1:
                self.db_settings = {
                    'host': os.getenv("GPOSTGRES_HOST"),
                    'port': int(os.getenv("GPOSTGRES_PORT", "5432")),
                    'database': os.getenv("GPOSTGRES_DB"),
                    'user': os.getenv("GPOSGITTGRES_USER"),
                    'password': os.getenv("GPOSTGRES_PASSWORD")
                }
                # 타입 1은 연결 풀을 생성하지 않고 SSH 터널링 사용 정보만 설정
                logger.info("SSH tunneling mode configured for database connections")
                
            else:
                raise ValueError(f"Invalid db_type: {self.db_type}. Must be 0 or 1.")
                
        except Exception as e:
            logger.error(f"Failed to create database pool: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            # 더 자세한 오류 추적
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    @contextmanager
    def get_connection(self):
        conn = None
        tunnel = None
        try:
            if self.db_type == 0:
                # 일반 연결 사용
                conn = self._pool.getconn()
            else:
                # SSH 터널링 사용
                tunnel = SSHTunnelForwarder(
                    (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", "22"))),
                    ssh_username=os.getenv("SSH_USER"),
                    ssh_password=os.getenv("SSH_PASSWORD"),
                    remote_bind_address=(os.getenv("GPOSTGRES_HOST"), int(os.getenv("GPOSTGRES_PORT", "5432"))),
                    local_bind_address=('127.0.0.1', 0)
                )
                tunnel.start()
                
                logger.info("SSH 터널링 연결 성공")
                logger.info(f"로컬에서 사용할 포트: {tunnel.local_bind_host}:{tunnel.local_bind_port}")

                # SSH 터널링을 통한 PostgreSQL 연결
                conn = psycopg2.connect(
                    dbname=os.getenv("GPOSTGRES_DB"),
                    user=os.getenv("GPOSGITTGRES_USER"),
                    password=os.getenv("GPOSTGRES_PASSWORD"),
                    host=tunnel.local_bind_host,
                    port=tunnel.local_bind_port,
                    cursor_factory=DictCursor
                )
            
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if self.db_type == 0 and conn:
                self._pool.putconn(conn)
            elif conn:
                conn.close()
            if tunnel:
                tunnel.stop()

    def get_db_connection(self):
        try:
            
            if self.db_type == 0:
                self.conn = psycopg2.connect(
                    **self.db_settings,
                    cursor_factory=DictCursor
                )
            else:
                # SSH 터널 생성 및 유지 (인스턴스 변수로 저장)
                self.tunnel = SSHTunnelForwarder(
                    (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", "22"))),
                    ssh_username=os.getenv("SSH_USER"),
                    ssh_password=os.getenv("SSH_PASSWORD"),
                    remote_bind_address=(os.getenv("GPOSTGRES_HOST"), int(os.getenv("GPOSTGRES_PORT", "5432"))),
                    local_bind_address=('127.0.0.1', 0)
                )
                self.tunnel.start()
                
                print("SSH 터널링 연결 성공")
                print(f"로컬에서 사용할 포트: {self.tunnel.local_bind_host}:{self.tunnel.local_bind_port}")

                # SSH 터널링을 통한 PostgreSQL 연결
                self.conn = psycopg2.connect(
                    dbname=os.getenv("GPOSTGRES_DB"),
                    user=os.getenv("GPOSGITTGRES_USER"),
                    password=os.getenv("GPOSTGRES_PASSWORD"),
                    host=self.tunnel.local_bind_host,
                    port=self.tunnel.local_bind_port,
                    cursor_factory=DictCursor
                )
            with self.conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            self.conn.commit()
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise

    @staticmethod
    def handle_db_error(error: Exception) -> tuple:
        """
        데이터베이스 오류 처리를 위한 유틸리티 함수
        
        Args:
            error: 발생한 예외
        
        Returns:
            tuple: (에러 메시지, HTTP 상태 코드)
        """
        logger.error(f"Database error: {str(error)}")
        if isinstance(error, psycopg2.OperationalError):
            return "데이터베이스 연결 오류가 발생했습니다.", 503
        if isinstance(error, psycopg2.IntegrityError):
            return "데이터 무결성 오류가 발생했습니다.", 400
        return "내부 서버 오류가 발생했습니다.", 500

    def require_session(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            session_id = request.cookies.get('session_id')
            
            if not session_id:
                logger.warning("No session ID found in request cookies")
                return redirect(url_for('auth.login'))
                
            try:
                with self.get_connection() as conn:                    
                    session_service = SessionService(conn)
                    user_data = session_service.validate_session(session_id)
                    
                    if not user_data:
                        logger.warning(f"Invalid or expired session: {session_id}")
                        return redirect(url_for('auth.login'))
                        
                    # 사용자 정보를 요청 객체에 추가
                    request.user = user_data
                    return f(*args, **kwargs)
                    
            except Exception as e:
                logger.error(f"Session validation error: {str(e)}")
                error_message, status_code = self.handle_db_error(e)
                return {"error": error_message}, status_code
                
        return decorated

    # 애플리케이션 종료 시 연결 풀 정리를 위한 함수
    def cleanup_pool(self):
        if DatabasePool._instance:
            if self.db_type == 0 and DatabasePool._instance._pool:
                DatabasePool._instance._pool.closeall()
                logger.info("Database connection pool closed")
            if hasattr(self, 'tunnel') and self.tunnel:
                self.tunnel.stop()
                logger.info("SSH tunnel closed")

    # Flask 애플리케이션에서 사용할 초기화 함수
    def init_db_pool(self, app):
        """
        Flask 애플리케이션에 데이터베이스 풀 초기화 및 정리 로직 등록
        
        Args:
            app: Flask 애플리케이션 인스턴스
        """
        DatabasePool.get_instance()
        app.teardown_appcontext(lambda exc: self.cleanup_pool())