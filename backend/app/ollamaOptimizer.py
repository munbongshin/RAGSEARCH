from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import threading
import logging
import json
import requests
import os, time
import psutil
import queue

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OllamaAPIClient:
    """Ollama API에 직접 HTTP 요청을 보내는 클래스"""
    
    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        self.api_url = f"{self.base_url}/api"
        self.session = requests.Session()
        
        # 연결 유지 설정
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=3
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def list_models(self):
        """설치된 모델 목록을 가져옵니다."""
        response = self.session.get(f"{self.api_url}/tags", timeout=30)
        response.raise_for_status()
        return response.json().get('models', [])
    
    def generate(self, model_name, prompt, system_message=None, options=None):
        """모델에 프롬프트를 전송하고 응답을 생성합니다."""
        full_prompt = f"{system_message}\n\n{prompt}" if system_message else prompt
        
        payload = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": False
        }
        
        # 옵션이 있으면 추가
        if options:
            payload["options"] = options
            
        start_time = time.time()
        
        response = self.session.post(
            f"{self.api_url}/generate",
            json=payload,
            timeout=300  # 긴 타임아웃 설정
        )
        response.raise_for_status()
        result = response.json()
        
        # 결과 포맷팅
        return {
            "response": result.get("response", ""),
            "prompt_eval_count": result.get("prompt_eval_count", 0),
            "eval_count": result.get("eval_count", 0),
            "total_duration": time.time() - start_time
        }
    
    def pull_model(self, model_name):
        """모델을 다운로드합니다."""
        payload = {"name": model_name}
        response = self.session.post(f"{self.api_url}/pull", json=payload, timeout=600)
        response.raise_for_status()
        return True
    
    def close(self):
        """세션을 닫습니다."""
        self.session.close()

class OllamaConnectionPool:
    """Ollama API 클라이언트 연결 풀을 관리하는 클래스"""
    
    def __init__(self, pool_size=5, base_url=None):
        self.pool_size = pool_size
        self.base_url = base_url
        self.clients = queue.Queue(maxsize=pool_size)
        self._init_clients()
        
    def _init_clients(self):
        """클라이언트 풀 초기화"""
        for _ in range(self.pool_size):
            client = OllamaAPIClient(base_url=self.base_url)
            self.clients.put(client)
    
    def get_client(self):
        """풀에서 클라이언트 가져오기"""
        try:
            return self.clients.get(block=True, timeout=5)
        except queue.Empty:
            logger.warning("Client pool empty, creating new client")
            return OllamaAPIClient(base_url=self.base_url)
    
    def release_client(self, client):
        """클라이언트를 풀에 반환"""
        try:
            self.clients.put(client, block=False)
        except queue.Full:
            logger.debug("Client pool full, closing extra client")
            client.close()
    
    def __enter__(self):
        self.current_client = self.get_client()
        return self.current_client
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_client(self.current_client)
    
    def close_all(self):
        """모든 클라이언트 연결 종료"""
        while not self.clients.empty():
            try:
                client = self.clients.get(block=False)
                client.close()
            except queue.Empty:
                break

