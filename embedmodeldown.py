from huggingface_hub import hf_hub_download
from sentence_transformers import SentenceTransformer
from transformers import AutoConfig
from pathlib import Path
import os

MODEL_PATH = r'./models/ko-sbert-nli'
model = SentenceTransformer('jhgan/ko-sroberta-nli')
model.save(MODEL_PATH)
config = AutoConfig.from_pretrained("jhgan/ko-sbert-nli")