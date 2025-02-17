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
        <div class="user-groups">
          <div class="header-container">
            <h2>할당된 그룹</h2>
            <button 
              @click="saveGroups" 
              :disabled="!selectedUser || !hasChanges"
              class="action-button save">
              저장
            </button>
          </div>
          <div v-if="selectedUser">
            <div v-if="isLoading" class="loading">로딩 중...</div>
            <template v-else>
              <!-- Table Header -->
              <div class="table-structure">
                <div class="table-header">
                  <div class="header-cell checkbox-cell"></div>
                  <div class="header-cell">그룹명</div>
                  <div class="header-cell">설명</div>
                </div>
                
                <!-- Table Body -->
                <div class="table-body">
                  <div v-for="group in userGroups" 
                      :key="group.id" 
                      class="table-row">
                    <div class="cell checkbox-cell">
                      <label class="checkbox-container">
                        <input type="checkbox" 
                              :checked="isUserGroupSelected(group)"
                              @change="toggleUserGroupSelection(group)">
                        <span class="checkmark"></span>
                      </label>
                    </div>
                    <div class="cell">{{ group.name }}</div>
                    <div class="cell">{{ group.description }}</div>
                  </div>
                  <div v-if="userGroups.length === 0" class="no-groups">
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

        <div class="button-group">
            <button 
            @click="moveUp" 
            :disabled="!selectedUser || selectedAvailableGroups.length === 0"
            class="action-button">
            위로
            </button>
            <button 
            @click="moveDown" 
            :disabled="!selectedUser || selectedUserGroups.length === 0"
            class="action-button">
            아래로
            </button>          
        </div>

        <div class="available-groups">
          <h2>이용자 그룹</h2>
          <div class="group-table">
            <!-- Table Header -->
            <div class="table-header">
              <div class="header-cell checkbox-cell"></div>
              <div class="header-cell name-cell">그룹명</div>
              <div class="header-cell description-cell">설명</div>
            </div>
            
            <!-- Table Body -->
            <div class="group-items">
              <div v-if="isLoading" class="loading">로딩 중...</div>
              <template v-else>
                <div v-for="group in availableGroups" 
                    :key="group.id" 
                    class="table-row">
                  <div class="cell checkbox-cell">
                    <label class="checkbox-container">
                      <input type="checkbox" 
                            :checked="isAvailableGroupSelected(group)"
                            @change="toggleAvailableGroupSelection(group)"
                            :disabled="!selectedUser">
                      <span class="checkmark"></span>
                    </label>
                  </div>
                  <div class="cell name-cell">{{ group.name }}</div>
                  <div class="cell description-cell">{{ group.description }}</div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, defineProps, toRefs, defineEmits } from 'vue';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

const props = defineProps({
  users: {
    type: Array,
    default: () => []
  }
});

const { users } = toRefs(props);
const emit = defineEmits(['refresh-data']);

const groups = ref([]);
const userGroups = ref([]);
const selectedUser = ref(null);
const isLoading = ref(false);
const originalUserGroups = ref([]);

// 상태 관리
const availableGroupsState = ref([]);
const userGroupsState = ref([]);

// 체크박스 선택 상태 확인을 위한 헬퍼 함수들
const isUserGroupSelected = (group) => {
  return userGroupsState.value.some(g => g.id === group.id);
};

const isAvailableGroupSelected = (group) => {
  return availableGroupsState.value.some(g => g.id === group.id);
};

const isGroupAssigned = (group) => {
  return userGroups.value.some(g => g.id === group.id);
};

const availableGroups = computed(() => {
  return groups.value
    .filter(group => !isGroupAssigned(group))
    .map(group => ({
      ...group,
      selected: availableGroupsState.value.some(g => g.id === group.id)
    }));
});

const selectedAvailableGroups = computed(() => 
  availableGroupsState.value
);

const selectedUserGroups = computed(() => 
  userGroupsState.value
);

const toggleAvailableGroupSelection = (group) => {
  if (!selectedUser.value) return;
  
  const index = availableGroupsState.value.findIndex(g => g.id === group.id);
  
  if (index !== -1) {
    availableGroupsState.value = availableGroupsState.value.filter(g => g.id !== group.id);
  } else {
    availableGroupsState.value.push({ ...group });
  }
};

const toggleUserGroupSelection = (group) => {
  const index = userGroupsState.value.findIndex(g => g.id === group.id);
  
  if (index !== -1) {
    userGroupsState.value = userGroupsState.value.filter(g => g.id !== group.id);
  } else {
    userGroupsState.value.push({ ...group });
  }
};

const moveUp = () => {
  if (!selectedUser.value || selectedAvailableGroups.value.length === 0) return;

  // 선택된 사용 가능한 그룹들을 userGroups에 추가
  const updatedUserGroups = [...userGroups.value];
  selectedAvailableGroups.value.forEach(group => {
    if (!updatedUserGroups.some(g => g.id === group.id)) {
      updatedUserGroups.push({ ...group });
    }
  });
  userGroups.value = updatedUserGroups;

  // 선택 상태 초기화
  availableGroupsState.value = [];
};

const moveDown = () => {
  if (!selectedUser.value || selectedUserGroups.value.length === 0) return;

  // 선택된 그룹들을 userGroups에서 제거
  userGroups.value = userGroups.value.filter(
    group => !selectedUserGroups.value.some(g => g.id === group.id)
  );

  // 선택 상태 초기화
  userGroupsState.value = [];
};

const hasChanges = computed(() => {
  if (!originalUserGroups.value.length && !userGroups.value.length) return false;
  
  const originalIds = originalUserGroups.value.map(g => g.id).sort();
  const currentIds = userGroups.value.map(g => g.id).sort();
  
  return JSON.stringify(originalIds) !== JSON.stringify(currentIds);
});

