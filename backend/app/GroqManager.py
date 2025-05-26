import os
from typing import List, Dict, Any, Union
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv, set_key
from pathlib import Path
from langchain.schema import Document
import logging
import json, re
from typing import Union, List
from icecream import ic


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ChatMessage(BaseModel):
    role: str
    content: str

class GroqManager:
    def __init__(self):
        self.model = "Llama-3.1-8b-Instant"
        
        # 프로젝트 루트 디렉토리 경로 설정
        project_root = Path(__file__).parent.parent.parent
      
        # .env 파일의 경로 설정
        self.env_path = project_root / '.env'

        if not self.env_path.exists():
            logging.error(f'.env 파일을 찾을 수 없습니다. 경로: {self.env_path}')
            raise FileNotFoundError(f'.env 파일이 {self.env_path}에 존재하지 않습니다.')
        
        # .env 파일 로드
        load_dotenv(dotenv_path=self.env_path)
        
        # GROQ_API_KEY 환경 변수에서 API 키 가져오기
        self.api_key = os.environ.get("GROQ_API_KEY")
        
        if not self.api_key:
            logging.error('API Key가 입력되지 않았습니다.')
            self.api_key = ""
            raise ValueError('no GROQ_API_KEY')
        # Groq 클라이언트 초기화
        self.client = Groq(api_key=self.api_key)
    
    def set_model(self, modelname: str) -> None:
        self.model = modelname    
        
    def safe_get(self, obj: Any, key: Union[str, int], default: Any = None) -> Any:
        """
        안전하게 객체에서 키 값을 가져오는 함수
        """
        if isinstance(obj, dict):
            return obj.get(key, default)
        elif isinstance(obj, (list, tuple)):
            try:
                return obj[key] if 0 <= key < len(obj) else default
            except (IndexError, TypeError):
                return default
        else:
            return default

    def format_response(self, chat_completion: Any):
        # ChatCompletion 객체에서 content 추출
        if hasattr(chat_completion, 'choices') and len(chat_completion.choices) > 0:
            content = chat_completion.choices[0].message.content
        else:
            raise ValueError("Invalid ChatCompletion object")

        # JSON 문자열 추출
        json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(1)
            try:
                # JSON 파싱
                original_data = json.loads(json_str)
                
                # 새로운 포맷으로 변환
                formatted_data = {
                    "total_similarity": 0,
                    "similarity_explanation": "",
                    "sentences": []
                }

                # original_data가 리스트인 경우 처리
                if isinstance(original_data, list):
                    for item in original_data:
                        total_similarity = self.safe_get(item, "total_similarity", 0)
                        similarity_explanation = self.safe_get(item, "similarity_explanation", "")
                        sentences = self.safe_get(item, "sentences", [])
                        
                        if total_similarity > formatted_data["total_similarity"]:
                            formatted_data["total_similarity"] = total_similarity
                            formatted_data["similarity_explanation"] = similarity_explanation

                        for sentence in sentences:
                            formatted_sentence = {
                                "sentence": self.safe_get(sentence, "sentence", ""),
                                "similarity": self.safe_get(sentence, "similarity", 0),
                                "originalInfo": self.safe_get(sentence, "originalInfo", ""),
                                "comparisonInfo": self.safe_get(sentence, "comparisonInfo", "해당 문장이 비교 텍스트에 없음")
                            }
                            formatted_data["sentences"].append(formatted_sentence)
                else:
                    # 단일 객체 처리
                    formatted_data["total_similarity"] = self.safe_get(original_data, "total_similarity", 0)
                    formatted_data["similarity_explanation"] = self.safe_get(original_data, "similarity_explanation", "")
                    sentences = self.safe_get(original_data, "sentences", [])
                    for sentence in sentences:
                        formatted_sentence = {
                            "sentence": self.safe_get(sentence, "sentence", ""),
                            "similarity": self.safe_get(sentence, "similarity", 0),
                            "originalInfo": self.safe_get(sentence, "originalInfo", ""),
                            "comparisonInfo": self.safe_get(sentence, "comparisonInfo", "해당 문장이 비교 텍스트에 없음")
                        }
                        formatted_data["sentences"].append(formatted_sentence)

                #print(f"============={formatted_data}====================")
                return formatted_data
            except json.JSONDecodeError:
                raise ValueError("Failed to parse JSON")
        else:
            raise ValueError("No JSON data found in the content")

    def generate_extractSimilarity(self, originalDoc, comparisonDoc, prompt):
        prompt = f"""
        두 텍스트의 전체 유사도와 문장별 유사도를 분석해주세요.

        유사도 계산 규칙:
        1. 전체 텍스트 유사도:
        - 핵심 내용 일치도: 50%
        - 문장 구조 유사성: 30%
        - 용어 일치도: 20%
        - 동일 텍스트만 100% 부여

        2. 문장별 유사도:
        - 완전 일치: 100%
        - 부분 일치: 일치하는 정도에 따라 30-90%
        - 최소 유사도: 30%

        분석할 텍스트:
        텍스트1: {originalDoc}
        텍스트2: {comparisonDoc}

        결과를 다음 JSON 형식으로 제공:
        {{
        "total_similarity": 전체_유사도,
        "similarity_explanation": "유사도_계산_설명",
        "sentences": [
            {{
                "sentence": "분석_문장",
                "similarity": 유사도,
                "originalInfo": "원본_문장",
                "comparisonInfo": "비교_문장"
            }}
        ]
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=4096
            )
            print(f"API Response: {response}")

            content = self.format_response(response)
            print(f"API Response after format_response: {content}")

            try:
                result = content
                # 완전히 동일한 텍스트 처리
                if originalDoc.strip() == comparisonDoc.strip():
                    result['total_similarity'] = 100
                    result['similarity_explanation'] = "두 텍스트가 완전히 동일함"
                    for sentence in result.get('sentences', []):
                        sentence['similarity'] = 100
                        sentence['comparisonInfo'] = sentence['originalInfo']
                else:
                    # 최소 유사도 보장
                    if result.get('total_similarity', 0) < 30 and any(word in comparisonDoc.lower() for word in originalDoc.lower().split()):
                        result['total_similarity'] = 30
                        if 'similarity_explanation' not in result:
                            result['similarity_explanation'] = "부분적인 유사성 발견"
                    
                    # comparisonInfo가 비어있거나 기본값인 경우 처리
                    for sentence in result.get('sentences', []):
                        if not sentence['comparisonInfo'] or sentence['comparisonInfo'] == "텍스트 2의 가장 유사한 부분":
                            sentence['comparisonInfo'] = "해당 문장과 유사한 내용이 텍스트 2에 없습니다."

                print(f"Parsed result: {json.dumps(result, indent=2)}")
                return result

            except json.JSONDecodeError as json_error:
                print(f"JSON parsing error: {json_error}")
                print(f"Raw content: {content}")
                return None

        except Exception as e:
            print(f"Error occurred during API call: {e}")
            return None
    
    def generate_questions(self,model_name: str,topic: str, question_type: str = "일반") -> List[str]:
        """
        주어진 주제에 대한 질문들을 생성합니다.
        
        Args:
            topic (str): 질문을 생성할 주제
            question_type (str): 질문의 유형 (예: 일반, 기술, 비즈니스 등)
            
        Returns:
            List[str]: 생성된 질문들의 리스트
        """
        # 기본 프롬프트 템플릿 정의
        
        try:
            system_message = f"""
            주제 "{topic}"에 대한 {question_type} 관련 질문 5개를 생성해주세요.
            질문은 구체적이고 명확해야 하며, 실용적인 답변이 가능해야 합니다.
            
            질문 생성 시 다음 기준을 따르세요:
            1. 질문은 주제와 직접적으로 연관되어야 합니다
            2. 질문은 단순한 예/아니오로 답할 수 없어야 합니다
            3. 질문은 실제 상황에서 유용한 정보를 얻을 수 있어야 합니다
            
            생성된 질문만 쉼표로 구분된 리스트 형태로 반환해주세요.
            """          
            self.set_model(model_name)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message}
                ],
                temperature=0,
                max_tokens=4096
            )

            answer = response.choices[0].message.content
            return {
                "content": answer,
                "metadata": {
                    "model": self.model,
                    "usage": response.usage.dict()
                }
            }
                
        except Exception as e:
            logging.error(f"Error in generate_questions: {str(e)}")
            return {
                "content": f"Error: {str(e)}", 
                "metadata": {
                    "error": str(e),
                    "model": self.model
                }
            }
    
    def generate_response(self, docs: str, query: str) -> dict:
        try:
            prompt = f"""Context:
                {docs}

                User Question: {query}

                Please provide a detailed answer based on the given context:"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an intelligent assistant. "
                     "You always provide well-reasoned answers that are both correct and helpful."
                     "Use the following pieces of context to answer the user's question."
                     "If you don't know the answer, just say that you don't know, "
                     "don't try to make up an answer. Please answer in Korean."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=4096
            )

            answer = response.choices[0].message.content
            return {
                "content": answer,
                "metadata": {
                    "model": self.model,
                    "usage": response.usage.dict()
                }
            }
        except Exception as e:
            logging.error(f"Error in generate_response: {str(e)}")
            return {"content": f"Error: {str(e)}", "metadata": {"error": str(e), "model": self.model}}
        
    def groq_generate(self, model_name: str, prompt: str) -> dict:
        try:         

            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an intelligent assistant. "
                     "You always provide well-reasoned answers that are both correct and helpful."
                     "Use the following pieces of context to answer the user's question."
                     "If you don't know the answer, just say that you don't know, "
                     "don't try to make up an answer. Please answer in Korean."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=4096
            )

            answer = response.choices[0].message.content
            return {
                "content": answer,
                "metadata": {
                    "model": self.model,
                    "usage": response.usage.dict()
                }
            }
        except Exception as e:
            logging.error(f"Error in generate_response: {str(e)}")
            return {"content": f"Error: {str(e)}", "metadata": {"error": str(e), "model": self.model}}
    
    def generate_response_query(self, docs: str, query: str, system_message: str = None):
        """
        Generate response based on query with documentation context and system message
        
        Args:
            docs (str): Context documentation
            query (str): User's question
            system_message (str, optional): Custom system message
                
        Returns:
            dict: Dictionary containing generated response and metadata
                {
                    "content": str,
                    "metadata": {
                        "model": str,
                        "usage": dict
                    }
                }
        """
        try:
            # Default system message if none provided    
            if system_message is None:
                system_message = """You are an intelligent assistant.
                You always provide well-reasoned answers that are both correct and helpful.
                Use the following pieces of context to answer the user's question.
                If you don't know the answer, just say that you don't know,
                don't try to make up an answer. Please answer in Korean."""

            # Format prompt with docs and query
            prompt = f"""Context:
            {docs}

            User Question: {query}

            Please provide a detailed answer based on the given context:"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=4096
            )

            answer = response.choices[0].message.content
            return {
                "content": answer,
                "metadata": {
                    "model": self.model,
                    "usage": response.usage.dict()
                }
            }
                
        except Exception as e:
            logging.error(f"Error in generate_response_query: {str(e)}")
            return {
                "content": f"Error: {str(e)}", 
                "metadata": {
                    "error": str(e),
                    "model": self.model
                }
            }

    def get_groq_response(self, docs, query, system_message=None):
        try:
            # Convert docs to string
            if isinstance(docs, list):
                if all(isinstance(doc, Document) for doc in docs):
                    docs_str = "\n".join(doc.page_content for doc in docs)
                elif all(isinstance(doc, str) for doc in docs):
                    docs_str = "\n".join(docs)
                else:
                    docs_str = "\n".join(str(doc) for doc in docs)
            elif isinstance(docs, str):
                docs_str = docs
            else:
                docs_str = str(docs)

            # Generate response by default system_message를 이용하는 경우
            #response = self.generate_response(docs_str, query)
            # generate_response_query(self, docs: str, query: str, system_message: str = None):
            # system_message를 매개변수로 전달하여 prompt를 유연하게 구성할 수 있음. 입력하지 않으면 기본값
            response = self.generate_response_query(docs_str, query, system_message)
            
            logging.info(f"Groq response: {response}")

            # Ensure content is string
            if not isinstance(response.get('content'), str):
                response['content'] = str(response.get('content', ''))

            return response

        except Exception as e:
            logging.error(f"Error in get_groq_response: {str(e)}")
            return {"content": f"Error: {str(e)}", "metadata": {"error": str(e), "model": self.model}}
"""
def main():
    st.title("Groq를 이용한 Q&A 시스템")

    groq_manager = GroqManager()

    docs = st.text_area("문서 내용을 입력하세요:", height=200)
    query = st.text_input("질문을 입력하세요:")

    if st.button("답변 생성"):
        if docs and query:
            with st.spinner('AI 답변을 생성 중...'):
                docs_list = [docs] if isinstance(docs, str) else docs
                result = get_groq_response(groq_manager, docs_list, query)
            
            st.write(f"AI 답변: {result['content']}")
            st.write(f"사용된 모델: {result['metadata'].get('model', 'Unknown')}")
            if 'usage' in result['metadata']:
                st.write(f"토큰 사용량: {result['metadata']['usage']}")
            if 'error' in result['metadata']:
                st.error(f"오류 발생: {result['metadata']['error']}")
        else:
            st.warning("문서 내용과 질문을 모두 입력해주세요.")

if __name__ == "__main__":
    main()    
    
"""
