<template>
  <div class="auth-container">
    <div class="auth-box">
      <div class="auth-tabs">
        <button 
          :class="['tab-btn', { active: currentView === 'login' }]"
          @click="currentView = 'login'"
        >
          로그인
        </button>
        <button 
          :class="['tab-btn', { active: currentView === 'register' }]"
          @click="currentView = 'register'"
        >
          회원가입
        </button>
      </div>

      <!-- 로그인 폼 -->
      <div v-if="currentView === 'login'" class="auth-form">
        <h2>로그인</h2>
        <div class="input-group">
          <input 
            type="text" 
            v-model="loginForm.username" 
            placeholder="아이디"
            @keyup.enter="login"
          >
        </div>
        <div class="input-group">
          <input 
            type="password" 
            v-model="loginForm.password" 
            placeholder="비밀번호"
            @keyup.enter="login"
          >
        </div>
        <div class="remember-me">
          <input 
            type="checkbox" 
            id="remember" 
            v-model="loginForm.rememberMe"
          >
          <label for="remember">자동 로그인</label>
        </div>
        <button @click="login" :disabled="isLoading">
          {{ isLoading ? '로그인 중...' : '로그인' }}
        </button>          
      </div>

      <!-- 회원가입 폼 -->
      <div v-if="currentView === 'register'" class="auth-form">
        <h2>회원가입</h2>
        <div class="input-group">
          <input 
          type="text"
          v-model="registerForm.username"
          @input="$event.target.value = $event.target.value.replace(/[^A-Za-z0-9-_]/g, '')"
          placeholder="아이디"
          title="영어, 숫자, 하이픈(-), 언더스코어(_)만 입력 가능합니다"
          >
        </div>
        <div class="input-group">
          <input 
            type="email" 
            v-model="registerForm.email" 
            placeholder="이메일"
          >
        </div>
        <div class="input-group">
          <input 
            type="password" 
            v-model="registerForm.password" 
            placeholder="비밀번호"
          >
        </div>
        <div class="input-group">
          <input 
            type="password" 
            v-model="registerForm.confirmPassword" 
            placeholder="비밀번호 확인"
          >
        </div>
        <button @click="register" :disabled="isLoading">
          {{ isLoading ? '가입 중...' : '회원가입' }}
        </button>
      </div>       

      <div v-if="error" class="error-message">
        {{ error }}
      </div>
      <div v-if="success" class="success-message">
        {{ success }}
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import axios from 'axios'
import { useStore } from 'vuex';

export default {
  name: 'LogIn',
  emits: ['login-success'],
 
  setup(props, { emit }) {
      const currentView = ref('login')
      const error = ref('')
      const success = ref('')
      const isLoading = ref(false)
      const loginForm = ref({
          username: '',
          password: '',
          rememberMe: false
      })
      const store = useStore();
      const apiBaseUrl = computed(() => store.getters.getApiBaseUrl); 
      const registerForm = ref({
          username: '',
          email: '',
          password: '',
          confirmPassword: ''
      })

      // axios 기본 설정을 setup 내부로 이동
      axios.defaults.withCredentials = true
      axios.defaults.headers.common['Content-Type'] = 'application/json'
      axios.defaults.headers.common['Accept'] = 'application/json'

      // axios 인터셉터 설정도 setup 내부에 배치
      axios.interceptors.request.use(config => {
        const token = sessionStorage.getItem('token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
      })

      axios.interceptors.response.use(
        response => response,
        error => {
            if (error.response?.status === 401) {
                sessionStorage.removeItem('token')
                sessionStorage.removeItem('username')
                sessionStorage.removeItem('user_id')
            }
            return Promise.reject(error)
        }
      )

      const getErrorMessage = (errorCode, message) => {
          switch (errorCode) {
              case 'USER_NOT_FOUND':
                  return '사용자가 존재하지 않습니다. 회원가입을 신청하세요!'
              case 'USER_INACTIVE':
                  return '등록 대기 상태입니다. 관리자에게 문의하세요.'
              case 'INVALID_PASSWORD':
                  return '올바른 비밀번호를 입력하세요!'
              case 'INVALID_CREDENTIALS':
                  return message || '로그인에 실패했습니다.'
              default:
                  return message || '알 수 없는 오류가 발생했습니다.'
          }
      }

      const login = async () => {
          if (!loginForm.value.username || !loginForm.value.password) {
              error.value = '아이디와 비밀번호를 입력해주세요.'
              return
          }

          try {
              isLoading.value = true
              error.value = ''
              const response = await axios.post(`${apiBaseUrl.value}/api/auth/login`, {
                  username: loginForm.value.username,
                  password: loginForm.value.password,
                  remember_me: loginForm.value.rememberMe
              })

              if (response.data.token) {
                  sessionStorage.setItem('token', response.data.token)
                  sessionStorage.setItem('username', response.data.username)
                  sessionStorage.setItem('user_id', response.data.user_id)
                  emit('login-success', response.data.username, response.data.user_id)
              }
          } catch (err) {
              const errorResponse = err.response?.data
              error.value = getErrorMessage(errorResponse?.error_code, errorResponse?.message)
          } finally {
              isLoading.value = false
          }
      }

      const register = async () => {
          if (!registerForm.value.username || !registerForm.value.email || 
              !registerForm.value.password || !registerForm.value.confirmPassword) {
              error.value = '모든 필드를 입력해주세요.'
              return
          }

          if (registerForm.value.password !== registerForm.value.confirmPassword) {
              error.value = '비밀번호가 일치하지 않습니다.'
              return
          }

          try {
              isLoading.value = true
              error.value = ''
              await axios.post(`${apiBaseUrl.value}/api/auth/register`, {
                  username: registerForm.value.username,
                  email: registerForm.value.email,
                  password: registerForm.value.password
              })

              success.value = '회원가입이 완료되었습니다. 로그인해주세요.'
              currentView.value = 'login'
              registerForm.value = {
                  username: '',
                  email: '',
                  password: '',
                  confirmPassword: ''
              }
          } catch (err) {
              const errorResponse = err.response?.data
              error.value = errorResponse?.message || '회원가입에 실패했습니다.'
          } finally {
              isLoading.value = false
          }
      }

      return {
          currentView,
          error,
          success,
          isLoading,
          loginForm,
          registerForm,
          login,
          register,
          apiBaseUrl // 이제 apiBaseUrl을 반환하여 템플릿에서 접근 가능
      }
  }
}
</script>

<style scoped>
.auth-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #000000;
}

.auth-box {
  background-color: #1e1e1e;
  padding: 2rem;
  border-radius: 8px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.auth-tabs {
  display: flex;
  margin-bottom: 2rem;
  border-bottom: 1px solid #333;
}

.tab-btn {
  flex: 1;
  padding: 0.75rem;
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
}

.tab-btn.active {
  color: white;
  border-bottom: 2px solid #1a3a5a;
}

.auth-form h2 {
  color: white;
  text-align: center;
  margin-bottom: 2rem;
}

.input-group {
  margin-bottom: 1rem;
}

input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #333;
  border-radius: 4px;
  background-color: #111;
  color: white;
}

input:focus {
  outline: none;
  border-color: #1a3a5a;
}

.remember-me {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
  color: white;
}

.remember-me input[type="checkbox"] {
  width: auto;
  margin-right: 0.5rem;
}

button {
  width: 100%;
  padding: 0.75rem;
  background-color: #1a3a5a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}

button:hover:not(:disabled) {
  background-color: #2a4a6a;
}

button:disabled {
  background-color: #666;
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