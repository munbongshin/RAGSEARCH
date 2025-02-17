import sys,os
#sys.path.append('C:/Dev/vueprj2')  # 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend/app'))
from backend.app.TextSummarizer import TextSummarizer #by mbs
from backend.app.GroqManager import  GroqManager
from backend.app.ChromaDbManager import ChromaDbManager
from backend.app.PostgresDbManager import PostgresDbManager
from backend.app.db_manager import DatabaseManager
from backend.app.CustomSentenceTransformerEmbeddings import CustomSentenceTransformerEmbeddings as CSTFM
from backend.app.systemMessageManager import SystemMessageManager
from backend.app.ollamaOptimizer import ollamaOptimizer

from dotenv import load_dotenv, set_key
from pathlib import Path
import asyncio
from langchain_core.messages import ChatMessage
from langchain_core.documents import Document
#from langchain.llms import Ollama
from langchain.chains.question_answering import load_qa_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
import base64, time
import subprocess, requests
from langchain_community.llms import Ollama
from langchain_groq import ChatGroq  #pip install langchain-groq
from langchain_openai import ChatOpenAI
import logging, json
import getpass
import traceback
from abc import ABC, abstractmethod
import psutil
from typing import  List,  Union

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def load_llm():
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
        
    baseurl = os.environ.get("BASE_URL")
    modelllm = os.environ.get("DEFAULT_LLMNAME")
    api_key = os.environ.get("API_KEY","lm-studio")  # API 키도 환경 변수에서 가져옴    
    FILLTERED_DOC_NUMBER = os.environ.get("FILLTERED_DOC_NUMBER", "5")
    SIMILALITY = os.environ.get("SIMILALITY")
    
    if not all([baseurl, modelllm]):
        raise ValueError("필요한 환경 변수가 설정되지 않았습니다.")

    chatllm = ChatOpenAI(
        base_url=baseurl,
        api_key=api_key,        
        model=modelllm,
        streaming=True,
        temperature=0,
    )    
    return chatllm

def load_embeddings():
    return CSTFM()


