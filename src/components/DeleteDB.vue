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
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import { useStore } from 'vuex';

export default {
  name: 'DeleteDB',
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
    const collectionsWithPermissions = ref({});
    
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
      collectionsWithPermissions.value = {};
      
      console.log('컬렉션 목록 조회 시작');
      
      try {
        // 사용자명 확인
        const currentUsername = username.value;
        
        if (!currentUsername) {
          throw new Error('사용자 정보를 확인할 수 없습니다.');
        }

        // 1. user_id 조회 (이미 있는 경우 재사용)
        let currentUserId = userId.value;
        
        if (!currentUserId) {
          const userResponse = await axios.get(`${apiBaseUrl.value}/api/user/id`, {
            params: { username: currentUsername }
          });

          if (!userResponse.data.user_id) {
            throw new Error('사용자 ID를 가져올 수 없습니다.');
          }
          
          currentUserId = userResponse.data.user_id;
          userId.value = currentUserId;
        }
        
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
        if (response.data.success && response.data.collections) {
          const fetchedCollections = response.data.collections;
          
          if (Array.isArray(fetchedCollections) && fetchedCollections.length > 0) {
            const uniqueCollections = new Set();
            const permissionsMap = {};

            for (const collection of fetchedCollections) {
              const [collection_id, collection_name, can_read, can_write, can_delete] = collection;

              if (!collection_name) continue;

              uniqueCollections.add(collection_name);

              permissionsMap[collection_id] = {
                id: collection_id,
                name: collection_name,
                permissions: {
                  read: can_read || false,
                  write: can_write || false,
                  delete: can_delete || false
                }
              };
            }

            // 컬렉션 업데이트
            collections.value = Array.from(uniqueCollections);
            collectionsWithPermissions.value = permissionsMap;

            console.log('처리된 컬렉션:', collections.value);
            console.log('권한 포함 컬렉션:', collectionsWithPermissions.value);
          } else {
            console.warn('조회된 컬렉션이 없습니다.');
            collections.value = [];
            collectionsWithPermissions.value = {};
          }
        } else {
          // 실패 응답 처리
          error.value = response.data.message || '컬렉션을 가져오는 데 실패했습니다.';
          console.error('컬렉션 조회 실패:', error.value);
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
        collectionsWithPermissions.value = {};
      } finally {
        // 로딩 상태 종료
        isLoading.value = false;
      }
    };
    
    const confirmDelete = () => {
      if (selectedCollection.value) {
        if (confirm(`정말로 "${selectedCollection.value}" 컬렉션을 삭제하시겠습니까?`)) {
          deleteDb();
        }
      } else {
        alert('collection을 선택해주세요.');
      }
    };
    
    const deleteDb = async () => {
      try {
        console.log(`Attempting to delete collection: ${selectedCollection.value}`);
        const response = await axios.post(`${apiBaseUrl.value}/api/delete-collection`, { 
          name: selectedCollection.value 
        }, {
          headers: {
            'Authorization': `Bearer ${sessionStorage.getItem('token')}`
          }
        });
        
        console.log('Delete response:', response.data);
        
        if (response.data.success) {
          alert(`컬렉션 "${selectedCollection.value}"이 성공적으로 삭제되었습니다.`);
          fetchCollections(); // 목록 새로고침
          selectedCollection.value = '';
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
    };
    
    // 컴포넌트 마운트 시 실행
    onMounted(async () => {
      console.log('DeleteDB component mounted');
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
      isLoading,
      error,
      isAuthenticated,
      userId,
      username,
      isAdmin,
      selectedCollection,
      collections,
      collectionsWithPermissions,
      checkAuth,
      resetAuth,
      fetchCollections,
      confirmDelete,
      deleteDb
    };
  }
};
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