<!-- SystemMessage.vue -->
<template>
  <div class="container mx-auto p-4">
    <h2 class="text-xl font-semibold mb-4">메세지 관리</h2>
    
    <!-- Action Selector -->
    <div class="mb-6">
      <select v-model="selectedAction" class="custom-style-box">
        <option value="list" class="custom-style">목록보기</option>
        <option value="create" class="custom-style">메시지 작성</option>
     <!--
        <option value="edit" class="custom-style">수정</option>
     -->
        <option value="delete" class="custom-style">메시지 삭제</option>
      </select>
    </div>
    <br>
    <hr class="my-4 border-t border-gray-300">
    <!-- Message List View -->
    <div v-if="selectedAction === 'list'" class="mb-8">      
      <!-- 현재 선택된 메시지 표시 -->
      <div v-if="selectedMessageDetails" class="space-y-2">
          <label class="font-semibold mb-0.5 label-16">현재 선택된 메시지: {{ selectedMessageDetails.name }}</label>                        
          </div>          
       <div v-else class="text-gray-500">
            선택된 메시지 정보를 불러오는 중...
       </div>
      
      <div v-if="messages.length === 0" class="text-gray-500">
        저장된 메시지가 없습니다.
      </div>
      <div v-else class="message-list-container">        
        <h3 class="text-xl font-semibold mb-4">메시지 목록</h3>        
        <div v-for="msg in messages" :key="msg.name" 
             class="custom-style">
          <div class="flex justify-between items-start">
            <div class="flex items-center space-x-3">
              <input 
                type="radio" 
                :id="msg.name" 
                :value="msg.name"
                v-model="selectedMessage"
                class="form-radio h-4 w-4 text-blue-600"
              />            
                <label :for="msg.id" class="font-bold cursor-pointer">제목: {{ msg.name }}</label>
                <p class="custom-style">설명: {{ msg.description }}</p>
              
            </div>       
            
              <button @click="handleEdit(msg)" 
                      class="px-3 py-1 bg-blue-500 text-white rounded">
                수정
              </button>
            
          </div>
          <div class="mt-4 ml-7">            
            <textarea 
              class="custom-message-box"
              readonly
              :value="msg.message"
            ></textarea>
          </div>
          <hr class="my-4 border-t border-gray-300">
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


    <!-- Delete Message View -->
    <div v-if="selectedAction === 'delete'" class="custom-style-box">
      <h3 class="text-xl font-semibold mb-4">삭제</h3>
      <div class="space-y-4">
        <div v-if="messages.length === 0" class="text-gray-500">
          삭제할 메시지가 없습니다.
        </div>
        <div v-else>
          <div class="mb-4">삭제할 메시지를 선택하세요:</div>
          <div class="space-y-2">
            <div v-for="msg in messages" :key="msg.name" 
                 class="flex items-center justify-between p-3 border rounded hover:bg-gray-50">
              <div class="flex items-center space-x-3">
                <input 
                  type="checkbox" 
                  :id="'delete-'+msg.name"
                  v-model="selectedMessagesToDelete"
                  :value="msg.name"
                  class="form-checkbox h-4 w-4 text-red-600"
                />
                <label :for="'delete-'+msg.name" class="cursor-pointer">
                  <span class="font-medium">{{ msg.name }}</span>
                  <span class="text-gray-600 text-sm ml-2">{{ msg.description }}</span>
                </label>
              </div>
            </div>
          </div>
          <div class="mt-6 flex space-x-2">
            <button @click="deleteSelectedMessages" 
                    :disabled="selectedMessagesToDelete.length === 0"
                    class="px-4 py-2 bg-red-500 text-white rounded disabled:opacity-50">
              선택한 메시지 삭제
            </button>
            <button @click="cancelAction" type="button"
                    class="px-4 py-2 bg-gray-500 text-white rounded">
              취소
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Reset Storage Button (항상 표시) 
    <div class="mt-8">
      <button @click="confirmReset"
              class="px-4 py-2 bg-red-500 text-white rounded">
        저장소 초기화
      </button>
    </div>
    -->
  </div>
</template>

<script>
import axios from 'axios';
import { ref, onMounted, watch, computed } from 'vue';

const API_BASE_URL = 'http://localhost:5001/api';

