<template>
  <div class="db-container">
    <div class="db-input-container">
      <input
        type="text"
        v-model="dbName"
        class="db-input"
        :class="{ 'db-input-invalid': !isValidDbName }"
        placeholder="Collection 이름을 입력하세요"
      >
      <p v-if="!isValidDbName" class="db-input-error">
        {{ dbNameErrorMessage }}
      </p>
      <button 
        class="db-action-button" 
        @click="createDb" 
        :disabled="!isValidDbName || dbName.trim() === ''"
      >
        생성
      </button>
    </div>
    <div class="db-list-container">
      <h4>Collection 정보</h4>
      <ul class="db-list">
        <li v-for="collection in collections" :key="collection">
          {{ collection }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001'; // 실제 서버 주소로 변경 필요

export default {
  name: 'CreateDB',
  data() {
    return {
      dbName: '',
      collections: [],
      dbNamePattern: /^[a-z0-9][a-z0-9-_]{1,61}[a-z0-9]$/,
    }
  },
  computed: {
    isValidDbName() {
      return this.dbNamePattern.test(this.dbName) && !this.dbName.includes('..');
    },
    dbNameErrorMessage() {
      if (this.dbName.length < 3 || this.dbName.length > 63) {
        return '컬렉션 이름은 3-63자 사이여야 합니다.';
      }   
      
      if (this.dbName.includes('..')) {
        return '컬렉션 이름에 연속된 마침표(..)를 포함할 수 없습니다.';
      }
      return '';
    }
  },
  mounted() {
    this.fetchCollections();
  },
  methods: {
    async createDb() {
      if (this.isValidDbName && this.dbName.trim()) {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/create-collection`, { name: this.dbName });
          if (response.data.success) {
            alert(`컬렉션 "${this.dbName}"가 성공적으로 생성되었습니다.`);
            this.$emit('collection-created', this.dbName);
            this.dbName = '';
            this.fetchCollections();
          } else {
            alert(`컬렉션 생성 실패: ${response.data.message}`);
          }
        } catch (error) {
          console.error('컬렉션 생성 중 오류 발생:', error);
          alert(`오류 발생: ${error.message}`);
        }
      }
    },
    async fetchCollections() {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/list-collections`);
        if (response.data.success) {
          this.collections = response.data.collections;
        } else {
          console.error('컬렉션 목록 가져오기 실패:', response.data.message);
        }
      } catch (error) {
        console.error('컬렉션 목록을 가져오는 중 오류 발생:', error);
      }
    }
  }
}
</script>

<style scoped>
.db-container {
  padding: 10px;
  margin-right: 10px;
  margin-top: 10px;
  color: white;
  background-color: #1e1e1e;
}

.db-input-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  margin-bottom: 15px;
}

.db-input {
  width: 100%;
  padding: 10px;
  margin-bottom: 10px;
  background-color: #1e1e1e;
  color: white;
  border: 1px solid #333;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.db-action-button {
  width: 100%;
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

.db-list-container {
  width: 100%;
}

.db-list-container h4 {
  margin-bottom: 10px;
  color: #fff;
}

.db-list {
  list-style-type: none;
  padding: 0;
  margin: 0;
  background-color: #1e1e1e;
  border: 1px solid #333;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.db-list li {
  padding: 8px 10px;
  border-bottom: 1px solid #333;
  color: white;
}

.db-list li:last-child {
  border-bottom: none;
}
</style>