class RAGChatApp:
    def __init__(self, db_type: str = 'chroma'):
        """
        RAGChatApp 초기화
        
        Args:
            db_type (str): 사용할 데이터베이스 타입 ('postgres' 또는 'chroma')
        """
        # PostHog 완전 비활성화
        os.environ["POSTHOG_DISABLED"] = "1"
        os.environ["DISABLE_POSTHOG_ANALYTICS"] = "1"
        self.db_type = db_type
        self._load_environment()
        self._initialize_database()
        self._initialize_other_components()       

    def _load_environment(self):
        project_root = Path(__file__).parent.parent        
        self.env_path = project_root / '.env'
        load_dotenv(dotenv_path=self.env_path)
        
        # DB_TYPE 로드 및 검증
        self.db_type = os.getenv('DB_TYPE')
        if not self.db_type:
            raise ValueError("DB_TYPE environment variable is not set")
        
        if self.db_type not in ['postgres', 'chroma']:
            raise ValueError(f"Invalid DB_TYPE: {self.db_type}. Must be 'postgres' or 'chroma'")
        
        # PostgreSQL configuration if needed
        if self.db_type == 'postgres':
            try:
                pg_config_str = os.getenv('POSTGRES_CONFIG')
                if pg_config_str:
                    self.db_config = json.loads(pg_config_str)
                else:
                    # 필수 환경변수 확인
                    required_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
                    missing_vars = [var for var in required_vars if not os.getenv(var)]
                    
                    if missing_vars:
                        raise ValueError(f"Missing required PostgreSQL environment variables: {', '.join(missing_vars)}")
                    
                    self.db_config = {
                        'host': os.getenv('POSTGRES_HOST'),
                        'port': int(os.getenv('POSTGRES_PORT')),
                        'database': os.getenv('POSTGRES_DB'),
                        'user': os.getenv('POSTGRES_USER'),
                        'password': os.getenv('POSTGRES_PASSWORD')
                    }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse POSTGRES_CONFIG: {e}")
                raise
            except ValueError as e:
                logger.error(str(e))
                raise
            except Exception as e:
                logger.error(f"Error loading PostgreSQL configuration: {e}")
                raise
        else:
            self.db_config = None

    def _initialize_database(self):
        """Initialize the database manager based on environment configuration"""
        try:
            if self.db_type == "postgres":
                if not self.db_config or not all([
                    self.db_config.get('user'),
                    self.db_config.get('password')
                ]):
                    raise ValueError("PostgreSQL configuration is incomplete")
                self.db_manager = PostgresDbManager()
                logger.info("Initialized PostgreSQL database manager")
            elif self.db_type == "chroma":
                self.db_manager = ChromaDbManager()
                logger.info("Initialized ChromaDB database manager")
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
            
            # persist_directory는 ChromaDB에서만 사용
            if self.db_type == "chroma":
                self.persist_directory = self.db_manager.get_persist_directory()
            else:
                self.persist_directory = None
                
            self.collection_name = os.getenv('COLLECTION_NAME')

            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _initialize_other_components(self):
        """Initialize other components of the RAG application"""
        self.lm_llm = load_llm()
        self.llm_model = self.lm_llm
        self.llm_name = ""
        self.embeddings = load_embeddings()
        self.models = self.load_models_from_env("LM")
        self.groq = GroqManager()
        self.groq_models = self.load_models_from_env("GROQ")
        self.baseurl = "http://localhost:1234/v1"
        self.ollama_processor = ollamaOptimizer(max_workers=3)
        sysMan = SystemMessageManager();
        sysManMessge=sysMan.get_selected_system_message(sysMan.get_current_selected_message_name())
        self.system_message = sysManMessge

    def change_database(self, db_type: str, db_config: dict = None):
        """
        Dynamically change the database manager and update environment
        Args:
            db_type: Type of database ('postgres' or 'chroma')
            db_config: Configuration dictionary for database connection
        """
        try:
            # Validate the new configuration
            if db_type.lower() == "postgres" and not db_config:
                raise ValueError("PostgreSQL configuration is required")

            # Update environment variables
            from dotenv import set_key
            set_key(self.env_path, "DB_TYPE", db_type.lower())
            
            if db_type.lower() == "postgres" and db_config:
                # Store PostgreSQL configuration in environment
                set_key(self.env_path, "POSTGRES_CONFIG", json.dumps(db_config))
            
            # Update instance variables and reinitialize
            self.db_type = db_type.lower()
            self._load_environment()
            self._initialize_database()
            
            logger.info(f"Successfully switched to {db_type} database")
            
        except Exception as e:
            logger.error(f"Failed to change database: {str(e)}")
            raise
        
    def set_llm_name(self, llm_name):
        self.llm_name =  llm_name    #GROQ, OLLAMA, LM Studion
        

    def set_system_message(self, message):
        self.system_message =  message    #system_message를 setting
    
    def setup_document_selection(self, collection_name):
        try:            
            source_search = ""
        except Exception as e:
                    error_message = f"setup_document_collection 오류 발생: {e}"
                    logger.error(error_message)
                    
    def setup_groq(self, app):
        try: 
            models = app.load_groq()
            if models:
                self.lm_llm.model_name = models
                self.set_llm_model(app.llm_model)
                logger.info("Groq(외부API)를 이용합니다.")            
            else:
                logger.error("Groq(외부API)를 사용하려면 .env 파일의 GROQ_API_KEY에 key를 입력해주세요.")
        except Exception as e:
                    error_message = f"setup_groq 오류 발생: {e}"
                    logger.error(error_message)
                    
    def setup_lm_studio(self, app):
        try: 
            models = self.get_lm_studio_models()
            if models:
                self.lm_llm.model_name = models
                self.set_llm_model(self.llm_model)
                self.set_llm_baseUrl("http://localhost:1234/v1")
                logger.info("LM Studio에서 동일한 모델이 실행되고 있어야 정상적으로 작동됩니다.")
            else:
                logger.error("LM Studio 모델을 찾을 수 없습니다. 기본 설정을 사용합니다.")
        except Exception as e:
                    error_message = f"setup_lm_studio 오류 발생: {e}"
                    logger.error(error_message)
    
    def get_model_name(self):
        return self.llm_name
    
    def set_model_name(self, name):
        self.lmmname = name            
             
    def ollama_generate(self, model_name: str, prompt: str, **kwargs) -> dict:
        try:
            response = self.ollama_processor.direct_ollama_generate(
                model_name=model_name,
                prompt=prompt,
                system_message=self.system_message
            )
            return response  # 이제 dictionary를 반환
        except Exception as e:
            logger.error(f"Query processing error: {str(e)}")
            raise          

                        
    def set_collection_name(self, ragname):
        try:
            self.collection_name = ragname
        except Exception as e:
            error_message = f"set_collection_name 오류 발생: {e}"
            logger.error(error_message)

    def set_llm_model(self, llm_model):
        try:
            self.llm_model = llm_model
        except Exception as e:
            error_message = f"set_llm_model 오류 발생: {e}"
            logger.error(error_message)
            
    def set_llm_baseUrl(self, url):
        try:
            self.baseurl = url
        except Exception as e:
            error_message = f"set_llm_baseUrl 오류 발생: {e}"
            logger.error(error_message)
    
    def list_ollama_models(self):
        try:
            #OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
            OLLAMA_HOST = os.getenv('OLLAMA_HOST')
            response = requests.get(f"{OLLAMA_HOST}/api/tags")
            if response.status_code == 200:
                data = response.json()
                # 'models' 키가 존재하고 리스트인지 확인
                if 'models' in data and isinstance(data['models'], list):
                    # 각 모델 데이터에서 'name' 필드만 추출
                    return [model['name'] for model in data['models'] if 'name' in model]
                else:
                    return []  # 'models' 키가 없거나 리스트가 아닌 경우 빈 리스트 반환
            else:
                logger.debug(f"Error: {response.status_code}, {response.text}")
                return []
        except requests.RequestException as e:
            logger.debug(f"Request failed: {e}")
            return []

    def get_ollama_models(self):
        try:
            models = self.list_ollama_models()
            if not models:  # 빈 리스트인 경우 처리
                logger.warning("사용 가능한 Ollama 모델이 없습니다.")
            return models
        except Exception as e:
            error_message = f"get_ollama_models 오류 발생: {e}"
            logger.error(error_message)
            return []  # 오류 발생 시 빈 리스트 반환
    
    def load_groq(self):
        try:
            project_root = Path(__file__).parent.parent
            env_path = project_root / '.env'
            
            # 매번 .env 파일을 새로 로드
            load_dotenv(dotenv_path=env_path, override=True)
            
            api_key = os.environ.get("GROQ_API_KEY")
            logger.debug(f"GROQ_API_KEY is {api_key}")
            if not api_key:
                logger.warning("GROQ_API_KEY가 설정되지 않았습니다. API 키를 입력해주세요.")
                new_api_key = getpass.getpass("Groq API Key: ")
                if new_api_key:
                    # .env 파일에 API 키 저장
                    set_key(env_path, "GROQ_API_KEY", new_api_key)
                    logger.info("API 키가 성공적으로 저장되었습니다.")
                    # 새로 저장된 API 키를 즉시 로드
                    load_dotenv(dotenv_path=env_path, override=True)
                    api_key = os.environ.get("GROQ_API_KEY")
                else:
                    logger.error("API 키를 입력해주세요.")
                    return None

            available_models = self.get_groq_models()
            if not available_models:
                logger.error("사용 가능한 Groq 모델이 없습니다.")
                return None

            self.set_llm_name(llm_name="Groq")
            
            # 첫 번째 사용 가능한 모델 선택
            selected_model = available_models[0] if isinstance(available_models, list) else available_models
            self.lm_llm.model_name = selected_model
            self.set_llm_model(selected_model)

            try:
                groq_llm = ChatGroq(
                    groq_api_key=api_key,
                    model_name=selected_model,
                    temperature=0,
                )
                logger.info(f"Groq 모델 '{selected_model}'이(가) 성공적으로 로드되었습니다.")
                return groq_llm
            except Exception as e:
                logger.error(f"Groq 클라이언트 초기화 중 오류 발생: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"load_groq 오류 발생: {str(e)}")
            return None
    
    
    
    def load_models_from_env(self,name):
        try:
            models = {}
            for key, value in os.environ.items():
                if name == "LM":
                    if key.startswith('LM_STUDIO_MODEL_'):
                        model_name = key.replace('LM_STUDIO_MODEL_', '')
                        models[model_name] = value
                if name == "GROQ":
                    if key.startswith('GROQ_MODEL_'):
                        model_name = key.replace('GROQ_MODEL_', '')
                        models[model_name] = value            
            return models
        except Exception as e:
            error_message = f"load_models_from_env 오류 발생: {e}"
            logger.error(error_message)

    def get_lm_studio_models(self, lm_studio_model):
        try:
            if not self.models:
                logger.error("No LM Studio models defined in .env file.")
                return None

            selected_model = lm_studio_model

            if selected_model:
                model_id = self.models[selected_model]
                return model_id
            else:
                return None
        except Exception as e:
            error_message = f"get_llm_studio_models오류 발생: {e}"
            logger.error(error_message)
    
    def get_groq_models(self,groq_model):
        try:
            if not self.groq_models:
                logger.error("No Groq models defined in .env file.")
                return None

            selected_groqmodel = groq_model
            if selected_groqmodel:
                model_id = self.groq_models[selected_groqmodel]
                return model_id
            else:
                return None
        except Exception as e:
            error_message = f"get_groq_models 오류 발생: {e}"
            logger.error(error_message)

    def parse_input(self, input_text):
        try:
            parts = input_text.split(']', 1)
            if len(parts) > 1 and parts[0].startswith('['):
                keyword = parts[0][1:].strip().lower()
                query = parts[1].strip()
                return keyword, query
            else:
                return None, input_text.strip() 
        except Exception as e:
            error_message = f"parse_input 오류 발생: {e}"
            logger.error(error_message)


    def perform_search(self, query, db_manager, collection_names: Union[str, List[str]], select_sources, score_threshold: float = 0.5):
        try:
            project_root = Path(__file__).parent.parent
            env_path = project_root / '.env'
            load_dotenv(dotenv_path=env_path)             
            FILLTERED_DOC_NUMBER = int(os.environ.get("FILLTERED_DOC_NUMBER", "5"))
            SIMILALITY = os.environ.get("SIMILALITY")
            docs = []

            if isinstance(collection_names, str):
                collection_names = [collection_names]

            if not collection_names:
                logger.error("No collection names provided")
                return []

            logger.debug(f"Searching in collections: {collection_names}")
            logger.debug(f"Selected sources: {select_sources}")
            
            raw_results = db_manager.search_collection(
            #raw_results = db_manager.search_keyword_collection(
                collection_names,
                query, 
                n_results=FILLTERED_DOC_NUMBER,
                score_threshold=score_threshold
            )

            if not raw_results:
                logger.debug("No raw results found for query")
                return []
                    
            for result in raw_results:
                if not isinstance(result['page_content'], str):
                    result['page_content'] = str(result['page_content'])
                
                metadata = {
                    "score": result['score'],
                    "collection": result.get('metadata', {}).get('collection', result.get('collection_name', 'Unknown')),
                    **result['metadata']
                }
                
                doc = Document(
                    page_content=result['page_content'],
                    metadata=metadata
                )
                docs.append(doc)
                
            if select_sources:
                filtered_docs = []
                for doc in docs:
                    source = doc.metadata.get('source', 'Unknown')
                    collection = doc.metadata.get('collection', 'Unknown')
                    
                    logger.debug(f"Checking document - Collection: {collection}, Source: {source}")
                    
                    for selected in select_sources:
                        if isinstance(selected, dict):
                            selected_collection = selected.get('collection')
                            selected_source = selected.get('source')
                            
                            if (selected_collection == collection and 
                                selected_source == source):
                                logger.debug(f"Matched - Collection: {collection}, Source: {source}")
                                filtered_docs.append(doc)
                                break
                                
                # 수정된 로깅 부분
                sources_info = [f"{s.get('collection', '')}:{s.get('source', '')}" for s in select_sources]
                docs_info = [f"{d.metadata.get('collection', '')}:{d.metadata.get('source', '')}" for d in filtered_docs]
                
                logger.debug(f"Filtered docs from {len(docs)} to {len(filtered_docs)} based on selected sources")
                logger.debug(f"Selected sources: {sources_info}")
                logger.debug(f"Filtered documents: {docs_info}")
            else:
                filtered_docs = docs
            
            logger.debug(f"Found {len(filtered_docs)} documents after filtering from {len(collection_names)} collections")
            return filtered_docs
            
        except Exception as e:
            error_message = f"Error in perform_search: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            return []


    def process_query(self, query, collection_names: Union[str, List[str]], score_threshold: float = 0.5):
        try:
            if isinstance(collection_names, str):
                collection_names = [collection_names]
                
            logger.debug(f"Processing query for collections: {collection_names}")
            logger.debug(f"Selected sources: {self.selected_sources}")
                    
            keyword, parsed_query = self.parse_input(query)
            if keyword == "f":
                self.process_filtered_query(
                    parsed_query,
                    self.db_manager,
                    collection_names,
                    self.llm_name,
                    self.selected_sources,
                    score_threshold=score_threshold
                )
            else:
                self.process_regular_query(
                    parsed_query,
                    self.db_manager,
                    collection_names,
                    self.llm_name,
                    self.selected_sources,
                    self.ragmode,
                    score_threshold=score_threshold
                )
        except Exception as e:
            error_message = f"Error in process_query: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())

    def process_filtered_query(self, query, db_manager, collection_names: Union[str, List[str]], 
                            llm_name, selected_sources, score_threshold: float = 0.5):
        try:
            if isinstance(collection_names, str):
                collection_names = [collection_names]

            logger.debug(f"Processing filtered query for collections: {collection_names}")
            logger.debug(f"Selected sources: {selected_sources}")

            all_docs = []
            
            # selected_sources가 dictionary 형태인 경우 처리
            if selected_sources and isinstance(selected_sources[0], dict):
                for collection_name in collection_names:
                    # 현재 컬렉션에 해당하는 소스만 필터링
                    collection_sources = [
                        source['source'] for source in selected_sources 
                        if source['collection'] == collection_name
                    ]
                    
                    if collection_sources:
                        logger.debug(f"Fetching documents for collection {collection_name} with sources: {collection_sources}")
                        docs = db_manager.get_documents_by_source(collection_name, collection_sources)
                        if docs:
                            all_docs.extend(docs)
            else:
                # 기존 방식 처리 (하위 호환성 유지)
                for collection_name in collection_names:
                    docs = db_manager.get_documents_by_source(collection_name, selected_sources)
                    if docs:
                        all_docs.extend(docs)

            logger.debug(f"Found {len(all_docs)} total documents across all collections")

            if all_docs:
                self.generate_response(all_docs, query, llm_name)
            else:
                logger.info("No documents found for the selected sources in any collection.")
                
        except Exception as e:
            error_message = f"Error in process_filtered_query: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())

    def process_regular_query(self, query, db_manager, collection_names: Union[str, List[str]], 
                            llm_name, select_sources, ragmode,score_threshold: float = 0.5):
        """
        Process a query using the specified database and parameters
        
        Args:
            query (str): User query
            db_manager (DatabaseManager): Database manager instance
            collection_names (Union[str, List[str]]): Name or list of names of collections to search
            llm_name (str): Name of the language model
            llm_model: Language model instance
            select_sources (list): List of selected sources
            ragmode (str): RAG mode ('RAG' or other)
            
        Returns:
            tuple: (response, documents)
        """
        try:
            # Ensure collection_names is a list
            if isinstance(collection_names, str):
                collection_names = [collection_names]

            logger.debug(f"Processing query across collections: {collection_names}")
                
            #벡터DB에서 해당되는 문서를 검색
            docs = self.perform_search(
                query=query,
                db_manager=db_manager,
                collection_names=collection_names,  # Pass list of collections
                select_sources=select_sources,
                score_threshold=score_threshold
            )
            
            #RAG 검색을 위해 벡터DB문서와 사용자 query를 전달 
            if ragmode == 'RAG':
                if docs:
                    response = self.generate_response(docs, query, llm_name)
                    return response, docs
                return ['No matching documents found in any collection.'], []
            else:
                if docs:
                    response = self.generate_response(docs, query, llm_name)
                    return response, docs
                response = self.fallback_to_llm(query, llm_name)
                return response, []
                
        except Exception as e:
            error_message = f"Error in process_regular_query: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            return error_message, []
        
    def generate_similarity(self, originalDoc, comparisonDoc, llm_name='Groq'):
        try:
            prompt = f"""
            원본 문서와 비교 문서의 유사도를 분석하고, 유사한 문장들을 추출해주세요.

            유사도 계산을 위한 필수 규칙:
            1. 문장이 완전히 동일한 경우에만 100% 유사도를 부여하세요.
            2. 한 문장이 다른 문장에 포함되어 있는 경우:
            - 포함된 문장 길이 / 전체 문장 길이 × 90을 유사도로 계산
            - 예: "ABC"와 "A"의 경우 → (1/3) × 90 = 30%의 유사도

            3. 문장 길이 차이에 따른 감점:
            - (짧은 문장 길이 / 긴 문장 길이) × 기본 유사도 = 최종 유사도
            - 예: 10단어와 5단어 문장 비교시 → (5/10) = 0.5를 곱함

            4. 일치하는 단어 수에 따른 기본 유사도:
            - (공통 단어 수 / 전체 고유 단어 수) × 80을 기본 유사도로 사용
            - 예: "A B C"와 "A B D" → (2/4) × 80 = 40% 기본 유사도

            아래 문장들의 유사도를 위 규칙에 따라 정확히 계산하여 JSON으로 반환해주세요.

            원본 문서:
            {originalDoc}

            비교 문서:
            {comparisonDoc}

            응답 형식:
            {{
                "similarity": 계산된 유사도 (0-100, 소수점 없는 정수),
                "similar_sentences": [
                    {{
                        "sentence": "비교한 문장",
                        "originalInfo": "원본 문장 전체",
                        "comparisonInfo": "비교 문장 전체",
                        "calculation_details": "유사도 계산 과정 설명",
                        "similarity": 계산된 유사도 값
                    }}
                ]
            }}

            주의: 
            - 각 규칙별 계산 과정을 calculation_details에 명시하세요
            - 문장이 다르다면 절대로 100%를 부여하지 마세요
            - 계산 과정을 정확히 보여주고 각 단계의 값을 명시하세요
            """

            print(f"groq call for generate_extractSimilarity: {prompt}")
            
            if llm_name == "Groq":
                response = self.groq.generate_extractSimilarity(originalDoc, comparisonDoc, prompt)
            elif llm_name == "Ollama":
                response = self.ollama_generate(model_name=self.llm_model, prompt=prompt)
            else:
                chain = load_qa_chain(self.llm, chain_type="stuff", verbose=True)
                response = chain.run(input_documents=[originalDoc, comparisonDoc], question=prompt)

            if isinstance(response, str):
                response = json.loads(response)
            
            return response

        except Exception as e:
            print(f"Error in generate_similarity: {str(e)}")
            print(traceback.format_exc())
            raise
    
    def generate_summary(self, llm_name, lines:int, documents):
        try:
            originalDoc = documents
            prompt = f"""
            원본 문서를 {lines} 줄로 요약하여주세요

            원본 문서:
            {originalDoc}                        
            """

            print(f"groq call for generate_cextractSimilarity: {prompt}")
            
            if llm_name == "Groq":
                response = self.groq.groq_generate(model_name=self.llm_model, prompt=prompt)
            elif llm_name == "Ollama":
                response = self.ollama_generate(model_name=self.llm_model, prompt=prompt)
            else:
                chain = load_qa_chain(self.llm, chain_type="stuff", verbose=True)
                response = chain.run(input_documents=[originalDoc], question=prompt)

            if isinstance(response, str):
                response = json.loads(response)
            
            return response

        except Exception as e:
            print(f"Error in generate_similarity: {str(e)}")
            print(traceback.format_exc())
            raise
        
        
    def generate_response(self, docs, query, llm_name):
        try:                  
            if llm_name == "Groq":
                docs_list = [docs] if isinstance(docs, str) else docs                
                response = self.groq.get_groq_response(docs_list, query, self.system_message)       
                return response

            elif llm_name == "Ollama":
                # 컨텍스트 준비
                context = "\n".join(doc.page_content for doc in docs) if isinstance(docs, list) else docs
                # 프롬프트 구성
                prompt = f"Context: {context}\n\nQuestion: {query}\n\n"
                
                try:
                    response = self.ollama_generate(
                       model_name=self.llm_model,
                       prompt=query
                    )
                    return response
                except Exception as e:
                    logger.error(f"Ollama 응답 생성 오류: {str(e)}")
                    raise

            else:
                # LM Studio 또는 기타 LLM 처리
                prompt_template = """
                System: You are an AI assistant that answers questions using only the provided information. 
                Do not include any content not present in the given information. 
                If the information is insufficient, say "I cannot answer with the given information."

                Context: {context}

                Human: {question}

                AI: """

                context = "\n".join([doc.page_content for  doc in docs])
                prompt = prompt_template.format(context=context, question=query)
                
                chain = load_qa_chain(self.llm, chain_type="stuff", verbose=True)
                response = chain.run(input_documents=docs or "", question=prompt)            
                return response

        except Exception as e:
            logger.error(f"응답 생성 오류: {str(e)}")
            raise
            

    
    def fallback_to_llm(self, query,llm_name):
        try:
            response =""
            logger.info("선택한 소스나 문서에서 관련 정보를 찾을 수 없어 LLM에 질의합니다.")
            response = self.generate_response(None, query, llm_name)
            return response
        except Exception as e:
            error_message = f"fallback_to_llm 오류 발생: {e}"
            logger.error(error_message)
            return ""

    def show_pdf(self, file_path):
        try:
            file_path = os.path.join(self.persist_directory, file_path)
            with open(file_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="800" height="800" type="application/pdf"></iframe>'            
        except Exception as e:
            error_message = f"show_pdf 오류 발생: {e}"
            logger.error(error_message)