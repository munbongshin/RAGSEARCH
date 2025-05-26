import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from backend.app.PostgresDbManager import PostgresDbManager
from backend.app.ChromaDbManager import ChromaDbManager
from backend.app.RagChatApp import RAGChatApp
from backend.app.systemMessageManager import SystemMessageManager
from backend.app.auth_session_service import SessionService
from backend.app.auth_middleware import DatabasePool
from backend.app.auth_service import AuthService

from flask import Blueprint, Flask, request, Response, jsonify, make_response
from flask_cors import CORS
import logging, json
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import urllib.parse
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import jwt
from functools import wraps
from dotenv import load_dotenv
import os

load_dotenv()

dbpool = DatabasePool()

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY must be set")
JWT_EXPIRATION_DELTA = timedelta(hours=9)

# 로깅 설정
logging.basicConfig(
    level=logging.CRITICAL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def generate_token(user_id: int, username: str) -> str:
    # is_admin 여부 확인
    is_admin = auth_service.is_admin(username)
    
    payload = {
        'user_id': user_id,
        'username': username,
        'is_admin': is_admin,  # 추가
        'exp': datetime.utcnow() + JWT_EXPIRATION_DELTA
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)
# RAGChatApp.py 파일의 시작 부분에 다음 환경 변수 추가
os.environ["LANGCHAIN_POSTHOG_DISABLED"] = "true"

# TensorFlow 경고 메시지 비활성화
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ["FILLTERED_DOC_NUMBER"] = '5'

  
app = Flask(__name__)
# Flask 서버 설정

CORS(app, resources={
    r"/api/*": {  
        "origins": "*",  # Allow all origins
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

auth_bp = Blueprint('auth', __name__)


# 서비스 초기화
auth_service = AuthService(
    db_pool=dbpool,
    jwt_secret_key=JWT_SECRET_KEY,
    jwt_expiration_delta=JWT_EXPIRATION_DELTA
)

# JWT 인증 데코레이터
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'message': 'Missing or invalid token'}), 401
        
        token = auth_header.split(' ')[1]
        try:
            request.user = auth_service.verify_token(token)
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({'message': str(e)}), 401
    return decorated

def require_admin(f):
    @require_auth
    @wraps(f)
    def decorated(*args, **kwargs):
        if not auth_service.is_admin(request.user['username']):
            return jsonify({'message': '관리자만 접근할 수 있습니다.'}), 403
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['POST'])
def login():
        try:
            if request.method == 'OPTIONS':
                response = jsonify({'message': 'OK'})
                response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
                return response

            data = request.get_json()
            username = data.get('username')
            password = data.get('password')

            user, token, session_id = auth_service.login(username, password)

            response = jsonify({
                'message': 'Login successful',
                'token': token,
                'username': user['username'],
                'group_id': user['group_id'],
                'user_id': user['id'],
                'sessionStorage': True
            })

            response.set_cookie(
                'session_id',
                session_id,
                secure=True,
                httponly=True,
                samesite='Lax',
                expires=None
            )

            return response

        except ValueError as e:
            error_message = str(e)
            error_code = 'INVALID_CREDENTIALS'
            
            if '사용자가 존재하지 않습니다' in error_message:
                error_code = 'USER_NOT_FOUND'
            elif '등록 대기 상태' in error_message:
                error_code = 'USER_INACTIVE'
            elif '올바른 비밀번호' in error_message:
                error_code = 'INVALID_PASSWORD'
                
            return jsonify({
                'message': error_message,
                'error_code': error_code
            }), 401
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return jsonify({'message': str(e)}), 500
    

@auth_bp.route('/check-auth', methods=['GET'])
@require_auth
def check_auth():
    try:
        # 현재 사용자 정보 로깅
        current_user = getattr(request, 'user', None)
        logger.info(f"Current user: {current_user}")
        
        # 토큰 검증 및 사용자 정보 추출
        if not current_user:
            logger.warning("No user information found in the request")
            return jsonify({
                'authenticated': False,
                'message': '유효한 사용자 정보를 찾을 수 없습니다.'
            }), 401
        
        # 사용자 추가 정보 조회 (선택사항)
        user = db_manager.get_user_by_username(current_user['username'])
        
        if not user:
            logger.warning(f"User not found: {current_user['username']}")
            return jsonify({
                'authenticated': False,
                'message': '사용자 정보를 찾을 수 없습니다.'
            }), 401
        
        # 응답 데이터 준비
        return jsonify({
            'authenticated': True,
            'username': current_user['username'],
            'user_id': user['id'] if isinstance(user, dict) else user.id,
            'is_admin': user.get('is_admin', False) if isinstance(user, dict) else user.is_admin
        })
    
    except Exception as e:
        logger.error(f"Error in check_auth: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'authenticated': False,
            'message': '인증 확인 중 오류가 발생했습니다.'
        }), 500
    
@auth_bp.route('/check-admin', methods=['POST'])
@require_auth
def check_admin_status():
    try:
        data = request.get_json()
        username = data.get('username')
        is_admin = auth_service.is_admin(username)
        logger.info(f"is_admin: {is_admin}")
        return jsonify({
            'success': True,
            'is_admin': is_admin,
            'username': username
        })
    except Exception as e:
        logger.error(f"Admin check error: {str(e)}")
        return jsonify({
            'success': False,
            'message': '관리자 상태 확인 중 오류가 발생했습니다.'
        }), 500

@auth_bp.route('/check-session', methods=['GET', 'OPTIONS'])
def check_session():
    try:
        session_id = request.cookies.get('session_id')
        if not session_id:
            return jsonify({'authenticated': False}), 401

        session_data = auth_service.check_session(session_id)
        if not session_data:
            return jsonify({'authenticated': False}), 401

        return jsonify({
            'authenticated': True,
            'username': session_data['username']
        })

    except Exception as e:
        logger.error(f"Session check error: {str(e)}")
        return jsonify({'authenticated': False}), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not all([username, email, password]):
            return jsonify({'message': '모든 필드를 입력해주세요.'}), 400

        user = auth_service.register(username, email, password)
        
        return jsonify({
            'message': '회원가입이 완료되었습니다.',
            'username': user['username']
        }), 201

    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'message': '회원가입 처리 중 오류가 발생했습니다.'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@require_auth
