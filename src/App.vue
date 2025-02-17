<!-- App.vue -->
<template>
  <div id="app">
    <div v-if="!isAuthenticated">
      <Login @login-success="onLoginSuccess" />
    </div>

    <div v-else>
      <header class="app-header">
        <div class="user-info">
          {{ username }}님 환영합니다!          
          <button 
            v-if="isAdmin"
            @click="handleAdminManagement" 
            class="admin-btn"
          >
            관리자 페이지
          </button>
          <button @click="showChangePassword = true" class="change-pw-btn">
            비밀번호 변경
          </button>
          <button @click="logout" class="logout-btn">로그아웃</button>
        </div>
      </header>
      
      <!-- 인증된 사용자에게만 RagChat 컴포넌트 노출 -->
      <RagChat v-if="!showAdminManagement" />

      <!-- 관리자 페이지 (동적 임포트) -->
      <component 
        v-if="isAdmin && showAdminManagement"
        :is="adminComponent"
        @close="showAdminManagement = false"
      />

      <ChangePassword 
        v-if="showChangePassword"
        @close="showChangePassword = false"
        @password-changed="handlePasswordChanged"
      />
    </div>
  </div>
</template>

<script>
import { ref, provide, onMounted, shallowRef, defineAsyncComponent } from 'vue'
import axios from 'axios'
import Login from '@/components/LogIn.vue'
import RagChat from '@/components/RagChat.vue'
import ChangePassword from '@/components/ChangePassword.vue'

const API_BASE_URL = 'http://localhost:5001'

export default {
  name: 'App',
  components: {
    Login,
    RagChat,
    ChangePassword
  },

  setup() {
    const isAuthenticated = ref(false)
    const username = ref('')
    const showChangePassword = ref(false)
    const showAdminManagement = ref(false)
    const isAdmin = ref(false)

    // 동적으로 관리자 컴포넌트 로드
    const adminComponent = shallowRef(null)

    // 인증 컨텍스트 제공
    const authContext = ref({
      isAuthenticated: false,
      username: '',
      isAdmin: false
    })

    const checkAuth = async () => {
      try {
        const token = sessionStorage.getItem('token')
        
        if (!token) {
          resetAuth()
          return
        }

        const response = await axios.get('/api/auth/check-auth', {
          headers: {
            'Authorization': `Bearer ${token}`
          },
          withCredentials: true
        })
        
        console.log('Authentication check response:', response.data)
        
        if (response.data.authenticated) {
          authContext.value = {
            isAuthenticated: true,
            username: response.data.username,
            userId: response.data.user_id,
            isAdmin: response.data.is_admin || false
          }

          isAuthenticated.value = true
          username.value = response.data.username
          isAdmin.value = response.data.is_admin || false
        } else {
          resetAuth()
        }
      } catch (error) {
        console.error('Authentication check failed:', error)
        resetAuth()
      }
    }

    const resetAuth = () => {
      sessionStorage.removeItem('token')
      sessionStorage.removeItem('username')
      
      authContext.value = {
        isAuthenticated: false,
        username: '',
        isAdmin: false
      }

      isAuthenticated.value = false
      username.value = ''
      isAdmin.value = false
      showAdminManagement.value = false
      adminComponent.value = null
    }

    const onLoginSuccess = async () => {
      await checkAuth()
    }

    const logout = async () => {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/auth/logout`, {}, {
          withCredentials: true,
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        })

        if (response.data.success) {
          resetAuth()
        }
      } catch (error) {
        console.error('Logout error:', error)
      }
    }

    const handleAdminManagement = async () => {
      if (!adminComponent.value) {
        // 관리자 컴포넌트를 동적으로 임포트
        adminComponent.value = defineAsyncComponent(() => 
          import('@/components/AdminManagement.vue')
        )
      }
      showAdminManagement.value = true      
    }

    const handlePasswordChanged = () => {
      showChangePassword.value = false
    }

    provide('authContext', authContext)

    onMounted(() => {
      checkAuth()
    })

    return {
      isAuthenticated,
      username,
      isAdmin,
      showChangePassword,
      showAdminManagement,
      adminComponent,
      onLoginSuccess,
      logout,
      handlePasswordChanged,
      handleAdminManagement
    }
  }
}
</script>

<style scoped>
.app-header {
  background-color: #1e1e1e;
  padding: 1rem;
  display: flex;
  justify-content: flex-end;
}

.user-info {
  color: white;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.admin-btn {
  padding: 0.5rem 1rem;
  background-color: #4a5568;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-right: 0.5rem;
}

.admin-btn:hover {
  background-color: #2d3748;
}

.change-pw-btn {
  padding: 0.5rem 1rem;
  background-color: #1a3a5a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.change-pw-btn:hover {
  background-color: #2a4a6a;
}

.logout-btn {
  padding: 0.5rem 1rem;
  background-color: #ff6b6b;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.logout-btn:hover {
  background-color: #ff8787;
}
</style>