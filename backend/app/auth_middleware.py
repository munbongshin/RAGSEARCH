import sys
import os
from functools import wraps
from flask import request, redirect, url_for, current_app
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import logging
from typing import Optional
from backend.app.auth_session_service import SessionService

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
        if self._pool is None:
            try:
                self._pool = SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dbname=os.getenv('POSTGRES_DB'),
                    user=os.getenv('POSTGRES_USER'),
                    password=os.getenv('POSTGRES_PASSWORD'),
                    host=os.getenv('POSTGRES_HOST'),
                    port=int(os.getenv('POSTGRES_PORT')),
                )
                logger.info("Database connection pool created successfully")
            except Exception as e:
                logger.error(f"Failed to create database pool: {str(e)}")
                raise

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    def get_db_connection(self):
        """
        Creates and returns a connection to the PostgreSQL database.
        
        Returns:
            psycopg2.extensions.connection: Database connection object
            
        Raises:
            psycopg2.Error: If connection fails
        """
        conn = psycopg2.connect(
            dbname=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            host=os.getenv('POSTGRES_HOST'),
            port=int(os.getenv('POSTGRES_PORT'))
        )
        conn.autocommit = False  # 명시적 트랜잭션 관리를 위해
        return conn

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

    def require_session(self,f):
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
        if DatabasePool._instance and DatabasePool._instance._pool:
            DatabasePool._instance._pool.closeall()
            logger.info("Database connection pool closed")

    # Flask 애플리케이션에서 사용할 초기화 함수
    def init_db_pool(self,app):
        """
        Flask 애플리케이션에 데이터베이스 풀 초기화 및 정리 로직 등록
        
        Args:
            app: Flask 애플리케이션 인스턴스
        """
        DatabasePool.get_instance()
        app.teardown_appcontext(lambda exc: self.cleanup_pool())