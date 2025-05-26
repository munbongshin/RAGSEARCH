<!-- SystemMessage.vue -->
<template>
  <div class="container mx-auto p-4">
    <h2 class="text-xl font-semibold mb-4">메세지 관리</h2>
    
    <!-- 인증 관련 메시지 표시 -->
    <div v-if="!isAuthenticated" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
      <strong>로그인이 필요합니다.</strong> 메시지 관리 기능을 사용하려면 로그인해주세요.
    </div>
    
    <div v-else>
      <!-- 사용자 정보 표시 -->
      <div class="mb-4 text-gray-600">
        <span class="font-medium">{{ username }}</span> 님으로 로그인됨
      </div>
      
      <!-- Action Selector -->
      <div class="mb-6">
        <select v-model="selectedAction" class="custom-style-box">
          <option value="list" class="custom-style">목록보기</option>
          <option value="create" class="custom-style">메시지 작성</option>
       <!--
          <option value="edit" class="custom-style">수정</option>
       -->
        </select>
      </div>
      <br>
      <hr class="my-4 border-t border-gray-300">
      
      <!-- Message List View -->
      <div v-if="selectedAction === 'list'" class="mb-8">      
        <!-- 현재 선택된 메시지 표시 - 로컬 데이터에서 직접 가져오기 -->
        <div v-if="selectedMessage && getSelectedMessageName()" class="space-y-2">
            <label class="font-semibold mb-0.5 label-16">현재 선택된 메시지: {{ getSelectedMessageName() }}</label>                        
        </div>          
        <div v-else class="text-gray-500">
            선택된 메시지 정보를 불러오는 중...
        </div>
        
        <div v-if="messages.length === 0" class="text-gray-500">
          저장된 메시지가 없습니다.
        </div>
        
        <div v-else class="message-list-container">        
          <h3 class="text-xl font-semibold mb-4">메시지 목록</h3>        
          <div v-for="msg in messages" :key="msg.id || msg.name" 
              class="custom-style mb-6 p-4 border border-gray-700 rounded">
            <div class="flex justify-between items-start">
              <div class="flex items-center space-x-3">
                <input 
                  type="radio" 
                  :id="'msg-' + msg.id"
                  :value="msg.name"
                  v-model="selectedMessage"
                  @change="handleMessageSelect(msg.name)"
                  class="form-radio h-4 w-4 text-blue-600"
                />            
                <div class="flex flex-col">
                  <label :for="'msg-' + msg.id" class="font-bold cursor-pointer text-lg">{{ msg.name || '제목 없음' }}</label>
                  <p class="text-gray-400 text-sm mt-1">{{ msg.description || '설명 없음' }}</p>
                </div>
              </div>       
              
              <div class="flex space-x-2">
                <button @click="handleEdit(msg)" 
                        class="px-3 py-1 bg-blue-500 text-white rounded">
                  수정
                </button>
                <button @click="deleteMessage(msg.name)" 
                        class="px-3 py-1 bg-red-500 text-white rounded">
                  삭제
                </button>
              </div>
            </div>
            <div class="mt-4 ml-7">
              <p class="text-sm text-gray-400 mb-2">메시지 내용:</p>            
              <textarea 
                class="custom-message-box w-full"
                readonly
                :value="msg.message || '내용 없음'"
              ></textarea>
            </div>
            <hr class="my-4 border-t border-gray-600">
          </div>
        </div>
      </div>

      <!-- Create Message View -->
      <div v-if="selectedAction === 'create'" class="custom-style">
        <h3 class="text-xl font-semibold mb-4">작성</h3>
        <form @submit.prevent="saveMessage" class="space-y-4">
          <div>
            <label class="custom-style">이름: </label>
            <br>  <!-- 줄바꿈 -->
            <input 
              v-model="form.name" 
              required
              class="custom-style" 
            />
          </div>
          <br>  <!-- 줄바꿈 -->
          <div>
            <label class="block mb-2">설명:</label>
            <br>  <!-- 줄바꿈 -->
            <input 
              v-model="form.description"
              class="custom-style" 
            />
          </div>
          <br>  <!-- 줄바꿈 -->
          <div>
            <label class="block mb-2">메시지 내용:</label>
            <br>  <!-- 줄바꿈 -->
            <textarea 
              v-model="form.message" 
              required
              class="custom-message-box"
            ></textarea>
          </div>
          <br>  <!-- 줄바꿈 -->
          <div class="flex space-x-2">
            <button 
              type="submit"
              class="border border-gray-800 px-4 py-1"
            >
              저장
            </button>
            <button 
              @click="cancelAction" 
              type="button"
              class="border border-gray-800 px-4 py-1"
            >
              취소
            </button>
          </div>
        </form>
      </div>

      <!-- Edit Message View -->
      <div v-if="selectedAction === 'edit'" class="custom-style">
        <h3 class="font-bold mb-4">수정</h3>
        <form @submit.prevent="saveMessage">
          <div class="mb-2">
            <div>
              <label class="block mb-2">이름:</label>
              <br>  <!-- 줄바꿈 --> 
                <input 
                  v-model="form.name"
                  class="custom-style" 
                />
            </div>
            <br>  <!-- 줄바꿈 -->          
            <div>
              <label class="block mb-2">설명:</label>
              <br>  <!-- 줄바꿈 --> 
                <input 
                  v-model="form.description"
                  class="custom-style" 
                />
            </div>          
            <br>  <!-- 줄바꿈 -->          
            <div class="mb-1">메시지 내용</div>
            <br>  <!-- 줄바꿈 -->
            <textarea 
              v-model="form.message" 
              required
              class="custom-message-box"
            ></textarea>
          </div>
          <br>  <!-- 줄바꿈 -->
          <div class="flex justify-between border-t pt-2">
            <button 
              type="submit"
              class="border border-gray-800 px-4"
            >
              수정
            </button>
            <button 
              @click="cancelAction" 
              type="button"
              class="border border-gray-800 px-4"
            >
              취소
            </button>
          </div>
        </form>
      </div>

      <!-- 'delete' 액션 삭제 - 이제 각 메시지 항목에 삭제 버튼이 있음 -->
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import { ref, computed, onMounted, watch} from 'vue';
import { useStore} from 'vuex';





