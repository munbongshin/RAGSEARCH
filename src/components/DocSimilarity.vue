<template>
  <div class="doc-similarity">
    <div class="fixed-content">
      <div class="document-panels">
        <div class="document-panel">
          <div class="panel-header">
            <span class="plus-icon">+</span>
            원본문서
          </div>
          <textarea placeholder="Text input area" v-model="originalDoc"></textarea>
        </div>
        <div class="document-panel">
          <div class="panel-header">
            <span class="plus-icon">+</span>
            비교문서
          </div>
          <textarea placeholder="Text input area" v-model="comparisonDoc"></textarea>
        </div>
      </div>
      <div class="compare-button-container">
        <button @click="compareDocs" class="compare-button" :disabled="isLoading">
          {{ isLoading ? '분석 중...' : '문서 비교' }}
        </button>
      </div>
    </div>
    <div v-if="comparisonResult" class="comparison-section">
      <div class="comparison-header">
        문서비교 결과 (유사도: {{ similarity.toFixed(2) }}%)
        <div class="similarity-explanation">{{ similarityExplanation }}</div>
      </div>
      <div class="comparison-content">
        <div class="similarity-list">
          <div class="list-header">유사문장 리스트</div>
          <ul>
            <li 
              v-for="(item, index) in similarSentences" 
              :key="index" 
              @click="showSentenceInfo(item)"
              :class="{ 'selected': selectedSentence === item }"
            >
              {{ item.sentence }} (유사도: {{ item.similarity.toFixed(2) }}%)
            </li>
          </ul>
        </div>
        <div class="document-info">
          <div v-if="selectedSentence">
            <h4>선택된 문장 정보</h4>
            <div><strong>문장:</strong> {{ selectedSentence.sentence }}</div>
            <div><strong>유사도:</strong> {{ selectedSentence.similarity.toFixed(2) }}%</div>
            <div><strong>원본 문서:</strong> {{ selectedSentence.originalInfo }}</div>
            <div><strong>비교 문서:</strong> {{ selectedSentence.comparisonInfo }}</div>
          </div>
          <div v-else>
            문장을 선택하면 상세 정보가 여기에 표시됩니다.
          </div>
        </div>
      </div>
    </div>
  </div>
 </template>
 
 <script>
 import axios from 'axios';
 
 const API_BASE_URL = 'http://localhost:5001';
 
 export default {
  name: 'DocSimilarity',
  props: {
    selectedSources: Array,
    collectionName: String,
    ragmode: String,
    sources: String,
    llmName: String,
    llmModel: String
  },
  data() {
    return {
      originalDoc: '',
      comparisonDoc: '',
      similarSentences: [],
      comparisonResult: false,
      isLoading: false,
      similarity: 0,
      selectedSentence: null,
      similarityExplanation: '',
    }
  },
  methods: {
    async compareDocs() {
      if (this.isLoading || !this.originalDoc || !this.comparisonDoc) return;
      
      this.isLoading = true;
      try {
        const response = await axios.post(`${API_BASE_URL}/api/compare-documents`, {
          collection_name: this.collectionName,
          sources: this.selectedSources,
          llm_name: this.llmName,
          llm_model: this.llmModel,
          ragmode: this.ragmode,
          originalDoc: this.originalDoc,
          comparisonDoc: this.comparisonDoc
        });
 
        console.log('Server response:', response.data);
 
        const result = response.data;
 
        if (result.total_similarity !== undefined && Array.isArray(result.sentences)) {
          this.similarity = result.total_similarity;
          this.similarSentences = result.sentences.map(sentence => ({
            ...sentence,
            similarity: sentence.similarity
          }));
          this.comparisonResult = true;
          this.selectedSentence = null;
          this.similarityExplanation = result.similarity_explanation;
        } else {
          console.error('올바른 형식의 분석 결과를 받지 못했습니다.');
        }
      } catch (error) {
        console.error('Error comparing documents:', error);
      } finally {
        this.isLoading = false;
      }
    },
    showSentenceInfo(item) {
      this.selectedSentence = item;
    }
  }
 }
 </script>
 
 <style scoped>
 .doc-similarity {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100vh;
  background-color: #1e1e1e;
  color: white;
 }
 
 .fixed-content {
  flex: 0 0 auto;
 }
 
 .document-panels {
  display: flex;
  height: 300px;
 }
 
 .document-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 10px;
  border: 1px solid #333;
 }
 
 .panel-header {
  background-color: #333;
  color: white;
  padding: 10px;
  display: flex;
  align-items: center;
 }
 
 .plus-icon {
  margin-right: 5px;
 }
 
 textarea {
  flex: 1;
  background-color: #222;
  color: white;
  border: none;
  padding: 10px;
  resize: none;
 }
 
 .compare-button-container {
  display: flex;
  justify-content: center;
  padding: 10px;
  height: 60px;
 }
 
 .compare-button {
  background-color: #4CAF50;
  border: none;
  color: white;
  padding: 15px 32px;
  text-align: center;
  text-decoration: none;
  display: inline-block;
  font-size: 16px;
  margin: 4px 2px;
  cursor: pointer;
  border-radius: 4px;
 }
 
 .comparison-section {
  flex: 1;
  overflow-y: auto;
  background-color: #333;
  margin: 10px;
  border: 1px solid #444;
 }
 
 .comparison-header {
  padding: 10px;
  border-bottom: 1px solid #444;
 }
 
 .comparison-content {
  display: flex;
  padding: 10px;
 }
 
 .similarity-list {
  flex: 1;
  padding-right: 10px;
 }
 
 .list-header {
  margin-bottom: 10px;
 }
 
 ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
 }
 
 li {
  margin-bottom: 5px;
  cursor: pointer;
  padding: 5px;
  border-radius: 3px;
 }
 
 li:hover {
  background-color: #444;
 }
 
 .document-info {
  flex: 1;
  padding-left: 10px;
  border-left: 1px solid #444;
 }
 
 .compare-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
 }
 
 .analysis-result {
  margin-top: 20px;
  padding: 10px;
  background-color: #222;
  border-radius: 4px;
 }
 
 .analysis-result pre {
  white-space: pre-wrap;
  word-wrap: break-word;
 }
 
 .similarity-list li {
  margin-bottom: 5px;
  cursor: pointer;
  padding: 5px;
  border-radius: 3px;
 }
 
 .similarity-list li:hover {
  background-color: #444;
 }
 
 .similarity-list li.selected {
  background-color: #555;
  font-weight: bold;
 }
 
 .document-info {
  flex: 1;
  padding-left: 10px;
  border-left: 1px solid #444;
  overflow-y: auto;
 }
 
 .document-info h4 {
  margin-top: 0;
  margin-bottom: 10px;
 }
 
 .document-info div {
  margin-bottom: 5px;
 }
 
 .similarity-explanation {
  font-size: 0.9em;
  color: #888;
  margin-top: 5px;
 }
 </style>