"""
PostgreSQL을 이용한 벡터 저장소 관리자 클래스
ChromaDbManager와 유사한 인터페이스를 제공하여 상호 교체 가능하게 구현
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend/app'))
from backend.app.CustomSentenceTransformerEmbeddings import CustomSentenceTransformerEmbeddings as CSTFM
from backend.app.ExtractTextFromFile import ExtractTextFromFile
from backend.app.QuoteExtractor import QuoteExtractor as QuoExt

from dotenv import load_dotenv
from pathlib import Path
import uuid
import logging
import json
import time
from datetime import datetime  # datetime 모듈 추가
import traceback
import re
from typing import Optional, Dict, Any, List, Generator, Union, Tuple
import psycopg2
from psycopg2.extensions import register_adapter, adapt
from psycopg2.extras import DictCursor, Json
import numpy as np
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter, TokenTextSplitter
from langchain.prompts import PromptTemplate
from langchain.chains.summarize import load_summarize_chain
from konlpy.tag import Okt
from langchain.text_splitter import RecursiveCharacterTextSplitter
from logging.handlers import RotatingFileHandler


# 프로젝트 루트 디렉토리 설정
project_root = Path(__file__).parent
log_dir = project_root / 'logs'
CHUNKSIZE = 2048

# 로그 디렉토리 생성
try:
    log_dir.mkdir(exist_ok=True)
except Exception as e:
    print(f"Error creating log directory: {e}")
    log_dir = project_root  # 폴백: 프로젝트 루트 디렉토리 사용

# 로그 파일 경로 설정
log_file = log_dir / 'postgres_db_manager.log'

# 로깅 기본 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

try:
    # 파일 핸들러 설정
    file_handler = RotatingFileHandler(
        str(log_file),  # Path 객체를 문자열로 변환
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)
except Exception as e:
    print(f"Error setting up file handler: {e}")
    print(f"Will log to console only")

# UUID 어댑터 등록
def adapt_uuid(uuid):
    return psycopg2.extensions.adapt(str(uuid))
register_adapter(uuid.UUID, adapt_uuid)

class VectorStoreType:
    """벡터 저장소 타입 정의"""
    POSTGRES = "postgres"

class VectorStore:
    """벡터 저장소 기본 클래스"""
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.conn_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password
        }
        self.conn = None
        self.embedding_model = CSTFM()
        self._connect()
        

    def _connect(self):
        """데이터베이스 연결 설정"""
        try:
            self.conn = psycopg2.connect(**self.conn_params, cursor_factory=DictCursor)
            with self.conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            self.conn.commit()
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise

    def _get_or_create_collection(self, collection_name: str) -> int:
        try:
            with self.conn.cursor() as cur:
                # 기존 컬렉션 확인
                cur.execute(
                    "SELECT id FROM collections WHERE name = %s",
                    (collection_name,)
                )
                result = cur.fetchone()
                
                if result:
                    return result[0]
                
                # 새 컬렉션 생성
                cur.execute(
                    "INSERT INTO collections (name) VALUES (%s) RETURNING id",
                    (collection_name,)
                )
                collection_id = cur.fetchone()[0]
                self.conn.commit()
                return collection_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in get_or_create_collection: {str(e)}")
            raise

    def store_documents(self, text: List[Any], filename: str, collection_name: str) -> int:
        """문서 저장"""
        try:
            # 입력 데이터 유효성 검사
            if not text:
                logger.warning("No documents provided for storage")
                return 0
            
            logger.info(f"Attempting to store documents for collection: {collection_name}")
            logger.info(f"Total number of chunks: {len(text)}")
            
            collection_id = self._get_or_create_collection(collection_name)
            stored_count = 0
            failed_count = 0
            
            for idx, chunk in enumerate(text, 1):
                try:
                    # 1. 텍스트 컨텐츠 처리
                    content = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
                    
                    if not isinstance(content, str):
                        content = str(content)
                    
                    # 2. 텍스트 정규화
                    content = content.replace('\xa0', ' ')
                    content = ' '.join(content.split())
                    content = content.encode('utf-8', errors='ignore').decode('utf-8')
                    
                    # 입력 길이 제한
                    if len(content) > CHUNKSIZE:  # 예시 길이 제한
                        content = content[:CHUNKSIZE]
                    
                    logger.debug(f"Processing chunk {idx}: {content[:100]}...")
                    
                    # 3. 임베딩 생성
                    try:
                        embedding = self.embedding_model.embed_documents([content])[0]
                        
                        # 추가 검증
                        if not embedding or (isinstance(embedding, list) and len(embedding) == 0):
                            logger.warning(f"Empty embedding generated for chunk {idx}")
                            failed_count += 1
                            continue
                        
                        if not isinstance(embedding, list):
                            embedding = embedding.tolist()
                        
                        # 차원 검증 (예: 768차원 고정)
                        if len(embedding) != 768:
                            logger.warning(f"Unexpected embedding dimension for chunk {idx}: {len(embedding)}")
                            failed_count += 1
                            continue
                            
                    except Exception as e:
                        logger.error(f"Embedding generation error for chunk {idx}: {str(e)}")
                        logger.error(f"Problematic content: {content[:200]}")
                        failed_count += 1
                        continue
                    
                    # 4. 메타데이터 준비
                    metadata = {
                        'source': str(filename),
                        'page': chunk.metadata.get('page', 0) if hasattr(chunk, 'metadata') else 0,
                        'chunk_size': len(content),
                        'processed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # 5. 데이터베이스 저장
                    with self.conn.cursor() as cur:
                        try:
                            cur.execute("""
                                INSERT INTO documents (
                                    id, collection_id, content, metadata, embedding, search_vector
                                ) VALUES (
                                    uuid_generate_v4(), 
                                    %s, 
                                    %s, 
                                    %s, 
                                    %s::vector, 
                                    to_tsvector('simple', %s)
                                )
                            """, (
                                collection_id,
                                content,
                                Json(metadata),
                                embedding,
                                content
                            ))
                            stored_count += 1
                        except psycopg2.Error as db_err:
                            logger.error(f"Database insertion error for chunk {idx}: {db_err}")
                            logger.error(f"Problematic data - Content: {content[:200]}, Metadata: {metadata}")
                            failed_count += 1
                            self.conn.rollback()
                            continue
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to process chunk {idx}: {str(e)}")
                    continue
            
            # 부분 성공/실패 로깅
            logger.info(f"Document storage completed. Stored: {stored_count}, Failed: {failed_count}")
            
            # 커밋은 모든 청크 처리 후에
            self.conn.commit()
            
            return stored_count
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Critical error in store_documents: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        

    def close(self):
        """연결 종료"""
        if self.conn:
            self.conn.close()

class PostgresDbManager:
    def __init__(self):
        try:
            project_root = Path(__file__).parent
            env_path = project_root / '.env'
            load_dotenv(dotenv_path=env_path)
            
            self.db_settings = {
                'host': os.getenv('POSTGRES_HOST'),
                'port': int(os.getenv('POSTGRES_PORT')),
                'database': os.getenv('POSTGRES_DB'),
                'user': os.getenv('POSTGRES_USER'),
                'password': os.getenv('POSTGRES_PASSWORD')
            }
            
            if not all(self.db_settings.values()):
                missing_keys = [k for k, v in self.db_settings.items() if not v]
                raise ValueError(f"Missing required PostgreSQL settings: {', '.join(missing_keys)}")
            
            self.embeddings = CSTFM()
            self.extractor = ExtractTextFromFile()
            self.docnum = int(os.getenv("DOC_NUM", "3"))
            self.chunk_size = int(os.getenv("CHUNK_SIZE", "2048"))
            self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
            
            self.conn = self._create_connection()
            self._initialize_database()
            
            logger.info("PostgreSQL vector manager successfully initialized")
            
        except Exception as e:
            logger.error(f"PostgresVectorManager initialization error: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _create_connection(self):
        """PostgreSQL 연결 생성"""
        return psycopg2.connect(
            **self.db_settings,
            cursor_factory=DictCursor
        )

    def get_db_connection(self):
        return self.conn
    
    def get_chunksize(self) -> int:
        return self.chunk_size
     
    def _check_connection(self) -> bool:
        """데이터베이스 연결 상태 확인"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
        except Exception:
            return False

    def _reconnect(self):
        """데이터베이스 재연결"""
        try:
            if self.conn:
                self.conn.close()
            self.conn = self._create_connection()
            logger.info("Successfully reconnected to PostgreSQL")
        except Exception as e:
            logger.error(f"Database reconnection error: {str(e)}")
            raise


    def _initialize_database(self):
        """데이터베이스 테이블 및 인덱스 초기화"""
        try:
            with self.conn.cursor() as cur:
                # vector 확장 설치
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            
                # users 테이블 생성
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users(
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    group_id VARCHAR(20),
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN DEFAULT false,
                    CONSTRAINT fk_user_group 
                        FOREIGN KEY (group_id) 
                        REFERENCES groups(id)
                        ON DELETE SET NULL
                    );
                """)
                # groups 테이블 생성
                cur.execute("""
                    CREATE SEQUENCE IF NOT EXISTS group_seq START WITH 1;
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS groups (
                        id VARCHAR(20) DEFAULT 'GRP' || LPAD(NEXTVAL('group_seq')::TEXT, 6, '0'),
                        name VARCHAR(50) UNIQUE NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id)
                        );
                """)
                # 그룹-컬렉션 권한 테이블 생성
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS collection_permissions (
                        id SERIAL PRIMARY KEY,
                        collection_id INTEGER NOT NULL,
                        group_id VARCHAR(20) NOT NULL,
                        can_read BOOLEAN DEFAULT false,
                        can_write BOOLEAN DEFAULT false,
                        can_delete BOOLEAN DEFAULT false,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                        UNIQUE(collection_id, group_id)
                    );
                """)
                
                # 사용자-그룹 매핑 테이블 생성
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_groups (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        group_id CHARACTER VARYING(20) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT unique_user_group UNIQUE (user_id, group_id),
                        CONSTRAINT fk_user_groups_user_id FOREIGN KEY (user_id) 
                            REFERENCES users(id),
                        CONSTRAINT fk_user_groups_group_id FOREIGN KEY (group_id) 
                            REFERENCES groups(id)
                    );
                 """)
                # 권한 확인을 위한 뷰 생성
                cur.execute("""
                    CREATE VIEW user_collection_permissions AS
                    WITH RECURSIVE all_permissions AS (
                        -- 직접적인 그룹 권한
                        SELECT 
                            ug.user_id,
                            cp.collection_id,
                            cp.can_read,
                            cp.can_write,
                            cp.can_delete
                        FROM user_groups ug
                        JOIN collection_permissions cp ON ug.group_id = cp.group_id

                        UNION ALL

                        -- Creator는 자동으로 모든 권한 가짐
                        SELECT 
                            c.creator as user_id,
                            c.id as collection_id,
                            true as can_read,
                            true as can_write,
                            true as can_delete
                        FROM collections c
                    )
                    SELECT 
                        user_id,
                        collection_id,
                        bool_or(can_read) as can_read,
                        bool_or(can_write) as can_write,
                        bool_or(can_delete) as can_delete
                    FROM all_permissions
                    GROUP BY user_id, collection_id;
                 """)                
                
                # password_reset_tokens 테이블 생성
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        token VARCHAR(100) UNIQUE NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        used BOOLEAN DEFAULT false,
                        CONSTRAINT fk_user
                            FOREIGN KEY (user_id)
                            REFERENCES users(id)
                            ON DELETE CASCADE
                    );
                """)
                
                # sessions 테이블
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        session_id VARCHAR(100) UNIQUE NOT NULL,
                        token TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        is_active BOOLEAN DEFAULT true,
                        CONSTRAINT fk_user
                            FOREIGN KEY (user_id)
                            REFERENCES users(id)
                            ON DELETE CASCADE,
                        CONSTRAINT valid_session 
                            CHECK (expires_at > created_at)
                    );
                """)
                
                # collections 테이블 생성
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS collections (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        creator INTEGER NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # documents 테이블 생성
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id UUID PRIMARY KEY,
                        collection_id INTEGER REFERENCES collections(id),                        
                        content TEXT,
                        metadata JSONB,
                        search_vector tsvector,
                        embedding vector(768),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_collection 
                            FOREIGN KEY (collection_id) 
                            REFERENCES collections(id) 
                            ON DELETE CASCADE
                    );
                """)
                
                # 인덱스 존재 여부 확인 후 생성
                # 사용자 관련 인덱스
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE indexname = 'idx_users_username'
                    );
                """)
                if not cur.fetchone()[0]:
                    cur.execute("CREATE INDEX idx_users_username ON users(username);")
                    logger.info("Created index idx_users_username")
                    
                # sessiom 관련 인덱스                    
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE indexname = 'idx_sessions_session_id'
                    );
                """)
                if not cur.fetchone()[0]:
                    cur.execute("CREATE INDEX idx_sessions_session_id ON sessions(session_id);")
                    logger.info("Created index idx_sessions_session_id")
                
                # collection 관련 인덱스
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE indexname = 'idx_collection_name'
                    );
                """)
                if not cur.fetchone()[0]:
                    cur.execute("CREATE INDEX idx_collection_name ON collections(name);")
                    logger.info("Created index idx_collection_name")
                
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE indexname = 'idx_documents_collection_id'
                    );
                """)
                if not cur.fetchone()[0]:
                    cur.execute("CREATE INDEX idx_documents_collection_id ON documents(collection_id);")
                    logger.info("Created index idx_documents_collection_id")
                
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE indexname = 'idx_reset_tokens_token'
                    );
                """)
                if not cur.fetchone()[0]:
                    cur.execute("CREATE INDEX idx_reset_tokens_token ON password_reset_tokens(token);")
                    logger.info("Created index idx_reset_tokens_token")
                
                # vector extension을 위한 인덱스 생성
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE indexname = 'documents_embedding_idx'
                    );
                """)
                if not cur.fetchone()[0]:
                    cur.execute("""
                        CREATE INDEX documents_embedding_idx ON documents 
                        USING ivfflat (embedding vector_l2_ops)
                        WITH (lists = 100);
                    """)
                    logger.info("Created vector similarity search index")
                
                self.conn.commit()
                logger.info("Database tables and indexes initialized successfully")
                
                # vector extension을 위한 인덱스 생성
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE indexname = 'documents_search_idx'
                    );
                """)
                if not cur.fetchone()[0]:
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS documents_search_idx ON documents USING gin(search_vector);
                    """)
                    logger.info("Created vector similarity search index")
                
                self.conn.commit()
                logger.info("Database tables and indexes initialized successfully")
                
        except psycopg2.errors.DuplicateTable:
            self.conn.rollback()
            logger.warning("Some tables or indexes already exist, continuing...")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Database initialization error: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """사용자명으로 사용자 검색"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        u.id, 
                        u.username, 
                        u.password_hash,
                        COALESCE(g.name = 'admin', FALSE) AS is_admin
                    FROM users u
                    LEFT JOIN groups g ON u.group_id = g.id
                    WHERE u.username = %s
                """, (username,))
                
                user = cur.fetchone()
                if user:
                    # 데이터베이스에서 받은 결과를 딕셔너리로 변환
                    user_dict = dict(user)
                    
                    # is_admin을 boolean으로 명시적 변환
                    user_dict['is_admin'] = bool(user_dict.get('is_admin', False))
                    
                    logger.info(f"User found: {username}, is_admin: {user_dict['is_admin']}")
                    return user_dict
                
                logger.info(f"User not found: {username}")
                return None
        
        except Exception as e:
            logger.error(f"Error in get_user_by_username: {str(e)}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """이메일로 사용자 검색"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, email 
                    FROM users 
                    WHERE email = %s
                """, (email,))
                user = cur.fetchone()
                if user:
                    return dict(user)
                logger.info(f"User not found for email: {email}")
                return None
        except Exception as e:
            logger.error(f"Error in get_user_by_email: {str(e)}")
            return None

    def create_user(self, username: str, email: str, password_hash: str) -> Optional[int]:
        """
        새 사용자 생성
        - username과 password는 9자 이상이어야 함
        - username과 email은 중복될 수 없음
        
        Args:
            username: 사용자명 (9자 이상)
            email: 이메일 주소
            password_hash: 해시된 비밀번호 (9자 이상)
            
        Returns:
            Optional[int]: 생성된 사용자의 ID 또는 None (생성 실패시)
        """
        try:
            # 길이 검증
            if len(username) < 9:
                logger.warning(f"Username too short: {len(username)} characters")
                raise ValueError("Username must be at least 9 characters long")
                
            if len(password_hash) < 9:
                logger.warning("Password too short")
                raise ValueError("Password must be at least 9 characters long")
                
            with self.conn.cursor() as cur:
                # 중복 검사
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM users 
                        WHERE username = %s OR email = %s
                    )
                """, (username, email))
                
                exists = cur.fetchone()[0]
                if exists:
                    logger.warning(f"User already exists with username: {username} or email: {email}")
                    raise ValueError("Username or email already exists")
                
                # 새 사용자 생성
                cur.execute("""
                    INSERT INTO users (username, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (username, email, password_hash))
                
                result = cur.fetchone()
                self.conn.commit()
                
                if result:
                    user_id = result[0]
                    logger.info(f"Created new user with ID: {user_id}")
                    return user_id
                    
                return None
                
        except ValueError as ve:
            self.conn.rollback()
            logger.error(f"Validation error in create_user: {str(ve)}")
            raise
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in create_user: {str(e)}")
            return None

    def update_last_login(self, user_id: int) -> bool:
        """사용자의 마지막 로그인 시간 업데이트"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET last_login = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (user_id,))
                self.conn.commit()
                logger.info(f"Updated last login for user ID: {user_id}")
                return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in update_last_login: {str(e)}")
            return False
    

    def create_collection(self, collection_name: str) -> bool:
        """컬렉션 생성"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO collections (name) VALUES (%s) RETURNING id",
                    (collection_name,)
                )
                collection_id = cur.fetchone()[0]
                self.conn.commit()
                logger.info(f"Created collection: {collection_name} (ID: {collection_id})")
                return True
                
        except psycopg2.errors.UniqueViolation:
            self.conn.rollback()
            logger.warning(f"Collection already exists: {collection_name}")
            return False
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"컬렉션 생성 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def add_permission(self, collection_id: int, group_id: int, 
                      can_read: bool = False, can_write: bool = False, 
                      can_delete: bool = False) -> bool:
        """
        컬렉션에 대한 그룹 권한 추가
        
        Args:
            collection_id: 컬렉션 ID
            group_id: 그룹 ID
            can_read: 읽기 권한
            can_write: 쓰기 권한
            can_delete: 삭제 권한
        
        Returns:
            bool: 성공 여부
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO collection_permissions 
                        (collection_id, group_id, can_read, can_write, can_delete)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (collection_id, group_id) 
                    DO UPDATE SET 
                        can_read = EXCLUDED.can_read,
                        can_write = EXCLUDED.can_write,
                        can_delete = EXCLUDED.can_delete,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (collection_id, group_id, can_read, can_write, can_delete))
                self.conn.commit()
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Error adding permission: {str(e)}")
            self.conn.rollback()
            return False

    def update_permission(self, collection_id: int, group_id: int,
                         can_read: Optional[bool] = None,
                         can_write: Optional[bool] = None,
                         can_delete: Optional[bool] = None) -> bool:
        """
        컬렉션에 대한 그룹 권한 수정
        
        Args:
            collection_id: 컬렉션 ID
            group_id: 그룹 ID
            can_read: 읽기 권한 (None인 경우 기존 값 유지)
            can_write: 쓰기 권한 (None인 경우 기존 값 유지)
            can_delete: 삭제 권한 (None인 경우 기존 값 유지)
        
        Returns:
            bool: 성공 여부
        """
        try:
            update_fields = []
            params = []
            
            if can_read is not None:
                update_fields.append("can_read = %s")
                params.append(can_read)
            if can_write is not None:
                update_fields.append("can_write = %s")
                params.append(can_write)
            if can_delete is not None:
                update_fields.append("can_delete = %s")
                params.append(can_delete)
                
            if not update_fields:
                return False
                
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([collection_id, group_id])
            
            with self.conn.cursor() as cur:
                cur.execute(f"""
                    UPDATE collection_permissions
                    SET {", ".join(update_fields)}
                    WHERE collection_id = %s AND group_id = %s
                    RETURNING id
                """, params)
                self.conn.commit()
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Error updating permission: {str(e)}")
            self.conn.rollback()
            return False

    def delete_permission(self, collection_id: int, group_id: str) -> bool:
        """
        컬렉션에 대한 그룹 권한 삭제
        
        Args:
            collection_id: 컬렉션 ID
            group_id: 그룹 ID
        
        Returns:
            bool: 성공 여부
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM collection_permissions
                    WHERE collection_id = %s AND group_id = %s
                    RETURNING id
                """, (collection_id, group_id))
                self.conn.commit()
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Error deleting permission: {str(e)}")
            self.conn.rollback()
            return False

    def get_collection_permissions(self, collection_id: int) -> List[Dict]:
        """
        특정 컬렉션의 모든 그룹 권한 조회
        
        Args:
            collection_id: 컬렉션 ID
        
        Returns:
            List[Dict]: 권한 정보 리스트
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        cp.*,
                        g.name as group_name,
                        g.description as group_description
                    FROM collection_permissions cp
                    JOIN groups g ON cp.group_id = g.id
                    WHERE cp.collection_id = %s
                    ORDER BY g.name
                """, (collection_id,))
                
                return [
                    {
                        'collection_id': row[1],
                        'group_id': row[2],
                        'group_name': row[6],
                        'group_description': row[7],
                        'permissions': {
                            'can_read': row[3],
                            'can_write': row[4],
                            'can_delete': row[5]
                        },
                        'created_at': row[6],
                        'updated_at': row[7]
                    }
                    for row in cur.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error getting collection permissions: {str(e)}")
            return []

    def get_group_permissions(self, group_id: str) -> List[Dict]:
        """
        특정 그룹의 모든 컬렉션 권한 조회
        
        Args:
            group_id: 그룹 ID
        
        Returns:
            List[Dict]: 권한 정보 리스트
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        cp.*,
                        c.name as collection_name
                    FROM collection_permissions cp
                    JOIN collections c ON cp.collection_id = c.id
                    WHERE cp.group_id = %s
                    ORDER BY c.name
                """, (group_id,))
                
                return [
                    {
                        'collection_id': row[1],
                        'collection_name': row[6],
                        'permissions': {
                            'can_read': row[3],
                            'can_write': row[4],
                            'can_delete': row[5]
                        },
                        'created_at': row[6],
                        'updated_at': row[7]
                    }
                    for row in cur.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error getting group permissions: {str(e)}")
            return []

    def check_permission(self, collection_id: int, group_id: str) -> Dict:
        """
        특정 컬렉션에 대한 특정 그룹의 권한 확인
        
        Args:
            collection_id: 컬렉션 ID
            group_id: 그룹 ID
        
        Returns:
            Dict: 권한 정보
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT can_read, can_write, can_delete
                    FROM collection_permissions
                    WHERE collection_id = %s AND group_id = %s
                """, (collection_id, group_id))
                
                row = cur.fetchone()
                if row:
                    return {
                        'can_read': row[0],
                        'can_write': row[1],
                        'can_delete': row[2]
                    }
                return {
                    'can_read': False,
                    'can_write': False,
                    'can_delete': False
                }
        except Exception as e:
            logger.error(f"Error checking permission: {str(e)}")
            return {
                'can_read': False,
                'can_write': False,
                'can_delete': False
            }
            
    def get_accessible_collections(self, user_id: int) -> List[Dict]:
        """
        사용자가 접근 가능한 모든 컬렉션 조회
        
        Args:
            user_id (int): 사용자 ID

        Returns:
            List[Dict]: 접근 가능한 컬렉션 목록과 각각의 권한 정보
            [
                {
                    'collection_id': int,
                    'collection_name': str,
                    'created_at': datetime,
                    'permissions': {
                        'can_read': bool,
                        'can_write': bool,
                        'can_delete': bool
                    },
                    'groups': [
                        {
                            'group_id': str,
                            'group_name': str,
                            'permissions': {
                                'can_read': bool,
                                'can_write': bool,
                                'can_delete': bool
                            }
                        }
                    ]
                }
            ]
        """
        try:
            with self.conn.cursor() as cur:
                # 사용자의 그룹을 통해 접근 가능한 모든 컬렉션 조회
                cur.execute("""
                    WITH user_permissions AS (
                        SELECT DISTINCT
                            c.id as collection_id,
                            c.name as collection_name,
                            c.created_at,
                            g.id as group_id,
                            g.name as group_name,
                            cp.can_read,
                            cp.can_write,
                            cp.can_delete
                        FROM collections c
                        JOIN collection_permissions cp ON c.id = cp.collection_id
                        JOIN groups g ON cp.group_id = g.id
                        JOIN user_groups ug ON g.id = ug.group_id
                        WHERE ug.user_id = %s
                    )
                    SELECT 
                        collection_id,
                        collection_name,
                        created_at,
                        BOOL_OR(can_read) as can_read,
                        BOOL_OR(can_write) as can_write,
                        BOOL_OR(can_delete) as can_delete,
                        ARRAY_AGG(
                            jsonb_build_object(
                                'group_id', group_id,
                                'group_name', group_name,
                                'permissions', jsonb_build_object(
                                    'can_read', can_read,
                                    'can_write', can_write,
                                    'can_delete', can_delete
                                )
                            )
                        ) as groups
                    FROM user_permissions
                    GROUP BY collection_id, collection_name, created_at
                    ORDER BY collection_name
                """, (user_id,))
                
                results = []
                for row in cur.fetchall():
                    collection = {
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'created_at': row[2],
                        'permissions': {
                            'can_read': row[3],
                            'can_write': row[4],
                            'can_delete': row[5]
                        },
                        'groups': row[6]  # ARRAY_AGG로 생성된 그룹 정보
                    }
                    results.append(collection)
                
                logger.debug(f"Found {len(results)} accessible collections for user {user_id}")
                return results
                
        except Exception as e:
            logger.error(f"Error getting accessible collections for user {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def get_accessible_collections_by_permission(self, user_id: int, 
                                               require_read: bool = True,
                                               require_write: bool = False,
                                               require_delete: bool = False) -> List[Dict]:
        """
        특정 권한 조건에 맞는 접근 가능한 컬렉션 조회
        
        Args:
            user_id (int): 사용자 ID
            require_read (bool): 읽기 권한 필요 여부
            require_write (bool): 쓰기 권한 필요 여부
            require_delete (bool): 삭제 권한 필요 여부

        Returns:
            List[Dict]: 접근 가능한 컬렉션 목록
        """
        try:
            with self.conn.cursor() as cur:
                conditions = []
                if require_read:
                    conditions.append("BOOL_OR(cp.can_read) = true")
                if require_write:
                    conditions.append("BOOL_OR(cp.can_write) = true")
                if require_delete:
                    conditions.append("BOOL_OR(cp.can_delete) = true")
                
                where_clause = " AND ".join(conditions)
                if where_clause:
                    where_clause = f"HAVING {where_clause}"
                
                cur.execute(f"""
                    SELECT 
                        c.id,
                        c.name,
                        c.created_at,
                        BOOL_OR(cp.can_read) as can_read,
                        BOOL_OR(cp.can_write) as can_write,
                        BOOL_OR(cp.can_delete) as can_delete
                    FROM collections c
                    JOIN collection_permissions cp ON c.id = cp.collection_id
                    JOIN user_groups ug ON cp.group_id = ug.group_id
                    WHERE ug.user_id = %s
                    GROUP BY c.id, c.name, c.created_at
                    {where_clause}
                    ORDER BY c.name
                """, (user_id,))
                
                results = []
                for row in cur.fetchall():
                    collection = {
                        'collection_id': row[0],
                        'collection_name': row[1],
                        'created_at': row[2],
                        'permissions': {
                            'can_read': row[3],
                            'can_write': row[4],
                            'can_delete': row[5]
                        }
                    }
                    results.append(collection)
                
                logger.debug(f"Found {len(results)} collections with specified permissions for user {user_id}")
                return results
                
        except Exception as e:
            logger.error(f"Error getting accessible collections by permission for user {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        
    def get_collections_by_creator(self, user_id):
        """특정 creator의 컬렉션 목록 조회. admin 그룹인 경우 모든 컬렉션 반환
        
        Args:
            creator_id (int): 생성자 ID
            
        Returns:
            list: 컬렉션 목록. 에러 발생 시 빈 리스트 반환
            
        Note:
            반환되는 각 컬렉션은 다음 필드를 포함:
            - id: 컬렉션 ID
            - name: 컬렉션 이름
            - created_at: 생성 시간
            - creator_id: 생성자 ID
            - creator_name: 생성자 그룹 이름
        """
        try:            
            with self.conn.cursor() as cur:
                # 먼저 creator의 그룹이 admin인지 확인
                cur.execute("""
                    SELECT id
                    FROM user_groups
                    WHERE user_id = %s AND group_id = 'GRP000001'   
                """, (user_id,))
                group_result = cur.fetchone()
                
                if not group_result:
                    is_admin = False
                else:
                    is_admin = True               
                
                
                # admin인 경우 모든 컬렉션 반환, 아닌 경우 해당 creator의 컬렉션만 반환
                if is_admin:
                    cur.execute("""
                        SELECT DISTINCT ON (c.id)    
                            c.id as collection_id,
                            c.name as collection_name,
                            cp.can_read,
                            cp.can_write,
                            cp.can_delete
                        FROM users u
                        JOIN user_groups ug ON u.id = ug.user_id
                        JOIN collection_permissions cp ON ug.group_id = cp.group_id
                        JOIN collections c ON cp.collection_id = c.id
                        ORDER BY c.id, cp.can_read DESC, cp.can_write DESC, cp.can_delete DESC
                    """)
                else:
                    cur.execute("""
                        SELECT DISTINCT ON (c.id)    
                            c.id as collection_id,
                            c.name as collection_name,
                            cp.can_read,
                            cp.can_write,
                            cp.can_delete
                        FROM users u
                        JOIN user_groups ug ON u.id = ug.user_id
                        JOIN collection_permissions cp ON ug.group_id = cp.group_id
                        JOIN collections c ON cp.collection_id = c.id
                        WHERE u.id = %s
                        ORDER BY c.id, cp.can_read DESC, cp.can_write DESC, cp.can_delete DESC
                    """, (user_id,))
                
                collections = cur.fetchall()
                
                logger.debug(
                    f"Retrieved {len(collections)} collections for creator {user_id} "
                    f"(admin access: {is_admin})"
                )
                
                return collections
                
        except Exception as e:
            logger.error(f"Error getting collections for creator {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def delete_collection(self, collection_name: str) -> str:
        """
        컬렉션과 관련 문서 삭제
        
        Args:
            collection_name (str): 삭제할 컬렉션 이름
            
        Returns:
            str: 삭제 결과 메시지
        """
        try:
            with self.conn.cursor() as cur:
                # 먼저 컬렉션이 존재하는지 확인
                cur.execute(
                    "SELECT id FROM collections WHERE name = %s",
                    (collection_name,)
                )
                result = cur.fetchone()
                
                if not result:
                    return f"Collection '{collection_name}' not found."
                
                collection_id = result[0]
                
                # CASCADE 옵션이 설정되어 있으므로 collections 테이블에서만 삭제하면 됨
                cur.execute(
                    "DELETE FROM collections WHERE id = %s",
                    (collection_id,)
                )
                
                # 트랜잭션 커밋 (self.conn.commit()로 수정)
                self.conn.commit()
                
                logger.info(f"Successfully deleted collection: {collection_name}")
                return f"Collection '{collection_name}' deleted successfully."
                
        except Exception as e:
            self.conn.rollback()
            error_msg = f"Error deleting collection: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return error_msg

    def list_collections(self) -> List[str]:
        """모든 컬렉션 목록 반환"""
        """모든 컬렉션 목록 반환"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT name 
                    FROM collections 
                    ORDER BY created_at DESC
                """)
                collections = [row[0] for row in cur.fetchall()]
                logger.info(f"Found {len(collections)} collections")
                return collections
        except Exception as e:
            logger.error(f"Error in list_collections: {str(e)}")
            return []

    def view_collection_content(self, collection_name: str, docnum=30) -> List[Dict]:
        """
        컬렉션 내용을 조회합니다.
        
        Args:
            collection_name (str): 조회할 컬렉션 이름
            docnum (int, optional): 조회할 문서 수. 기본값 30
            
        Returns:
            List[Dict]: 문서 정보 리스트. 각 문서는 ID, Document, Metadata, Created 포함
        """
        try:
            with self.conn.cursor() as cur:
                # 컬렉션 존재 여부 확인
                cur.execute("""
                    SELECT id 
                    FROM collections 
                    WHERE name = %s
                """, (collection_name,))
                
                collection_result = cur.fetchone()
                if not collection_result:
                    logger.warning(f"Collection '{collection_name}' not found")
                    return []
                    
                collection_id = collection_result[0]
                logger.debug(f"Found collection_id: {collection_id} for '{collection_name}'")
                
                # 문서 조회 쿼리 실행
                cur.execute("""
                    SELECT 
                        d.id,
                        d.content as page_content,
                        d.metadata,
                        d.created_at
                    FROM documents d
                    WHERE d.collection_id = %s
                    ORDER BY d.created_at DESC
                    LIMIT %s
                """, (collection_id, docnum))
                
                content = []
                rows = cur.fetchall()
                
                if not rows:
                    logger.info(f"No documents found in collection '{collection_name}'")
                    return []
                
                for row in rows:
                    # UTF-8 디코딩 처리 추가
                    page_content = (row['page_content'].decode('utf-8') 
                                if isinstance(row['page_content'], bytes) 
                                else str(row['page_content']))
                    
                    item_info = {
                        "ID": row['id'],
                        "Document": page_content,
                        "Metadata": dict(row['metadata']) if row['metadata'] else {},
                        "Created": row['created_at'].isoformat() if row['created_at'] else None
                    }
                    content.append(item_info)
                
                logger.info(f"Retrieved {len(content)} documents from collection '{collection_name}'")
                return content
                
        except psycopg2.Error as e:
            logger.error(f"Database error while viewing collection '{collection_name}': {str(e)}")
            logger.error(traceback.format_exc())
            return []
        except Exception as e:
            logger.error(f"Unexpected error while viewing collection '{collection_name}': {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def split_embed_docs_store(self, text: List[Document], filename: str, collection_name: str) -> int:
        """VectorStore 방식으로 문서 처리"""
        store = None
        try:
            # 입력 데이터 유효성 검사
            if not text:
                logger.warning("No documents provided for processing")
                return 0
                
            logger.info(f"Starting document processing for collection: {collection_name}")
            
            # 입력 문서 기본 정보 로깅
            logger.info(f"Total input documents: {len(text)}")
            logger.debug(f"First document metadata: {text[0].metadata if text else 'N/A'}")
            
            # PostgreSQL 벡터 저장소 초기화
            store = VectorStore(
                host=self.db_settings['host'],
                port=self.db_settings['port'],
                database=self.db_settings['database'],
                user=self.db_settings['user'],
                password=self.db_settings['password']
            )
            
            chunks = text  # 이미 chunk된 데이터이므로 그대로 사용
            
            # 청크 크기 제한 (선택적)
            if len(chunks) > self.chunk_size:
                logger.warning(f"Too many chunks ({len(chunks)}). Limiting to first {self.chunk_size}.")
                chunks = chunks[:self.chunk_size]
            
            # 문서 저장
            try:
                stored_count = store.store_documents(
                    text=chunks,
                    filename=filename,
                    collection_name=collection_name
                )
            except Exception as store_error:
                logger.error(f"Error storing documents: {store_error}")
                logger.error(traceback.format_exc())
                return 0
                
            # 저장 결과 로깅
            logger.info(f"Successfully stored {stored_count} chunks in collection '{collection_name}'")
            
            return stored_count
            
        except Exception as e:
            logger.error(f"Critical error in split_embed_docs_store: {str(e)}")
            logger.error(traceback.format_exc())
            return 0
            
        finally:
            # 항상 리소스 정리
            if store:
                try:
                    store.close()
                except Exception as close_error:
                    logger.error(f"Error closing vector store: {close_error}")
                
    def add_user_to_group(self, user_id: int, group_id: str) -> bool:
        """사용자를 그룹에 추가"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_groups (user_id, group_id)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, group_id) DO NOTHING
                    RETURNING id
                """, (user_id, group_id))
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Error adding user to group: {str(e)}")
            return False

    def set_collection_permissions(self, collection_id: int, group_id: str,
                                 can_read: bool = False, can_write: bool = False,
                                 can_delete: bool = False) -> bool:
        """그룹의 컬렉션 접근 권한 설정"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO collection_permissions 
                    (collection_id, group_id, can_read, can_write, can_delete)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (collection_id, group_id) 
                    DO UPDATE SET 
                        can_read = EXCLUDED.can_read,
                        can_write = EXCLUDED.can_write,
                        can_delete = EXCLUDED.can_delete,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (collection_id, group_id, can_read, can_write, can_delete))
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Error setting collection permissions: {str(e)}")
            return False

    def check_user_permission(self, user_id: int, collection_id: int) -> dict:
        """사용자의 컬렉션 접근 권한 확인"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT can_read, can_write, can_delete
                    FROM user_collection_permissions
                    WHERE user_id = %s AND collection_id = %s
                """, (user_id, collection_id))
                result = cur.fetchone()
                if result:
                    return {
                        'can_read': result[0],
                        'can_write': result[1],
                        'can_delete': result[2]
                    }
                return {
                    'can_read': False,
                    'can_write': False,
                    'can_delete': False
                }
        except Exception as e:
            logger.error(f"Error checking user permissions: {str(e)}")
            return {
                'can_read': False,
                'can_write': False,
                'can_delete': False
            }

    def get_user_collections(self, user_id: int) -> List[Dict]:
        """사용자가 접근 가능한 컬렉션 목록 조회"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        c.id,
                        c.name,
                        c.created_at,
                        ucp.can_read,
                        ucp.can_write,
                        ucp.can_delete
                    FROM collections c
                    JOIN user_collection_permissions ucp 
                        ON c.id = ucp.collection_id
                    WHERE ucp.user_id = %s
                    ORDER BY c.created_at DESC
                """, (user_id,))
                results = cur.fetchall()
                return [
                    {
                        'id': row[0],
                        'name': row[1],
                        'created_at': row[2],
                        'permissions': {
                            'can_read': row[3],
                            'can_write': row[4],
                            'can_delete': row[5]
                        }
                    }
                    for row in results
                ]
        except Exception as e:
            logger.error(f"Error getting user collections: {str(e)}")
            return []
    
    def get_list_collections(self) -> list:
        """컬렉션 목록 조회"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT name 
                    FROM collections 
                    ORDER BY created_at DESC
                """)
                collections = [row[0] for row in cur.fetchall()]
                return collections
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"컬렉션 목록 조회 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        
    def get_collection_id(self, collection_name: str) -> Optional[int]:
        """컬렉션 ID 조회"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM collections WHERE name = %s",
                    (collection_name,)
                )
                result = cur.fetchone()
                return result[0] if result else None
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"컬렉션 ID 조회 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return None
        
    def get_persist_directory(self) -> None:
        """PostgreSQL은 persist_directory가 필요하지 않음"""
        return None
    
    def split_keywords(self, text):
        okt = Okt()
        morphs = okt.pos(text)
        
        # 형태소 분석
        keywords = [word for word, pos in morphs if pos.startswith('Noun') and len(word) > 1]
        if text not in keywords:
            keywords.append(text)
        for word in text.split():
            if word not in keywords:
                keywords.append(word)
        
        # 디버깅을 위한 로깅
        logger.debug(f"Original text: {text}")
        logger.debug(f"Extracted keywords: {keywords}")
        
        return keywords    
    
    
    def search_collection(self, collection_names: Union[str, List[str]], query: str, n_results: int = 5, 
                     source_name: str = None, score_threshold: float = 0.5) -> List[Dict]:
        try:
           
            # collection_names를 항상 리스트로 처리
            if isinstance(collection_names, str):
                collection_names = [collection_names]
                
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=100,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            
            # 쿼리 전처리 및 토큰화
            querytmp = QuoExt.extract_and_join(query)
            keywords = self.split_keywords(querytmp)            

            logger.debug(f"Keywords: {[k.encode('utf-8') for k in keywords]}")
            
            # ILIKE 조건 생성
            """like_conditions = " OR ".join([f"d.content ILIKE ANY(ARRAY[{', '.join(['%s'] * len(keywords))}])"])
            like_params = [f"{keyword}%" for keyword in keywords]"""
            
            tsquery_parts = []
            for keyword in keywords:
                if keyword:  # 빈 문자열이 아닌 경우만 처리
                    if ' ' in keyword:
                        # 공백이 포함된 키워드는 & 연산자로 결합
                        words = keyword.split()
                        phrase_condition = '&'.join(f"{word}:*" for word in words)
                        tsquery_parts.append(f"({phrase_condition})")
                else:
                    # 단일 키워드는 그대로 처리
                    tsquery_parts.append(f"{keyword}:*")

            # OR 연산자로 모든 조건 결합
            if tsquery_parts:
                tsquery_conditions = ' | '.join(tsquery_parts)
                like_conditions = f"d.search_vector @@ to_tsquery('simple', %s)"
                like_params = [tsquery_conditions]
            else:
                # 유효한 키워드가 없는 경우의 처리
                like_conditions = "TRUE"  # 또는 적절한 기본 조건
                like_params = []
            
            processed_query = ' '.join(keywords)           
            query_embedding = self.embeddings.embed_query(processed_query)
            
            if isinstance(query_embedding, np.ndarray):
                query_embedding = query_embedding.tolist()

            with self.conn.cursor() as cur:
                # 여러 collection의 ID들과 이름을 가져옴
                placeholders = ','.join(['%s'] * len(collection_names))
                cur.execute(f"""
                    SELECT id, name 
                    FROM collections 
                    WHERE name = ANY(ARRAY[{placeholders}])
                """, collection_names)
                collection_data = {row[0]: row[1] for row in cur.fetchall()}
                collection_ids = list(collection_data.keys())
                
                if not collection_ids:
                    logger.error("No valid collection IDs found")
                    return []

                # collection_id_condition 정의
                collection_id_condition = f"d.collection_id = ANY(ARRAY[{', '.join(map(str, collection_ids))}])"

                if source_name:
                    query_sql = f"""
                        WITH keyword_matches AS (
                            SELECT 
                                d.content as page_content,
                                d.metadata,
                                d.collection_id,
                                1.0 as keyword_score
                            FROM documents d
                            WHERE {collection_id_condition}
                            AND {like_conditions}
                        ),
                        vector_matches AS (
                            SELECT 
                                d.content as page_content,
                                d.metadata,
                                d.collection_id,
                                1 - (d.embedding <=> %s::vector) as vector_score
                            FROM documents d
                            WHERE {collection_id_condition}
                        ),
                        scored_results AS (
                            SELECT 
                                COALESCE(k.page_content, v.page_content) as page_content,
                                COALESCE(k.metadata, v.metadata) as metadata,
                                COALESCE(k.collection_id, v.collection_id) as collection_id,
                                CASE 
                                    WHEN k.page_content IS NOT NULL AND v.page_content IS NOT NULL THEN
                                        LEAST(1.0, 
                                            GREATEST(0.0, 
                                                (k.keyword_score * 0.4 + v.vector_score * 0.6)
                                            )
                                        )
                                    WHEN k.page_content IS NOT NULL THEN
                                        LEAST(1.0, 
                                            GREATEST(0.0, k.keyword_score)
                                        )
                                    ELSE
                                        LEAST(1.0, 
                                            GREATEST(0.0, v.vector_score)
                                        )
                                END as combined_score
                            FROM keyword_matches k
                            FULL OUTER JOIN vector_matches v ON k.page_content = v.page_content
                            WHERE (k.page_content IS NOT NULL OR v.vector_score >= %s)
                        )
                        SELECT *
                        FROM scored_results
                        WHERE combined_score >= %s
                        ORDER BY combined_score DESC
                        LIMIT %s
                    """
                    query_params = like_params + [query_embedding, score_threshold, score_threshold, n_results]
                else:
                    query_sql = f"""
                        WITH keyword_matches AS (
                            SELECT 
                                d.content as page_content,
                                d.metadata,
                                d.collection_id,
                                1.0 as keyword_score,
                                ROW_NUMBER() OVER (ORDER BY d.content) as rank
                            FROM documents d
                            WHERE {collection_id_condition}
                            AND {like_conditions}
                        ),
                        vector_matches AS (
                            SELECT 
                                d.content as page_content,
                                d.metadata,
                                d.collection_id,
                                1 - (d.embedding <=> %s::vector) as vector_score,
                                ROW_NUMBER() OVER (ORDER BY 1 - (d.embedding <=> %s::vector) DESC) as rank
                            FROM documents d
                            WHERE {collection_id_condition}
                        ),
                        scored_results AS (
                            SELECT 
                                COALESCE(k.page_content, v.page_content) as page_content,
                                COALESCE(k.metadata, v.metadata) as metadata,
                                COALESCE(k.collection_id, v.collection_id) as collection_id,
                                CASE 
                                    WHEN k.page_content IS NOT NULL AND v.page_content IS NOT NULL THEN
                                        LEAST(1.0, 
                                            GREATEST(0.0, 
                                                (k.keyword_score * 0.3 + v.vector_score * 0.7)
                                            )
                                        )
                                    WHEN k.page_content IS NOT NULL THEN
                                        LEAST(1.0, 
                                            GREATEST(0.0, k.keyword_score)
                                        )
                                    ELSE
                                        LEAST(1.0, 
                                            GREATEST(0.0, v.vector_score)
                                        )
                                END as combined_score
                            FROM vector_matches v
                            LEFT JOIN keyword_matches k ON v.page_content = k.page_content
                        )
                        SELECT *
                        FROM scored_results
                        WHERE combined_score >= %s
                        ORDER BY combined_score DESC
                        LIMIT %s
                    """
                    query_params = like_params + [query_embedding, query_embedding, score_threshold, n_results]

                logger.debug(f"Query params: {len(query_params)}")
                logger.debug(f"Keywords: {keywords}")
                cur.execute(query_sql, query_params)
                results = cur.fetchall()

                filtered_results = []
                for row in results:
                    try:
                        # 메타데이터에 collection 정보 추가
                        metadata = dict(row['metadata']) if row['metadata'] else {}
                        collection_id = row['collection_id']
                        metadata['collection'] = collection_data.get(collection_id, 'Unknown')
                        
                        result_dict = {
                            'page_content': row['page_content'].decode('utf-8') if isinstance(row['page_content'], bytes) else str(row['page_content']),
                            'metadata': metadata,
                            'score': float(row['combined_score'])
                        }
                        filtered_results.append(result_dict)
                    except Exception as e:
                        logger.error(f"Error processing row: {str(e)}")
                        continue

                logger.debug(f"Raw query results count: {len(results)}")
                logger.debug(f"Filtered results count: {len(filtered_results)}")
                return filtered_results

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        
    def search_keyword_collection(self, collection_names: Union[str, List[str]], query: str, n_results: int = 5, 
                    source_name: str = None, score_threshold: float = 0.5) -> List[Dict]:
       try:           
           if isinstance(collection_names, str):
               collection_names = [collection_names]
               
           # 벡터 임베딩 생성
           vector_embedding = self.embeddings.embed_query(query)
           if isinstance(vector_embedding, np.ndarray):
               vector_embedding = vector_embedding.tolist()

           # Full Text Search를 위한 쿼리 처리
           processed_query = self.preprocess_fts_query(query)
           
   
           with self.conn.cursor() as cur:
               placeholders = ','.join(['%s'] * len(collection_names))
               collection_query = f"""
                   SELECT id, name 
                   FROM collections 
                   WHERE name = ANY(ARRAY[{placeholders}])
               """
               cur.execute(collection_query, collection_names)
               collection_data = {row[0]: row[1] for row in cur.fetchall()}
               collection_ids = list(collection_data.keys())
               logger.debug(f"collection_id : {collection_ids}")
               if not collection_ids:
                   logger.error("No valid collection IDs found")
                   return []

               collection_id_condition = f"d.collection_id = ANY(ARRAY[{', '.join(map(str, collection_ids))}])"

               query_sql = f"""
                   WITH fts_matches AS (
                       SELECT 
                           d.content as page_content,
                           d.metadata,
                           d.collection_id,
                           GREATEST(0.0, LEAST(1.0, ts_rank_cd(d.search_vector, 
                               plainto_tsquery('simple', %s)) / 2.0)) as fts_score,
                           ts_headline('simple', d.content, 
                               plainto_tsquery('simple', %s),
                               'StartSel = <mark>, StopSel = </mark>, MaxWords=75, MinWords=25'
                           ) as headline
                       FROM documents d
                       WHERE {collection_id_condition}
                       AND d.search_vector @@ plainto_tsquery('simple', %s)
                   ),
                   vector_matches AS (
                       SELECT 
                           d.content as page_content,
                           d.metadata,
                           d.collection_id,
                           1 - (d.embedding <=> %s::vector) as vector_score
                       FROM documents d
                       WHERE {collection_id_condition}
                   ),
                   combined_scores AS (
                       SELECT 
                           COALESCE(f.page_content, v.page_content) as page_content,
                           COALESCE(f.metadata, v.metadata) as metadata,
                           COALESCE(f.collection_id, v.collection_id) as collection_id,
                           f.headline,
                           COALESCE(f.fts_score, 0.0) as fts_score,
                           COALESCE(v.vector_score, 0.0) as vector_score,
                           CASE 
                               WHEN f.page_content IS NOT NULL AND v.page_content IS NOT NULL THEN
                                   GREATEST(0.0, LEAST(1.0, COALESCE(f.fts_score * 0.3, 0) + COALESCE(v.vector_score * 0.7, 0)))
                               WHEN f.page_content IS NOT NULL THEN
                                   COALESCE(f.fts_score, 0.0)
                               ELSE
                                   COALESCE(v.vector_score, 0.0)
                           END as combined_score
                       FROM fts_matches f
                       FULL OUTER JOIN vector_matches v ON f.page_content = v.page_content
                       WHERE COALESCE(f.fts_score, 0) > 0.1 OR COALESCE(v.vector_score, 0) > %s
                   )
                   SELECT 
                       page_content,
                       metadata,
                       collection_id,
                       headline,
                       combined_score,
                       fts_score,
                       vector_score
                   FROM combined_scores
                   WHERE combined_score >= %s
                   ORDER BY combined_score DESC
                   LIMIT %s
               """
               
               # processed_query가 문자열이 맞는지 확인
               if isinstance(processed_query, list):
                   processed_query = ' '.join(processed_query)
               
               query_params = [
                   processed_query,  # for ts_rank_cd
                   processed_query,  # for ts_headline
                   processed_query,  # for plainto_tsquery
                   vector_embedding,
                   score_threshold,
                   score_threshold,
                   n_results
               ]

               cur.execute(query_sql, query_params)
               results = cur.fetchall()

               filtered_results = []
               for row in results:
                   try:
                       metadata = dict(row['metadata']) if row['metadata'] else {}
                       collection_id = row['collection_id']
                       metadata['collection'] = collection_data.get(collection_id, 'Unknown')
                       metadata['headline'] = row['headline'] if 'headline' in row else None
                       
                       result_dict = {
                           'page_content': row['page_content'].decode('utf-8') if isinstance(row['page_content'], bytes) else str(row['page_content']),
                           'metadata': metadata,
                           'score': float(row['combined_score'])
                       }
                       filtered_results.append(result_dict)
                   except Exception as e:
                       logger.error(f"Error processing row: {str(e)}")
                       continue

               logger.debug(f"Raw query results count: {len(results)}")
               logger.debug(f"Filtered results count: {len(filtered_results)}")
               return filtered_results

       except Exception as e:
           logger.error(f"Search error: {str(e)}")
           logger.error(traceback.format_exc())
           return []

    def preprocess_fts_query(self, query: str) -> List[str]:
        """Full Text Search 쿼리 전처리"""
        # 불용어 제거, 형태소 분석 등 추가 가능
        keywords = self.split_keywords(query)
        
        return keywords
        
    def get_document_pages(self, collection_id: int, source: str) -> int:
        """
        문서의 총 페이지 수를 반환하는 함수
        
        Args:
            collection_id (int): 컬렉션 ID
            source (str): 문서 소스명
            
        Returns:
            int: 총 페이지 수
            
        Raises:
            Exception: DB 조회 중 오류 발생 시
        """
        try:
            with self.conn.cursor() as cur:           
                # 쿼리 실행
                query = """
                    SELECT COUNT(DISTINCT d.metadata->>'page') as total_pages
                    FROM documents d
                    WHERE d.collection_id = %s 
                    AND d.metadata->>'source' = %s
                """
                
                cur.execute(query, (collection_id, source))
                result = cur.fetchone()
                logger.debug(f"get_document_pages------------: {result}")
                
                # 결과가 없는 경우 0 반환
                if not result:
                    return 0                    
                return result[0]  # 첫 번째 컬럼(total_pages) 값만 반환
        except Exception as e:
            logger.error(f"Error getting document pages: {str(e)}")
            raise
        
    def get_document_page_content(self, collection: int, source: str, page_num: str) -> str:
        """
        특정 문서의 특정 페이지 내용을 반환하는 함수
        
        Args:
            collection (int): 컬렉션 ID
            source (str): 문서 소스명
            page_num (str): 페이지 번호
            
        Returns:
            str: 페이지 내용
            
        Raises:
            Exception: DB 조회 중 오류 발생 시
        """
        try:            
            with self.conn.cursor() as cur:
                query = """
                    SELECT 
                        string_agg(d.content, E'\n' ORDER BY (d.metadata->>'page')::integer) as content
                    FROM documents d
                    WHERE 
                        d.collection_id = %s 
                        AND d.metadata->>'source' = %s
                        AND d.metadata->>'page' = %s
                    GROUP BY 
                        d.collection_id, 
                        d.metadata->>'page',
                        d.metadata->>'source'
                """
                
                cur.execute(query, (collection, source, page_num))
                result = cur.fetchone()
                
                # 결과가 없는 경우 None 반환
                if not result:
                    return None
                    
                return result[0]  # content 값 반환

        except Exception as e:
            logger.error(f"Error getting document page content: {str(e)}")
            raise
        
    
    def get_document_content(self, collection: int, source: str) -> str:
        """
        특정 문서의 특정 페이지 내용을 반환하는 함수
        
        Args:
            collection (int): 컬렉션 ID
            source (str): 문서 소스명
            page_num (str): 페이지 번호
            
        Returns:
            str: 페이지 내용
            
        Raises:
            Exception: DB 조회 중 오류 발생 시
        """
        try:            
            with self.conn.cursor() as cur:
                query = """
                    SELECT 
                        string_agg(d.content, E'\n' ORDER BY (d.metadata->>'source')::integer) as content
                    FROM documents d
                    WHERE 
                        d.collection_id = %s 
                        AND d.metadata->>'source' = %s
                        AND d.metadata->>'page' = %s
                    GROUP BY 
                        d.collection_id, 
                        d.metadata->>'source'
                """
                
                cur.execute(query, (collection, source))
                result = cur.fetchone()
                
                # 결과가 없는 경우 None 반환
                if not result:
                    return None
                    
                return result[0]  # content 값 반환

        except Exception as e:
            logger.error(f"Error getting document page content: {str(e)}")
            raise
            
    
    def _serialize_document(self, doc) -> dict:
        """Document 객체를 JSON 직렬화 가능한 딕셔너리로 변환"""
        try:
            if isinstance(doc, Document):
                return {
                    'page_content': str(doc.page_content),
                    'metadata': {
                        k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                        for k, v in doc.metadata.items()
                    }
                }
            elif isinstance(doc, dict):
                return {
                    'page_content': str(doc.get('page_content', '')),
                    'metadata': {
                        k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                        for k, v in (doc.get('metadata', {})).items()
                    }
                }
            else:
                return {'page_content': str(doc), 'metadata': {}}
        except Exception as e:
            logger.error(f"Error serializing document: {str(e)}")
            return {'page_content': '', 'metadata': {}}

    def get_all_documents_source(self, collection_name: str, source_search: str = '') -> list:
        """문서 소스 목록 조회"""
        try:
            with self.conn.cursor() as cur:
                # 먼저 collection_id 조회
                cur.execute("""
                    SELECT id 
                    FROM collections 
                    WHERE name = %s
                """, (collection_name,))
                
                collection_result = cur.fetchone()
                if not collection_result:
                    logger.warning(f"Collection not found: {collection_name}")
                    return []
                    
                collection_id = collection_result[0]
                
                # collection_id로 문서 소스 조회
                cur.execute("""
                    SELECT DISTINCT metadata->>'source' as source
                    FROM documents d
                    WHERE d.collection_id = %s
                    AND (
                        CASE 
                            WHEN %s = '' THEN TRUE  -- 검색어가 없으면 모든 소스 반환
                            ELSE metadata->>'source' ILIKE %s  -- 검색어가 있으면 필터링
                        END
                    )
                    ORDER BY source;
                """, (collection_id, source_search, f'%{source_search}%'))
                
                sources = [row[0] for row in cur.fetchall()]
                
                # 결과 로깅
                logger.info(f"Retrieved {len(sources)} sources from collection '{collection_name}'")
                return sources
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"문서 소스 조회 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def get_documents_by_source(self, collection_name: str, sources: Union[str, List[Dict], List[str]]) -> List[Document]:
        """
        소스별 문서 조회
        Args:
            collection_name: 컬렉션 이름
            sources: 단일 소스 문자열 또는 소스 목록 [{'collection': str, 'source': str}] 또는 [str]
        """
        try:
            with self.conn.cursor() as cur:
                # 먼저 collection_id 조회
                cur.execute("""
                    SELECT id 
                    FROM collections 
                    WHERE name = %s
                """, (collection_name,))
                
                collection_result = cur.fetchone()
                if not collection_result:
                    logger.warning(f"Collection not found: {collection_name}")
                    return []
                    
                collection_id = collection_result[0]

                # sources 타입 처리
                if not sources:
                    logger.warning("No sources provided")
                    return []

                source_list = []
                if isinstance(sources, str):
                    source_list = [sources]
                elif isinstance(sources, list):
                    if sources and isinstance(sources[0], dict):
                        # dictionary 형태인 경우 현재 collection에 해당하는 source만 추출
                        source_list = [
                            s['source'] for s in sources 
                            if s.get('collection') == collection_name
                        ]
                    else:
                        source_list = sources

                if not source_list:
                    logger.warning(f"No valid sources found for collection {collection_name}")
                    return []

                # IN 절을 사용하여 여러 소스 한 번에 조회
                cur.execute("""
                    SELECT content, metadata
                    FROM documents d
                    WHERE d.collection_id = %s 
                    AND metadata->>'source' = ANY(%s)
                    ORDER BY created_at DESC
                """, (collection_id, source_list))
                
                documents = []
                for row in cur.fetchall():
                    try:
                        # 메타데이터가 JSONB 형식이므로 파이썬 딕셔너리로 자동 변환됨
                        doc = Document(
                            page_content=row['content'],
                            metadata=row['metadata']
                        )
                        documents.append(doc)
                    except Exception as e:
                        logger.error(f"Error creating Document object: {str(e)}")
                        continue
                
                logger.info(f"Retrieved {len(documents)} documents from sources {source_list} in collection '{collection_name}'")
                return documents
                
        except Exception as e:
            logger.error(f"문서 조회 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        
    def get_document_metadata(self, collection_name: str, source: str) -> dict:
        """
        Gets metadata for a specific document in a collection.
        
        Args:
            collection_name (str): Name of the collection (will be converted to collection_id)
            source (str): Document source/filename
            
        Returns:
            dict: Document metadata or empty dict if not found
        """
        try:            
            with self.conn.cursor() as cur:
                # First get collection_id from collection_name
                collection_query = """
                SELECT id FROM collections 
                WHERE name = %s
                """
                cur.execute(collection_query, (collection_name,))
                collection_result = cur.fetchone()
                
                if not collection_result:
                    logger.warning(f"Collection not found: {collection_name}")
                    return {}
                    
                collection_id = collection_result[0]
                
                # Then get document metadata using collection_id
                doc_query = """
                SELECT d.metadata
                FROM documents d
                WHERE d.collection_id = %s AND d.metadata->>'source' = %s
                """
                
                cur.execute(doc_query, (collection_id, source))
                result = cur.fetchone()
                
                return result[0] if result else {}
                        
        except Exception as e:
            logger.error(f"Error getting metadata for {source} in {collection_name}: {str(e)}")
            return {}

    
    def get_ids_by_source(self, collection_name: str, source: str) -> List[str]:
        """소스별 문서 ID 조회"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id
                    FROM documents
                    WHERE collection_name = %s 
                    AND metadata->>'source' = %s
                """, (collection_name, source))
                
                return [str(row['id']) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"문서 ID 조회 오류: {e}")
            return []

    def delete_source(self, collection_id: int, sources: Union[str, List[str]]) -> Dict[str, List[str]]:
        """소스별 문서 삭제"""
        try:
            if not isinstance(sources, list):
                sources = [sources]
            
            successful = []
            failed = []
            
            with self.conn.cursor() as cur:        
                
                # 각 소스별 문서 삭제
                for source in sources:
                    try:
                        # 삭제 전 존재 여부 확인
                        cur.execute("""
                            SELECT COUNT(*) 
                            FROM documents 
                            WHERE collection_id = %s 
                            AND metadata->>'source' = %s
                        """, (collection_id, str(source)))
                        
                        count = cur.fetchone()[0]
                        if count == 0:
                            logger.warning(f"No documents found for source '{source}' in collection '{collection_id}'")
                            failed.append(source)
                            continue
                        
                        # 문서 삭제
                        cur.execute("""
                            DELETE FROM documents 
                            WHERE collection_id = %s 
                            AND metadata->>'source' = %s
                            RETURNING metadata->>'source' as source
                        """, (collection_id, str(source)))
                        
                        deleted = cur.fetchall()
                        if deleted:
                            successful.extend([row['source'] for row in deleted])
                            logger.info(f"Successfully deleted {len(deleted)} documents from source '{source}'")
                        else:
                            failed.append(source)
                            logger.warning(f"Failed to delete documents from source '{source}'")
                            
                    except Exception as e:
                        logger.error(f"Error deleting source '{source}': {str(e)}")
                        logger.error(traceback.format_exc())
                        failed.append(source)
                        self.conn.rollback()  # 현재 소스 삭제 실패 시 롤백
                
                self.conn.commit()  # 모든 성공한 삭제 작업 커밋
                
                # 결과 로깅
                logger.info(f"Delete operation completed. Successful: {len(successful)}, Failed: {len(failed)}")
                return {
                    "successful": successful, 
                    "failed": failed,
                    "deleted_count": len(successful)
                }
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in delete_source: {str(e)}")
            logger.error(traceback.format_exc())
            return {"successful": [], "failed": sources, "deleted_count": 0}

    def check_source_exists(self, collection_name: str, source: str) -> bool:
        """소스 존재 여부 확인"""
        try:
            if not isinstance(source, str):  # 파일 객체인 경우
                source = source.name
            source = os.path.basename(source)
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM documents 
                        WHERE collection_name = %s 
                        AND metadata->>'source' = %s
                    )
                """, (collection_name, str(source)))
                
                exists = cur.fetchone()[0]
                
                if exists:
                    logger.debug(f"Documents with source '{source}' exist in the collection")
                else:
                    logger.debug(f"No documents with source '{source}' found in the collection")
                    
                return exists
                
        except Exception as e:
            logger.error(f"소스 존재 여부 확인 오류: {e}")
            return False

    def verify_storage(self, collection_name: str) -> int:
        """저장소 검증"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM documents 
                    WHERE collection_name = %s
                """, (collection_name,))
                
                count = cur.fetchone()[0]
                
                if count > 0:
                    # 샘플 데이터 확인
                    cur.execute("""
                        SELECT content, metadata, embedding 
                        FROM documents 
                        WHERE collection_name = %s 
                        LIMIT 1
                    """, (collection_name,))
                    
                    sample = cur.fetchone()
                    logger.debug(f"Sample document found: {sample['content'][:100]}...")
                
                return count
                
        except Exception as e:
            logger.error(f"저장소 검증 오류: {e}")
            return 0
    
    def extract_text_from_file(self, file, file_name):
        return self.extractor.extract_text_from_file(file, file_name)


    def set_return_docnum(self, docnum: int):
        """반환할 문서 수 설정"""
        self.docnum = docnum
        
    def summarize_documents_from_page(self, collection_id: int, sources: List[str], 
                             llm_name: str, llm_model: str, 
                             page: int=1) -> Generator:
        """
        소스별 문서 요약
        
        Args:
            collection_id (int): 컬렉션 ID
            sources (List[str]): 소스 목록
            llm_name (str): LLM 이름
            llm_model (str): LLM 모델
            page (int): 페이지 번호 (기본값: 1)
        """
        def generator():
            try:
                total_steps = len(sources) + 3
                current_step = 0

                # 문서 수집 및 페이지 수 확인
                total_pages = 0
                for source in sources:
                    docs = self.get_document_page_content(collection_id, source, page)
                    total_pages += 1                                      
                    current_step += 1
                    yield {'type': 'progress', 'value': (current_step / total_steps) * 100}                  

                # LLM 초기화
                if llm_name == "Ollama":
                    from langchain_community.llms import Ollama
                    llm = Ollama(model=llm_model)
                elif llm_name == "Openai":
                    from langchain_community.chat_models import ChatOpenAI
                    llm = ChatOpenAI(model_name=llm_model, max_tokens=1024)
                elif llm_name == "Groq":
                    from langchain_groq import ChatGroq
                    llm = ChatGroq(model_name=llm_model, max_tokens=1024)
                else:
                    raise ValueError(f"Unsupported LLM: {llm_name}")
                
                current_step += 1
                yield {'type': 'progress', 'value': (current_step / total_steps) * 100}

                splits = [Document(page_content=docs)]
                
                current_step += 1
                yield {'type': 'progress', 'value': (current_step / total_steps) * 100}

                # 요약 프롬프트
                from langchain.prompts import PromptTemplate
                summarize_prompt = PromptTemplate(
                    template="""[시스템 지시사항]
                    이 프롬프트는 주어진 텍스트{text}를 한국어로 요약합니다.                  

                    [요약 지침]
                    1. 텍스트의 전반적인 주제와 핵심 개념을 1-2문장으로 소개하세요.

                    2. 주요 항목들을 나열하고, 각 항목에 대해:
                    - 항목명을 볼드체(**항목명**)로 표시
                    - 핵심 개념을 간단히 설명
                    - 주요 장단점이나 특징을 불릿 포인트(-)로 제시

                    3. 형식 요구사항:
                    - 전체 개요 먼저 제시
                    - 각 항목을 번호로 구분
                    - 중요 특징은 불릿 포인트로 표시
                    - 3-4문단 이내로 제한
                    - 전문 용어는 가능한 쉽게 설명

                    4. 전체 개요에서 전체 내용을 아우르는 통찰을 제시하세요.

                    [출력 형식]
                    
                    [전체 개요]
                                       
                    [주요 항목]
                    

     

                    """,
                    input_variables=["text"],
                    validate_template=True
                )

                # 요약 체인 생성
                from langchain.chains.summarize import load_summarize_chain
                summarize_chain = load_summarize_chain(llm, chain_type="stuff", prompt=summarize_prompt)

                # 단일 문서 요약
                chunk = splits[0]  # 단일 Document 사용
                summary = summarize_chain.invoke({"input_documents": [chunk]})
                logger.debug(f"Summary: {summary['output_text']}")

                # 요약 결과 반환
                yield {
                    'pages': summary['output_text'],
                    'metadata': {
                        'collection': collection_id,
                        'sources': sources,
                        'model': f"{llm_name}-{llm_model}",
                        'total_chunks': 1
                    }
                }
                
            except Exception as e:
                error_msg = f"요약 프로세스 오류: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                yield {'type': 'error', 'value': error_msg}

        return generator()
    

    def summarize_documents_from_source(self, collection_name: str, sources: List[str], 
                                 llm_name: str, llm_model: str, 
                                 page_size: int = 2048) -> Generator:
        """
        소스별 문서 요약
        
        Args:
            collection_name (str): 컬렉션 이름
            sources (List[str]): 소스 목록
            llm_name (str): LLM 이름
            llm_model (str): LLM 모델
            page_size (int): 각 페이지당 단어 수 (기본값: 2048)
        """
        def generator():
            try:
                total_steps = len(sources) + 3
                current_step = 0

                # 문서 수집 및 페이지 수 확인
                all_documents = []
                total_pages = 0
                for source in sources:
                    docs = self.get_documents_by_source(collection_name, source)
                    total_pages += len(docs)
                    
                    # 100페이지 초과 확인
                    if total_pages > 100:
                        yield {
                            'type': 'error',
                            'value': f"문서의 총 페이지 수({total_pages})가 100페이지를 초과합니다. 요약이 불가능합니다."
                        }
                        return

                    all_documents.extend(docs)
                    current_step += 1
                    yield {'type': 'progress', 'value': (current_step / total_steps) * 100}

                # LLM 초기화
                if llm_name == "Ollama":
                    from langchain_community.llms import Ollama
                    llm = Ollama(model=llm_model)
                elif llm_name == "Openai":
                    from langchain_community.chat_models import ChatOpenAI
                    llm = ChatOpenAI(model_name=llm_model, max_tokens=1024)
                elif llm_name == "Groq":
                    from langchain_groq import ChatGroq
                    llm = ChatGroq(model_name=llm_model, max_tokens=1024)
                else:
                    raise ValueError(f"Unsupported LLM: {llm_name}")
                
                current_step += 1
                yield {'type': 'progress', 'value': (current_step / total_steps) * 100}

                # 텍스트 분할
                from langchain.text_splitter import TokenTextSplitter
                text_splitter = TokenTextSplitter(chunk_size=self.chunk_size, chunk_overlap=100)
                splits = text_splitter.split_documents(all_documents)
                
                # 분할된 청크 수 확인
                if len(splits) > 100:
                    yield {
                        'type': 'error',
                        'value': f"분할된 청크의 수({len(splits)})가 100을 초과합니다. 요약이 불가능합니다."
                    }
                    return
                
                current_step += 1
                yield {'type': 'progress', 'value': (current_step / total_steps) * 100}

                # 요약 프롬프트
                from langchain.prompts import PromptTemplate
                summarize_prompt = PromptTemplate(
                    template="다음 텍스트를 요약해주세요. 주요 포인트만 추출하여 간단명료하게 작성하세요:\n\n{text}\n\n요약:",
                    input_variables=["text"]
                )

                # 요약 체인 생성
                from langchain.chains.summarize import load_summarize_chain
                summarize_chain = load_summarize_chain(llm, chain_type="stuff", prompt=summarize_prompt)

                # 각 청크 요약
                summaries = []
                for i, chunk in enumerate(splits):
                    retry_count = 0
                    max_retries = 5
                    while retry_count < max_retries:
                        try:
                            summary = summarize_chain.invoke({"input_documents": [chunk]})
                            summaries.append(summary['output_text'])
                            yield {'type': 'progress', 'value': ((current_step + (i+1)/len(splits)) / total_steps) * 100}
                            break
                        except Exception as e:
                            retry_count += 1
                            yield {'type': 'info', 'value': f"요약 오류 발생 (시도 {retry_count}/{max_retries}): {str(e)}"}
                            
                            if retry_count == max_retries:
                                yield {'type': 'error', 'value': f"최대 재시도 횟수 도달. 청크 {i+1} 요약 실패."}

                # 최종 요약 생성
                final_summary = "\n\n".join(summaries)
                
                # 페이지로 분할
                words = final_summary.split()
                pages = []
                current_page = []
                word_count = 0

                for word in words:
                    current_page.append(word)
                    word_count += 1
                    
                    if word_count >= page_size:
                        pages.append(' '.join(current_page))
                        current_page = []
                        word_count = 0
                
                # 마지막 페이지 처리
                if current_page:
                    pages.append(' '.join(current_page))

                # 페이지 정보와 함께 요약 결과 반환
                yield {
                    'type': 'summary',
                    'value': {
                        'total_pages': len(pages),
                        'pages': pages,
                        'metadata': {
                            'collection': collection_name,
                            'sources': sources,
                            'model': f"{llm_name}-{llm_model}",
                            'page_size': page_size,
                            'total_chunks': len(splits)
                        }
                    }
                }
            
            except Exception as e:
                error_msg = f"요약 프로세스 오류: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                yield {'type': 'error', 'value': error_msg}

        return generator()

   
    def close(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except Exception as e:
            logger.error(f"리소스 정리 오류: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()