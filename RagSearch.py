from dotenv import load_dotenv, set_key
from pathlib import Path
import streamlit as st
import sys, platform
import asyncio
import re
from langchain_core.messages import ChatMessage
from langchain_core.documents import Document
#from langchain.llms import Ollama
from langchain.chains.question_answering import load_qa_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
import os, base64, time
import subprocess, requests
from langchain_community.llms import Ollama
from langchain_groq import ChatGroq  #pip install langchain-groq
from langchain_openai import ChatOpenAI
from backend.app.TextSummarizer import TextSummarizer #by mbs
from backend.app.GroqManager import  GroqManager
from backend.app.GroqManager import get_groq_response as GroqResponse
from backend.app.ChromaDbManager import ChromaDbManager
from backend.app.CustomSentenceTransformerEmbeddings import CustomSentenceTransformerEmbeddings as CSTFM

import logging, json


logging.basicConfig(level=logging.ERROR)
logging.getLogger("langchain").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


st.set_page_config(page_title="AI에게 질문하기", layout="wide")
st.cache_data.clear()

FILLTERED_DOC_NUMBER = 5
DOCKER_USE = True
SIMILALITY = 0.9
#@st.cache_data
def load_embeddings():
    return CSTFM()

@st.cache_resource
def load_llm():
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
    
    baseurl = os.environ.get("BASE_URL")
    modelllm = os.environ.get("DEFAULT_LLMNAME")
    api_key = os.environ.get("API_KEY", "lm-studio")  # API 키도 환경 변수에서 가져옴

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

