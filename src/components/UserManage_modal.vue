<!-- src/components/UserManagement.vue -->
<template>
  <div class="modal-backdrop">
    <div class="modal-content">
      <div class="modal-header">
        <h2>사용자 관리</h2>
        <button class="close-btn" @click="$emit('close')">&times;</button>
      </div>

      <div class="user-management">
        <div class="controls">
          <div class="filters">
            <select v-model="activeFilter" class="filter-select">
              <option value="all">전체 사용자</option>
              <option value="true">활성 사용자</option>
              <option value="false">비활성 사용자</option>
            </select>
          </div>
          <div class="bulk-actions">
            <button 
              @click="updateAllUsers(true)"
              class="activate-all-btn"
            >
              전체 활성화
            </button>
            <button 
              @click="updateAllUsers(false)"
              class="deactivate-all-btn"
            >
              전체 비활성화
            </button>
          </div>
        </div>

        <div class="summary" v-if="!loading && users.length > 0">
          <p>활성 사용자: {{ activeUsers }}명</p>
          <p>비활성 사용자: {{ inactiveUsers }}명</p>
        </div>

        <div v-if="loading" class="loading">
          <div class="loading-text">데이터 로딩 중...</div>
        </div>

        <div v-else class="users-table">
          <table>
            <thead>
              <tr>
                <th>
                  <input 
                    type="checkbox" 
                    :checked="allSelected"
                    @change="handleSelectAll"
                  >
                </th>
                <th>사용자명</th>
                <th>이메일</th>
                <th>그룹</th>
                <th>상태</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>
                  <input 
                    type="checkbox"
                    :checked="isSelected(user.id)"
                    @change="(event) => handleSelect(user.id, event)"
                  >
                </td>
                <td>{{ user.username }}</td>
                <td>{{ user.email }}</td>
                <td>{{ getGroupName(user.group_id) }}</td>
                <td>
                  <span :class="['status-badge', user.is_active ? 'active' : 'inactive']">
                    {{ user.is_active ? '활성' : '비활성' }}
                  </span>
                </td>
                <td>
                  <button 
                    @click="updateUserStatus([user.id], !user.is_active)"
                    :class="user.is_active ? 'deactivate-btn' : 'activate-btn'"
                  >
                    {{ user.is_active ? '비활성화' : '활성화' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="selected-actions" v-if="selectedUsers.length > 0">
          <button 
            @click="updateSelectedUsers(true)"
            class="activate-selected-btn"
          >
            선택 활성화 ({{ selectedUsers.length }})
          </button>
          <button 
            @click="updateSelectedUsers(false)"
            class="deactivate-selected-btn"
          >
            선택 비활성화 ({{ selectedUsers.length }})
          </button>
        </div>

        <div v-if="message" :class="['message', messageType]">
          {{ message }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

const API_BASE_URL = 'http://localhost:5001'

export default {
  name: 'UserManagement',
  emits: ['close'],
  
  setup() {
    const users = ref([])
    const selectedUsers = ref([])
    const activeFilter = ref('all')
    const message = ref('')
    const messageType = ref('')
    const loading = ref(false)
    const totalUserCount = ref(0)
    const activeUserCount = ref(0)
    const groups = ref({})
    

    // 전체 선택 상태 계산
    const allSelected = computed(() => {
      return users.value.length > 0 && selectedUsers.value.length === users.value.length
    })

    // 개별 사용자 선택 여부 확인
    const isSelected = (userId) => {
      return selectedUsers.value.includes(userId)
    }

    const handleSelectAll = (event) => {
      if (event.target.checked) {
        // 전체 선택
        selectedUsers.value = users.value.map(user => user.id)
      } else {
        // 전체 해제
        selectedUsers.value = []
      }
    }


    // 개별 선택/해제 처리
    const handleSelect = (userId, event) => {  // event 매개변수 추가
      
      const checked = event.target.checked
      if (checked) {
        selectedUsers.value = Array.from(new Set([...selectedUsers.value, userId]))
      } else {
        selectedUsers.value = selectedUsers.value.filter(id => id !== userId)
      }
    }

    const activeUsers = computed(() => {
      return users.value.filter(user => user.is_active).length
    })

    const inactiveUsers = computed(() => {
      return users.value.filter(user => !user.is_active).length
    })
    
    // loadUsers 함수 수정
    const loadUsers = async () => {
      try {
        loading.value = true
        const token = sessionStorage.getItem('token')
        
        const response = await axios.get(`${API_BASE_URL}/api/auth/list`, { 
          headers: {
            'Authorization': `Bearer ${token}`,
          },
          withCredentials: true
        })

        if (response.data.success) {
          const { users: usersList } = response.data.data
          
          // id 필드명 사용
          users.value = usersList.map(user => ({
            id: user.id,  
            username: user.username,
            email: user.email,
            is_active: user.is_active,
            group_id: user.group_id
          }))
          
          if (activeFilter.value !== 'all') {
            const isActive = activeFilter.value === 'true'
            users.value = users.value.filter(user => user.is_active === isActive)
          }
        }
      } catch (err) {
        showMessage('사용자 목록을 불러오는데 실패했습니다.', 'error')
      } finally {
        loading.value = false
      }
    }
    // getGroupName 함수 수정
    const getGroupName = (groupId) => {
      if (!groups.value.groups) return '알 수 없음';
      const group = groups.value.groups[groupId];
      return group ? `${group.description}` : '알 수 없음';
    }

    // 그룹 데이터를 가져오는 함수 추가
    const loadGroups = async () => {
      try {
        const token = sessionStorage.getItem('token')
        const response = await axios.get(`${API_BASE_URL}/api/auth/groups`, {
          headers: {
            'Authorization': `Bearer ${token}`
          },
          withCredentials: true
        })

        if (response.data.success) {
          groups.value = response.data.data
          
          const groupData = response.data.data.groups.reduce((acc, group) => {
            acc[group.id] = group
            return acc
          }, {})
          groups.value.groups = groupData
          console.log('Loaded groups data:', groups.value) // 디버깅용
          
        }
      } catch (err) {
        console.error('Error loading groups:', err)
      }
    }

    const updateUserStatus = async (userIds, isActive) => {
      try {
        const token = sessionStorage.getItem('token')
        const response = await axios.post(
          `${API_BASE_URL}/api/auth/update-status`,
          {
            user_ids: userIds,
            is_active: isActive
          },
          { 
            headers: {
              'Authorization': `Bearer ${token}`
            },
            withCredentials: true 
          }
        )
        
        if (response.data.success) {
          showMessage(`${userIds.length}명의 사용자 상태가 변경되었습니다.`, 'success')
          await loadUsers()
        } else {
          showMessage(response.data.message, 'error')
        }
      } catch (err) {
        showMessage(err.response?.data?.message || '상태 변경 실패', 'error')
      }
    }

    const updateAllUsers = async (isActive) => {
      if (!confirm(`모든 사용자를 ${isActive ? '활성화' : '비활성화'} 하시겠습니까?`)) {
        return
      }

      try {
        const token = sessionStorage.getItem('token')
        const response = await axios.post(
          `${API_BASE_URL}/api/auth/bulk-update`,
          { is_active: isActive },
          { 
            headers: {
              'Authorization': `Bearer ${token}`
            },
            withCredentials: true 
          }
        )
        
        if (response.data.success) {
          showMessage('모든 사용자의 상태가 변경되었습니다.', 'success')
          await loadUsers()
        } else {
          showMessage(response.data.message, 'error')
        }
      } catch (err) {
        showMessage(err.response?.data?.message || '일괄 변경 실패', 'error')
      }
    }

    const updateSelectedUsers = (isActive) => {
      if (selectedUsers.value.length === 0) {
        showMessage('선택된 사용자가 없습니다.', 'error')
        return
      }

      if (!confirm(`선택한 사용자를 ${isActive ? '활성화' : '비활성화'} 하시겠습니까?`)) {
        return
      }
      showMessage('선택된 사용자 전환성공')
      updateUserStatus(selectedUsers.value, isActive)
    }

    const toggleAllUsers = (event) => {
      if (event.target.checked) {
        // 전체 선택
        selectedUsers.value = users.value.map(u => u.id)
      } else {
        // 전체 선택 해제
        selectedUsers.value = []
      }
    }

    const toggleUser = (userId) => {
      const index = selectedUsers.value.indexOf(userId)
      if (index === -1) {
        // 선택되지 않은 경우 추가
        selectedUsers.value.push(userId)
      } else {
        // 이미 선택된 경우 제거
        selectedUsers.value.splice(index, 1)
      }
    }

    const showMessage = (msg, type = 'success') => {
      message.value = msg
      messageType.value = type
      setTimeout(() => {
        message.value = ''
      }, 3000)
    }

    watch(activeFilter, () => {
      loadUsers()
    })

    onMounted(() => {
      loadUsers()
      loadGroups()
    })

    return {
      users,
      selectedUsers,
      allSelected,
      isSelected,
      activeFilter,
      message,
      messageType,
      loading,
      activeUsers,
      inactiveUsers,
      getGroupName,
      groups,
      updateUserStatus,
      updateAllUsers,
      updateSelectedUsers,
      toggleAllUsers,
      toggleUser,
      totalUserCount,
      activeUserCount,
      handleSelectAll,
      handleSelect
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
  align-items: start;
  z-index: 1000;
  padding-top: 2rem;
}

.modal-content {
  background-color: #1e1e1e;
  border-radius: 8px;
  width: 90%;
  max-width: 1200px;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
  position: relative;
}

.modal-header {
  background-color: #1e1e1e;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  border-bottom: 1px solid #333;
}

.modal-header h2 {
  color: white;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 1.5rem;
  cursor: pointer;
}

.close-btn:hover {
  color: white;
}

.user-management {
  padding: 2rem;
}

.controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  gap: 1rem;
}

.filter-select {
  padding: 0.5rem;
  border-radius: 4px;
  border: 1px solid #333;
  background-color: #2d3748;
  color: white;
  min-width: 150px;
}

.users-table {
  margin-top: 1rem;
  margin-bottom: 2rem;
  overflow: hidden;
  background-color: #1e1e1e;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

table {
  width: 100%;
  border-collapse: collapse;
  color: white;
  background-color: #1e1e1e;
}

thead tr {
  background-color: #2d3748;
  border-bottom: 2px solid #4a5568;
}

th {
  background-color: #2d3748;
  color: white;
  font-weight: 500;
  text-align: left;
  padding: 1rem;
  border-bottom: none;
}

td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #4a5568;
}

th:first-child,
td:first-child {
  width: 40px;
  text-align: center;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: white;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 500;
  text-align: center;
  display: inline-block;
  min-width: 80px;
}

.status-badge.active {
  background-color: #2f855a;
  color: white;
}

.status-badge.inactive {
  background-color: #c53030;
  color: white;
}

tbody tr:hover {
  background-color: #2d3748;
}

.summary {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background-color: #2d3748;
  border-radius: 4px;
  color: white;
  display: flex;
  gap: 2rem;
}

.summary p {
  margin: 0;
}

button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.3s;
}

.activate-btn,
.activate-all-btn,
.activate-selected-btn {
  background-color: #2c5282;
  color: white;
}

.activate-btn:hover,
.activate-all-btn:hover,
.activate-selected-btn:hover {
  background-color: #2b6cb0;
}

.deactivate-btn,
.deactivate-all-btn,
.deactivate-selected-btn {
  background-color: #c53030;
  color: white;
}

.deactivate-btn:hover,
.deactivate-all-btn:hover,
.deactivate-selected-btn:hover {
  background-color: #e53e3e;
}

.message {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 4px;
  text-align: center;
  color: white;
}
/* 이전 스타일에 이어서 추가 */

.message.success {
  background-color: #2f855a;
}

.message.error {
  background-color: #c53030;
}

.selected-actions {
  margin-top: 1rem;
  display: flex;
  gap: 1rem;
}

.bulk-actions {
  display: flex;
  gap: 0.5rem;
}

.bulk-actions button {
  white-space: nowrap;
}

@media (max-width: 768px) {
  .modal-content {
    width: 95%;
    margin: 0.5rem;
  }

  .controls {
    flex-direction: column;
  }

  .filters,
  .bulk-actions {
    width: 100%;
  }

  .bulk-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .users-table {
    overflow-x: auto;
  }

  .summary {
    flex-direction: column;
    gap: 0.5rem;
  }

  .selected-actions {
    flex-direction: column;
  }

  th, td {
    padding: 0.5rem;
  }

  .status-badge {
    min-width: 60px;
    padding: 0.25rem 0.5rem;
  }
}

/* 체크박스 스타일링 */
input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #2c5282;
}

/* 스크롤바 스타일링 */
.modal-content::-webkit-scrollbar {
  width: 8px;
}

.modal-content::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.modal-content::-webkit-scrollbar-thumb {
  background-color: #4a5568;
  border-radius: 4px;
}

.modal-content::-webkit-scrollbar-thumb:hover {
  background-color: #718096;
}

/* 테이블 스크롤바 */
.users-table::-webkit-scrollbar {
  height: 8px;
}

.users-table::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.users-table::-webkit-scrollbar-thumb {
  background-color: #4a5568;
  border-radius: 4px;
}

.users-table::-webkit-scrollbar-thumb:hover {
  background-color: #718096;
}

</style>