def change_password():
        try:
            data = request.get_json()
            current_password = data.get('currentPassword')
            new_password = data.get('newPassword')

            if not all([current_password, new_password]):
                return jsonify({
                    'success': False,
                    'message': '모든 필드를 입력해주세요.'
                }), 400

            result = auth_service.change_password(
                user_id=request.user['user_id'],
                current_password=current_password,
                new_password=new_password
            )
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400

        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return jsonify({
                'success': False,
                'message': '비밀번호 변경 중 오류가 발생했습니다.'
            }), 500


@auth_bp.route('/logout', methods=['POST', 'OPTIONS'])
def logout():
    try:
        if request.method == 'OPTIONS':
            return jsonify({'message': 'OK'})

        session_id = request.cookies.get('session_id')
        if session_id:
            auth_service.logout(session_id)

        response = make_response(jsonify({
            'success': True,
            'message': 'Logout successful'
        }))
        
        # 쿠키 삭제 설정
        response.delete_cookie(
            'session_id',
            path='/',
            domain=None,
            samesite='Lax',
            secure=True,
            httponly=True
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    
@auth_bp.route('/list', methods=['GET'])
@require_auth
def get_users():
  try:        
      
      users_list, total_count, active_count = auth_service.get_users()
      
      return jsonify({
          'users': users_list,
          'totalCount': total_count, 
          'activeCount': active_count
      }), 200
      
  except Exception as e:
      logger.error(f"User list error: {str(e)}")
      return jsonify({
          'message': str(e)
      }), 500

@auth_bp.route('/update-status', methods=['POST'])
@require_auth
def update_status():
    try:
        if request.method == 'OPTIONS':
            return jsonify({'message': 'OK'})

        data = request.get_json()
        user_ids = data.get('user_ids', [])
        is_active = data.get('is_active')

        if not isinstance(user_ids, list):
            return jsonify({
                'success': False,
                'message': 'user_ids must be a list'
            }), 400

        if is_active is None:
            return jsonify({
                'success': False,
                'message': 'is_active is required'
            }), 400

        result = auth_service.update_user_status(user_ids, is_active)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Update status error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auth_bp.route('/bulk-update', methods=['POST'])
@require_auth
def bulk_update():
    try:
        data = request.get_json()
        is_active = data.get('is_active')

        if is_active is None:
            return jsonify({
                'success': False,
                'message': 'is_active is required'
            }), 400

        result = auth_service.bulk_update_status(is_active)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Bulk update error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        

# 그룹 API 엔드포인트
# 그룹 목록 조회
@auth_bp.route('/groups', methods=['GET'])
@require_auth
def get_groups():
    try:
        groups = auth_service.get_groups()  # groups 테이블에서 데이터 조회
        return jsonify({
            'success': True,
            'message': '그룹 목록을 성공적으로 불러옸습니다.',
            'groups': groups
        }), 200
    except Exception as e:
        logger.error(f"Error getting groups: {str(e)}")
        return jsonify({
            'success': False,
            'message': '그룹 목록을 불러오는데 실패했습니다.'
        }), 500

# 특정 그룹 조회
@auth_bp.route('/groups/<int:group_id>', methods=['GET'])
@require_auth
@require_admin
def get_group(group_id: int):
    try:
        group = auth_service.get_group_by_id(group_id)
        if not group:
            return jsonify({'message': '해당 그룹을 찾을 수 없습니다.'}), 404
        return jsonify({'group': group}), 200
    except Exception as e:
        logger.error(f"Error getting group {group_id}: {str(e)}")
        return jsonify({'message': '그룹 조회 중 오류가 발생했습니다.'}), 500

# 새 그룹 생성
@auth_bp.route('/groups/create', methods=['POST'])
@require_auth
def create_group():
    try:
       data = request.get_json()
       name = data.get('name')
       description = data.get('description')

       if not name:
           return jsonify({'message': '그룹 이름은 필수입니다.'}), 400

       result = auth_service.create_group(name, description)       
       return jsonify(result), 200
       
    except ValueError as e:
            return jsonify({
                'success': False,
                'message': f'그룹 생성 중 오류: {str(e)}'
            }), 400
    except Exception as e:
        logger.error(f"Error creating group: {str(e)}")
        return jsonify({
            'success': False,
            'message': '그룹 생성 중 오류가 발생했습니다.'
        }), 500

# 그룹 정보 수정
@auth_bp.route('/groups/update', methods=['POST'])
@require_auth
def update_group():
   if request.method == 'POST':
        try:
            data = request.get_json()
            group_id = data.get('group_id')
            name = data.get('name')
            description = data.get('description')
            updated_group = auth_service.update_group(
                group_id=group_id,
                name=name,
                description=description
            )
            return jsonify(updated_group), 200

        except ValueError as e:
            return jsonify({
                'success': False,
                'message': f' 오류가 발생했습니다. {str(e)}'
            }), 400
        except Exception as e:
            logger.error(f"그룹 수정 중 에러: {group_id}: {str(e)}")
            return jsonify({'message': f' 오류가 발생했습니다. {str(e)}'}), 500

@auth_bp.route('/groups/delete', methods=['POST'])
@require_auth
def delete_group():   # Remove parameter here
    try:
        group_id = request.json.get('group_id')
        if not group_id:
            return jsonify({'success': False, 'message': 'Group ID is required'}), 400
        deleted = auth_service.delete_group(group_id)
        return jsonify(deleted), 200
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': str(e)
        }), 500
        
@auth_bp.route('/users/grouplist', methods=['POST'])
@require_auth
def get_user_groups():
    """사용자의 그룹 목록 조회"""
    try:
        user_id = request.json.get('user_id')
        if not user_id:
            return jsonify({
                'success': False, 
                'message': 'User ID is required'
            }), 400
            
        # int로 형변환 추가
        groups = auth_service.get_user_groups(int(user_id))    
        return jsonify(groups), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