const fetchGroups = async () => {
  isLoading.value = true;
  try {
    const response = await axios.get(`${API_BASE_URL}/api/auth/groups`);
    
    if (response.data && response.data.groups) {
      groups.value = response.data.groups;
    } else {
      throw new Error('데이터를 불러올 수 없습니다.');
    }
  } catch (error) {
    console.error('그룹 조회 실패:', error);
    groups.value = [];
  } finally {
    isLoading.value = false;
  }
};

const fetchUserGroups = async (userId) => {
  if (!userId) return;
  
  isLoading.value = true;
  try {
    const response = await axios.post(`${API_BASE_URL}/api/auth/users/grouplist`, {
      user_id: parseInt(userId)
    });
    
    if (response.data && Array.isArray(response.data)) {
      userGroups.value = response.data.map(group => ({
        ...group,
        checked: false
      }));
      originalUserGroups.value = JSON.parse(JSON.stringify(userGroups.value));
    } else {
      userGroups.value = [];
      originalUserGroups.value = [];
    }
  } catch (error) {
    console.error('사용자 그룹 조회 실패:', error);
    userGroups.value = [];
    originalUserGroups.value = [];
  } finally {
    isLoading.value = false;
  }
};

const selectUser = async (user) => {
  selectedUser.value = user;
  availableGroupsState.value = [];
  userGroupsState.value = [];
  await fetchUserGroups(user.id);
};

const saveGroups = async () => {
  if (!selectedUser.value) {
    alert('사용자를 선택해주세요.');
    return;
  }

  // 현재 할당된 그룹의 ID 목록 생성
  const groupIds = userGroups.value
    .map(group => group.id)
    .filter(id => id != null && id !== undefined);

  if (groupIds.length === 0 && userGroups.value.length > 0) {
    alert('유효한 그룹 ID가 없습니다.');
    return;
  }

  isLoading.value = true;
  try {
    const requestData = {
      user_id: selectedUser.value.id,
      group_ids: groupIds
    };

    console.log('저장 요청 데이터:', requestData); // 디버깅용

    const response = await axios.post(
      `${API_BASE_URL}/api/auth/users/savegroups`, 
      requestData
    );
    
    if (response.data && response.data.success) {
      originalUserGroups.value = JSON.parse(JSON.stringify(userGroups.value));
      alert('그룹 설정이 성공적으로 저장되었습니다.');
      emit('refresh-data');
    } else {
      throw new Error(response.data?.message || '그룹 저장에 실패했습니다.');
    }
  } catch (error) {
    console.error('그룹 저장 실패:', error);
    const errorMessage = error.response?.data?.message || 
                        error.message || 
                        '그룹 저장 중 오류가 발생했습니다.';
    alert(errorMessage);
  } finally {
    isLoading.value = false;
  }
};

onMounted(async () => {
  await fetchGroups();
});
</script>
  
<style scoped>
.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.action-button.save {
  padding: 8px 16px;
  background-color: #40c057;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.action-button.save:hover:not(:disabled) {
  background-color: #1d4ed8;
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
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
  
.user-groups,
.available-groups {
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
  
h2 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.2rem;
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
  
.status {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  background: #e9ecef;
}
  
.status.active {
  background: #d3f9d8;
  color: #2b8a3e;
}
  
.group-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
  
.group-item {
  display: flex;
  align-items: center;
  padding: 0.5rem;
  background: white;
  border-radius: 4px;
}
  
.group-description {
  margin-left: 0.5rem;
  font-size: 0.9rem;
  color: #666;
}
  
  
.no-selection,
.no-groups {
  text-align: center;
  color: #868e96;
  padding: 2rem;
}
  
  
input[type="checkbox"]:disabled + .checkmark {
  opacity: 0.5;
  cursor: not-allowed;
}


.button-group {
  display: flex;
  justify-content: center;
  gap: 1rem;
  padding: 1rem;
}

.action-button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  background-color: #339af0;
  color: white;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.action-button:disabled {
  background-color: #adb5bd;
  cursor: not-allowed;
}

.action-button:hover:not(:disabled) {
  background-color: #228be6;
}

.available-groups {
  width: 100%;
}

.group-table {
  border: 1px solid #e5e7eb;
  border-radius: 4px;
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
  opacity: 0;
  cursor: pointer;
  height: 0;
  width: 0;
}


.loading {
  padding: 20px;
  text-align: center;
  color: #6b7280;
}

.group-item {
  margin: 8px 0;
}

.checkbox-container {
  display: flex;
  align-items: center;
  position: relative;
  padding-left: 30px;
  cursor: pointer;
}


.checkbox-container input {
  position: absolute;
  opacity: 0;
  cursor: pointer;
  height: 0;
  width: 0;
}

.checkmark {
  position: absolute;
  left: 0;
  height: 20px;
  width: 20px;
  background-color: #fff;
  border: 1px solid #010101e1;
  border-radius: 4px;
}

.checkmark::after {
  content: "";
  position: absolute;
  display: none;
  left: 6px;
  top: 2px;
  width: 6px;
  height: 12px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

/* 체크박스가 체크되었을 때 배경색 변경 및 체크마크 표시 */
.checkbox-container input:checked ~ .checkmark {
  background-color: #2563eb;
  border-color: #2563eb;
}

/* 체크박스가 체크되었을 때 V 표시 나타나게 함 */
.checkbox-container input:checked ~ .checkmark::after {
  display: block;
}

.label-text {
  margin-left: 10px;
}
</style>