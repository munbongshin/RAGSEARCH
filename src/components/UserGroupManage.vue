<template>
  <div class="container">
    <div class="user-list">
      <h2>사용자 목록</h2>
      <div class="user-items">
        <div v-for="user in users" 
             :key="user.id" 
             :class="['user-item', { active: selectedUser?.id === user.id }]"
             @click="selectUser(user)">
          <div class="user-info">
            <div class="username">{{ user.username }}</div>
            <div class="email">{{ user.email }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="right-panel">
      <!-- 그룹 관리 버튼 -->
      <div class="group-management">
        <div class="header-container">
          <h2>그룹 관리</h2>
          <button @click="showModal = true" class="action-button add">
            그룹 추가
          </button>
        </div>
      </div>

      <!-- 그룹 추가 모달 -->
      <div v-if="showModal" class="modal-overlay">
        <div class="modal-content">
          <h3>새 그룹 추가</h3>
          <div class="form-group">
            <label for="groupName">그룹명</label>
            <input 
              type="text" 
              id="groupName" 
              v-model="groupName"
              placeholder="그룹명 입력"
              class="form-input"
            >
          </div>
          <div class="form-group">
            <label for="groupDesc">설명</label>
            <input 
              type="text" 
              id="groupDesc" 
              v-model="groupDesc"
              placeholder="그룹 설명 입력"
              class="form-input"
            >
          </div>
          <div class="modal-actions">
            <button @click="createGroup" class="action-button save" :disabled="!groupName">저장</button>
            <button @click="showModal = false" class="action-button cancel">취소</button>
          </div>
        </div>
      </div>

      <!-- 할당된 그룹 섹션 -->
      <div class="user-groups">
        <div class="header-container">
          <h2>할당된 그룹</h2>
          <button 
            @click="saveUserGroups" 
            :disabled="!selectedUser || !hasChanges"
            class="action-button save">
            저장
          </button>
        </div>
        <div v-if="selectedUser">
          <div v-if="loading" class="loading">로딩 중...</div>
          <template v-else>
            <div class="table-structure">
              <div class="table-header">
                <div class="header-cell checkbox-cell">선택</div>
                <div class="header-cell">그룹명</div>
                <div class="header-cell">설명</div>
              </div>
              
              <div class="table-body">
                <div v-for="group in assignedGroups" 
                    :key="group.id" 
                    class="table-row">
                    <div class="cell checkbox-cell">
                    <input 
                      type="checkbox" 
                      :checked="selectedAvailableGroups.includes(group.id)"
                      @change="(event) => toggleAvailableGroup(event, group.id)"
                      class="standard-checkbox"
                    >
                  </div>
                  <div class="cell">{{ group.name }}</div>
                  <div class="cell">{{ group.description }}</div>
                </div>
                <div v-if="assignedGroups.length === 0" class="no-groups">
                  할당된 그룹이 없습니다.
                </div>
              </div>
            </div>
          </template>
        </div>
        <div v-else class="no-selection">
          사용자를 선택해주세요.
        </div>
      </div>

      <!-- 그룹 이동 버튼 -->
      <div class="button-group">
        <button 
          @click="moveGroupsUp" 
          :disabled="!selectedUser || selectedAvailableGroups.length === 0"
          class="action-button">
          위로
        </button>
        <button 
          @click="moveGroupsDown" 
          :disabled="!selectedUser || selectedAssignedGroups.length === 0"
          class="action-button">
          아래로
        </button>          
      </div>

      <!-- 이용 가능한 그룹 섹션 -->
      <div class="available-groups">
        <h2>이용자 그룹</h2>
        <div class="group-table">
          <div class="table-header">
            <div class="header-cell checkbox-cell">선택</div>
            <div class="header-cell name-cell">그룹명</div>
            <div class="header-cell description-cell">설명</div>
          </div>
          
          <div class="group-items">
            <div v-if="loading" class="loading">로딩 중...</div>
            <template v-else>
              <div v-for="group in availableGroups" 
                  :key="group.id" 
                  class="table-row">
                <div class="cell checkbox-cell">
                  <input 
                    type="checkbox" 
                    :checked="selectedAvailableGroups.includes(group.id)"
                    @change="(event) => toggleAvailableGroup(event, group.id)"
                    :disabled="!selectedUser"
                    class="standard-checkbox"
                  >
                </div>
                <div class="cell name-cell">{{ group.name }}</div>
                <div class="cell description-cell">{{ group.description }}</div>
              </div>
              <div v-if="availableGroups.length === 0" class="no-groups">
                이용 가능한 그룹이 없습니다.
              </div>
            </template>
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
  name: 'UserGroupManagement',
  
  props: {
    users: {
      type: Array,
      default: () => []
    }
  },
  
  emits: ['refresh-data'],
  
  setup(props, { emit }) {
    const store = useStore();
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);

    // 기본 상태 관리
    const loading = ref(false);
    const allGroups = ref([]);
    const assignedGroups = ref([]);
    const originalAssignedGroups = ref([]);
    const selectedUser = ref(null);

    // 체크박스 선택 상태 - 단순 배열 사용
    const selectedAssignedGroups = ref([]);
    const selectedAvailableGroups = ref([]);

    // 그룹 추가 모달 상태
    const showModal = ref(false);
    const groupName = ref('');
    const groupDesc = ref('');

    // 체크박스 토글 함수
    const toggleAssignedGroup = (event, groupId) => {
      const isChecked = event.target.checked;
      
      if (isChecked) {
        selectedAssignedGroups.value.push(groupId);
      } else {
        selectedAssignedGroups.value = selectedAssignedGroups.value.filter(id => id !== groupId);
      }
      console.log('할당된 그룹 선택 상태:', selectedAssignedGroups.value);
    };

    const toggleAvailableGroup = (event, groupId) => {
      const isChecked = event.target.checked;
      
      if (isChecked) {
        selectedAvailableGroups.value.push(groupId);
      } else {
        selectedAvailableGroups.value = selectedAvailableGroups.value.filter(id => id !== groupId);
      }
      console.log('가용 그룹 선택 상태:', selectedAvailableGroups.value);
    };

    // 이용 가능한 그룹 (사용자에게 할당되지 않은 그룹들)
    const availableGroups = computed(() => {
      const assignedGroupIds = assignedGroups.value.map(g => g.id);
      return allGroups.value.filter(group => !assignedGroupIds.includes(group.id));
    });

    // 변경 사항이 있는지 확인
    const hasChanges = computed(() => {
      if (!originalAssignedGroups.value.length && !assignedGroups.value.length) return false;
      
      const originalIds = originalAssignedGroups.value.map(g => g.id).sort().join(',');
      const currentIds = assignedGroups.value.map(g => g.id).sort().join(',');
      
      return originalIds !== currentIds;
    });

    // 사용자 선택
    const selectUser = async (user) => {
      // 사용자 설정 및 로딩 상태 변경
      selectedUser.value = user;
      loading.value = true;
      
      try {
        // 데이터 로드 후 초기화
        await fetchUserGroups(user.id);
        selectedAssignedGroups.value = [];
        selectedAvailableGroups.value = [];
      } catch (error) {
        console.error('사용자 그룹 로딩 실패:', error);
      } finally {
        loading.value = false;
      }
    };

    // 모든 그룹 목록 조회
    const fetchAllGroups = async () => {
      loading.value = true;
      try {
        const token = sessionStorage.getItem('token');
        const response = await axios.get(`${apiBaseUrl.value}/api/auth/groups`, {
          headers: {
            'Authorization': `Bearer ${token}`
          },
          withCredentials: true
        });
        
        if (response.data && response.data.groups) {
          allGroups.value = response.data.groups;
        } else {
          console.error('그룹 데이터를 불러올 수 없습니다.');
          allGroups.value = [];
        }
      } catch (error) {
        console.error('그룹 조회 실패:', error);
        allGroups.value = [];
      } finally {
        loading.value = false;
      }
    };

    // 사용자의 그룹 목록 조회
    const fetchUserGroups = async (userId) => {
      if (!userId) return;
      
      try {
        const token = sessionStorage.getItem('token');
        const response = await axios.post(
          `${apiBaseUrl.value}/api/auth/users/grouplist`, 
          { user_id: parseInt(userId) },
          {
            headers: {
              'Authorization': `Bearer ${token}`
            },
            withCredentials: true
          }
        );
        
        if (response.data && Array.isArray(response.data)) {
          assignedGroups.value = response.data;
          originalAssignedGroups.value = JSON.parse(JSON.stringify(response.data));
        } else {
          assignedGroups.value = [];
          originalAssignedGroups.value = [];
        }
      } catch (error) {
        console.error('사용자 그룹 조회 실패:', error);
        assignedGroups.value = [];
        originalAssignedGroups.value = [];
      }
    };

    // 그룹 추가
    const createGroup = async () => {
      if (!groupName.value) {
        alert('그룹명을 입력해주세요.');
        return;
      }
      
      loading.value = true;
      try {
        const token = sessionStorage.getItem('token');
        const response = await axios.post(
          `${apiBaseUrl.value}/api/auth/groups/create`,
          {
            name: groupName.value,
            description: groupDesc.value || ''
          },
          {
            headers: {
              'Authorization': `Bearer ${token}`
            },
            withCredentials: true
          }
        );
        
        if (response.data && response.data.success) {
          // 모달 닫기 및 입력 초기화
          showModal.value = false;
          groupName.value = '';
          groupDesc.value = '';
          
          // 그룹 목록 새로고침
          await fetchAllGroups();
          alert('그룹이 성공적으로 추가되었습니다.');
        } else {
          throw new Error(response.data?.message || '그룹 추가에 실패했습니다.');
        }
      } catch (error) {
        console.error('그룹 추가 실패:', error);
        alert(error.response?.data?.message || error.message || '그룹 추가 중 오류가 발생했습니다.');
      } finally {
        loading.value = false;
      }
    };

    // 그룹 위로 이동 (사용 가능한 그룹 -> 할당된 그룹)
    const moveGroupsUp = () => {
      if (!selectedUser.value || selectedAvailableGroups.value.length === 0) return;

      // 선택된 ID에 해당하는 그룹 객체 찾기
      const groupsToAdd = allGroups.value.filter(group => 
        selectedAvailableGroups.value.includes(group.id)
      );
      
      // 할당된 그룹에 추가
      assignedGroups.value = [...assignedGroups.value, ...groupsToAdd];
      
      // 선택 상태 초기화
      selectedAvailableGroups.value = [];
    };

    // 그룹 아래로 이동 (할당된 그룹 -> 사용 가능한 그룹)
    const moveGroupsDown = () => {
      if (!selectedUser.value || selectedAssignedGroups.value.length === 0) return;

      // 선택된 그룹들을 제외한 나머지 그룹들만 유지
      assignedGroups.value = assignedGroups.value.filter(
        group => !selectedAssignedGroups.value.includes(group.id)
      );
      
      // 선택 상태 초기화
      selectedAssignedGroups.value = [];
    };

    // 변경사항 저장
    const saveUserGroups = async () => {
      if (!selectedUser.value) {
        alert('사용자를 선택해주세요.');
        return;
      }

      // 현재 할당된 그룹의 ID 목록 생성
      const groupIds = assignedGroups.value.map(group => group.id);

      loading.value = true;
      try {
        const token = sessionStorage.getItem('token');
        const requestData = {
          user_id: selectedUser.value.id,
          group_ids: groupIds
        };

        const response = await axios.post(
          `${apiBaseUrl.value}/api/auth/users/savegroups`, 
          requestData,
          {
            headers: {
              'Authorization': `Bearer ${token}`
            },
            withCredentials: true
          }
        );
        
        if (response.data && response.data.success) {
          originalAssignedGroups.value = JSON.parse(JSON.stringify(assignedGroups.value));
          alert('그룹 설정이 성공적으로 저장되었습니다.');
          emit('refresh-data');
        } else {
          throw new Error(response.data?.message || '그룹 저장에 실패했습니다.');
        }
      } catch (error) {
        console.error('그룹 저장 실패:', error);
        alert(error.response?.data?.message || error.message || '그룹 저장 중 오류가 발생했습니다.');
      } finally {
        loading.value = false;
      }
    };

    // 컴포넌트 마운트 시 데이터 로드
    onMounted(async () => {
      await fetchAllGroups();
    });

    // 템플릿에서 사용할 값 및 함수 반환
    return {
      loading,
      assignedGroups,
      selectedUser,
      selectedAssignedGroups,
      selectedAvailableGroups,
      availableGroups,
      hasChanges,
      showModal,
      groupName,
      groupDesc,
      selectUser,
      moveGroupsUp,
      moveGroupsDown,
      saveUserGroups,
      createGroup,
      toggleAssignedGroup,
      toggleAvailableGroup
    };
  }
}
</script>

