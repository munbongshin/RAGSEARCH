from typing import List, Dict, Optional, Tuple
import logging
import traceback
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class CollectionPermissionManager:
    def __init__(self, conn):
        """
        Collection Permissions 관리 클래스 초기화
        
        Args:
            conn: 데이터베이스 연결 객체
        """
        self.conn = conn

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

    def delete_permission(self, collection_id: int, group_id: int) -> bool:
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

    def get_group_permissions(self, group_id: int) -> List[Dict]:
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

    def check_permission(self, collection_id: int, group_id: int) -> Dict:
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
                            'group_id': int,
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
        
    def get_collections_by_creator(self, creator_id):
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
                    SELECT name 
                    FROM groups 
                    WHERE id = %s
                """, (creator_id,))
                group_result = cur.fetchone()
                
                if not group_result:
                    logger.warning(f"Group not found for creator_id: {creator_id}")
                    return []
                
                is_admin = group_result['name'].lower() == 'admin'
                
                # admin인 경우 모든 컬렉션 반환, 아닌 경우 해당 creator의 컬렉션만 반환
                if is_admin:
                    cur.execute("""
                        SELECT 
                            c.id, 
                            c.name, 
                            c.created_at,
                            c.creator as creator_id,
                            g.name as creator_name
                        FROM collections c
                        JOIN groups g ON c.creator = g.id
                        ORDER BY c.name
                    """)
                else:
                    cur.execute("""
                        SELECT 
                            c.id, 
                            c.name, 
                            c.created_at,
                            c.creator as creator_id,
                            g.name as creator_name
                        FROM collections c
                        JOIN groups g ON c.creator = g.id
                        WHERE c.creator = %s
                        ORDER BY c.name
                    """, (creator_id,))
                
                collections = cur.fetchall()
                
                logger.debug(
                    f"Retrieved {len(collections)} collections for creator {creator_id} "
                    f"(admin access: {is_admin})"
                )
                
                return collections
                
        except Exception as e:
            logger.error(f"Error getting collections for creator {creator_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return []