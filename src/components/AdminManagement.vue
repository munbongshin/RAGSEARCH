<template>
  <div class="admin-management">
    <div class="header">
      <h1 class="title">시스템 관리</h1>
      <button @click="$emit('close')" class="close-button">
        닫기
      </button>
    </div>

    <div class="tab-menu">
      <nav class="tab-nav">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="selectTab(tab.id)"
          :class="['tab-button', { active: currentTab === tab.id }]"
        >
          {{ tab.name }}
        </button>
      </nav>
    </div>

    <div class="tab-content">
      <component 
        v-if="currentComponent"
        :is="currentComponent"
        :users="users"
        @refresh-data="loadData"
      />
    </div>
  </div>
</template>

<script>
import { ref, shallowRef, computed, defineAsyncComponent, onMounted } from 'vue'
import axios from 'axios'
import { useStore} from 'vuex';

export default {
  name: 'AdminManagement',
  
  emits: ['close'],

  setup() {
    const currentTab = ref('users')
    const currentComponent = shallowRef(null)
    const users = ref([])
    const store = useStore();
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);

    // 탭 정의
    const tabs = [
      { id: 'users', name: 'User관리' },
      { id: 'groups', name: '그룹룹관리' },
      { id: 'permissions', name: '이용자 그룹관리' },
      { id: 'collectionPermissions', name: 'Collection 권한관리'}
    ]

    // 컴포넌트 매핑
    const componentMap = {
      users: () => import('@/components/UserManagement.vue'),
      groups: () => import('@/components/GroupsManagement.vue'),
      permissions: () => import('@/components/UserGroupManage.vue'),
      collectionPermissions: () => import('@/components/collectionPermission.vue')
    }

    // 탭 선택 처리
    const selectTab = async (tabId) => {
      currentTab.value = tabId
      currentComponent.value = defineAsyncComponent(componentMap[tabId])
    }

    // 데이터 로딩
    const loadData = async () => {
      try {
        const token = sessionStorage.getItem('token')  

        const usersResponse = await axios.get(`${apiBaseUrl.value}/api/auth/list`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          withCredentials: true
        })
        
        users.value = usersResponse.data.users

      } catch (error) {
        console.error('데이터 로딩 실패:', error)
        
        if (error.response) {
          console.error('Error data:', error.response.data)
          console.error('Error status:', error.response.status)
          
          switch (error.response.status) {
            case 401:
              alert('인증이 만료되었습니다. 다시 로그인해주세요.')
              break
            case 403:
              alert('해당 작업을 수행할 권한이 없습니다.')
              break
            default:
              alert(error.response.data.message || '데이터를 불러오는데 실패했습니다.')
          }
        } else if (error.request) {
          alert('서버와 연결할 수 없습니다. 네트워크 연결을 확인해주세요.')
        } else {
          alert('요청 중 오류가 발생했습니다.')
        }
      }
    }

    onMounted(async () => {
      await loadData()
      // 초기 탭의 컴포넌트만 로드
      await selectTab('users')
    })

    return {
      currentTab,
      currentComponent,
      tabs,
      users,
      selectTab,
      loadData
    }
  }
}
</script>

<style scoped>
.admin-management {
  padding: 1.5rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.title {
  font-size: 1.875rem;
  font-weight: bold;
}

.close-button {
  padding: 0.5rem 1rem;
  background-color: #6b7280;
  color: white;
  border-radius: 0.25rem;
}

.close-button:hover {
  background-color: #4b5563;
}

.tab-menu {
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 1.5rem;
}

.tab-nav {
  display: flex;
  gap: 2rem;
}

.tab-button {
  padding: 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #2563eb;
}

.tab-button:hover {
  background-color: #78fba5;
  color: #d81d1d;
}

.tab-button.active {
  background-color: #2563eb;
  color: white;
}
</style>