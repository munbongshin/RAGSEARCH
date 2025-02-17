<template>
  <div class="db-view-container">
    <select v-model="selectedCollection" class="db-select">
      <option value="">Collection을 선택하세요</option>
      <option v-for="collection in collections" :key="collection" :value="collection">
        {{ collection }}
      </option>
    </select>
    <button class="db-action-button" @click="viewDb" :disabled="!selectedCollection">내용 보기</button>
    
    <!-- 모달 다이얼로그 -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>{{ selectedCollection }} 내용</h2>
          <button class="close-button" @click="closeModal">&times;</button>
        </div>
        <div class="modal-body">
          <div class="documents-container">
            <ul class="document-list">
              <li v-for="(doc, index) in documents" :key="index" class="document-item">
                <div class="document-header">
                  <strong>ID:</strong> {{ doc.ID }}
                </div>
                <div class="document-body">
                  <div class="metadata">
                    <strong>메타데이터:</strong>
                    <pre>{{ JSON.stringify(doc.Metadata, null, 2) }}</pre>
                  </div>
                  <div class="content">
                    <strong>문서:</strong>
                    <p>{{ doc.Document }}</p>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001'; // 실제 서버 주소로 변경 필요

export default {
  name: 'ViewDB',
  data() {
    return {
      selectedCollection: '',
      collections: [],
      documents: [],
      showModal: false
    }
  },
  mounted() {
    this.fetchCollections();
  },
  methods: {
    async fetchCollections() {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/list-collections`);
        if (response.data.success) {
          this.collections = response.data.collections;
          if (this.collections.length > 0) {
            this.selectedCollection = this.collections[0];
          }
        } else {
          console.error('컬렉션 목록 가져오기 실패:', response.data.message);
        }
      } catch (error) {
        console.error('컬렉션 목록을 가져오는 중 오류 발생:', error);
      }
    },
    async viewDb() {
      if (this.selectedCollection) {
        try {
          const response = await axios.get(`${API_BASE_URL}/api/view-collection`, {
            params: { collection_name: this.selectedCollection }
          });
          if (response.data.success) {
            this.documents = response.data.documents;
            this.showModal = true;
          } else {
            console.error('컬렉션 내용 가져오기 실패:', response.data.message);
            alert('컬렉션 내용을 가져오는데 실패했습니다.');
          }
        } catch (error) {
          console.error('컬렉션 내용을 가져오는 중 오류 발생:', error);
          alert('컬렉션 내용을 가져오는 중 오류가 발생했습니다.');
        }
      }
    },
    closeModal() {
      this.showModal = false;
    }
  }
}
</script>

<style scoped>
.db-view-container {
  padding: 10px;
  margin-right: 10px;
  margin-top: 10px;
  color: white;
  background-color: #1e1e1e;
}

.db-select {
  width: 100%;
  padding: 10px;
  margin-bottom: 10px;
  background-color: #1e1e1e;
  color: white;
  border: 1px solid #333;
  border-radius: 4px;
  font-size: 14px;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23FFFFFF%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E");
  background-repeat: no-repeat;
  background-position: right 10px top 50%;
  background-size: 12px auto;
}

.db-action-button {
  padding: 10px;
  background-color: #2c2c2c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.3s;
}

.db-action-button:hover {
  background-color: #3a3a3a;
}

.db-action-button:disabled {
  background-color: #1a1a1a;
  cursor: not-allowed;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999; /* 최상위 레이어로 설정 */
}




.modal-content {
  background-color: #1e1e1e;
  width: 90%;
  max-width: 1200px;  /* 최대 너비 설정 */
  height: 90%;
  max-height: 800px;  /* 최대 높이 설정 */
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;  /* 헤더를 고정하기 위해 */
}

.modal-header {
  position: sticky;  /* 헤더를 고정 */
  top: 0;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background-color: #2c2c2c;
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);  /* 헤더에 그림자 추가 */
}

.modal-header h2 {
  margin: 0;
  font-size: 24px;
}

.modal-body {
  flex-grow: 1;
  overflow-y: auto;
}

.close-button {
  background: none;
  border: none;
  font-size: 28px;
  color: white;
  cursor: pointer;
}

.documents-container {
  margin-top: 20px;
}

.document-list {
  list-style-type: none;
  padding: 0;
}

.document-item {
  color: white;
  padding: 10px;
  border-bottom: 1px solid #333;
}

.document-item:last-child {
  border-bottom: none;
}

/* 스크롤바 스타일링 (웹킷 브라우저용) */
.modal-body::-webkit-scrollbar {
  width: 10px;
}

.modal-body::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.modal-body::-webkit-scrollbar-thumb {
  background-color: #4a4a4a;
  border-radius: 5px;
  border: 2px solid #1e1e1e;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background-color: #5a5a5a;
}
</style>