@auth_bp.route('/users/savegroups', methods=['POST'])
@require_auth
def save_user_groups():
    """사용자의 그룹 목록 저장"""
    try:
        user_id = int(request.json.get('user_id'))
        group_ids = request.json.get('group_ids')
        
        if not user_id or not isinstance(group_ids, list):
            return jsonify({
                'success': False,
                'message': 'Invalid request data'
            }), 400
            
        # 사용자의 기존 그룹을 모두 제거하고 새로운 그룹 할당
        auth_service.update_user_groups(user_id, group_ids)
        
        return jsonify({
            'success': True,
            'message': 'Groups updated successfully'
        }), 200        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auth_bp.route('/users/assigngroup', methods=['POST'])
@require_auth
def assign_group():
    try:
        """사용자에게 그룹 할당"""
        user_id = int(request.json.get('user_id'))
        group_id = request.json.get('group_id')
        
        if not user_id or not group_id:
            return jsonify({"error": "groupId is required"}), 400

        success = auth_service.assign_user_to_group(user_id, group_id)
        
        if success:
            return jsonify({'success': True,'message': 'Group assigned successfully'}), 201
        return jsonify({'success': False, 'message': str(e)}), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auth_bp.route('/users/deletegroup', methods=['DELETE'])  # 'methods' 오타
@require_auth
def remove_group():
    try:
        """사용자의 그룹 할당 해제"""
        user_id = int(request.json.get('user_id'))
        group_id = request.json.get('group_id')
        
        if not user_id or not group_id:
            return jsonify({'error': 'groupId is required'}), 400
        success = auth_service.remove_user_from_group(user_id, group_id)
        
        if success:
            return jsonify({'success': True,'message': 'Group removed successfully.'}), 200
        else:
            return jsonify({
            'success': False,
            'message': '그룹을 삭제 실패'}), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auth_bp.route('/groups/groupusers', methods=['POST'])
@require_auth
def get_group_users():
    try:
        """그룹에 속한 사용자 목록 조회"""
        group_id = request.json.get('group_id')
        users = auth_service.get_group_users(group_id)        
        return jsonify(users),200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# Front-end의 요청 형식에 맞춘 새로운 API 엔드포인트