class OllamaFullGPUOptimizer:
    """GPU를 100% 활용하는 Ollama 최적화 클래스"""
    
    def __init__(self, max_workers=5, connection_pool_size=10, base_url=None):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.host_name = base_url or os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        
        # 연결 풀 설정
        self.connection_pool = OllamaConnectionPool(
            pool_size=connection_pool_size, 
            base_url=self.host_name
        )
        
        # 요청 처리 세마포어 - 동시 요청 수 제한
        self.request_semaphore = threading.Semaphore(max_workers)
        
        # 모델 로드 상태 추적
        self.loaded_models = set()
        self.model_load_lock = threading.RLock()
        
        logger.info(f"Connecting to Ollama server at: {self.host_name}")
        logger.info(f"Connection pool size: {connection_pool_size}, Max workers: {max_workers}")
    
    def ensure_model_loaded(self, model_name):
        """모델이 서버에 로드되어 있는지 확인하고 로드되지 않았다면 로드합니다."""
        with self.model_load_lock:
            if model_name in self.loaded_models:
                return
            
            logger.info(f"Checking if model {model_name} is loaded...")
            try:
                with self.connection_pool as client:
                    # 모델 정보 확인
                    models = client.list_models()
                    model_names = [model.get('name') for model in models]
                    
                    if model_name in model_names:
                        logger.info(f"Model {model_name} is already loaded")
                        self.loaded_models.add(model_name)
                        return
                    
                    # 모델이 로드되어 있지 않으면 로드
                    logger.info(f"Model {model_name} not loaded, loading now...")
                    client.pull_model(model_name)
                    self.loaded_models.add(model_name)
                    logger.info(f"Model {model_name} successfully loaded")
            except Exception as e:
                logger.error(f"Error ensuring model is loaded: {str(e)}")
    
    def direct_ollama_generate(self, model_name, prompt, system_message=None, **kwargs):
        """
        Ollama API를 직접 호출하여 응답을 생성합니다.
        
        Args:
            model_name (str): 사용할 모델 이름
            prompt (str): 입력 프롬프트
            system_message (str, optional): 커스텀 시스템 메시지
            **kwargs: 추가 인자
        
        Returns:
            dict: 생성된 응답과 메타데이터를 포함하는 딕셔너리
        """
        # 세마포어를 사용하여 동시 요청 수 제한
        with self.request_semaphore:
            start_time = time.time()
            
            try:
                # 모델 로드 확인
                self.ensure_model_loaded(model_name)
                
                # 시스템 프롬프트 설정
                system_prompt = system_message if system_message else """
                    You are an intelligent assistant. 
                    You always provide well-reasoned, structured, and comprehensive answers.
                    Please provide your answer in Korean, ensuring it is natural and fluent.
                """
                
                # 옵션 설정 - GPU를 최대한 활용하기 위해 옵션을 전달하지 않음
                # Ollama 서버의 기본 설정을 사용하게 함 (일반적으로 가능한 모든 GPU 사용)
                options = kwargs.get('options', None)
                
                # 연결 풀에서 클라이언트 가져오기
                with self.connection_pool as client:
                    # 요청 전송
                    response = client.generate(
                        model_name=model_name,
                        prompt=prompt,
                        system_message=system_prompt,
                        options=options
                    )
                    
                    # 결과 포맷팅
                    result = {
                        "content": response["response"],
                        "metadata": {
                            "model": model_name,
                            "usage": {
                                "prompt_tokens": response.get("prompt_eval_count", 0),
                                "completion_tokens": response.get("eval_count", 0),
                                "total_duration": response.get("total_duration", time.time() - start_time)
                            },
                            "gpu_used": True  # 직접 API 요청은 서버의 GPU 설정을 사용
                        }
                    }
                    
                    logger.info(f"Response generated in {result['metadata']['usage']['total_duration']:.2f} seconds")
                    return result
            
            except Exception as e:
                error_msg = f"Processing error: {str(e)}"
                logger.error(error_msg)
                return {"content": f"Error: {str(e)}", "metadata": {"error": str(e)}}
    
    def batch_process(self, prompts, model_name, system_message=None, **kwargs):
        """여러 프롬프트를 병렬로 처리합니다."""
        # 모델 로드 확인
        self.ensure_model_loaded(model_name)
        
        # 병렬 처리를 위한 작업 제출
        futures = []
        for prompt in prompts:
            future = self.executor.submit(
                self.direct_ollama_generate, 
                model_name, 
                prompt, 
                system_message, 
                **kwargs
            )
            futures.append(future)
        
        # 결과 수집
        results = []
        for future in futures:
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch processing: {str(e)}")
                results.append({"content": f"Error: {str(e)}", "metadata": {"error": str(e)}})
        
        return results
    
    def async_generate(self, model_name, prompt, system_message=None, callback=None, **kwargs):
        """
        비동기 방식으로 응답을 생성합니다. 결과는 콜백 함수로 전달됩니다.
        
        Args:
            model_name (str): 사용할 모델 이름
            prompt (str): 입력 프롬프트
            system_message (str, optional): 커스텀 시스템 메시지
            callback (callable): 결과를 처리할 콜백 함수
            **kwargs: 추가 인자
        """
        def _process_and_callback():
            try:
                result = self.direct_ollama_generate(model_name, prompt, system_message, **kwargs)
                if callback:
                    callback(result)
            except Exception as e:
                logger.error(f"Async generate error: {str(e)}")
                if callback:
                    callback({"content": f"Error: {str(e)}", "metadata": {"error": str(e)}})
        
        # 작업 제출
        self.executor.submit(_process_and_callback)
    
    def ollama_generate(self, model_name, prompt, system_message=None, **kwargs):
        """
        Ollama API를 사용하여 단일 요청으로 응답을 생성하고 텍스트만 반환합니다.
        
        호환성을 위한 메소드입니다.
        """
        result = self.direct_ollama_generate(model_name, prompt, system_message, **kwargs)
        return result["content"]
    
    def shutdown(self):
        """리소스 정리 및 종료"""
        try:
            logger.info("Shutting down optimizer...")
            self.executor.shutdown(wait=True)
            self.connection_pool.close_all()
            logger.info("Optimizer shut down successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")