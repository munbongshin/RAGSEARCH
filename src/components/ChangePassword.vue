<template>
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-content">
        <h2>비밀번호 변경</h2>
        
        <form @submit.prevent="changePassword">
          <div class="form-group">
            <input
              type="password"
              v-model="form.currentPassword"
              placeholder="현재 비밀번호"
              required
            >
          </div>
          <div class="form-group">
            <input
              type="password"
              v-model="form.newPassword"
              placeholder="새 비밀번호"
              required
            >
          </div>
          <div class="form-group">
            <input
              type="password"
              v-model="form.confirmPassword"
              placeholder="새 비밀번호 확인"
              required
            >
          </div>
          
          <div v-if="error" class="error-message">
            {{ error }}
          </div>
          <div v-if="success" class="success-message">
            {{ success }}
          </div>
  
          <div class="button-group">
            <button type="submit" :disabled="isLoading">
              {{ isLoading ? '변경 중...' : '변경' }}
            </button>
            <button type="button" @click="$emit('close')">
              취소
            </button>
          </div>
        </form>
      </div>
    </div>
  </template>
  
  <script>
  import { ref,computed} from 'vue'
  import axios from 'axios'
  import { useStore} from 'vuex';



  export default {
    name: 'ChangePassword',
    emits: ['close', 'password-changed'],
    setup(props, { emit }) {
      const form = ref({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      })

      const store = useStore();
      const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);
      
      const error = ref('')
      const success = ref('')
      const isLoading = ref(false)
  
      const changePassword = async () => {
        if (form.value.newPassword !== form.value.confirmPassword) {
          error.value = '새 비밀번호가 일치하지 않습니다.'
          return
        }
  
        if (form.value.newPassword.length < 6) {
          error.value = '비밀번호는 6자 이상이어야 합니다.'
          return
        }
  
        try {
          isLoading.value = true
          error.value = ''
  
          await axios.post(`${apiBaseUrl.value}/api/auth/change-password`, {
            currentPassword: form.value.currentPassword,
            newPassword: form.value.newPassword
          })
  
          success.value = '비밀번호가 성공적으로 변경되었습니다.'
          emit('password-changed')
          
          // 3초 후 모달 닫기
          setTimeout(() => {
            emit('close')
          }, 3000)
        } catch (err) {
          error.value = err.response?.data?.message || '비밀번호 변경에 실패했습니다.'
        } finally {
          isLoading.value = false
        }
      }
  
      return {
        form,
        error,
        success,
        isLoading,
        apiBaseUrl,
        changePassword
      }
    }
  }
  </script>
  
  <style scoped>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
  }
  
  .modal-content {
    background-color: #1e1e1e;
    padding: 2rem;
    border-radius: 8px;
    width: 90%;
    max-width: 400px;
  }
  
  h2 {
    color: white;
    text-align: center;
    margin-bottom: 1.5rem;
  }
  
  .form-group {
    margin-bottom: 1rem;
  }
  
  input {
    width: 100%;
    padding: 0.75rem;
    background-color: #333;
    border: 1px solid #444;
    border-radius: 4px;
    color: white;
  }
  
  input:focus {
    outline: none;
    border-color: #1a3a5a;
  }
  
  .button-group {
    display: flex;
    gap: 1rem;
    margin-top: 1.5rem;
  }
  
  button {
    flex: 1;
    padding: 0.75rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
  }
  
  button[type="submit"] {
    background-color: #1a3a5a;
    color: white;
  }
  
  button[type="submit"]:hover:not(:disabled) {
    background-color: #2a4a6a;
  }
  
  button[type="button"] {
    background-color: #333;
    color: white;
  }
  
  button[type="button"]:hover {
    background-color: #444;
  }
  
  button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
  
  .error-message {
    color: #ff6b6b;
    margin-top: 1rem;
    text-align: center;
  }
  
  .success-message {
    color: #51cf66;
    margin-top: 1rem;
    text-align: center;
  }
  </style>