export default {
  setup() {
    const messages = ref([]);
    const selectedMessage = ref('default');
    const selectedAction = ref('list');
    const selectedMessagesToDelete = ref([]);
    const form = ref({
      name: '',
      description: '',
      message: ''
    });
    const isEditing = ref(false);
    const editingMessage = ref(null);

    // setup 내부에 추가
    const selectedMessageContent = computed(() => {
      if (!selectedMessageDetails.value) {
        return null;
      }
      return selectedMessageDetails.value.message;
    });

    const loadMessages = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/messages`);
        if (response.data.success) {
          messages.value = response.data.messages;
          
          // 선택된 메시지 확인 로직 제거 (이제 별도의 API에서 관리)
          if (messages.value.length === 0) {
            selectedMessage.value = '';
          }
        }
      } catch (error) {
        alert('메시지 목록을 불러오는데 실패했습니다.');
        console.error(error);
      }
    };

    const saveMessage = async () => {
      try {
        if (isEditing.value) {
          await axios.put(`${API_BASE_URL}/messages/${editingMessage.value.name}`, {
            name: form.value.name,
            message: form.value.message,
            description: form.value.description
          });
        } else {
          await axios.post(`${API_BASE_URL}/messages`, form.value);
        }
        
        await loadMessages();
        resetForm();
        selectedAction.value = 'list';
      } catch (error) {
        alert('메시지 저장에 실패했습니다.');
        console.error(error);
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
      if (!confirm('정말 삭제하시겠습니까?')) return;
      
      try {
        await axios.delete(`${API_BASE_URL}/messages/${name}`);
        
        // 삭제된 메시지가 현재 선택된 메시지인 경우
        if (selectedMessage.value === name) {
          // 선택된 메시지를 default로 설정
          selectedMessage.value = 'default';
          await saveSelectedMessage('default');
        }
        
        await loadMessages();
      } catch (error) {
        alert('메시지 삭제에 실패했습니다.');
        console.error(error);
      }
    };

    const deleteSelectedMessages = async () => {
      if (selectedMessagesToDelete.value.length === 0) return;
      
      if (!confirm(`선택한 ${selectedMessagesToDelete.value.length}개의 메시지를 삭제하시겠습니까?`)) return;
      
      try {
        // 현재 선택된 메시지가 삭제 대상에 포함되어 있는지 확인
        const isSelectedMessageDeleted = selectedMessagesToDelete.value.includes(selectedMessage.value);
        
        const deletePromises = selectedMessagesToDelete.value.map(name => 
          axios.delete(`${API_BASE_URL}/messages/${name}`)
        );
        
        await Promise.all(deletePromises);
        
        // 선택된 메시지가 삭제된 경우 default로 설정
        if (isSelectedMessageDeleted) {
          selectedMessage.value = 'default';
          await saveSelectedMessage('default');
        }
        
        await loadMessages();
        selectedMessagesToDelete.value = [];
        selectedAction.value = 'list';
        
      } catch (error) {
        alert('메시지 삭제 중 오류가 발생했습니다.');
        console.error(error);
      }
    };

    const confirmReset = async () => {
      if (!confirm('모든 메시지가 삭제됩니다. 계속하시겠습니까?')) return;
      
      try {
        await axios.post(`${API_BASE_URL}/storage/reset`);
        // 저장소 초기화 시 선택된 메시지도 default로 설정
        selectedMessage.value = 'default';
        await saveSelectedMessage('default');
        await loadMessages();
      } catch (error) {
        alert('저장소 초기화에 실패했습니다.');
        console.error(error);
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

    const loadSelectedMessage = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/selected-message`);
        if (response.data.success) {
          selectedMessage.value = response.data.selectedMessage;
        }
      } catch (error) {
        console.error('선택된 메시지 로드 실패:', error);
      }
    };

    const selectedMessageDetails = ref(null);

    // 선택된 메시지의 상세 정보를 가져오는 함수
    const loadSelectedMessageDetails = async () => {
      if (!selectedMessage.value) {
        selectedMessageDetails.value = null;
        return;
      }
      
      try {
        // 현재 메시지 목록에서 선택된 메시지 찾기
        selectedMessageDetails.value = messages.value.find(
          msg => msg.name === selectedMessage.value
        );
      } catch (error) {
        console.error('선택된 메시지 상세 정보 로드 실패:', error);
        selectedMessageDetails.value = null;
      }
    };

    const saveSelectedMessage = async (messageName) => {
      try {
        await axios.post(`${API_BASE_URL}/selected-message`, {
          selectedMessage: messageName
        });
      } catch (error) {
        console.error('선택된 메시지 저장 실패:', error);
      }
    };

    
    onMounted(async () => {
      await loadMessages();  // 먼저 메시지 목록을 로드
      await loadSelectedMessage();  // 선택된 메시지 정보를 로드
      await loadSelectedMessageDetails();  // 선택된 메시지의 상세 정보를 로드
    });

    watch(selectedMessage, async (newVal) => {
      console.log('Selected message:', newVal);
      await saveSelectedMessage(newVal);
      await loadSelectedMessageDetails();
    });

    return {
      messages,
      selectedMessage,
      selectedMessageDetails,
      selectedMessageContent,
      selectedAction,
      selectedMessagesToDelete,
      form,
      handleEdit,
      saveMessage,
      cancelAction,
      deleteMessage,
      deleteSelectedMessages,
      confirmReset,
      formatDate
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