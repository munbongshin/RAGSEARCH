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
         :disabled="!isValidDbName || dbName.trim() === '' || !isAuthenticated"
      >
        생성
      </button>
      <p v-if="!isAuthenticated" class="db-input-error">
        로그인이 필요합니다.
      </p>
    </div>
    <div class="db-list-container">
      <h4>Collection 정보</h4>
      <ul class="db-list">
        <li v-for="collection in collections" :key="collection.id">
          {{ collection.name }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import { useStore } from 'vuex';

export default {
  name: 'CreateDB',
  setup(props, { emit }) {
    const store = useStore();
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);
    const isLoading = ref(false);
    const error = ref(null);

    
    // 인증 관련 상태를 setup 내부로 이동
    const isAuthenticated = ref(false);
    const userId = ref(null);
    const username = ref('');
    const isAdmin = ref(false);
    
    // 데이터 관련 상태
    const dbName = ref('');
    const collections = ref([]);
    const dbNamePattern = /^[a-z0-9가-힣][a-z0-9가-힣\-_ ]{1,61}[a-z0-9가-힣]$/;
    
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
      // sessionStorage에서 토큰을 제거하지는 않습니다(다른 컴포넌트에서 사용 중일 수 있음)
    };
    
    const isValidDbName = computed(() => {
      return dbNamePattern.test(dbName.value) && !dbName.value.includes('..');
    });

    const dbNameErrorMessage = computed(() => {
      if (dbName.value.length < 3 || dbName.value.length > 63) {
        return '컬렉션 이름은 3-63자 사이여야 합니다.';
      }
              
      if (dbName.value.includes('..')) {
        return '컬렉션 이름에 연속된 마침표(..)를 포함할 수 없습니다.';
      }
      return '';
    });
    
    const createDb = async () => {
      if (isValidDbName.value && dbName.value.trim() && isAuthenticated.value) {
        try {
          console.log('Creating collection with name:', dbName.value);
          const response = await axios.post(`${apiBaseUrl.value}/api/create-collection`, {
            name: dbName.value,
            creator: userId.value
          }, {
            headers: {
              'Authorization': `Bearer ${sessionStorage.getItem('token')}`
            }
          });
          
          console.log('Create collection response:', response.data);
          
          if (response.data.success) {
            alert(`컬렉션 "${dbName.value}"가 성공적으로 생성되었습니다.`);
            // 이벤트를 emit할 때는 현재 컴포넌트 내에서 정의된 함수 사용
            emit('collection-created', dbName.value);
            dbName.value = '';
            fetchCollections();
          } else {
            alert(`컬렉션 생성 실패: ${response.data.message}`);
          }
        } catch (error) {
          console.error('컬렉션 생성 중 오류 발생:', error);
          
          // 상세 에러 정보 로깅
          if (error.response) {
            console.error('Error response data:', error.response.data);
            console.error('Error response status:', error.response.status);
          }
          
          alert(`오류 발생: ${error.message}`);
        }
      } else {
        if (!isAuthenticated.value) {
          console.warn('User not authenticated for createDb');
          alert('로그인이 필요합니다.');
        } else if (!isValidDbName.value) {
          console.warn('Invalid database name:', dbName.value);
          alert('유효한 컬렉션 이름을 입력해주세요.');
        }
      }
    };
    
    const fetchCollections = async () => {
      // 로딩 상태 초기화
      isLoading.value = true;
      error.value = null;
      collections.value = [];
      
      console.log('컬렉션 목록 조회 시작');
      
      try {
        // 사용자명 확인 - this 대신 로컬 변수 사용
        const currentUsername = username.value;
        
        if (!currentUsername) {
          throw new Error('사용자 정보를 확인할 수 없습니다.');
        }

        // 1. user_id 조회 - this.apiBaseUrl 대신 apiBaseUrl 사용
        const userResponse = await axios.get(`${apiBaseUrl.value}/api/user/id`, {
          params: { username: currentUsername }
        });

        if (!userResponse.data.user_id) {
          throw new Error('사용자 ID를 가져올 수 없습니다.');
        }

        const currentUserId = userResponse.data.user_id;
        console.log('사용자명:', currentUsername, '사용자 ID:', currentUserId);

        // 2. 컬렉션과 권한 정보 가져오기
        const response = await axios.get(`${apiBaseUrl.value}/api/collections`, {
          params: { 
            username: currentUsername,
            user_id: currentUserId
          },
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        console.log('컬렉션 조회 응답:', response.data);
        
        // 성공적인 응답 처리
        if (response.data.success) {
          const fetchedCollections = response.data.collections;
          
          if (Array.isArray(fetchedCollections) && fetchedCollections.length > 0) {
            // 컬렉션 데이터 가공
            const processedCollections = fetchedCollections.map(collection => ({
              id: collection[0],
              name: collection[1],
              permissions: {
                read: collection[2] || false,
                write: collection[3] || false,
                delete: collection[4] || false
              }
            }));
            
            collections.value = processedCollections;
            console.log(`총 ${processedCollections.length}개의 컬렉션 조회 완료`);
          } else {
            console.warn('조회된 컬렉션이 없습니다.');
            collections.value = [];
          }
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
        
        collections.value = [];
      } finally {
        // 로딩 상태 종료
        isLoading.value = false;
      }
    };
    
    // 컴포넌트 마운트 시 실행
    onMounted(async () => {
      console.log('CreateDB component mounted');
      await checkAuth();
      console.log('Auth check completed, authenticated:', isAuthenticated.value);
      
      if (isAuthenticated.value) {
        await fetchCollections();
      } else {
        console.warn('User not authenticated, cannot fetch collections');
      }
    });
    
    return {
      apiBaseUrl,
      isAuthenticated,
      userId,
      username,
      isAdmin,
      dbName,
      collections,
      isValidDbName,
      dbNameErrorMessage,
      createDb,
      fetchCollections,
      checkAuth,
      resetAuth
    };
  },
  
  // 이벤트 정의
  emits: ['collection-created'],
  
  // Options API의 메서드들은 제거하고 setup에서 정의한 함수들을 사용합니다
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

.db-input-invalid {
  border-color: #ff5555;
}

.db-input-error {
  color: #ff5555;
  margin: 5px 0 10px;
  font-size: 12px;
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

.db-action-button:disabled {
  background-color: #444;
  cursor: not-allowed;
  opacity: 0.7;
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