<style scoped>
.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.action-button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.2s;
}

.action-button.save {
  background-color: #40c057;
  color: white;
}

.action-button.add {
  background-color: #228be6;
  color: white;
}

.action-button.cancel {
  background-color: #e9ecef;
  color: #343a40;
}

.action-button:hover:not(:disabled) {
  opacity: 0.9;
}

.action-button:disabled {
  background-color: #adb5bd;
  cursor: not-allowed;
}

.container {
  display: flex;
  gap: 2rem;
  padding: 1rem;
  height: calc(100vh - 2rem);
}
  
.user-list {
  flex: 1;
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1rem;
}
  
.right-panel {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
  
.user-groups,
.available-groups,
.group-management {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1rem;
}
  
.user-groups {
  flex: 1;
}
  
.available-groups {
  flex: 1;
}

.group-management {
  padding-bottom: 0.5rem;
}
  
h2 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.2rem;
}

h3 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.1rem;
}
  
.user-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
  
.user-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}
  
.user-item:hover {
  background: #e9ecef;
}
  
.user-item.active {
  background: #e7f5ff;
  border-left: 4px solid #339af0;
}
  
.user-info .username {
  font-weight: 600;
}
  
.user-info .email {
  font-size: 0.9rem;
  color: #666;
}
  
.no-selection,
.no-groups {
  text-align: center;
  color: #868e96;
  padding: 2rem;
}
  
input[type="checkbox"]:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.button-group {
  display: flex;
  justify-content: center;
  gap: 1rem;
  padding: 1rem;
}

.table-header {
  display: grid;
  grid-template-columns: 50px 1fr 2fr;
  background-color: #f3f4f6;
  border-bottom: 1px solid #e5e7eb;
}

.header-cell {
  padding: 12px;
  font-weight: bold;
  color: #374151;
}

.table-row {
  display: grid;
  grid-template-columns: 50px 1fr 2fr;
  border-bottom: 1px solid #e5e7eb;
}

.table-row:last-child {
  border-bottom: none;
}

.cell {
  padding: 12px;
  display: flex;
  align-items: center;
}

.checkbox-cell {
  display: flex;
  justify-content: center;
  align-items: center;
}

input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #339af0;
}

.loading {
  padding: 20px;
  text-align: center;
  color: #6b7280;
}

/* Modal 스타일 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}

.modal-content {
  background-color: white;
  padding: 24px;
  border-radius: 8px;
  width: 400px;
  max-width: 90%;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-weight: 500;
  color: #333;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 24px;
}
</style>