import uuid
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any
from psycopg2.extras import RealDictCursor
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self, conn):
        self.conn = conn
        self.session_duration = timedelta(hours=24)
        
    def create_session(self, user_id: int, ip_address: str, user_agent: str) -> str:
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + self.session_duration

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO sessions 
                (user_id, session_id, expires_at, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING session_id
            """, (user_id, session_id, expires_at, ip_address, user_agent))
            self.conn.commit()
            return session_id

    def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 유효성 검증
        
        Args:
            session_id: 검증할 세션 ID
            
        Returns:
            세션 정보 딕셔너리 또는 None
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        u.id as user_id,
                        u.username,
                        u.email,
                        s.expires_at,
                        s.ip_address,
                        s.created_at
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.session_id = %s 
                    AND s.is_active = true 
                    AND s.expires_at > NOW()
                """, (session_id,))
                result = cur.fetchone()
                
                if result:
                    # 세션 접근 시간 업데이트
                    cur.execute("""
                        UPDATE sessions 
                        SET last_accessed = NOW()
                        WHERE session_id = %s
                    """, (session_id,))
                    self.conn.commit()
                    
                return result

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Session validation failed: {str(e)}")
            return None

    def end_session(self, session_id: str) -> bool:
        """세션 종료
        
        Args:
            session_id: 종료할 세션 ID
            
        Returns:
            성공 여부
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE sessions 
                    SET 
                        is_active = false,
                        ended_at = NOW()
                    WHERE session_id = %s
                    RETURNING session_id
                """, (session_id,))
                
                if cur.fetchone():
                    self.conn.commit()
                    logger.info(f"Session {session_id} ended")
                    return True
                return False

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to end session: {str(e)}")
            return False

    def cleanup_expired_sessions(self) -> int:
        """만료된 세션 정리
        
        Returns:
            정리된 세션 수
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE sessions 
                    SET 
                        is_active = false,
                        ended_at = NOW()
                    WHERE expires_at < NOW()
                    AND is_active = true
                    RETURNING session_id
                """)
                cleaned_sessions = cur.fetchall()
                self.conn.commit()
                
                count = len(cleaned_sessions)
                if count > 0:
                    logger.info(f"Cleaned up {count} expired sessions")
                return count

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Session cleanup failed: {str(e)}")
            return 0

    def get_active_sessions(self, user_id: int) -> list:
        """사용자의 활성 세션 목록 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            활성 세션 목록
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        session_id,
                        ip_address,
                        user_agent,
                        created_at,
                        last_accessed,
                        expires_at
                    FROM sessions
                    WHERE user_id = %s
                    AND is_active = true
                    AND expires_at > NOW()
                    ORDER BY created_at DESC
                """, (user_id,))
                return cur.fetchall()

        except Exception as e:
            logger.error(f"Failed to get active sessions: {str(e)}")
            return []