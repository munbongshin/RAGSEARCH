import os
import json
import datetime
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional


# system_message_manager.py
import json
import datetime
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional

class SystemMessageManager:
    """System message storage and management class"""
    
    def __init__(self, storage_dir: str = "system_messages"):
        """
        Initialize the SystemMessageManager with directory creation and setup
        
        Args:
            storage_dir (str): Directory to store system message files
        """
        self.base_dir = Path(__file__).parent
        self.storage_dir = self.base_dir / storage_dir        
        self.initialize_storage()
        # 선택된 메시지 파일이 없으면 기본값으로 생성        
        self.store_dir = self.base_dir / 'src' / 'store'
        self.selected_message_file = self.store_dir / 'selected_message.json'
                
        
        if not self.selected_message_file.exists():
            self._init_selected_message()
    
    def _init_selected_message(self):
        """선택된 메시지 파일을 기본값으로 초기화"""
        try:
            with open(self.selected_message_file, 'w', encoding='utf-8') as f:
                json.dump({'selectedMessage': 'default'}, f)
        except Exception as e:
            logging.error(f"Error initializing selected message: {str(e)}")
    
        
    def initialize_storage(self) -> bool:
        """Initialize the storage directory with necessary setup"""
        try:
            if not self.storage_dir.exists():
                self.storage_dir.mkdir(parents=True)
                logging.info(f"Created storage directory: {self.storage_dir}")
                
                default_message = {
                    "name": "default",
                    "message": """You are an intelligent assistant.
                    You always provide well-reasoned answers that are both correct and helpful.
                    If you don't know the answer, just say that you don't know.
                    Please answer in Korean.""",
                    "description": "기본 시스템 메시지",
                    "created_at": str(datetime.datetime.now())
                }
                
                self.save_system_message(
                    name=default_message["name"],
                    message=default_message["message"],
                    description=default_message["description"]
                )
                logging.info("Created default system message")
                
            self.storage_dir.chmod(0o755)
            return True
            
        except Exception as e:
            logging.error(f"Error initializing storage: {str(e)}")
            return False
            
    def list_system_messages(self) -> List[Dict]:
        """List all available system messages"""
        messages = []
        try:
            # selected_message.json을 제외한 모든 .json 파일을 읽음
            for file_path in self.storage_dir.glob("*.json"):
                # selected_message.json 파일 제외
                if file_path.name == 'selected_message.json':
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 필수 필드가 있는 유효한 메시지 파일인지 확인
                        if all(key in data for key in ["name", "message"]):
                            messages.append({
                                "name": data.get("name"),
                                "description": data.get("description", ""),
                                "message": data.get("message"),
                                "created_at": data.get("created_at", ""),
                                "updated_at": data.get("updated_at", "")
                            })
                        else:
                            logging.warning(f"Skipping invalid message file {file_path}: Missing required fields")
                except json.JSONDecodeError:
                    logging.error(f"Invalid JSON format in file {file_path}")
                    continue
                except Exception as e:
                    logging.error(f"Error reading message file {file_path}: {str(e)}")
                    continue
                    
            logging.info(f"Found {len(messages)} valid system messages")
            return messages
            
        except Exception as e:
            logging.error(f"Error listing system messages: {str(e)}")
            return []
        
    def save_system_message(self, name: str, message: str, description: str = "") -> bool:
        """Save a system message to a file"""
        try:
            file_path = self.storage_dir / f"{name}.json"
            data = {
                "name": name,
                "message": message,
                "description": description,
                "created_at": str(datetime.datetime.now())
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logging.info(f"Saved system message: {name}")
            return True
            
        except Exception as e:
            logging.error(f"Error saving system message: {str(e)}")
            return False
            
    def load_system_message(self, name: str) -> Optional[Dict]:
        """Load a system message by name"""
        try:
            file_path = self.storage_dir / f"{name}.json"
            if not file_path.exists():
                return None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logging.error(f"Error loading system message: {str(e)}")
            return None
    
    def get_current_selected_message_name(self) -> str:
        """Get the name of currently selected message from selected_message.json"""
        try:
            if not self.selected_message_file.exists():
                return "default"
                
            with open(self.selected_message_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('selectedMessage', 'default')
                
        except Exception as e:
            logging.error(f"Error getting selected message name: {str(e)}")
            return "default"

    def get_selected_system_message(self, name: str) -> str:
        """Get message content from a system message by name"""
        try:
            file_path = self.store_dir / f"{name}.json"
            if not file_path.exists():
                return ""
                
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('message', '')
                
        except Exception as e:
            logging.error(f"Error getting system message content: {str(e)}")
            return ""
            
    def edit_system_message(self, name: str, new_message: str, new_description: str = None) -> bool:
        """Edit an existing system message"""
        try:
            file_path = self.storage_dir / f"{name}.json"
            if not file_path.exists():
                return False
                
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            data['message'] = new_message
            if new_description is not None:
                data['description'] = new_description
            data['updated_at'] = str(datetime.datetime.now())
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logging.info(f"Edited system message: {name}")
            return True
            
        except Exception as e:
            logging.error(f"Error editing system message: {str(e)}")
            return False
            
    def delete_system_message(self, name: str) -> bool:
        """Delete a system message"""
        try:
            file_path = self.storage_dir / f"{name}.json"
            if file_path.exists():
                file_path.unlink()
                logging.info(f"Deleted system message: {name}")
                return True
            return False
            
        except Exception as e:
            logging.error(f"Error deleting system message: {str(e)}")
            return False
            
    def reset_storage(self) -> bool:
        """Reset the storage directory"""
        try:
            if self.storage_dir.exists():
                shutil.rmtree(self.storage_dir)
            return self.initialize_storage()
            
        except Exception as e:
            logging.error(f"Error resetting storage: {str(e)}")
            return False
    
    def get_selected_message(self):
        """Get the currently selected message"""
        try:
            if os.path.exists(self.selected_message_file):
                with open(self.selected_message_file, 'r') as f:
                    data = json.load(f)
                    return data.get('selectedMessage')
            return "default"
        except Exception as e:
            logging.error(f"Error reading selected message: {str(e)}")
            return "default"

    def save_selected_message(self, selected_message):
        """Save the selected message"""
        try:
            with open(self.selected_message_file, 'w') as f:
                json.dump({'selectedMessage': selected_message}, f)
            return True
        except Exception as e:
            logging.error(f"Error saving selected message: {str(e)}")
            return False


class SystemMessageTester:
    """Test interface for SystemMessageManager"""
    
    def __init__(self):
        self.system_message_manager = SystemMessageManager()
        
    def display_menu(self):
        """Display the main menu options"""
        print("\n=== 시스템 메시지 관리 시스템 ===")
        print("1. 시스템 메시지 저장")
        print("2. 시스템 메시지 목록 보기")
        print("3. 시스템 메시지 내용 보기")
        print("4. 시스템 메시지 수정")
        print("5. 시스템 메시지 삭제")
        print("6. 저장소 초기화")
        print("7. 종료")
        print("===========================")
        
    def get_user_input(self, prompt: str, allow_empty: bool = False) -> Optional[str]:
        """Get user input with validation"""
        while True:
            value = input(prompt).strip()
            if value or allow_empty:
                return value
            print("값을 입력해주세요.")
    
    def get_multiline_input(self, prompt: str) -> str:
        """Get multiline input from user"""
        print(prompt)
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        return "\n".join(lines)
            
    def save_message(self):
        """Save a new system message"""
        print("\n--- 시스템 메시지 저장 ---")
        name = self.get_user_input("메시지 이름: ")
        description = self.get_user_input("메시지 설명: ")
        message = self.get_multiline_input("메시지 내용을 입력하세요 (입력 완료 후 빈 줄에서 Enter):")
        
        if self.system_message_manager.save_system_message(name, message, description):
            print("메시지가 성공적으로 저장되었습니다.")
        else:
            print("메시지 저장 중 오류가 발생했습니다.")
            
    

    def list_messages(self):
        """Display all saved messages with full information"""
        print("\n--- 시스템 메시지 목록 ---")
        messages = self.system_message_manager.list_system_messages()
        if not messages:
            print("저장된 메시지가 없습니다.")
            return
            
        for msg in messages:
            print("\n" + "=" * 50)
            print(f"이름: {msg['name']}")
            print(f"설명: {msg['description']}")            
            print("\n--- 메시지 내용 ---")
            print(msg['message'])
            print("=" * 50)
            
    def view_message(self):
        """View content of a specific message"""
        print("\n--- 시스템 메시지 내용 보기 ---")
        name = self.get_user_input("조회할 메시지 이름: ")
        message = self.system_message_manager.load_system_message(name)
        
        if message:
            print("\n=== 메시지 내용 ===")
            print(message)
            print("=" * 30)
        else:
            print(f"메시지 '{name}'를 찾을 수 없습니다.")
    
    def edit_message(self):
        """Edit an existing system message"""
        print("\n--- 시스템 메시지 수정 ---")
        name = self.get_user_input("수정할 메시지 이름: ")
        
        # 먼저 메시지가 존재하는지 확인
        current_message = self.system_message_manager.load_system_message(name)
        if not current_message:
            print(f"메시지 '{name}'를 찾을 수 없습니다.")
            return
            
        # 현재 내용 표시
        print("\n=== 현재 메시지 내용 ===")
        print(current_message)
        print("=" * 30)
        
        # 새로운 내용 입력 받기
        change_description = self.get_user_input("설명도 수정하시겠습니까? (y/n): ").lower() == 'y'
        new_description = None
        if change_description:
            new_description = self.get_user_input("새로운 설명: ")
            
        new_message = self.get_multiline_input("새로운 메시지 내용을 입력하세요 (입력 완료 후 빈 줄에서 Enter):")
        
        if self.system_message_manager.edit_system_message(name, new_message, new_description):
            print("메시지가 성공적으로 수정되었습니다.")
        else:
            print("메시지 수정 중 오류가 발생했습니다.")
            
    def delete_message(self):
        """Delete a saved message"""
        print("\n--- 시스템 메시지 삭제 ---")
        name = self.get_user_input("삭제할 메시지 이름: ")
        if self.system_message_manager.delete_system_message(name):
            print("메시지가 성공적으로 삭제되었습니다.")
        else:
            print(f"메시지 '{name}'를 찾을 수 없거나 삭제 중 오류가 발생했습니다.")
            
    def reset_storage(self):
        """Reset the storage directory"""
        print("\n--- 저장소 초기화 ---")
        confirm = self.get_user_input("모든 메시지가 삭제됩니다. 계속하시겠습니까? (y/n): ").lower()
        
        if confirm == 'y':
            if self.system_message_manager.reset_storage():
                print("저장소가 성공적으로 초기화되었습니다.")
                print("기본 시스템 메시지가 생성되었습니다.")
            else:
                print("저장소 초기화 중 오류가 발생했습니다.")
        else:
            print("초기화가 취소되었습니다.")
            
    def run(self):
        """Main program loop"""
        while True:
            self.display_menu()
            choice = self.get_user_input("선택할 메뉴 번호를 입력하세요: ")
            
            try:
                if choice == "1":
                    self.save_message()
                elif choice == "2":
                    self.list_messages()
                elif choice == "3":
                    self.view_message()
                elif choice == "4":
                    self.edit_message()
                elif choice == "5":
                    self.delete_message()
                elif choice == "6":
                    self.reset_storage()
                elif choice == "7":
                    print("\n프로그램을 종료합니다.")
                    break
                else:
                    print("\n잘못된 메뉴 번호입니다. 다시 선택해주세요.")
            except Exception as e:
                print(f"\n오류가 발생했습니다: {str(e)}")


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('system_message_manager.log'),
            logging.StreamHandler()
        ]
    )
    
    tester = SystemMessageTester()
    tester.run()