@auth_bp.route('/permissionsave', methods=['POST'])
@require_auth
def save_collection_permissions():
    try:
        data = request.json
        # 데이터 구조 직접 접근
        collection_id = data.get('collection_id')
        group_permissions = data.get('group_permissions', [])

        # 필수 데이터 검증
        if not collection_id:
            return jsonify({
                'success': False,
                'message': f'collection_id가 {collection_id} 필요합니다.'
            }), 400

        if not group_permissions:
            return jsonify({
                'success': False,
                'message': '최소 1개 이상의 그룹이 필요합니다.'
            }), 400

        # 권한 업데이트 수행
        success = auth_service.update_collection_groups(collection_id, group_permissions)
        
        if success:            
            return jsonify({
                "success": True, 
                "message": "권한이 성공적으로 저장되었습니다."
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'collection 권한 부여 실패'
            }), 400
        
    except Exception as e:
        print(f"권한 저장 중 오류 발생: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
        
@auth_bp.route('/permissionlist', methods=['POST'])
@require_auth
def get_collection_permissions():       
    try:
        # GET 요청의 쿼리 파라미터에서 collection_id 획득
        collection_id = request.json.get('collection_id')
        
        if not collection_id:
            return jsonify({
                'success': False,
                'message': 'collection_id is required'
            }), 400
            
        # 서비스 레이어를 통한 권한 정보 조회
        response = auth_service.get_collection_permissions(collection_id)
        logger.debug(f"permissions: {response}")
        
        return jsonify({
            'success': True,
            'message': '그룹 목록을 성공적으로 불러왔습니다.',
            'groups': response
        }), 200
        
    except Exception as e:
        print(f"Error in get_collection_permissions: {str(e)}")  # 디버깅용 로그
        return jsonify({
            'success': False,
            'message': f'권한 정보 조회 중 오류가 발생했습니다: {str(e)}'
        }), 500
        
    
app.register_blueprint(auth_bp, url_prefix='/api/auth')

# 파일 핸들러 추가
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
file_handler = RotatingFileHandler(
    f'{log_dir}/app.log', 
    maxBytes=1024*1024, 
    backupCount=5
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
logger.addHandler(file_handler)


# 전역 에러 핸들러
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({
        "success": False,
        "error": str(e),
        "message": "Internal server error"
    }), 500

# 데이터베이스 매니저 초기화
db_type = os.getenv('DB_TYPE', 'chroma').lower()
if db_type == 'postgres':    
    db_manager = PostgresDbManager()
else:
    db_manager = ChromaDbManager()

rag_app = RAGChatApp(db_type=db_type)
message_manager = SystemMessageManager()

def document_to_dict(document):
    """Document 객체를 dictionary로 변환합니다."""
    try:
        if isinstance(document, dict):
            page_content = document.get('page_content', '')
            metadata = document.get('metadata', {})
        elif hasattr(document, 'page_content') and hasattr(document, 'metadata'):
            page_content = document.page_content
            metadata = document.metadata
        else:
            page_content = str(document)
            metadata = {}

        source = metadata.get('source', '')
        page = metadata.get('page', '')

        return {
            'title': source,
            'page': page,
            'content': page_content
        }
    except Exception as e:
        logger.error(f"Error in document_to_dict: {e}")
        return {
            'title': 'Error',
            'page': '',
            'content': 'Failed to process document'
        }

@app.route('/api/delete-sources', methods=['POST'])
def delete_sources():
    try:
        # 입력 데이터 검증
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400

        documents = data.get('documents', [])
        
        if not isinstance(documents, list):
            return jsonify({
                "success": False,
                "message": "Documents must be an array"
            }), 400

        logger.info(f"Starting deletion process for {len(documents)} documents")
        logger.debug(f"Documents to delete: {documents}")

        deletion_results = {
            "successful": [],
            "failed": []
        }

        try:
            with db_manager.conn:  # 트랜잭션 시작
                for doc_item in documents:
                    try:
                        # 새로운 문서 구조에 맞게 데이터 추출
                        doc_info = doc_item.get('source', {})
                        collection = doc_info.get('collection')
                        source = doc_info.get('source')
                        collection_id = doc_info.get('collection_id')
                        
                        if not collection or not source:
                            deletion_results['failed'].append({
                                'collection': collection,
                                'source': source,
                                'reason': 'Missing collection or source'
                            })
                            continue
                        
                        results = db_manager.delete_source(collection_id, [source])
                        
                        if results.get('successful', False):
                            deletion_results['successful'].append({
                                'collection': collection,
                                'source': source,
                                'collection_id': collection_id
                            })
                        else:
                            deletion_results['failed'].append({
                                'collection': collection,
                                'source': source,
                                'collection_id': collection_id,
                                'reason': results.get('error', 'Unknown error')
                            })
                            
                    except Exception as e:
                        logger.error(f"Error deleting document {source} from {collection}: {str(e)}")
                        deletion_results['failed'].append({
                            'collection': collection,
                            'source': source,
                            'collection_id': collection_id,
                            'reason': str(e)
                        })
                
                db_manager.conn.commit()
                
        except Exception as e:
            db_manager.conn.rollback()
            raise

        # 결과 로깅
        for result in deletion_results['failed']:
            logger.error(f"Failed to delete {result['source']} from {result['collection']}: {result.get('reason')}")
            
        logger.info(f"Deletion complete. Success: {len(deletion_results['successful'])}, "
                   f"Failed: {len(deletion_results['failed'])}")

        # 응답 반환
        return jsonify({
            "success": len(deletion_results['failed']) == 0,
            "message": f"Deletion process completed. {len(deletion_results['successful'])} documents deleted, "
                      f"{len(deletion_results['failed'])} failed.",
            "results": {
                "successful": deletion_results['successful'],
                "failed": deletion_results['failed'],
                "total_processed": len(documents),
                "success_rate": f"{(len(deletion_results['successful'])/len(documents))*100:.1f}%"
            }
        }), 200 if len(deletion_results['failed']) == 0 else 207

    except Exception as e:
        logger.error(f"Error in delete_sources endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False, 
            "message": str(e),
            "error_details": traceback.format_exc()
        }), 500


@app.route('/api/create-collection', methods=['POST'])
def create_collection():    
    try:
        data = request.json
        collection_name = data.get('name')
        creator = data.get('creator')
        
        if not collection_name:
            return jsonify({"success": False, "message": "컬렉션 이름이 제공되지 않았습니다."}), 400
        
        result = db_manager.create_collection(collection_name,creator)
        if result:
            logger.info(f"Successfully created collection: {collection_name}")
            return jsonify({"success": True, "message": result}), 201
        else:
            return jsonify({
                "success": False,
                "message": "Collection name must: (1) contain 3-63 characters, (2) start and end with alphanumeric, " +
                          "(3) contain only alphanumeric, underscores or hyphens, (4) no consecutive periods, " +
                          "(5) not be a valid IPv4 address"
            }), 400
    except Exception as e:
        logger.error(f"Error creating collection: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/list-collections', methods=['GET'])
def list_collections():
    try:
        logger.info("Attempting to list collections")
        collections = db_manager.get_list_collections()
        logger.info(f"Successfully retrieved {len(collections)} collections")
        return jsonify({"success": True, "collections": collections}), 200
    except Exception as e:
        logger.error(f"Error in list_collections: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/user/id', methods=['GET'])
@require_auth
def get_user_id():
    """
    사용자명(username)으로 사용자 ID 조회 API
    
    Query Parameters:
        username (str): 조회할 사용자명
        
    Returns:
        JSON: 성공 시 사용자 ID, 실패 시 에러 메시지
    """
    try:   
        # 쿼리 파라미터로 전달된 username 확인
        requested_username = request.args.get('username')          
        # 데이터베이스에서 사용자 조회
        user = db_manager.get_user_by_username(requested_username)
        
        if user:
            # 딕셔너리나 객체에서 ID 추출
            user_id = user.get('id') if isinstance(user, dict) else user.id
            
            return jsonify({
                "success": True,
                "user_id": user_id,
                "username": requested_username
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error in get_user_id: {str(e)}")
        return jsonify({
            "success": False,
            "message": "An error occurred while processing your request"
        }), 500
    
@app.route('/api/collections', methods=['GET'])
@require_auth
def get_collections_auth():
    """
    컬렉션 목록 조회 API
    """
    try:
        # GET 파라미터에서 creator_id 가져오기
        user_id = request.args.get('user_id')
        
        # 로깅 추가
        logger.info(f"Received creator_id: {user_id}")
        
        # user_id 유효성 검사
        if user_id is None:
            logger.warning("user id is required")
            return jsonify({
                "success": False,
                "message": "user id is required"
            }), 400
            
        try:
            user_id = int(user_id)
        except ValueError:
            logger.warning(f"Invalid creator_id: {user_id}")
            return jsonify({
                "success": False,
                "message": "creator_id must be a number"
            }), 400
            
        if user_id <= 0:
            logger.warning(f"Invalid creator_id: {user_id}")
            return jsonify({
                "success": False,
                "message": "Invalid creator_id"
            }), 400
            
        # 컬렉션 조회
        collections = db_manager.get_collections_by_creator(user_id)
        
        # 추가 로깅
        logger.info(f"Retrieved collections: {collections}")
        
        # 결과 반환
        return jsonify({
            "success": True,
            "collections": collections,
            "count": len(collections)
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_collections_auth: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "message": "An error occurred while processing your request"
        }), 500

@app.route('/api/delete-collection', methods=['POST'])
@require_auth
def delete_collection():
    try:
        data = request.json
        collection_name = data.get('name')
        
        if not collection_name:
            return jsonify({"success": False, "message": "컬렉션 이름이 제공되지 않았습니다."}), 400
        
        result = db_manager.delete_collection(collection_name)
        logger.info(f"Successfully deleted collection: {collection_name}")
        return jsonify({"success": True, "message": result}), 200
    except Exception as e:
        logger.error(f"Error deleting collection: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/search-documents', methods=['GET'])
@require_auth
def search_documents():
    try:
        # 요청 파라미터 검증
        collection_name = request.args.get('collection_name')
        search_query = request.args.get('source_search')
        limit = request.args.get('limit', db_manager.docnum, type=int)
        
        logger.debug(f"Search request - Collection: {collection_name}, Query: {search_query}, Limit: {limit}")
        
        if not collection_name or not search_query:
            return jsonify({
                'success': False, 
                'message': '컬렉션 이름과 검색어가 필요합니다.'
            }), 400

        # 검색 실행
        #results = db_manager.search_collection(        
        results = db_manager.search_keyword_collection(
            collection_names=collection_name,  # 변수명 수정
            query=search_query,
            n_results=limit,
            score_threshold=0.1
        )

        # 결과 가공
        formatted_results = []
        for result in results:
            try:
                formatted_doc = {
                    'content': result.get('page_content', ''),
                    'metadata': result.get('metadata', {}),
                    'score': result.get('score', 0),
                }
                formatted_results.append(formatted_doc)
            except Exception as format_error:
                logger.warning(f"Error formatting result: {str(format_error)}")
                continue

        logger.info(f"Found {len(formatted_results)} documents matching the search criteria")
        
        return jsonify({
            'success': True,
            'count': len(formatted_results),
            'results': formatted_results,
            'query_info': {
                'collection': collection_name,
                'query': search_query,
                'limit': limit
            }
        })

    except Exception as e:
        error_message = f"Error in search_documents: {str(e)}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'message': '검색 중 오류가 발생했습니다.',
            'error': str(e)
        }), 500

@app.route('/api/view-collection', methods=['GET'])
@require_auth
def view_collection():
    try:
        collection_name = request.args.get('collection_name')
        
        if not collection_name:
            return jsonify({"success": False, "message": "컬렉션 이름이 제공되지 않았습니다."}), 400
        
        documents = db_manager.view_collection_content(collection_name)
        return jsonify({"success": True, "documents": documents}), 200
    except Exception as e:
        logger.error(f"Error viewing collection: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/check_file_exists', methods=['POST'])
@require_auth
def check_file_exists():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        collection = data.get('collection')
        filename = data.get('filename')
        
        if not collection or not filename:
            return jsonify({'error': 'Missing collection or filename'}), 400
        
        exists = db_manager.check_source_exists(collection, filename)
        return jsonify({'exists': exists})
    except Exception as e:
        logger.error(f"Error checking file existence: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_and_embed', methods=['POST'])
@require_auth
def upload_and_embed():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        UPLOAD_FOLDER = os.path.abspath(os.path.join(current_dir, 'uploads'))
        logger.debug(f"Upload folder path: {UPLOAD_FOLDER}")
        
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        collection = request.form['collection']
        
        if file:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
                    
            try:
                text = db_manager.extract_text_from_file(filepath, filename)
                chunks_stored = db_manager.split_embed_docs_store(text, filename, collection)
                if chunks_stored >0:
                    return jsonify({'success': True, 'chunks_stored': chunks_stored})
                else: 
                    return jsonify({'success': False, 'error': f'{chunks_stored} 저장이 않됨됨'})
            finally:
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.debug(f"Temporary file {filepath} has been deleted.")
                    except Exception as e:
                        logger.error(f"Error deleting file {filepath}: {str(e)}")
    except Exception as e:
        logger.error(f"Error in upload_and_embed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-all-documents-source', methods=['GET'])
@require_auth
def get_all_documents_source():
    try:
        # 디버깅을 위한 로깅
        logger.info(f"Request arguments: {request.args}")
        
        # 컬렉션 이름 추출
        collection_names = request.args.getlist('collection_name[]')
        
        logger.info(f"Received collection names: {collection_names}")
        
        # 유효성 검사
        if not collection_names:
            logger.warning("No collection names provided")
            return jsonify({
                'success': False,
                'message': 'At least one collection name is required'
            }), 400
        
        # 결과 저장할 딕셔너리
        all_documents = {}
        
        for collection_name in collection_names:
            try:
                # 문서 소스 조회
                sources = db_manager.get_all_documents_source(collection_name)
                
                documents_info = []
                for source in sources:
                    try:
                        # 각 소스의 메타데이터 조회
                        metadata = db_manager.get_document_metadata(collection_name, source)
                        
                        documents_info.append({
                            'source': source,
                            'metadata': metadata or {}
                        })
                    except Exception as meta_error:
                        logger.warning(f"Failed to get metadata for {source} in {collection_name}: {str(meta_error)}")
                
                all_documents[collection_name] = {
                    'documents': documents_info,
                    'count': len(documents_info)
                }
                
            except Exception as coll_error:
                logger.error(f"Error processing collection {collection_name}: {str(coll_error)}")
                all_documents[collection_name] = {
                    'error': str(coll_error),
                    'documents': [],
                    'count': 0
                }
        
        return jsonify({
            'success': True,
            'collections': all_documents,
            'total_count': sum(info.get('count', 0) for info in all_documents.values())
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in get_all_documents_source: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/process_query', methods=['POST'])
@require_auth
def process_query():
    try:
        data = request.json
        logger.debug(f"Received data: {data}")  # 전체 요청 데이터 로깅

        query = data.get('query')
        collection_names = data.get('collections', [])
        llm_name = data.get('llm_name')
        llm_model = data.get('llm_model')
        select_sources = data.get('select_sources', [])
        rag_mode = data.get('ragmode')
        score_threshold= data.get('score_threshold')
        system_message = data.get('system_message')

        # 필수 파라미터 체크 전 값 확인
        # 파라미터 검증 및 로깅 강화
        logger.debug(f"Parsed parameters - query: {query}, collections: {collection_names}, "
                    f"llm_name: {llm_name}, llm_model: {llm_model}")
        
        if not all([query, collection_names, llm_name]):
            missing = []
            if not query: missing.append('query')
            if not collection_names: missing.append('collections')
            if not llm_name: missing.append('llm_name')
            return jsonify({'error': f'Missing required parameters: {", ".join(missing)}'}), 400
            
        # 선택된 system message를 반영
        rag_app.set_system_message(system_message)
        logger.debug(f"System_message: {system_message}")  # 전체 요청 데이터 로깅
        # select_sources 처리 - 컬렉션별 소스 필터링은 perform_search 내부에서 처리
        logger.info(f"Processing query across collections: {collection_names} with sources: {'all' if not select_sources else select_sources}")
        
        # 한 번에 모든 컬렉션에 대해 검색 수행
        rag_app.set_llm_model(llm_model)
        result, docs = rag_app.process_regular_query(
            query=query,
            db_manager=db_manager,
            collection_names=collection_names,  # 전체 collection_names 리스트 전달
            llm_name=llm_name,
            select_sources=select_sources,
            ragmode=rag_mode,
            score_threshold=score_threshold
        )
        
        # 응답 생성
        if result:
            if isinstance(result, dict):
                response = {
                    'result': result.get('content', str(result)),
                    'metadata': {
                        'collections': collection_names,
                        'sources': select_sources if select_sources else 'all documents',
                        'search_mode': 'selected documents' if select_sources else 'all documents',
                        **result.get('metadata', {})
                    }
                }
            else:
                response = {
                    'result': str(result),
                    'metadata': {
                        'collections': collection_names,
                        'sources': select_sources if select_sources else 'all documents',
                        'search_mode': 'selected documents' if select_sources else 'all documents'
                    }
                }
        else:
            response = {
                'result': '결과를 찾을 수 없습니다.',
                'metadata': {
                    'collections': collection_names,
                    'sources': select_sources if select_sources else 'all documents',
                    'search_mode': 'selected documents' if select_sources else 'all documents'
                }
            }
        
        if docs:
            response['docs'] = [document_to_dict(doc) for doc in docs]
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error in process_query: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/summarize-selectdocs', methods=['POST'])
@require_auth
def summarize_selectdocs():
    try:
        # 상세 로깅 추가
        app.logger.info("Received request data: %s", request.json)
        
        data = request.json
        
        # 데이터 검증 강화
        if not data:
            app.logger.error("No data received")
            return jsonify({
                "success": False, 
                "error": "요청 데이터가 없습니다."
            }), 400

        documents = data.get('documents')
        if not documents:
            app.logger.error("No documents provided")
            return jsonify({
                "success": False, 
                "error": "요약할 문서 내용이 비어있습니다."
            }), 400

        # 기본값 및 유효성 검사
        lines = max(1, min(data.get('lines', 5), 20))
        llm_name = data.get('llm_name')
        llm_model = data.get('llm_model')

        app.logger.info(f"Summarization parameters: "
                        f"lines={lines}, "
                        f"llm_name={llm_name}, "
                        f"llm_model={llm_model}")

        try:
            # 요약 생성 로직 
            rag_app.set_llm_model(llm_model)
            result = rag_app.generate_summary( 
                llm_name=llm_name, 
                lines=lines, 
                documents=documents
            )
            
            app.logger.info(f"Summary generation result: {result}")

        except Exception as summary_error:
            app.logger.error(f"Summary generation error: {traceback.format_exc()}")
            return jsonify({
                "success": False, 
                "error": f"요약 생성 중 오류 발생: {str(summary_error)}",
                "metadata": {
                    'collections': '',
                    'sources': 'selected documents',
                    'search_mode': 'selected documents'
                }
            }), 500

        # 결과 처리
        if result:
            response_data = {
                'success': True,
                'result': (result.get('content', str(result)) if isinstance(result, dict) else str(result)).strip(),
                'metadata': {
                    'collections': '',
                    'sources': 'selected documents',
                    'search_mode': 'selected documents',
                    **(result.get('metadata', {}) if isinstance(result, dict) else {})
                }
            }
        else:
            response_data = {
                'success': False,
                'result': '요약 결과를 찾을 수 없습니다.',
                'metadata': {
                    'collections': '',
                    'sources': 'selected documents',
                    'search_mode': 'selected documents'
                }
            }

        return jsonify(response_data), 200

    except Exception as e:
        # 최종 예외 처리
        app.logger.error(f"Unexpected error: {traceback.format_exc()}")
        return jsonify({
            "success": False, 
            "error": f"예기치 않은 오류 발생: {str(e)}"
        }), 500

@app.route('/api/summarize-sources', methods=['POST'])
@require_auth
def summarize_sources():
    try:
        data = request.json
        
        if not all(key in data for key in ['collection_name', 'sources', 'llm_name', 'llm_model']):
            raise ValueError("Missing required parameters")

        def generate():
            try:
                for result in db_manager.summarize_documents_from_source(
                    data['collection_name'],
                    data['sources'],
                    data['llm_name'],
                    data['llm_model']
                ):
                    yield f"data: {json.dumps(result)}\n\n"
            except Exception as e:
                error_msg = f"요약 프로세스 중 예기치 않은 오류 발생: {str(e)}\n{traceback.format_exc()}"
                yield f"data: {json.dumps({'type': 'error', 'value': error_msg})}\n\n"

        return Response(generate(), content_type='text/event-stream')

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        error_msg = f"API 처리 중 예기치 않은 오류 발생: {str(e)}\n{traceback.format_exc()}"
        return jsonify({"success": False, "error": error_msg}), 500

@app.route('/api/summarize-sse', methods=['GET'])
@require_auth
def summarize_sse():
    try:
        collections = json.loads(request.args.get('collections', '[]'))
        documents = json.loads(request.args.get('documents', '[]'))
        llm_name = request.args.get('llm_name')
        llm_model = request.args.get('llm_model')

        if not all([collections, documents, llm_name, llm_model]):
            raise ValueError("Missing required parameters")

        logger.debug(f"Received parameters - collections: {collections}, documents: {documents}, llm: {llm_name}-{llm_model}")

        # documents에서 source 정보 추출
        sources_by_collection = {}
        total_documents = 0
        for doc in documents:
            if isinstance(doc, dict) and 'source' in doc:
                source_info = doc['source']
                collection = source_info.get('collection')
                source = source_info.get('source')
                if collection and source:
                    if collection not in sources_by_collection:
                        sources_by_collection[collection] = []
                    sources_by_collection[collection].append(source)
                    total_documents += 1

        def generate():
            try:
                processed_documents = 0

                for collection, sources in sources_by_collection.items():
                    for source in sources:
                        # 각 문서 처리 시작을 알림
                        yield f"data: {json.dumps({'type': 'progress', 'status': 'processing', 'document': source, 'progress': (processed_documents / total_documents) * 100})}\n\n"

                        # 문서 요약 처리
                        results = db_manager.summarize_documents_from_source(
                            collection,
                            [source],
                            llm_name,
                            llm_model
                        )
                        
                        for result in results:
                            if isinstance(result, dict):
                                result['progress'] = ((processed_documents + 1) / total_documents) * 100
                            yield f"data: {json.dumps(result)}\n\n"
                        
                        processed_documents += 1

                # 완료 메시지
                yield f"data: {json.dumps({'type': 'complete', 'progress': 100})}\n\n"

            except Exception as e:
                error_msg = f"요약 프로세스 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                yield f"data: {json.dumps({'type': 'error', 'value': error_msg})}\n\n"

        return Response(generate(), content_type='text/event-stream')
    
    except Exception as e:
        error_msg = f"API 처리 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        return jsonify({"type": "error", "value": error_msg}), 500
    
# 요약을 원하는 문서의 페이지정보를 제공하는 API
@app.route('/api/get-document-pages', methods=['GET', 'POST'])
@require_auth
def get_document_pages():
    try:
        # GET 또는 POST 메서드에 따라 파라미터 추출
        if request.method == 'POST':
            data = request.json
            collection_id = data.get('collection_id')
            source = data.get('source')
        else:  # GET
            collection_id = request.args.get('collection_id')
            source = request.args.get('source')
            # GET 파라미터가 문자열로 오므로 collection_id를 정수로 변환
            if collection_id:
                collection_id = int(collection_id)

        # URL 디코딩 처리
        if source:
            source = urllib.parse.unquote(source)

        logger.debug(f"Request method: {request.method}")
        logger.debug(f"Received parameters FROM get_document_pages- collection_id: {collection_id}, source: {source}")

        if not all([collection_id, source]):
            raise ValueError("Missing required parameters: collection_id and source are required")

        try:
            # 문서의 페이지 정보 추출
            pages = db_manager.get_document_pages(collection_id, source)
            
            return jsonify({
                'success': True,
                'documents': {
                    'collection_id': collection_id,
                    'source': source,
                    'pages': pages
                }
            })

        except Exception as e:
            logger.error(f"Error processing document collection_id: {collection_id}, source: {source}: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    except Exception as e:
        error_msg = f"API 처리 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        return jsonify({"success": False, "error": error_msg}), 500

# 요약을 원하는 문서의 페이지만 요약하는 API
@app.route('/api/page-content', methods=['POST'])
@require_auth
def page_content():
    try:
        data = request.get_json()
        collection = data.get('collection_id')
        source = data.get('source')
        page_num = data.get('page_num')
        llm_name = data.get('llm_name')
        llm_model = data.get('llm_model')

        if not all([collection, source, page_num, llm_name, llm_model]):
            raise ValueError("Missing required parameters")

        logger.debug(f"Summarizing page {page_num} of document {collection}/{source}")        
        # 페이지 컨텐츠 가져오기
        response = db_manager.get_document_page_content(collection, source, page_num)
        return jsonify({
            "success": True, 
            "pages": response
        }), 200
    except Exception as e:
        error_msg = f"API 처리 중 오류 발생: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return jsonify({
            "success": False, 
            "error": error_msg
        }), 500



# 요약을 원하는 문서의 페이지만 요약하는 API
@app.route('/api/summarize-page-content', methods=['POST'])
@require_auth
def summarize_page_content():
    try:
        data = request.get_json()
        collection = data.get('collection_id')
        source = data.get('source')
        page_num = data.get('page_num')
        llm_name = data.get('llm_name')
        llm_model = data.get('llm_model')

        if not all([collection, source, page_num, llm_name, llm_model]):
            raise ValueError("Missing required parameters")

        logger.debug(f"Summarizing page {page_num} of document {collection}/{source}")

        # sources를 리스트로 변환
        sources = [source] if isinstance(source, str) else source

        # 페이지 컨텐츠 가져오기
        generator = db_manager.summarize_documents_from_page(
            collection, 
            sources, 
            llm_name, 
            llm_model, 
            page=page_num  # page_num을 page로 변경
        )

        for result in generator:
            if 'type' in result and result['type'] == 'progress':
                # 진행 상황 처리는 건너뛰기
                continue
            elif 'type' in result and result['type'] == 'error':
                # 에러 처리
                return jsonify({
                    'success': False,
                    'error': result['value']
                })
            elif 'pages' in result:
                # 최종 요약 결과 반환
                return jsonify({
                    'success': True,
                    'pages': result['pages'],
                    'metadata': result.get('metadata', {})
                })

    except Exception as e:
        error_msg = f"API 처리 중 오류 발생: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return jsonify({
            "success": False, 
            "error": error_msg
        }), 500


@app.route('/api/compare-documents', methods=['POST'])
@require_auth
def compare_documents():
    try:
        data = request.json
        originalDoc = data.get('originalDoc')
        comparisonDoc = data.get('comparisonDoc')
        llm_name = data.get('llm_name', 'Groq')  # Default to Groq if not specified
        llm_model = request.args.get('llm_model')
        
        logger.debug(f"Comparing documents using {llm_name}")
        
        if not all([originalDoc, comparisonDoc]):
            return jsonify({'error': 'Original and comparison documents are required'}), 400
        
        rag_app.set_llm_model(llm_model)      
        result = rag_app.generate_similarity(
            originalDoc=originalDoc,
            comparisonDoc=comparisonDoc,
            llm_name=llm_name
        )
        
        logger.debug(f"Comparison result generated: {result}")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error in compare_documents: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/change-database', methods=['POST'])
@require_auth
def change_database():
    try:
        data = request.json
        new_db_type = data.get('db_type')
        db_config = data.get('db_config')

        if not new_db_type:
            return jsonify({'error': 'Database type is required'}), 400

        # Update environment variable
        os.environ['DB_TYPE'] = new_db_type.lower()
        
        if new_db_type.lower() == 'postgres' and db_config:
            for key, value in db_config.items():
                os.environ[f'POSTGRES_{key.upper()}'] = str(value)

        # Reinitialize RAG application with new database
        global rag_app, db_manager
        rag_app = RAGChatApp(db_type=new_db_type.lower())
        
        if new_db_type.lower() == 'postgres':
            db_manager = PostgresDbManager(**db_config)
        else:
            db_manager = ChromaDbManager()

        logger.info(f"Successfully changed database to {new_db_type}")
        return jsonify({
            'success': True,
            'message': f'Database changed to {new_db_type}'
        }), 200

    except Exception as e:
        logger.error(f"Error changing database: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-current-db-config', methods=['GET'])
@require_auth
def get_current_db_config():
    try:
        current_config = {
            'db_type': os.getenv('DB_TYPE', 'chroma')
        }
        
        if current_config['db_type'] == 'postgres':
            current_config['db_config'] = {
                'host': os.getenv('POSTGRES_HOST'),
                'port': os.getenv('POSTGRES_PORT'),
                'database': os.getenv('POSTGRES_DB'),
                'user': os.getenv('POSTGRES_USER'),
                # Password is not included in response for security reasons
            }
        
        return jsonify(current_config), 200
    
    except Exception as e:
        logger.error(f"Error getting database configuration: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
@require_auth
def health_check():
    """상태 확인 엔드포인트"""
    try:
        status = {
            "status": "healthy",
            "database": {
                "type": db_type,
                "connected": True
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 데이터베이스 연결 확인
        try:
            if hasattr(db_manager, '_check_connection'):
                status["database"]["connected"] = db_manager._check_connection()
        except Exception as e:
            status["database"]["connected"] = False
            status["database"]["error"] = str(e)
        
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 Error: {error}")
    return jsonify({
        "error": "Resource not found",
        "message": str(error)
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 Error: {error}")
    logger.error(traceback.format_exc())
    return jsonify({
        "error": "Internal server error",
        "message": str(error)
    }), 500

# Add this after_request handler to ensure proper CORS headers
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, PUT, POST, DELETE, OPTIONS'
    return response

@app.route('/api/get_system_message_list', methods=['POST'])
@require_auth
def get_system_message_list():
    """특정 시스템 메시지 조회 API"""    
    user_id = int(request.json.get('user_id'))
    name = request.json.get('name')
        
    
    message = db_manager.list_system_messages(user_id)
    
    if message:
        return jsonify(message), 200
    else:
        return jsonify({'message': f"메시지 '{name}'를 찾을 수 없습니다."}), 404

@app.route('/api/get_system_message', methods=['POST'])
@require_auth
def get_message():
    """특정 시스템 메시지 조회 API"""    
    user_id = int(request.json.get('user_id'))
    name = request.json.get('name')
        
    
    message = db_manager.get_system_message(name, user_id)
    
    if message:
        return jsonify(message), 200
    else:
        return jsonify({'message': f"메시지 '{name}'를 찾을 수 없습니다."}), 404

@app.route('/api/save_system_message', methods=['POST'])
@require_auth
def create_message():
    """시스템 메시지 생성 API"""
    data = request.get_json()
    
    # 필수 필드 검증
    if not all(k in data for k in ('name', 'message')):
        return jsonify({'message': '메시지 이름과 내용은 필수입니다!'}), 400    
    
    
    result = db_manager.save_system_message(
        name=data['name'],
        message=data['message'],
        description=data.get('description', ''),
        user_id=data.get('user_id')
    )
    if result:
        return jsonify({'message': '메시지가 성공적으로 저장되었습니다.'}), 201
    else:
        return jsonify({'message': '메시지 저장에 실패했습니다.'}), 400

@app.route('/api/update_system_message', methods=['POST'])
@require_auth
def update_message():
    """시스템 메시지 수정 API"""
    data = request.get_json()
    
    # 필수 필드 검증
    if 'message' not in data:
        return jsonify({'message': '메시지 내용은 필수입니다!'}), 400    
        
    result = db_manager.edit_system_message(
        name=data['name'],
        new_message=data['message'],
        new_description=data.get('description'),
        user_id= data.get('user_id')
    )
    
    if result:
        return jsonify({'message': '메시지가 성공적으로 수정되었습니다.'}), 200
    else:
        return jsonify({'message': '메시지 수정에 실패했습니다.'}), 400

@app.route('/api/delete_system_message', methods=['POST'])
@require_auth
def delete_message():
    """시스템 메시지 삭제 API"""
    user_id = int(request.json.get('user_id'))
    name = request.json.get('name')
    
    result = db_manager.delete_system_message(name, user_id)
    
    if result:
        return jsonify({'message': '메시지가 성공적으로 삭제되었습니다.'}), 200
    else:
        return jsonify({'message': '메시지 삭제에 실패했습니다.'}), 400

@app.route('/api/get_current_selected_message', methods=['POST'])
@require_auth
def get_current_message():
    """현재 선택된 메시지 조회 API"""
    try:
        user_id = int(request.json.get('user_id'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid user_id"}), 400
    
    selected_message = db_manager.get_selected_system_message(user_id)
    
    if selected_message:
        return jsonify(selected_message), 200
    else:
        return jsonify({"data": None}), 404  # Consider 404 for no content

@app.route('/api/save_selected_message', methods=['POST'])
@require_auth
def set_selected_message():
    """선택된 메시지 설정 API"""
    user_id = int(request.json.get('user_id'))
    name = request.json.get('name')    
    
    # 필수 필드 검증
    if not name:
        return jsonify({'message': '메시지 이름은 필수입니다!'}), 400
    
    
    result = db_manager.save_selected_message(name, user_id)
    
    if result:
        return jsonify({'message': '선택된 메시지가 성공적으로 설정되었습니다.'}), 200
    else:
        return jsonify({'message': '선택된 메시지 설정에 실패했습니다.'}), 400


if __name__ == '__main__':
    try:
        logger.info("Starting Flask application...")
        logger.info(f"Using database type: {os.getenv('DB_TYPE')}")
        app.run(host='127.0.0.1', port=5001, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        logger.error(traceback.format_exc())
                        
