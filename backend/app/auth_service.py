# auth_service.py
from datetime import datetime
import jwt
from psycopg2.extras import RealDictCursor
import os
from typing import Optional, Tuple, Dict, List,Union
import bcrypt
import logging

class AuthService:
    def __init__(self, db_pool, jwt_secret_key, jwt_expiration_delta):
        self.db_pool = db_pool
        self.jwt_secret_key = jwt_secret_key
        self.jwt_expiration_delta = jwt_expiration_delta
        self.currentuser=0
        self.logger = logging.getLogger(__name__)

    def get_currentuser_id(self):
        return self.currentuser
     
    def login(self, username: str, password: str) -> Tuple[Dict, str, datetime]:
        """
        사용자 로그인을 처리하고 세션을 생성합니다.
        Returns: (user_data, token, session_id)
        """
        try: 
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 사용자 확인
                    cur.execute("""
                        SELECT id, username, password_hash, is_active, group_id
                        FROM users
                        WHERE username = %s
                    """, (username,))
                    user = cur.fetchone()                
                    
                    if not user:
                        raise ValueError('사용자가 존재하지 않습니다.\n회원가입하세요!')
                    
                    if not user['is_active']:
                        raise ValueError('등록 대기 상태입니다.\n관리자에게 문의하세요!')

                    if not self._verify_password(password, user['password_hash']):
                        raise ValueError('올바른 비밀번호를 입력하세요!')

                    # 기존 세션 비활성화
                    self._deactivate_user_sessions(cur, user['id'])

                    # 새로운 세션 생성
                    token = self._generate_token(user['id'], user['username'])
                    session_id = os.urandom(32).hex()
                    expires_at = datetime.utcnow() + self.jwt_expiration_delta

                    self._create_session(cur, session_id, user['id'], token, expires_at)
                    conn.commit()
                    self.currentuser= int(user['id'])
                    return user, token, session_id
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database connection error: {e}")
            raise

    def register(self, username: str, email: str, password: str) -> Dict:
        """새로운 사용자를 등록합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 중복 체크
                    if self._check_duplicate_username(cur, username):
                        raise ValueError('이미 존재하는 사용자 이름입니다.')
                    
                    if self._check_duplicate_email(cur, email):
                        raise ValueError('이미 사용 중인 이메일입니다.')

                    # 사용자 생성
                    password_hash = self._hash_password(password)
                    cur.execute("""
                        INSERT INTO users (username, email, password_hash,is_active, group_id)
                        VALUES (%s, %s, %s, false, 'GRP000002')
                        RETURNING id, username
                    """, (username, email, password_hash))
                    conn.commit()
                    return cur.fetchone()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database connection error: {e}")
            raise
       

    def check_session(self, session_id: str) -> Optional[Dict]:
        """세션의 유효성을 검사합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            u.id, 
                            u.username, 
                            s.expires_at,
                            s.is_active
                        FROM sessions s
                        JOIN users u ON s.user_id = u.id
                        WHERE s.session_id = %s
                    """, (session_id,))
                    
                    session_data = cur.fetchone()
                    
                    if not session_data or \
                    not session_data['is_active'] or \
                    session_data['expires_at'] <= datetime.utcnow():
                        return None
                        
                    return session_data
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            raise
        
    
    def change_password(self, user_id: int, current_password: str, new_password: str) -> dict:
        """현재 로그인된 사용자의 비밀번호를 변경합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 현재 비밀번호 확인
                    cur.execute("""
                        SELECT password_hash
                        FROM users
                        WHERE id = %s
                    """, (user_id,))
                    
                    user = cur.fetchone()
                    if not user or not self._verify_password(current_password, user['password_hash']):
                        return {
                            'success': False,
                            'message': '현재 비밀번호가 일치하지 않습니다.'
                        }

                    # 새 비밀번호 설정
                    new_password_hash = self._hash_password(new_password)
                    cur.execute("""
                        UPDATE users 
                        SET password_hash = %s
                        WHERE id = %s
                    """, (new_password_hash, user_id))
                    
                    conn.commit()
                    
                    return {
                        'success': True,
                        'message': '비밀번호가 성공적으로 변경되었습니다.'
                    }

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Password change error for user {user_id}: {str(e)}")
            return {
                'success': False,
                'message': '비밀번호 변경 중 오류가 발생했습니다.'
            }
        
    def logout(self, session_id: str) -> None:
        """사용자 세션을 종료합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE sessions 
                        SET is_active = false 
                        WHERE session_id = %s
                    """, (session_id,))
                    conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database connection error: {e}")
            raise
        
    
    def is_admin(self, username: str) -> bool:
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 1 FROM users u JOIN user_groups ug ON u.id = ug.user_id
                        WHERE u.username = %s AND ug.group_id = 'GRP000001'
                    """, (username,))
                    return cur.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            raise
       
                
    def get_users(self):
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT u.id, u.username, u.email, u.group_id, u.is_active, g.name as group_name 
                        FROM users u
                        LEFT JOIN groups g ON u.group_id = g.id
                        ORDER BY u.username ASC
                    """)
                    users_list = cur.fetchall()

                    # 단일 쿼리로 통계 조회
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_count,
                            SUM(CASE WHEN is_active = true THEN 1 ELSE 0 END) as active_count 
                        FROM users
                    """)
                    counts = cur.fetchone()

                    return users_list, counts['total_count'], counts['active_count']
                    
        except Exception as e:
            self.logger.error(f"Error getting users: {e}")
            raise
        
    
    # auth_service.py에서 get_groups 메서드 수정    
    def get_groups(self):
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 그룹 목록 조회
                    cur.execute("""
                        SELECT id, name, description, created_at
                        FROM groups
                    """)
                    group_list = cur.fetchall()
                    return group_list
        except Exception as e:
            self.logger.error(f"Error getting groups: {e}")
            raise
        
        
    def assign_user_to_group(self, user_id: int, group_id: str) -> bool:
        """사용자를 특정 그룹에 할당"""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    # 사용자와 그룹이 존재하는지 확인
                    cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                    if not cur.fetchone():
                        raise ValueError(f"User ID {user_id} does not exist")

                    cur.execute("SELECT id FROM groups WHERE id = %s", (group_id,))
                    if not cur.fetchone():
                        raise ValueError(f"Group ID {group_id} does not exist")

                    # 중복 할당 방지
                    cur.execute("""
                        INSERT INTO user_groups (user_id, group_id, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, group_id) DO NOTHING
                        """, (user_id, group_id, datetime.now()))
                    conn.commit()
                    return {
                        'success': True,
                        'message': '성공적으로 생성되었습니다.'
                    }
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error assigning user to group: {e}")
            return {
                'success': False,
                'message': f'그룹룹 생성중 오류가 발생했습니다: {str(e)}'
            }
       
    
    def update_user_groups(self, user_id: int, group_ids: List[str]) -> Dict[str, Union[bool, str]]:
        """사용자의 그룹 목록 업데이트"""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    # 기존 그룹 삭제 시도
                    try:
                        cur.execute("""
                            DELETE FROM user_groups
                            WHERE user_id = %s
                        """, (user_id,))
                    except Exception as e:
                        # 삭제 중 에러가 발생해도 로그만 남기고 계속 진행
                        print(f"Delete operation error: {str(e)}")
                    
                    # group_ids가 비어있는 경우도 성공으로 처리 (모든 그룹 연결 제거)
                    if not group_ids:
                        conn.rollback()
                        return {
                            'success': False,
                            'message': '모든 그룹 연결이 제거되었습니다.'
                        }

                    try:
                        values = [(user_id, group_id) for group_id in group_ids]
                        cur.executemany("""
                            INSERT INTO user_groups (user_id, group_id)
                            VALUES (%s, %s)
                        """, values)
                        conn.commit()
                        return {
                            'success': True,
                            'message': '그룹 업데이트에 성공했습니다.'
                        }

                    except ValueError as ve:
                        # 정수 변환 실패 시
                        conn.rollback()
                        return {
                            'success': False,
                            'message': f'잘못된 그룹 ID 형식입니다: {str(ve)}'
                        }
                    except Exception as insert_error:
                        # 기타 삽입 중 오류 발생 시
                        conn.rollback()
                        return {
                            'success': False,
                            'message': f'그룹 생성 중 오류가 발생했습니다: {str(insert_error)}'
                        }

        except Exception as e:
            # 데이터베이스 연결 등 전반적인 오류
            return {
                'success': False,
                'message': f'데이터베이스 작업 중 오류가 발생했습니다: {str(e)}'
            }
    
    def update_collection_groups(self,collection_id: int, group_ids: List[str]) -> Dict[str, Union[bool, str]]:
        """사용자의 그룹 목록 업데이트"""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    # 기존 그룹 삭제 시도
                    try:
                        cur.execute("""
                            DELETE FROM collection_permissions
                            WHERE collection_id = %s
                        """, (collection_id,))
                    except Exception as e:
                        # 삭제 중 에러가 발생해도 로그만 남기고 계속 진행
                        print(f"Delete operation error: {str(e)}")
                    
                    # group_ids가 비어있는 경우도 성공으로 처리 (모든 그룹 연결 제거)
                    if not group_ids:
                        conn.rollback()
                        return {
                            'success': False,
                            'message': '모든 그룹 연결이 제거되었습니다.'
                        }

                    try:
                        
                        # 새로운 권한 정보 삽입
                        current_time = datetime.now()
                    
                        # 새로운 권한 정보 삽입
                        values = [
                        (
                            collection_id,
                            group['group_id'],  # group_id
                            group['permissions']['read'],
                            group['permissions']['write'],
                            group['permissions']['delete'],                            
                            current_time,
                            current_time
                        ) 
                        for group in group_ids]
                    
                        cur.executemany("""
                            INSERT INTO collection_permissions 
                            (collection_id, group_id, can_read, can_write, can_delete, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, values)
                        conn.commit()
                        return {
                            'success': True,
                            'message': '그룹 업데이트에 성공했습니다.'
                        }

                    except ValueError as ve:
                        # 정수 변환 실패 시
                        conn.rollback()
                        return {
                            'success': False,
                            'message': f'잘못된 그룹 ID 형식입니다: {str(ve)}'
                        }
                    except Exception as insert_error:
                        # 기타 삽입 중 오류 발생 시
                        conn.rollback()
                        return {
                            'success': False,
                            'message': f'그룹 생성 중 오류가 발생했습니다: {str(insert_error)}'
                        }

        except Exception as e:
            # 데이터베이스 연결 등 전반적인 오류
            return {
                'success': False,
                'message': f'데이터베이스 작업 중 오류가 발생했습니다: {str(e)}'
            }
    
    def get_collection_permissions(self, collection_id: str) -> Dict[str, Union[bool, List, str]]:        
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 그룹 목록 조회
                    cur.execute("""
                        SELECT 
                            cp.group_id,
                            g.name as group_name,
                            g.description,
                            cp.can_read,
                            cp.can_write,
                            cp.can_delete
                        FROM collection_permissions cp
                        JOIN groups g ON cp.group_id = g.id
                        WHERE cp.collection_id = %s
                    """, (collection_id,))
                    permissions = cur.fetchall()
                    
                    if not permissions:
                        return {
                            "success": True,
                            "groups": []
                        }
                    
                    result = [
                        {
                            "id": permission['group_id'],
                            "name": permission['group_name'],
                            "description": permission['description'],
                            "permissions": {
                                "read": permission['can_read'],
                                "write": permission['can_write'],
                                "delete": permission['can_delete']
                            }
                        }
                        for permission in permissions
                    ]
                    
                    return {
                        "success": True, 
                        "groups": result
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "message": "권한 정보 조회 중 오류가 발생했습니다",
                "error_details": str(e),
                "groups": []
            }   
        
    
    

    def remove_user_from_group(self, user_id: int, group_id: str) -> bool:
        """사용자를 특정 그룹에서 제거"""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM user_groups 
                        WHERE user_id = %s AND group_id = %s
                        """, (user_id, group_id))
                    conn.commit()
                    return {
                        'success': True,
                        'message': '성공적으로 생성되었습니다.'
                    }
        except Exception as e:
            self.logger.error(f"Error removing user from group: {e}")
            return {
                'success': False,
                'message': f'그룹룹 생성중 오류가 발생했습니다: {str(e)}'
            }
            
    def get_user_groups(self, user_id: int) -> List[dict]:
        """사용자의 모든 그룹 조회"""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT g.id, g.name, g.description
                        FROM groups g
                        JOIN user_groups ug ON g.id = ug.group_id
                        WHERE ug.user_id = %s
                        """, (user_id,))
                    columns = ['id', 'name', 'description']
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting user groups: {e}")
            raise

    def get_group_users(self, group_id: str) -> List[dict]:
        """그룹의 모든 사용자 조회"""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT u.id, u.username, u.email
                        FROM users u
                        JOIN user_groups ug ON u.id = ug.user_id
                        WHERE ug.group_id = %s
                        """, (group_id,))
                    columns = ['id', 'username', 'email']
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting group users: {e}")
            raise


    def get_group_by_id(self, group_id: str) -> Optional[Dict]:
        """특정 그룹을 ID로 조회합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id, name, description, created_at
                        FROM groups
                        WHERE id = %s
                    """, (group_id,))
                    return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error getting group {group_id}: {e}")
            raise
        

    def create_group(self, name: str, description: str) -> bool:
        """새로운 그룹을 생성합니다."""
        if not name or len(name.strip()) == 0:
            raise ValueError("그룹 이름은 필수입니다.")
            
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        INSERT INTO groups (id, name, description, created_at)
                        VALUES ('GRP' || LPAD(NEXTVAL('group_seq')::TEXT, 6, '0'), %s, %s, CURRENT_TIMESTAMP)
                        RETURNING id, name, description, created_at;
                    """, (name.strip(), description.strip() if description else None))
                    conn.commit()
                    return {
                        'success': True,
                        'message': '성공적으로 생성되었습니다.'
                    }
        except Exception as e:
            return {
                'success': False,
                'message': f'그룹룹 생성중 오류가 발생했습니다: {str(e)}'
            }

    def update_group(self, group_id: str, name: str, description: str) -> Dict:
        """기존 그룹 정보를 수정합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 현재 그룹 정보 조회
                    cur.execute("SELECT name, description FROM groups WHERE id = %s", (group_id,))
                    current_group = cur.fetchone()
                    
                    if not current_group:
                        return {
                            'success': False,
                            'message': f'그룹룹 변경중 오류가 발생했습니다: {str(e)}'
                        }
                    
                    # 수정할 값이 없으면 현재 값 사용
                    update_name = name if name is not None else current_group['name']
                    update_description = description if description is not None else current_group['description']
                    
                    cur.execute("""
                        UPDATE groups
                        SET name = %s, description = %s
                        WHERE id = %s
                        RETURNING id, name, description, created_at
                    """, (update_name, update_description, group_id))
                    conn.commit()
                    return {
                        'success': True,
                        'message': '성공적으로 변경되었습니다.'
                    }
        except Exception as e:
            return {
                'success': False,
                'message': f'그룹룹 변경중 오류가 발생했습니다: {str(e)}'
            }
       

    def delete_group(self, group_id: str) -> Dict:
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM groups WHERE id = %s RETURNING id", (group_id,))
                    deleted = cur.fetchone()
                    if not deleted:
                        return {
                            'success': False,
                            'message': '그룹을 찾을 수 없습니다.'
                        }
                    conn.commit()
                    return {
                        'success': True,
                        'message': '성공적으로 삭제되었습니다.'
                    }
        except Exception as e:
            return {
                'success': False,
                'message': f'그룹 삭제중 오류가 발생했습니다: {str(e)}'
            }
        
    

    def update_user_status(self, user_ids: List[int], is_active: bool) -> Dict:
        """선택된 사용자들의 활성화 상태를 변경합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE users 
                        SET is_active = %s
                        WHERE id = ANY(%s)
                        RETURNING id
                    """, (is_active, user_ids))
                    
                    updated_ids = [row[0] for row in cur.fetchall()]
                    conn.commit()
                    
                    return {
                        'success': True,
                        'message': f'{len(updated_ids)}명의 사용자 상태가 변경되었습니다.',
                        'updated_ids': updated_ids
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'message': f'사용자 상태 변경 중 오류가 발생했습니다: {str(e)}'
            }
       

    def bulk_update_status(self, is_active: bool) -> Dict:
        """모든 사용자의 활성화 상태를 변경합니다."""
        try:
            with self.db_pool.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE users 
                        SET is_active = %s
                        WHERE is_active != %s
                        RETURNING id
                    """, (is_active, is_active))
                    
                    updated_ids = [row[0] for row in cur.fetchall()]
                    conn.commit()
                    
                    return {
                        'success': True,
                        'message': f'모든 사용자({len(updated_ids)}명)의 상태가 변경되었습니다.',
                        'updated_ids': updated_ids
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'message': f'사용자 상태 일괄 변경 중 오류가 발생했습니다: {str(e)}'
            }
        

    def verify_token(self, token: str) -> Optional[Dict]:
        """JWT 토큰의 유효성을 검증합니다."""
        try:
            return jwt.decode(token, self.jwt_secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise ValueError('Token has expired')
        except jwt.InvalidTokenError:
            raise ValueError('Invalid token')
        

    # Private helper methods     
    def _hash_password(self, password: str) -> str:
        """
        비밀번호를 해시화하는 함수
        
        Args:
            password: 해시할 원본 비밀번호
            
        Returns:
            str: 해시된 비밀번호
        """
        try:
            # 비밀번호를 바이트로 인코딩
            password_bytes = password.encode('utf-8')
            # salt 생성 및 해시화
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            # 해시된 비밀번호를 문자열로 디코딩
            return hashed.decode('utf-8')
        except Exception as e:            
            raise
    def _verify_password(self,plain_password: str, hashed_password: str) -> bool:
        """
        비밀번호 검증 함수
        
        Args:
            plain_password: 검증할 원본 비밀번호
            hashed_password: 저장된 해시 비밀번호
            
        Returns:
            bool: 비밀번호 일치 여부
        """
        try:
            # 문자열을 바이트로 인코딩
            plain_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            # 비밀번호 검증
            return bcrypt.checkpw(plain_bytes, hashed_bytes)
        except Exception as e:        
            return False
        
    def _generate_token(self, user_id: int, username: str) -> str:
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + self.jwt_expiration_delta
        }
        return jwt.encode(payload, self.jwt_secret_key, algorithm='HS256')

    def _deactivate_user_sessions(self, cur, user_id: int) -> None:
        cur.execute("""
            UPDATE sessions 
            SET is_active = false 
            WHERE user_id = %s
        """, (user_id,))

    def _create_session(self, cur, session_id: str, user_id: int, 
                       token: str, expires_at: datetime) -> None:
        cur.execute("""
            INSERT INTO sessions (
                session_id, user_id, token, is_active, 
                created_at, expires_at
            ) VALUES (%s, %s, %s, true, NOW(), %s)
        """, (session_id, user_id, token, expires_at))

    def _check_duplicate_username(self, cur, username: str) -> bool:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        return cur.fetchone() is not None

    def _check_duplicate_email(self, cur, email: str) -> bool:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        return cur.fetchone() is not None