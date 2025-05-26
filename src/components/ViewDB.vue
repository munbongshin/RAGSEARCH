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
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import { useStore } from 'vuex';

export default {
  name: 'ViewDB',
  setup() {
    const store = useStore();
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);
    const isLoading = ref(false);
    const error = ref(null);
    
    // 인증 관련 상태
    const isAuthenticated = ref(false);
    const userId = ref(null);
    const username = ref('');
    const isAdmin = ref(false);
    
    // 데이터 관련 상태
    const selectedCollection = ref('');
    const collections = ref([]);
    const documents = ref([]);
    const showModal = ref(false);
    
    // 인증 확인 함수
    const checkAuth = async () => {
      try {
        const token = sessionStorage.getItem('token');
        
        if (!token) {
          console.log('Token not found, resetting auth state');
          resetAuth();
          return;
        }

        console.log('Checking authentication with token');
        const response = await axios.get(`${apiBaseUrl.value}/api/auth/check-auth`, {
          headers: {
            'Authorization': `Bearer ${token}`
          },
          withCredentials: true
        });
        
        console.log('Authentication check response:', response.data);
        
        if (response.data.authenticated) {
          console.log('Authentication successful');
          isAuthenticated.value = true;
          username.value = response.data.username;
          userId.value = response.data.user_id;
          isAdmin.value = response.data.is_admin || false;
        } else {
          console.warn('Server responded but authentication failed');
          resetAuth();
        }
      } catch (error) {
        console.error('Authentication check failed:', error);
        
        // 상세 에러 정보 로깅
        if (error.response) {
          console.error('Error response data:', error.response.data);
          console.error('Error response status:', error.response.status);
        } else if (error.request) {
          console.error('No response received:', error.request);
        } else {
          console.error('Error creating request:', error.message);
        }
        
        resetAuth();
      }
    };
    
    // 인증 정보 초기화
    const resetAuth = () => {
      console.log('Resetting authentication state');
      isAuthenticated.value = false;
      username.value = '';
      userId.value = null;
      isAdmin.value = false;
    };
    
    const fetchCollections = async () => {
      // 로딩 상태 초기화
      isLoading.value = true;
      error.value = null;
      collections.value = [];
      
      console.log('컬렉션 목록 조회 시작');
      
      try {
        // 인증이 필요한 경우 확인
        let requestConfig = {};
        if (isAuthenticated.value) {
          requestConfig = {
            headers: {
              'Authorization': `Bearer ${sessionStorage.getItem('token')}`
            }
          };
        }
        
        // 컬렉션 목록 가져오기
        const response = await axios.get(`${apiBaseUrl.value}/api/list-collections`, requestConfig);
        
        console.log('컬렉션 조회 응답:', response.data);
        
        if (response.data.success) {
          collections.value = response.data.collections;
          
          // 컬렉션이 있으면 첫 번째 항목 선택
          if (collections.value.length > 0) {
            selectedCollection.value = collections.value[0];
            console.log(`컬렉션 '${selectedCollection.value}' 자동 선택됨`);
          } else {
            console.warn('조회된 컬렉션이 없습니다.');
          }
          
          console.log(`총 ${collections.value.length}개의 컬렉션 조회 완료`);
        } else {
          console.error('컬렉션 목록 가져오기 실패:', response.data.message);
          error.value = response.data.message || '컬렉션을 가져오는 데 실패했습니다.';
        }
      } catch (err) {
        console.error('컬렉션 목록 조회 중 오류 발생:', err.message);
        
        if (err.response) {
          console.error('Error response:', {
            data: err.response.data,
            status: err.response.status
          });
          
          // HTTP 상태 코드에 따른 처리
          if (err.response.status === 401) {
            error.value = '인증 토큰이 유효하지 않습니다. 다시 로그인해주세요.';
          } else if (err.response.status === 403) {
            error.value = '컬렉션에 접근할 권한이 없습니다.';
          } else {
            error.value = err.response.data.message || '서버와 통신 중 오류가 발생했습니다.';
          }
        } else if (err.request) {
          error.value = '서버에 연결할 수 없습니다. 네트워크 연결을 확인해주세요.';
        } else {
          error.value = err.message || '알 수 없는 오류가 발생했습니다.';
        }
      } finally {
        // 로딩 상태 종료
        isLoading.value = false;
      }
    };
    
    const viewDb = async () => {
      if (!selectedCollection.value) {
        alert('컬렉션을 선택해주세요.');
        return;
      }
      
      isLoading.value = true;
      
      try {
        console.log(`컬렉션 '${selectedCollection.value}' 내용 조회 시작`);
        
        const response = await axios.get(`${apiBaseUrl.value}/api/view-collection`, {
          params: { collection_name: selectedCollection.value },
          headers: isAuthenticated.value ? {
            'Authorization': `Bearer ${sessionStorage.getItem('token')}`
          } : undefined
        });
        
        if (response.data.success) {
          documents.value = response.data.documents;
          showModal.value = true;
          console.log(`총 ${documents.value.length}개의 문서 조회 완료`);
        } else {
          console.error('컬렉션 내용 가져오기 실패:', response.data.message);
          alert('컬렉션 내용을 가져오는데 실패했습니다.');
        }
      } catch (error) {
        console.error('컬렉션 내용을 가져오는 중 오류 발생:', error);
        
        let errorMessage = '컬렉션 내용을 가져오는 중 오류가 발생했습니다.';
        if (error.response && error.response.data && error.response.data.message) {
          errorMessage = `오류: ${error.response.data.message}`;
        }
        
        alert(errorMessage);
      } finally {
        isLoading.value = false;
      }
    };
    
    const closeModal = () => {
      showModal.value = false;
    };
    
    // 컴포넌트 마운트 시 실행
    onMounted(async () => {
      console.log('ViewDB component mounted');
      await checkAuth();
      await fetchCollections();
    });
    
    return {
      apiBaseUrl,
      isLoading,
      error,
      isAuthenticated,
      userId,
      username,
      selectedCollection,
      collections,
      documents,
      showModal,
      checkAuth,
      fetchCollections,
      viewDb,
      closeModal
    };
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