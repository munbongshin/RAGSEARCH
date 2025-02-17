from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import threading
import logging
import json
import requests
import os, time
import psutil
try:
    import torch
except ImportError:
    pass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ollama import Client

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ollamaOptimizer:
    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self.thread_local = threading.local()  
        self.host_name = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        self.client = Client(host=self.host_name)
        # GPU 사용 가능 여부 확인
        self.gpu_available = False
        try:
            import torch
            self.gpu_available = torch.cuda.is_available()
        except ImportError:
            pass
         # 기본 옵션 설정
        self.default_options = {
            "num_thread": min(psutil.cpu_count(logical=False) or 4, 4),
            "num_ctx": 2048,
            "temperature": 0,
            "top_p": 0.7,
            "num_gpu": 1 if self.gpu_available else 0
        }
        
        
    def direct_process_chunk(self, chunk: str, model_name: str, system_prompt: str):
        try:
            # response 변수를 try 블록 시작 부분에서 초기화
            response = None
            
            response = self.client.generate(
                model=model_name,
                prompt=f"{system_prompt}\n\n{chunk}",
                options={
                    "num_thread": min(psutil.cpu_count(logical=False) or 4, 4),
                    "num_ctx": 2048,
                    "temperature": 0
                }
            )
            
            # 응답 처리
            if isinstance(response, dict):
                return response.get('response', '')
            elif hasattr(response, '__iter__'):
                responses = []
                for resp in response:
                    if isinstance(resp, dict) and 'response' in resp:
                        responses.append(resp['response'])
                    elif isinstance(resp, str):
                        responses.append(resp)
                return ' '.join(responses)
            elif isinstance(response, str):
                return response
                
            logger.warning(f"Unexpected response type: {type(response)}")
            return ""
            
        except Exception as e:
            logger.error(f"Direct processing error: {str(e)}")
            if response is not None:
                logger.error(f"Response type: {type(response)}")
            return ""

    def combine_results(self, results: List[str]) -> str:
        # 빈 결과 필터링
        valid_results = [r for r in results if r and isinstance(r, str)]
        if not valid_results:
            return ""
            
        # 결과 통합
        return ' '.join(valid_results)
    
    
    def direct_ollama_generate(self, model_name: str, prompt: str, system_message: str = None, **kwargs) -> dict:
        """
        Ollama를 사용하여 단일 요청으로 응답을 생성합니다.
        
        Args:
            model_name (str): 사용할 모델 이름
            prompt (str): 입력 프롬프트
            system_message (str, optional): 커스텀 시스템 메시지
            **kwargs: 추가 인자
            
        Returns:
            dict: 생성된 응답과 메타데이터를 포함하는 딕셔너리
                {
                    "content": str,
                    "metadata": {
                        "model": str,
                        "usage": dict
                    }
                }
        """
        start_time = time.time()
        
        try:
            # 시스템 프롬프트 설정
            system_prompt = system_message if system_message else """You are an intelligent assistant. 
                You always provide well-reasoned, structured, and comprehensive answers that are both correct and helpful.
                Use the following pieces of context to answer the user's question.
                Please provide your answer in Korean, ensuring it is natural and fluent."""

            # 단일 요청으로 처리
            response = self.client.generate(
                model=model_name,
                prompt=f"{system_prompt}\n\n{prompt}",
                options={
                    "num_thread": min(psutil.cpu_count(logical=False) or 4, 4),
                    "num_ctx": 2048,
                    "temperature": 0,
                    "top_p": 0.7,
                    "num_gpu": 1 if self.gpu_available else 0
                }
            )

            # Ollama의 응답 구조에 맞게 처리
            generated_text = response.response if hasattr(response, 'response') else response.get('response', '')
            
            # 결과 포맷팅
            return {
                "content": generated_text,
                "metadata": {
                    "model": model_name,
                    "usage": {
                        "prompt_tokens": response.prompt_eval_count if hasattr(response, 'prompt_eval_count') else 0,
                        "completion_tokens": response.eval_count if hasattr(response, 'eval_count') else 0,
                        "total_duration": time.time() - start_time
                    }
                }
            }

        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            logger.error(error_msg)
            return {"content": f"Error: {str(e)}", "metadata": {"error": str(e)}}
        finally:
            self.cleanup(model_name)

    def process_chunk(self, chunk: str, model_name: str, system_prompt: str) -> str:
        session = self.get_session()
        base_url = os.getenv('OLLAMA_HOST')
        url = f"{base_url}/api/generate"

        # GPU 사용 가능 여부 확인
        gpu_available = False
        try:
            import torch
            gpu_available = torch.cuda.is_available()
        except ImportError:
            pass

        payload = {
            "model": model_name,
            "prompt": f"{system_prompt}\n\n{chunk}",
            "stream": False,
            "options": {
                "num_thread": min(psutil.cpu_count(logical=False) or 4, 4),
                "num_ctx": 2048,
                "temperature": 0,
                "top_p": 0.7,
                "num_gpu": 1 if gpu_available else 0
            }
        }

        try:
            response = session.post(
                url,
                json=payload,
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                    'Accept': 'application/json'
                },
                timeout=(10, 300)
            )
            response.raise_for_status()
            return response.json().get('response', '')
        except Exception as e:
            logger.error(f"Chunk processing error: {str(e)}")
            return ""
        
    def generate_questions(self, model_name: str, topic: str, question_type: str = "일반") -> Dict:
        """
        주어진 주제에 대한 질문들을 생성합니다.
        
        Args:
            model_name (str): 사용할 모델의 이름
            topic (str): 질문을 생성할 주제
            question_type (str): 질문의 유형 (예: 일반, 기술, 비즈니스 등)
                
        Returns:
            Dict: 생성된 질문들과 메타데이터를 포함하는 딕셔너리
        """
        if not topic or not model_name:
            raise ValueError("topic과 model_name은 필수 입력값입니다.")
            
        system_prompt = f"""
            주제 "{topic}"에 대한 {question_type} 관련 질문 5개를 생성해주세요.
            질문은 구체적이고 명확해야 하며, 실용적인 답변이 가능해야 합니다.
            
            질문 생성 시 다음 기준을 따르세요:
            1. 질문은 주제와 직접적으로 연관되어야 합니다
            2. 질문은 단순한 예/아니오로 답할 수 없어야 합니다
            3. 질문은 한글로 만든다.                  
            4. 생성된 질문만 쉼표로 구분된 리스트 형태로 반환해주세요.
            """
        
        try:
            session = self.get_session()
            
            payload = {
                "model": model_name,
                "prompt": system_prompt,
                "stream": False,
                "options": {
                    "num_thread": min(psutil.cpu_count(logical=False) or 4, 4),
                    "num_ctx": 2048,
                    "temperature": 0,
                    "top_p": 0.7,
                    "num_gpu": 1 if hasattr(self, 'gpu_available') and self.gpu_available else 0
                }
            }
            
            response = session.post(
                f"{self.host_name}/api/generate",
                json=payload,
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                    'Accept': 'application/json'
                },
                timeout=(10, 300)
            )
            response.raise_for_status()
            
            response_json = response.json()
            content = response_json.get('response', '')
            
            if not content:
                logger.warning(f"Empty response received for topic: {topic}")
                return {
                    "content": "",
                    "metadata": {
                        "error": "Empty response from model",
                        "model": model_name
                    }
                }
            
            # 응답 처리 및 반환
            return {
                "content": content,
                "metadata": {
                    "model": model_name,
                    "usage": {
                        "prompt_tokens": len(system_prompt.split()),
                        "completion_tokens": len(content.split()),
                        "total_tokens": len(system_prompt.split()) + len(content.split())
                    }
                }
            }
            
        except requests.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            logger.error(error_msg)
            return {
                "content": f"Error: {error_msg}",
                "metadata": {
                    "error": str(e),
                    "model": model_name
                }
            }
        except Exception as e:
            error_msg = f"Unexpected error in generate_questions: {str(e)}"
            logger.error(error_msg)
            return {
                "content": f"Error: {error_msg}",
                "metadata": {
                    "error": str(e),
                    "model": model_name
                }
            }     
    

    def ollama_generate(self, model_name: str, llm_model: str, prompt: str, system_message: str = None, **kwargs) -> str:
        try:
            # 시스템 메시지 처리 개선
            system_prompt = system_message if system_message else """You are an intelligent assistant...."""
            
            # GPU 설정과 옵션 통합
            options = {
                "num_thread": min(psutil.cpu_count(logical=False) or 4, 4),
                "num_ctx": 2048,
                "temperature": 0,
                "top_p": 0.7,
                "num_gpu": 1 if self.gpu_available else 0
            }
            options.update(kwargs.get('options', {}))
            logger.debug(f"response -----:{model_name}")
                # 응답 처리
            try:
                # 직접 Ollama 클라이언트 사용
                response = self.client.generate(
                    model=llm_model,
                    prompt=f"{system_prompt}\n\n{prompt}",
                    options=options
                )
                logger.info(f"response -----:{response}")
                # 응답 처리
                if isinstance(response, dict):
                    return response.get('response', '')
                elif hasattr(response, '__iter__'):
                    return ' '.join([r.get('response', '') if isinstance(r, dict) else str(r) for r in response])
                else:
                    return str(response)
                    
            except Exception as api_error:
                logger.error(f"Ollama API error: {str(api_error)}")
                # HTTP 요청으로 폴백
                return self._fallback_http_request(model_name, prompt, system_prompt, options)

        except Exception as e:
            logger.error(f"Ollama generate error: {str(e)}")
            return f"Error generating response: {str(e)}"
            
    def _fallback_http_request(self, model_name: str, prompt: str, system_prompt: str, options: dict) -> str:
        try:
            session = self.get_session()
            url = f"{self.host_name}/api/generate"
            
            payload = {
                "model": model_name,
                "prompt": f"{system_prompt}\n\n{prompt}",
                "stream": False,
                "options": options
            }
            
            response = session.post(
                url,
                json=payload,
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                    'Accept': 'application/json'
                },
                timeout=(10, 300)
            )
            response.raise_for_status()
            return response.json().get('response', '')
            
        except Exception as e:
            logger.error(f"HTTP fallback request failed: {str(e)}")
            return f"Error in fallback request: {str(e)}"
            

    def split_into_chunks(self, text: str, chunk_size: int = 500) -> List[str]:
        # 텍스트를 의미 있는 단위로 분할
        sentences = text.split('.')
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence = sentence.strip() + '.'
            if current_size + len(sentence) > chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_size = len(sentence)
            else:
                current_chunk.append(sentence)
                current_size += len(sentence)

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

           
    def cleanup(self, model_name: str):
        try:
            # 세션 정리
            self.cleanup_session()
            # 메모리 정리 요청
            import gc
            gc.collect()
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
                
    def get_session(self):
        if not hasattr(self.thread_local, "session"):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=self.max_workers,
                pool_maxsize=self.max_workers,
                max_retries=3
            )
            session.mount('http://', adapter)
            self.thread_local.session = session
        return self.thread_local.session

    def cleanup_session(self):
        if hasattr(self.thread_local, "session"):
            self.thread_local.session.close()
            delattr(self.thread_local, "session")
                