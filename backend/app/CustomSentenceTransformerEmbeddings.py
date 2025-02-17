import os
import logging
from pathlib import Path
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
from typing import List
logger = logging.getLogger(__name__)

class CustomSentenceTransformerEmbeddings:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.MODEL_PATH = os.path.join(os.path.dirname(current_dir), "models", "ko-sbert-nli")
        self.MODEL_NAME = "jhgan/ko-sroberta-nli"
        
        try:
            self.load_or_download_model()
        except Exception as e:
            logger.error(f"모델 로딩 중 오류 발생: {e}")
            raise

    def load_or_download_model(self):
        try:
            if os.path.exists(self.MODEL_PATH):
                logger.info(f"로컬에서 모델을 로드합니다: {self.MODEL_PATH}")
                self.model = SentenceTransformer(self.MODEL_PATH)
            else:
                logger.info(f"모델을 다운로드하고 저장합니다: {self.MODEL_NAME}")
                self.model = SentenceTransformer(self.MODEL_NAME)
                self.model.save(self.MODEL_PATH)
                logger.info(f"모델이 저장되었습니다: {self.MODEL_PATH}")
        except Exception as e:
            logger.error(f"모델 다운로딩 중 오류 발생: {e}")
            raise

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        try:
            if not documents:
                raise ValueError("Empty document list")
            
            embeddings = self.model.encode(documents)
            
            if isinstance(embeddings, torch.Tensor):
                return embeddings.tolist()
            elif isinstance(embeddings, np.ndarray):
                return embeddings.tolist()
            else:
                return embeddings  # 이미 리스트 형태일 경우
        except Exception as e:
            logger.error(f"문서 임베딩 중 오류 발생: {str(e)}")
            raise

    def embed_query(self, query):
        try:
            return self.model.encode(query).tolist()
        except Exception as e:
            logger.error(f"쿼리 임베딩 중 오류 발생: {e}")
            raise