export default {
  name: 'SystemMessage',

  setup() {
    // 반응형 변수들 올바르게 초기화
    const messages = ref([]);
    const selectedMessage = ref('');
    const selectedAction = ref('list');
    const selectedMessageDetails = ref(null);
    const store = useStore();  // store 인스턴스 생성
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);
    const form = ref({
      name: '',
      description: '',
      message: ''
    });

    const currentSystemMessage = computed(() => 
      store.getters.getCurrentSystemMessage
    );

    const isEditing = ref(false);
    const editingMessage = ref(null);
    
    // 인증 관련 상태 추가
    const isAuthenticated = ref(false);
    const userId = ref(null);
    const username = ref('');
    const isAdmin = ref(false);

    // 현재 선택된 메시지 이름을 직접 가져오는 함수 추가
    const getSelectedMessageName = () => {
      if (selectedMessage.value) {
        const foundMessage = messages.value.find(msg => msg.name === selectedMessage.value);
        if (foundMessage) {
          return foundMessage.name;
        }
        return selectedMessage.value;
      }
      return null;
    };

    // 현재 선택된 메시지 본문을 가져오는 함수 추가
    const getSelectedMessageContent = () => {
      if (selectedMessage.value) {
        const foundMessage = messages.value.find(msg => msg.name === selectedMessage.value);
        if (foundMessage) {
          return foundMessage.message;
        }
      }
      if (selectedMessageDetails.value && selectedMessageDetails.value.message) {
        return selectedMessageDetails.value.message;
      }
      return null;
    };

    // 메시지 선택 처리 함수 추가
    const handleMessageSelect = async (name) => {
      // 기존 로직 유지
      try {
        // 선택된 메시지 저장
        await saveSelectedMessage(name);
        
        // 선택된 메시지 정보 로드
        await loadSelectedMessage(name);

        // Vuex 스토어에 현재 선택된 메시지 업데이트
        store.dispatch('updateCurrentSystemMessage', selectedMessageDetails.value);
      } catch (error) {
        console.error('메시지 선택 처리 중 오류 발생:', error);
      }
    };

    // 사용자의 현재 선택된 메시지 정보 불러오기
    const loadCurrentSelectedMessage = async () => {
      try {
        const token = sessionStorage.getItem('token');
        if (!token || !isAuthenticated.value) {
          throw new Error('Not authenticated');
        }
        
        const response = await axios.post(`${apiBaseUrl.value}/api/get_current_selected_message`, 
          { user_id: userId.value },
          { 
            timeout: 5000,  // 5-second timeout
            headers: { 'Authorization': `Bearer ${token}` }
          }
        );
        
        const selectedMessageData = response.data?.data;
        
        if (selectedMessageData && selectedMessageData.name) {
          const foundMessage = messages.value.find(msg => msg.name === selectedMessageData.name);
          
          if (foundMessage) {
            selectedMessage.value = selectedMessageData.name;
            await loadSelectedMessage(selectedMessageData.name);
            return true;
          } else {
            console.warn(`Message '${selectedMessageData.name}' not found in local list`);
            return false;
          }
        } else {
          console.log('No selected message found');
          return false;
        }
      } catch (error) {
        console.error('Failed to load current selected message:', error);
        return false;
      }
    };

    // 인증 확인 함수
    const checkAuth = async () => {
      try {
        const token = sessionStorage.getItem('token');
        
        if (!token) {
          resetAuth();
          return;
        }

        const response = await axios.get(`${apiBaseUrl.value}/api/auth/check-auth`, {
          headers: {
            'Authorization': `Bearer ${token}`
          },
          withCredentials: true
        });
        
        if (response.data.authenticated) {
          isAuthenticated.value = true;
          username.value = response.data.username;
          userId.value = response.data.user_id;
          isAdmin.value = response.data.is_admin || false;
        } else {
          resetAuth();
        }
      } catch (error) {
        console.error('Authentication check failed:', error);
        resetAuth();
      }
    };
    
    // 인증 정보 초기화
    const resetAuth = () => {
      isAuthenticated.value = false;
      username.value = '';
      userId.value = null;
      isAdmin.value = false;
      sessionStorage.removeItem('token');
    };

    const loadMessages = async () => {
      try {
        const token = sessionStorage.getItem('token');
        if (!token || !isAuthenticated.value) {
          return;
        }
        
        const response = await axios.post(`${apiBaseUrl.value}/api/get_system_message_list`, {
          user_id: userId.value
        });
        
        if (response.data && response.data.data && Array.isArray(response.data.data)) {
          messages.value = response.data.data.map(msg => ({
            name: msg.name,
            message: msg.message,
            description: msg.description || '',
            id: msg.id,
          }));
          
          const hasSelectedMessage = await loadCurrentSelectedMessage();
          
          if (!hasSelectedMessage && messages.value.length > 0 && !selectedMessage.value) {
            console.log('선택된 메시지가 없어 첫 번째 메시지를 자동 선택합니다.');
            selectedMessage.value = messages.value[0].name;
            await loadSelectedMessage(messages.value[0].name);
          }
        }


      } catch (error) {
        console.error('메시지 목록을 불러오는데 실패했습니다:', error);
        alert('메시지 목록을 불러오는데 실패했습니다.');
      }
    };

    const saveMessage = async () => {
      try {
        const token = sessionStorage.getItem('token');
        if (!token || !isAuthenticated.value) {
          alert('로그인이 필요합니다.');
          return;
        }
        
        if (isEditing.value) {
          await axios.post(`${apiBaseUrl.value}/api/update_system_message`, {
            name: form.value.name,
            message: form.value.message,
            description: form.value.description,
            user_id: userId.value
          });
        } else {
          await axios.post(`${apiBaseUrl.value}/api/save_system_message`, {
            name: form.value.name,
            message: form.value.message,
            description: form.value.description,
            user_id: userId.value
          });
        }
        
        await loadMessages();
        resetForm();
        selectedAction.value = 'list';
      } catch (error) {
        console.error('메시지 저장 실패:', error);
        alert('메시지 저장에 실패했습니다.');
      }
    };

    const handleEdit = (message) => {
      isEditing.value = true;
      editingMessage.value = message;
      form.value = { ...message };
      selectedAction.value = 'edit';
    };

    const cancelAction = () => {
      isEditing.value = false;
      editingMessage.value = null;
      resetForm();
      selectedAction.value = 'list';
    };

    const deleteMessage = async (name) => {
      if (!confirm(`"${name}" 메시지를 정말 삭제하시겠습니까?`)) return;
      
      try {
        const token = sessionStorage.getItem('token');
        if (!token || !isAuthenticated.value) {
          alert('로그인이 필요합니다.');
          return;
        }
        
        await axios.post(`${apiBaseUrl.value}/api/delete_system_message`, {
          user_id: userId.value,
          name: name
        });
        
        if (selectedMessage.value === name) {
          selectedMessage.value = 'default';
          await saveSelectedMessage('default');
        }
        
        await loadMessages();
        
        console.log(`메시지 "${name}" 삭제 완료`);
        
      } catch (error) {
        console.error('메시지 삭제 실패:', error);
        alert('메시지 삭제에 실패했습니다.');
      }
    };

    const resetForm = () => {
      form.value = {
        name: '',
        description: '',
        message: ''
      };
      isEditing.value = false;
      editingMessage.value = null;
    };

    const formatDate = (dateStr) => {
      return new Date(dateStr).toLocaleString();
    };

    // 선택된 메시지 정보를 가져오는 함수
    const loadSelectedMessage = async (name) => {
      try {
        const messageName = name || selectedMessage.value;
        
        if (!messageName) {
          console.warn('메시지 이름이 제공되지 않았습니다.');
          return;
        }

        console.log(`[loadSelectedMessage] 메시지 정보 로드 시작: ${messageName}`);

        const token = sessionStorage.getItem('token');
        if (!token || !isAuthenticated.value) {
          console.warn('인증 토큰이 없거나 인증되지 않은 상태입니다.');
          return;
        }

        // 로컬 메시지 데이터로 먼저 설정
        const localMessage = messages.value.find(msg => msg.name === messageName);
        if (localMessage) {
          console.log('[loadSelectedMessage] 로컬 메시지 데이터 사용:', localMessage);
          selectedMessageDetails.value = { ...localMessage };
        }

        try {
          const response = await axios.post(`${apiBaseUrl.value}/api/get_system_message`, {
            name: messageName,
            user_id: userId.value
          });

          console.log('[loadSelectedMessage] 서버 응답:', response.data);

          // 서버 응답 처리 로직 개선
          if (response.data && response.data.data && response.data.data.length > 0) {
            const messageData = response.data.data[0];  // 배열의 첫 번째 항목 사용
            console.log('[loadSelectedMessage] 메시지 데이터 찾음:', messageData);
            
            selectedMessageDetails.value = {
              id: messageData.id || localMessage?.id,
              name: messageData.name || localMessage?.name,
              message: messageData.message || localMessage?.message,
              description: messageData.description || localMessage?.description
            };
            
            console.log('[loadSelectedMessage] selectedMessageDetails 업데이트됨:', selectedMessageDetails.value);
          } else {
            // 서버 응답이 없으면 로컬 메시지 유지
            console.warn('[loadSelectedMessage] 서버에서 유효한 데이터를 찾을 수 없음');
          }

          // Vuex 스토어에 시스템 메시지 업데이트
          if (selectedMessageDetails.value) {
            store.dispatch('updateCurrentSystemMessage', selectedMessageDetails.value);
          }

        } catch (apiError) {
          console.error('[loadSelectedMessage] API 호출 오류:', apiError);
          // API 호출 실패 시 로컬 메시지 유지
        }
      } catch (error) {
        console.error('[loadSelectedMessage] 전체 함수 실행 오류:', error);
      }
    };

    const saveSelectedMessage = async (messageName) => {
      try {
        const token = sessionStorage.getItem('token');
        if (!token || !isAuthenticated.value) {
          return;
        }
        
        await axios.post(`${apiBaseUrl.value}/api/save_selected_message`, {
          user_id: userId.value,
          name: messageName
        });
      } catch (error) {
        console.error('선택된 메시지 저장 실패:', error);
      }
    };

    onMounted(async () => {
      console.log('컴포넌트 마운트 시작');
      await checkAuth();
      console.log('인증 확인 완료, 인증 상태:', isAuthenticated.value);
      
      if (isAuthenticated.value) {
        await loadMessages();
        console.log('메시지 목록 및 현재 선택된 메시지 로드 완료');
      }
    });

    // selectedMessage 변경 시 자동 처리
    watch(selectedMessage, async (newVal) => {
      if (isAuthenticated.value && newVal) {
        console.log('Selected message changed:', newVal);
        await saveSelectedMessage(newVal);
        await loadSelectedMessage(newVal);
      }
    });

    return {
      messages,
      selectedMessage,
      selectedMessageDetails,
      selectedAction,
      form,
      isAuthenticated,
      username,
      userId,
      isAdmin,
      handleEdit,
      handleMessageSelect,
      saveMessage,
      cancelAction,
      deleteMessage,
      formatDate,
      getSelectedMessageName,
      getSelectedMessageContent,
      loadCurrentSelectedMessage,
      currentSystemMessage
    };
  }
}
</script>

<style>
.form-radio {
  cursor: pointer;
}

.form-radio:checked {
  background-color: #2563eb;
  border-color: #2563eb;
}

.form-checkbox {
  cursor: pointer;
}

.form-checkbox:checked {
  background-color: #dc2626;
  border-color: #dc2626;
}

.input, textarea {
  outline: none;
}
.button {
  background: #e0e0e0;
}
.button:active {
  background: #c0c0c0;
}

.select option {
  background-color: black !important;
  color: white !important;
}

.custom-style {
    background-color: black;
    color: white;
    font-size: 15px;
}
.custom-style-box {
    background-color: black;
    color: white;
    width: 150px;  /* 박스 너비 */
    height: 30px; /* 박스 높이 */
    font-size: 16px; /* 폰트 크기 */
}

.custom-message-box {
    background-color: black;
    color: white;
    width: 240px;  /* 박스 너비 */
    height: 200px; /* 박스 높이 */
    font-size: 15px; /* 폰트 크기 */
}

.message-list-container {
    background-color: #1f2937;  /* 회색 배경 */
    padding: 1rem;
    border-radius: 0.5rem;
}

</style>