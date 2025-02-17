<template>
  <div class="db-delete-container">
    <select v-model="selectedCollection" class="db-select">
      <option value="">Collection을 선택하세요</option>
      <option v-for="collection in collections" :key="collection" :value="collection">
        {{ collection }}
      </option>
    </select>
    <button class="db-action-button" @click="confirmDelete" :disabled="!selectedCollection">삭제</button>
  </div>
</template>

<script>
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001'; // 실제 서버 주소로 변경 필요

export default {
  name: 'DeleteDB',
  data() {
    return {
      selectedCollection: '',
      collections: []
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
        } else {
          console.error('컬렉션 목록 가져오기 실패:', response.data.message);
          alert('컬렉션 목록을 가져오는 데 실패했습니다.');
        }
      } catch (error) {
        console.error('컬렉션 목록을 가져오는 중 오류 발생:', error);
        alert('컬렉션 목록을 가져오는 데 실패했습니다.');
      }
    },
    confirmDelete() {
      if (this.selectedCollection) {
        if (confirm(`정말로 "${this.selectedCollection}" 컬렉션을 삭제하시겠습니까?`)) {
          this.deleteDb();
        }
      } else {
        alert('collection을 선택해주세요.');
      }
    },
    async deleteDb() {
      try {
        console.log(`Attempting to delete collection: ${this.selectedCollection}`);
        const response = await axios.post(`${API_BASE_URL}/api/delete-collection`, { name: this.selectedCollection });
        console.log('Delete response:', response.data);
        if (response.data.success) {
          alert(`컬렉션 "${this.selectedCollection}"이 성공적으로 삭제되었습니다.`);
          this.fetchCollections(); // 목록 새로고침
          this.selectedCollection = '';
        } else {
          alert(`컬렉션 삭제 실패: ${response.data.message}`);
        }
      } catch (error) {
        console.error('컬렉션 삭제 중 오류 발생:', error);
        if (error.response) {
          console.error('Error response:', error.response.data);
          alert(`오류 발생: ${error.response.data.message || error.message}`);
        } else {
          alert(`오류 발생: ${error.message}`);
        }
      }
    }
  }
}
</script>

<style scoped>
.db-delete-container {
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
</style>