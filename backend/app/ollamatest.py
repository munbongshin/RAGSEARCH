#!/usr/bin/env python3
import requests
import json
import argparse
import sys
import time

class OllamaConnectionTester:
    def __init__(self, url="http://210.91.154.131:20443/nia-ollama"):
        self.base_url = url  # 전체 URL을 그대로 사용
        self.api_url = f"{self.base_url}/api"
        self.timeout = 100  # 기본 타임아웃 10초

    def check_server_status(self):
        """
        OLLAMA 서버가 실행 중인지 확인합니다.
        """
        try:
            response = requests.get(f"{self.base_url}", timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"서버 연결 확인 중 오류 발생: {e}")
            return False

    def list_models(self):
        """
        설치된 모델 목록을 가져옵니다.
        """
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=self.timeout)
            if response.status_code == 200:
                return response.json().get('models', [])
            else:
                print(f"모델 목록 요청 실패. 상태 코드: {response.status_code}")
                print(f"응답: {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"모델 목록 요청 중 오류 발생: {e}")
            return []

    def test_generate(self, model="llama3", prompt="안녕하세요. 간단한 테스트입니다."):
        """
        지정된 모델에 프롬프트를 전송하고 응답을 생성합니다.
        """
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            
            print(f"\n요청 중... 모델: {model}, 프롬프트: '{prompt}'")
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/generate",
                json=payload,
                timeout=30  # 생성에는 더 긴 타임아웃 설정
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result.get("response", ""),
                    "elapsed_time": elapsed_time
                }
            else:
                print(f"생성 요청 실패. 상태 코드: {response.status_code}")
                print(f"응답: {response.text}")
                return {
                    "success": False,
                    "error": f"상태 코드: {response.status_code}, 응답: {response.text}",
                    "elapsed_time": elapsed_time
                }
        except requests.exceptions.RequestException as e:
            print(f"생성 요청 중 오류 발생: {e}")
            return {
                "success": False,
                "error": str(e),
                "elapsed_time": 0
            }

    def run_comprehensive_test(self, model=None):
        """
        종합적인 연결 테스트를 실행합니다.
        """
        print("\n======= OLLAMA 연결 테스트 시작 =======")
        print(f"OLLAMA 서버 URL: {self.base_url}")
        
        # 1. 서버 상태 확인
        print("\n1. 서버 상태 확인 중...")
        server_running = self.check_server_status()
        if server_running:
            print("✅ OLLAMA 서버가 실행 중입니다.")
        else:
            print("❌ OLLAMA 서버에 연결할 수 없습니다.")
            print(f"   - URL {self.base_url}이 올바른지 확인하세요.")
            print("   - OLLAMA가 설치되어 실행 중인지 확인하세요.")
            return False
        
        # 2. 모델 목록 확인
        print("\n2. 설치된 모델 목록 확인 중...")
        models = self.list_models()
        if models:
            print(f"✅ {len(models)}개의 모델이 설치되어 있습니다:")
            for idx, model_info in enumerate(models, 1):
                name = model_info.get('name', 'Unknown')
                modified = model_info.get('modified', 'Unknown date')
                size = model_info.get('size', 0) / (1024 * 1024 * 1024)  # Convert to GB
                print(f"   {idx}. {name} (수정일: {modified}, 크기: {size:.2f} GB)")
            
            # 테스트할 모델 선택
            if model is None and models:
                model = models[0]['name']  # 첫 번째 모델 선택
                print(f"\n테스트에 '{model}' 모델을 사용합니다.")
        else:
            print("❌ 설치된 모델이 없거나 모델 목록을 가져오는데 실패했습니다.")
            print("   - 'ollama pull llama3' 등의 명령어로 모델을 설치해보세요.")
            return False
        
        # 3. 생성 테스트
        if model:
            print("\n3. 모델 응답 생성 테스트 중...")
            test_prompt = "안녕하세요. 오늘 날씨가 어떤가요?"
            result = self.test_generate(model, test_prompt)
            
            if result["success"]:
                print(f"✅ 응답 생성 성공! (소요 시간: {result['elapsed_time']:.2f}초)")
                print("\n----- 응답 내용 -----")
                print(result["response"])
                print("---------------------")
            else:
                print(f"❌ 응답 생성 실패: {result.get('error', '알 수 없는 오류')}")
                return False
        
        print("\n======= 테스트 완료 =======")
        print("✅ OLLAMA가 정상적으로 연결되어 있으며 사용 가능합니다!")
        return True


def main():
    parser = argparse.ArgumentParser(description='OLLAMA 연결 테스트 프로그램')
    parser.add_argument('--url', default='http://210.91.154.131:20443/nia-ollama', 
                       help='OLLAMA 서버 URL (기본값: http://210.91.154.131:20443/nia-ollama)')
    parser.add_argument('--model', help='테스트할 특정 모델 (기본값: 설치된 첫 번째 모델)')
    
    args = parser.parse_args()
    
    tester = OllamaConnectionTester(url=args.url)
    success = tester.run_comprehensive_test(model=args.model)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()