class RAGChatAppUI:
    def __init__(self, app):
        try:
            self.app = app
            self.llm_name = "LM Studio"
            os.environ['STREAMLIT_CACHE_STORAGE_MANAGER'] = 'FileStorageManager'
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            if 'search_results' not in st.session_state:
                st.session_state.search_results = []
            if 'chat_input_key' not in st.session_state:
                st.session_state.chat_input_key = f"chat_input_query_{int(time.time() * 1000)}"
            
            
        except Exception as e:
            error_message = f"_init_ 오류 발생: {e}"
            st.error(error_message)

    def setup_main_ui(self):
        try:
            st.header("Ask your PDF, DOC, PPT, Excel, HWP 💬")
            
            main_content = st.empty()
            with main_content.container():
                self.maincol1, self.maincol2 = st.columns([7, 3])
        except Exception as e:
            error_message = f"set_main_ui 오류 발생: {e}"
            st.error(error_message)
            
    def set_llm_name(self, llm_name):
        self.llm_name =  llm_name

    def setup_sidebar(self):
        try:
            with st.sidebar:
                st.header("Rag Menu")
                tab1, tab2, tab3, tab4 = st.tabs(["Arg Chat", "임베딩", "ChromaDB 관리", "LLM 모델"])
                
                with tab1:
                    self.update_tab("Arg Chat")
                    self.setup_rag_chat_tab()
                with tab2:
                    self.update_tab("임베딩")
                    self.setup_embed_tab()
                with tab3:
                    self.update_tab("ChromaDB 관리")
                    self.setup_chromadb_tab()
                with tab4:
                    self.update_tab("LLM 모델")
                    self.setup_llmmodel_tab()
        except Exception as e:
            error_message = f"setup_sidebar 오류 발생: {e}"
            st.error(error_message)
    
    def update_tab(self, tab_name):
        if st.session_state.current_tab != tab_name:
            st.session_state.current_tab = tab_name
            self.app.update_collections()

    def setup_rag_chat_tab(self):
        try:
            st.header("Arg Chat")
            st.session_state.rag_usage = st.radio("Rag이용여부 👇", ["Rag+LLM", "LLM"], index=0 if st.session_state.rag_usage == "Rag+LLM" else 1)
            collections = st.session_state.updated_collections            
            selected_collection = st.selectbox("검색할 컬렉션을 선택하세요", collections, key="search_collection_name")
            self.app.set_collection_name(selected_collection)
            self.setup_document_selection(selected_collection)
        except Exception as e:
            error_message = f"setup_arg_chat_tab 오류 발생: {e}"
            st.error(error_message)

    def setup_document_selection(self, collection_name):
        try:            
            source_search = st.text_input("문서검색:", key="source_search_input")
            
            if st.button("검색"):
                st.session_state.filtered_sources = self.app.db_manager.get_all_documents_source(collection_name, source_search)
                st.session_state.show_search_results = True
            
            if st.session_state.show_search_results:
                with st.expander("검색 결과", expanded=True):
                    st.write("다음 문서들이 검색되었습니다. 선택하세요:")
                    for source in st.session_state.filtered_sources:
                        if st.checkbox(source, key=f"check_{source}"):
                            if source not in st.session_state.selected_sources:
                                st.session_state.selected_sources.append(source)
                        elif source in st.session_state.selected_sources:
                            st.session_state.selected_sources.remove(source)                
                    if st.button("선택 완료"):
                        st.session_state.show_search_results = False
                        
            selected = st.multiselect(
                "선택된 문서:", 
                options=st.session_state.filtered_sources,
                default=st.session_state.selected_sources,
                key="final_selected_sources",
            )
            
            st.session_state.selected_sources = selected
            
            col1, col2 = st.columns(2)
            with col1: 
                st.session_state.apply_filter = st.checkbox("적용", value=st.session_state.apply_filter)
            with col2:
                if st.button("필터 초기화"):
                    st.session_state.selected_sources = []
                    st.session_state.filtered_sources = []
                    st.session_state.apply_filter = False
        except Exception as e:
            error_message = f"setup_document_collection 오류 발생: {e}"
            st.error(error_message)

    def setup_embed_tab(self):
        try:
            st.header("임베딩")
            
            collections = st.session_state.updated_collections
            
            if collections:
                selected_collection = st.selectbox("컬렉션을 선택하세요", collections, key="embed_collection_select")
            else:
                st.warning("사용 가능한 컬렉션이 없습니다. 먼저 컬렉션을 생성해주세요.")
                return
            # 세션 상태 초기화
            if 'file_uploader_key' not in st.session_state:
                st.session_state.file_uploader_key = 0
            if 'uploaded_files' not in st.session_state:
                st.session_state.uploaded_files = []

            # 파일 업로더 초기화 버튼
            if st.button("파일 업로더 초기화"):
                old_key = f"file_uploader_{st.session_state.file_uploader_key}"
                st.session_state.file_uploader_key += 1
                st.session_state.uploaded_files = []
                # 이전 file_uploader_key 삭제
                if old_key in st.session_state:
                    del st.session_state[old_key]

            # 파일 업로더
            current_key = f"file_uploader_{st.session_state.file_uploader_key}"
            uploaded_files = st.file_uploader("파일을 선택하세요", 
                                            type=['.pdf','.pptx','.ppt','.doc','.docx','.hwp','.hwpx','.xlsx','.md','.txt','html','.htm'], 
                                            accept_multiple_files=True,
                                            key=current_key)
            
            # 새로 업로드된 파일 처리
            if uploaded_files:
                st.session_state.uploaded_files = uploaded_files
           
            # 벡터 저장 버튼
            if st.button("벡터저장", key="store_vector_collection"):            
                if st.session_state.uploaded_files:                
                    total_chunks_stored = 0
                    for file in st.session_state.uploaded_files:
                        if self.app.db_manager.check_source_exists(selected_collection, file):
                            st.info(f"{file.name} 파일이 DB에 이미 존재하여 저장하지 않습니다.")
                        else:                            
                            try:
                                with st.spinner(f"{file.name} 파일의 텍스트 추출 중..."):
                                    text = self.app.db_manager.extract_text_from_file(file, file.name)
                                
                                if not text:
                                    st.warning(f"{file.name}에서 추출된 텍스트가 없습니다.")
                                    continue

                                with st.spinner(f"{file.name} 텍스트 처리 및 임베딩 중..."):
                                    processed_text = text
                                    chunks_stored = self.app.db_manager.split_embed_docs_store(
                                        processed_text, file.name, selected_collection)
                                
                                total_chunks_stored += chunks_stored
                                st.success(f"'{file.name}' 파일이 처리되어 {chunks_stored}개의 청크가 '{selected_collection}' 컬렉션에 저장되었습니다.")
                            except Exception as e:
                                st.error(f"{file.name} 파일 처리 중 오류가 발생했습니다: {str(e)}")
                    
                    st.success(f"총 {total_chunks_stored}개의 청크가 저장되었습니다.")
                    st.session_state.uploaded_files = []  # 업로드된 파일 리스트 초기화
                    
                    # 파일 업로더 리셋 및 이전 키 삭제
                    old_key = current_key
                    st.session_state.file_uploader_key += 1
                    if old_key in st.session_state:
                        del st.session_state[old_key]
                else:
                    st.warning("처리할 파일이 없습니다. 파일을 먼저 업로드해주세요.")

        except Exception as e:
            error_message = f"setup_embed_tab 오류 발생: {e}"
            st.error(error_message)       

    def setup_chromadb_tab(self):
        try:
            st.title("Arg Search를 위한 ChromaDB 관리 Section")
            management_menu = st.selectbox(
                "작업을 선택하세요",
                ("Collection 생성", "Collection 삭제", "Collection 내용검색", "Collection 내용보기"),
                key="tabmenu_select"
            )
            
            collections = self.app.db_manager.get_list_collections()
            
            if management_menu == "Collection 생성":
                self.create_collection_ui()
            elif management_menu == "Collection 삭제":
                self.delete_collection_ui(collections)
            elif management_menu == "Collection 내용검색":
                self.search_collection_ui(collections)
            elif management_menu == "Collection 내용보기":
                self.view_collection_ui(collections)
        except Exception as e:
            error_message = f"Setup_embed_tab 오류 발생: {e}"
            st.error(error_message)

    def create_collection_ui(self):
        try:
            st.header("새 컬렉션 생성")
            collection_name = st.text_input("생성할 컬렉션 이름을 입력하세요")
                       
            
            if st.button("생성", key="create_new_collection"):
                if re.match("^[a-zA-Z0-9_-]+$", collection_name):
                    if collection_name not in st.session_state.updated_collections:
                        result = self.app.db_manager.create_collection(collection_name)
                        if result:
                            st.session_state.need_update = True
                            st.success(f"컬렉션 '{collection_name}'이 생성되었습니다.")
                            st.rerun()
                        else:
                            st.error(f"컬렉션 '{collection_name}' 생성에 실패했습니다.")
                    else:
                        st.info(f"컬렉션 '{collection_name}'이 이미 존재합니다.")
                    if st.session_state.need_update:
                        self.app.update_collections()
                else:
                    st.error("영문과 숫자, -, _만 입력 해주세요.")
        except Exception as e:
            st.error(f"컬렉션 생성 중 오류 발생: {str(e)}")
                                    
    def delete_collection_ui(self, collections):
        try:
            if 'delete_state' not in st.session_state:
                st.session_state.delete_state = 'initial'
            if 'selected_collection' not in st.session_state:
                st.session_state.selected_collection = None
            if 'show_message' not in st.session_state:
                st.session_state.show_message = None
            if 'confirm_delete' not in st.session_state:
                st.session_state.confirm_delete = False
            if 'updated_collections' not in st.session_state:
                st.session_state.updated_collections = self.app.db_manager.get_list_collections()

            # 메시지 표시 (있는 경우)
            if st.session_state.show_message:
                st.success(st.session_state.show_message)
                st.session_state.show_message = None

            st.session_state.selected_collection = st.selectbox(
                "삭제할 컬렉션을 선택하세요", 
                st.session_state.updated_collections, 
                key="delete_collection_select"
            )

            if st.button("삭제", key="delete_collection"):
                st.session_state.delete_state = 'confirm'

            if st.session_state.delete_state == 'confirm':
                st.write(f"'{st.session_state.selected_collection}' 컬렉션을 삭제하시겠습니까?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("예", key="confirm_yes"):
                        st.session_state.confirm_delete = True
                with col2:
                    if st.button("아니오", key="confirm_no"):
                        st.session_state.delete_state = 'initial'
                        st.session_state.selected_collection = None

            # '예' 버튼 클릭 처리
            if st.session_state.confirm_delete:
                result = self.app.db_manager.delete_collection(st.session_state.selected_collection)
                if result:
                    st.session_state.show_message = f"'{st.session_state.selected_collection}' 컬렉션이 삭제되었습니다."
                    st.session_state.need_update = True
                    st.session_state.delete_state = 'initial'
                    st.session_state.selected_collection = None
                    st.session_state.confirm_delete = False
                    st.rerun()
                else:
                    st.error(f"'{st.session_state.selected_collection}' 컬렉션 삭제에 실패했습니다.")
            
            if st.session_state.need_update:
                self.app.update_collections()
                
        except Exception as e:
            error_message = f"delete_collection_ui 오류 발생: {e}"
            st.error(error_message)

    def search_collection_ui(self, collections):
        try:
            st.header("컬렉션 검색")
            selected_collection = st.selectbox("검색할 컬렉션을 선택하세요", collections, key="search_collection_select")
            search_query = st.text_input("검색어를 입력하세요")
            if st.button("검색", key="search_collectison_content"):
                results = self.app.db_manager.search_collection(selected_collection, search_query, self.app.db_manager.docnum,SIMILALITY)                
                self.display_search_results(results)  # self.app.display_search_results(results) 대신
        except Exception as e:
            error_message = f"search_collection_ui 오류 발생: {e}"
            st.error(error_message)


    def view_collection_ui(self, collections):
        try:
            st.header("컬렉션 내용보기")
            selected_collection = st.selectbox("컬렉션을 선택하세요", collections, key="view_collection_select")            
            if st.button("내용 보기", key="view_collection_content"):
                content = self.app.db_manager.view_collection_content(selected_collection)
                st.write(f"'{selected_collection}'의 내용입니다.")
                st.markdown(content)
        except Exception as e:
            error_message = f"view_collection_ui 오류 발생: {e}"
            st.error(error_message)
    
    
    
    def setup_ollama(self, app):
        models = self.app.get_ollama_models()
        if models:
            selected_model = st.selectbox("사용할 Ollama 모델을 선택하세요:", models)
            st.write(f"선택한 모델: {selected_model}")
            app.set_model_name(selected_model)
            app.llmname = selected_model
            st.success(f"Ollama 모델 {selected_model}이 선택되었습니다.")
        else:
            st.error("사용 가능한 Ollama 모델이 없습니다. 'ollama pull' 명령어로 모델을 다운로드 해주세요.")
            app.set_llm_model(app.lm_llm, "http://localhost:11434")

    def setup_groq(self, app):
        models = app.load_groq()
        if models:
            app.lm_llm.model_name = models
            app.set_llm_model(app.lm_llm, "")
            st.success("Groq(외부API)를 이용합니다.")            
        else:
            st.error("Groq(외부API)를 사용하려면 .env 파일의 GROQ_API_KEY에 key를 입력해주세요.")
        

    def setup_lm_studio(self, app):
        models = self.app.get_lm_studio_models()
        if models:
            app.lm_llm.model_name = models
            app.set_llm_model(app.lm_llm, "http://localhost:1234/v1")
            st.success("LM Studio에서 동일한 모델이 실행되고 있어야 정상적으로 작동됩니다.")
        else:
            app.set_llm_model(app.lm_llm, "http://localhost:1234/v1")
            st.error("LM Studio 모델을 찾을 수 없습니다. 기본 설정을 사용합니다.")
    
    

    def setup_llmmodel_tab(self):
        try:
            if 'llm_source' not in st.session_state:
                st.session_state.llm_source = "Ollama"

            llm_sources = ["Ollama", "Groq"] if DOCKER_USE else ["LM Studio", "Ollama", "Groq"]
            st.session_state.llm_source = st.radio("LLM 소스 선택:", llm_sources)

            if st.session_state.llm_source == "Ollama":
                self.set_llm_name(llm_name="Ollama")
                self.setup_ollama(self.app)
            elif st.session_state.llm_source == "Groq":
                self.set_llm_name(llm_name="Groq")
                self.setup_groq(self.app)
            elif not DOCKER_USE and st.session_state.llm_source == "LM Studio":
                self.set_llm_name(llm_name="LM Studio")
                self.setup_lm_studio(self.app)

        except Exception as e:
            st.error(f"LLM 모델 설정 중 오류가 발생했습니다: {str(e)}")
                    

    def display_chat_interface(self):
        try:
            with self.maincol1:           
                input_container = st.container()
                chat_history = st.container()
                # 사용자 입력 처리
                with input_container:
                    user_question = st.chat_input("Enter your search query", key=st.session_state.chat_input_key)
                    if user_question:
                        st.session_state.messages.append(ChatMessage(role="user", content=user_question))
                        try:
                            asyncio.run(self.app.process_query_async(user_question))
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
                        self.update_chat_history(chat_history)
        except Exception as e:
            error_message = f"display_chat_interface 오류 발생: {e}"
            st.error(error_message)
            
    def display_chat_messages(self):
        try:
            for message in st.session_state.messages[-8:]:  # 최신 4개 메시지만 표시
                with st.chat_message(message.role):
                    st.markdown(message.content)
        except Exception as e:
            error_message = f"display_chat_messages 오류 발생: {e}"
            st.error(error_message)
   
    def update_chat_history(self, chat_history):
        try:
            with chat_history:
                st.session_state.messages = st.session_state.messages[-8:]  # 최신 4개 메시지만 유지
                for message in reversed(st.session_state.messages):
                    if message.role == "user":
                        st.chat_message("user").write(message.content)
                    else:
                        st.chat_message("assistant").write(message.content)
        except Exception as e:
            error_message = f"update_chat_history 오류 발생: {e}"
            st.error(error_message)
    

    def display_search_results(self, results):
        try:
            with self.maincol2:            
                if not results:
                    st.write("No results found.")
                else:
                    for i, result in enumerate(results, 1):
                        key = "view_" + str(i)
                        with st.expander(f"Result {i}"):
                            if isinstance(result, dict):
                                st.write(f"**Content:** {result['page_content']}")
                                st.write(f"**Metadata:** {result['metadata']}")
                                st.write(f"**Score:** {result['score']:.1f}")
                                if st.button(f"**File_name:** {result['metadata']['file_name']}", key=key):
                                    self.app.show_pdf(result['metadata']['file_name'])
                            else:
                                st.write(f"**Content:** {result.page_content}")
                                st.write(f"**Metadata:** {result.metadata}")
                                st.write(f"**Score:** {result.metadata.get('score', 'N/A'):.1f}")
                                if st.button(f"**File_name:** {result.metadata.get('file_name', 'Unknown')}", key=key):
                                    self.app.show_pdf(result.metadata.get('file_name'))
        except Exception as e:
            error_message = f"display_search_results 오류 발생: {e}"
            st.error(error_message)
                

class RAGChatApp:
    def __init__(self):
        project_root = Path(__file__).parent.parent
        # .env 파일의 경로 설정
        env_path = project_root / '.env'
        load_dotenv(dotenv_path=env_path)
        self.chromadb = ChromaDbManager()
        self.persist_directory = self.chromadb.get_persist_directory;
        self.collection_name = "rag_test"
        self.db_manager = self.chromadb
        self.lm_llm = load_llm()
        self.llm = self.lm_llm
        self.lmmname =""
        self.initialize_session_state()
        self.ui = RAGChatAppUI(self)
        os.environ["POSTHOG_DISABLED"] = "1"
        self.embeddings = load_embeddings()
        self.models = self.load_models_from_env("LM")
        self.groq = GroqManager()
        self.groq_models = self.load_models_from_env("GROQ")
        self.baseurl = "http://localhost:1234/v1"
        
    async def process_query_async(self, query):
        try:
            keyword, parsed_query = self.parse_input(query)
            if (keyword == "f" or st.session_state.apply_filter) and st.session_state.rag_usage == "Rag+LLM":
                await self.process_filtered_query_async(parsed_query)
            else:
                await self.process_regular_query_async(parsed_query)
        except Exception as e:
            error_message = f"process_query_async 오류 발생: {e}"
            st.error(error_message)

    async def process_filtered_query_async(self, query):
        try:
            if st.session_state.selected_sources:
                docs = await asyncio.to_thread(self.db_manager.get_documents_by_source, 
                                            self.collection_name, st.session_state.selected_sources)
                if docs:
                    await self.generate_response_async(docs, query)
                else:
                    st.write("No documents found for the selected sources.")
            else:
                st.info("검색할 문서를 선택하세요!")
        except Exception as e:
            error_message = f"process_filtered_query_async 오류 발생: {e}"
            st.error(error_message)

    async def process_regular_query_async(self, query):
        try: 
            docs=[]
            if st.session_state.RagUsage == "Rag+LLM":
                with st.spinner('Rag+LLM 답변 사전 준비중...'):
                    docs = await asyncio.to_thread(self.perform_search, query, self.db_manager, 
                                                self.collection_name, st.session_state.selected_sources)
                if docs:
                    await self.generate_response_async(docs, query)
                    self.ui.display_search_results(docs)
                else:
                    await self.fallback_to_llm_async(query)
            else:
                await self.generate_response_async(None, query)
        except asyncio.CancelledError:
            st.error("작업이 취소되었습니다.")
        except RuntimeError as e:
            st.error(f"런타임 오류: {e}")
        except Exception as e:
            error_message = f"process_regular_query_async 오류 발생: {e}"

    def get_model_name(self):
        return self.lmmname
    
    def set_model_name(self, name):
        self.lmmname = name            
             
    def ollama_generate(self, model_name: str, prompt: str, **kwargs) -> str:
        base_url = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        url = f"{base_url}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,  # 스트리밍 비활성화
            **kwargs
        }
        
        headers = {
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            
            response.raise_for_status()
            
           
            try:
                data = response.json()
                return data.get('response', '')
            except json.JSONDecodeError as e:
                raise Exception(f"Ollama API 응답 파싱 오류: {str(e)}")            
        except requests.RequestException as e:
            raise Exception(f"Ollama API HTTP 오류: {str(e)}")
        except Exception as e:
            raise Exception(f"Ollama API 예상치 못한 오류: {str(e)}")
            
     
    async def generate_response_async(self, docs, query):
        try:         
            
            with st.spinner('AI 답변을 기다리고 있는중...'):
                if self.ui.llm_name == "Groq":
                    docs_list = [docs] if isinstance(docs, str) else docs
                    response = GroqResponse(self.groq, docs_list, query)
                    content = response['content'] if isinstance(response['content'], str) else str(response['content'])
                    response = content
                elif self.ui.llm_name == "Ollama":
                    # Ollama API 사용
                    context = "\n".join(doc.page_content for doc in docs) if isinstance(docs, list) else docs
                    prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
                    modelname = self.get_model_name()
                    response = self.ollama_generate(model_name=modelname, prompt=prompt)  # model 인자 제거
                    response = response.strip()
                else:
                    chain = load_qa_chain(self.llm, chain_type="stuff", verbose=True)
                    response = await asyncio.to_thread(chain.run, input_documents=docs or "", question=query)
                st.session_state.messages.append(ChatMessage(role="assistant", content=response))
        except Exception as e:
            error_message = f"LLM 서버연결 오류 발생: {e}"
            st.error(error_message)
            st.session_state.messages.append(ChatMessage(role="assistant", content=error_message))


    async def fallback_to_llm_async(self, query):
        st.info("선택한 소스나 문서에서 관련 정보를 찾을 수 없어 LLM에 질의합니다.")
        await self.generate_response_async("", query)
        
           

    def initialize_session_state(self):
        try:
            if "messages" not in st.session_state:
                st.session_state.messages = []
            if "docs" not in st.session_state:
                st.session_state.docs = None
            if "selected_sources" not in st.session_state:
                st.session_state.selected_sources = []
            if "last_query" not in st.session_state:
                st.session_state.last_query = ""
            if "rag_usage" not in st.session_state:
                st.session_state.rag_usage = "Rag+LLM"
            if "max_docnum" not in st.session_state:
                st.session_state.max_docnum = 3
            if "apply_filter" not in st.session_state:
                st.session_state.apply_filter = False
            if "filtered_sources" not in st.session_state:
                st.session_state.filtered_sources = []
            if "RagUsage" not in st.session_state:    
                st.session_state.RagUsage = "Rag+LLM"
                
                    # 새로운 초기화 코드 추가
            if "show_search_results" not in st.session_state:
                st.session_state.show_search_results = False
            if "files_processed" not in st.session_state:
                st.session_state.files_processed = False
            if "updated_collections" not in st.session_state:
                st.session_state.updated_collections = self.db_manager.get_list_collections()
            if "need_update" not in st.session_state:
                st.session_state.need_update = False
            if "current_tab" not in st.session_state:
                st.session_state.current_tab = None
            
        except Exception as e:
            error_message = f"initialize_session_state 오류 발생: {e}"
            st.error(error_message)
        
    def update_collections(self):
        st.session_state.updated_collections = self.db_manager.get_list_collections()
        st.session_state.need_update = False

    def set_collection_name(self, ragname):
        try:
            self.collection_name = ragname
        except Exception as e:
            error_message = f"set_collection_name 오류 발생: {e}"
            st.error(error_message)

    def set_llm_model(self, modelname, url):
        try:
            self.llm = modelname
            self.baseurl = url
        except Exception as e:
            error_message = f"set_llm_model 오류 발생: {e}"
            st.error(error_message)
    
    def list_ollama_models(self):
        try:
            OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
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
                st.warning("사용 가능한 Ollama 모델이 없습니다.")
            return models
        except Exception as e:
            error_message = f"get_ollama_models 오류 발생: {e}"
            st.error(error_message)
            return []  # 오류 발생 시 빈 리스트 반환
    
    def load_groq(self):
        try:
            project_root = Path(__file__).parent.parent
            env_path = project_root / '.env'
            
            # 매번 .env 파일을 새로 로드
            load_dotenv(dotenv_path=env_path, override=True)
            
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                st.warning("GROQ_API_KEY가 설정되지 않았습니다. API 키를 입력해주세요.")
                new_api_key = st.text_input("Groq API Key", type="password")
                if new_api_key:
                    # .env 파일에 API 키 저장
                    set_key(env_path, "GROQ_API_KEY", new_api_key)
                    st.success("API 키가 성공적으로 저장되었습니다.")
                    # 새로 저장된 API 키를 즉시 로드
                    load_dotenv(dotenv_path=env_path, override=True)
                    api_key = os.environ.get("GROQ_API_KEY")
                else:
                    st.error("API 키를 입력해주세요.")
                    return None

            available_models = self.get_groq_models()
            if not available_models:
                st.error("사용 가능한 Groq 모델이 없습니다.")
                return None

            self.ui.set_llm_name(llm_name="Groq")
            
            # 첫 번째 사용 가능한 모델 선택
            selected_model = available_models[0] if isinstance(available_models, list) else available_models
            self.lm_llm.model_name = selected_model
            self.set_llm_model(self.groq, "")

            try:
                groq_llm = ChatGroq(
                    groq_api_key=api_key,
                    model_name=selected_model,
                    temperature=0,
                )
                st.success(f"Groq 모델 '{selected_model}'이(가) 성공적으로 로드되었습니다.")
                return groq_llm
            except Exception as e:
                st.error(f"Groq 클라이언트 초기화 중 오류 발생: {str(e)}")
                return None

        except Exception as e:
            st.error(f"load_groq 오류 발생: {str(e)}")
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
            st.error(error_message)

    def get_lm_studio_models(self):
        try:
            if not self.models:
                st.error("No LM Studio models defined in .env file.")
                return None

            selected_model = st.selectbox(
                "Select LM Studio Model",
                options=list(self.models.keys()),
                format_func=lambda x: f"{x} ({self.models[x]})"
            )

            if selected_model:
                model_id = self.models[selected_model]
                return model_id
            else:
                return None
        except Exception as e:
            error_message = f"get_llm_studio_models오류 발생: {e}"
            st.error(error_message)
    
    def get_groq_models(self):
        try:
            if not self.groq_models:
                st.error("No Groq models defined in .env file.")
                return None

            selected_groqmodel = st.selectbox(
                "Select Groq Model",
                options=list(self.groq_models.keys()),
                format_func=lambda x: f"{x} ({self.groq_models[x]})"
            )

            if selected_groqmodel:
                model_id = self.groq_models[selected_groqmodel]
                return model_id
            else:
                return None
        except Exception as e:
            error_message = f"get_groq_models 오류 발생: {e}"
            st.error(error_message)

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
            st.error(error_message)


    def perform_search(self, query, db_manager, collection_name, selected_sources=None):
        try:
            raw_results = db_manager.search_collection(collection_name, query, n_results=FILLTERED_DOC_NUMBER)        
            if not raw_results:
                return []
            docs = []
            for result in raw_results:
                if not isinstance(result['page_content'], str):
                    result['page_content'] = str(result['page_content'])
                
                doc = Document(
                    # 원본 text를 summarize를 해서 보내는 방법-LLM 속도개선 테스트
                    page_content=TextSummarizer.summarize(result['page_content'], 5),
                    # 원본 text를 그대로 전달하는 방법
                    # page_content=result['page_content'],
                    metadata={"score": result['score'], **result['metadata']}
                )            
                docs.append(doc)
                
            filtered_docs = [doc for doc in docs]
            
            if selected_sources:
                filtered_docs = [doc for doc in filtered_docs if doc.metadata.get('source', 'Unknown') in selected_sources]
            
            return filtered_docs
        except Exception as e:
            error_message = f"perform_search 오류 발생: {e}"
            st.error(error_message)


    def process_query(self, query):
        try:
            keyword, parsed_query = self.parse_input(query)
            if (keyword == "f" or st.session_state.apply_filter) and st.session_state.rag_usage == "Rag+LLM":
                self.process_filtered_query(parsed_query)
            else:
                self.process_regular_query(parsed_query)
        except Exception as e:
            error_message = f"process_query 오류 발생: {e}"
            st.error(error_message)

    def process_filtered_query(self, query):
        try:
            if st.session_state.selected_sources:
                docs = self.db_manager.get_documents_by_source(self.collection_name, st.session_state.selected_sources)
                if docs:
                    self.generate_response(docs, query)
                else:
                    st.write("No documents found for the selected sources.")
            else:
                st.info("검색할 문서를 선택하세요!")
        except Exception as e:
            error_message = f"process_filtered_query오류 발생: {e}"
            st.error(error_message)

    def process_regular_query(self, query):
        try:
            asyncio.run(self.process_regular_query_async(query))
            if st.session_state.RagUsage == "Rag+LLM":
                with st.spinner('Rag+LLM 답변 사전 준비중...'):
                    docs = self.perform_search(query, self.db_manager, self.collection_name, st.session_state.selected_sources)                
                if docs:
                    self.generate_response(docs, query)                
                    self.ui.display_search_results(docs)
                else:
                    self.fallback_to_llm(query)
            else:
                self.generate_response(None, query)            
        except Exception as e:
            error_message = f"process_regular_query오류 발생: {e}"
            st.error(error_message)
            
    def generate_response(self, docs, query):
        try:
            # Create the prompt template
            prompt_template = """
            System: You are an AI assistant that answers questions using only the provided information. Do not include any content not present in the given information. If the information is insufficient, say "I cannot answer with the given information."

            Context: {context}

            Human: {question}

            AI: """

            # Prepare the context from the retrieved documents
            context = "\n".join([doc.page_content for doc in docs])

            # Create the prompt
            prompt = prompt_template.format(context=context, question=query)

            # Load the QA chain
            chain = load_qa_chain(self.llm, chain_type="stuff", verbose=True)

            with st.spinner('AI 답변을 기다리고 있는중...'):
                # Run the chain with the prepared prompt
                response = chain.run(input_documents=docs or "", question=prompt)
                st.session_state.messages.append(ChatMessage(role="assistant", content=response))
        except Exception as e:
            error_message = f"LLM 서버연결 오류 발생: {e}"
            st.error(error_message)
            st.session_state.messages.append(ChatMessage(role="assistant", content=error_message))            

    
    def fallback_to_llm(self, query):
        try:
            st.info("선택한 소스나 문서에서 관련 정보를 찾을 수 없어 LLM에 질의합니다.")
            self.generate_response(None, query)
        except Exception as e:
            error_message = f"fallback_to_llm 오류 발생: {e}"
            st.error(error_message)

    def show_pdf(self, file_path):
        try:
            file_path = os.path.join(self.persist_directory, file_path)
            with open(file_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="800" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        except Exception as e:
            error_message = f"show_pdf 오류 발생: {e}"
            st.error(error_message)

    def run(self):
        try:
            self.ui.setup_main_ui()
            with st.sidebar:
                self.ui.setup_sidebar()
            self.ui.display_chat_interface()
        except Exception as e:
            error_message = f"run 오류 발생: {e}"
            st.error(error_message)
        
if __name__ == '__main__':
    if platform.system() != 'Windows':
        logger.debug("이 애플리케이션은 Windows에서만 실행할 수 있습니다.")
    app = RAGChatApp()
    app.run()
    