<template>
  <div class="permission-container">
    <!-- 좌측 Collection 목록 -->
    <div class="collection-list">
      <h2>Collection 목록</h2>
      <div class="items">
        <div v-for="collection in collections" 
             :key="collection.id"
             :class="['collection-item', { active: selectedCollection === collection.id }]"
             @click="selectCollection(collection.id)">
          <div class="item-content">
            <div class="name">{{ collection.name }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 우측 권한 관리 패널 -->
    <div class="right-panel">
      <!-- 할당된 그룹 섹션 -->
      <div class="assigned-groups">
        <div class="header-container">
          <h2>할당된 그룹</h2>
          <button 
            @click="saveGroups" 
            :disabled="!selectedCollection || !hasChanges"
            class="action-button save">
            저장
          </button>
        </div>
        
        <div v-if="selectedCollection">
          <div v-if="isLoading" class="loading">로딩 중...</div>
          <template v-else>
            <div class="group-table">
              <div class="table-header">
                <div class="header-cell checkbox-cell"></div>
                <div class="header-cell">그룹명</div>                
                <div class="header-cell">권한</div>
                <div class="header-cell">설명</div>
              </div>
              <div class="table-body">
                <template v-if="userGroups && userGroups.length > 0">
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
                    <div class="cell permissions-cell">
                      <div class="permissions-checkboxes">
                        <div class="permission-item">
                          <label class="permission-checkbox-container">
                            <input type="checkbox" 
                                  v-model="group.permissions.read"
                                  @change="updatePermissions(group)">
                            <span class="checkmark"></span>
                            <span class="permission-label">읽기</span>
                          </label>
                        </div>                      
                        <div class="permission-item">
                          <label class="permission-checkbox-container">
                            <input type="checkbox" 
                                  v-model="group.permissions.write"
                                  @change="updatePermissions(group)">
                            <span class="checkmark"></span>
                            <span class="permission-label">쓰기</span>
                          </label>
                        </div>
                        <div class="permission-item">
                          <label class="permission-checkbox-container">
                            <input type="checkbox" 
                                  v-model="group.permissions.delete"
                                  @change="updatePermissions(group)">
                            <span class="checkmark"></span>
                            <span class="permission-label">삭제</span>
                          </label>
                        </div>
                      </div>
                    </div>
                    <div class="cell">{{ group.description }}</div>
                  </div>
                </template>
                <div v-else class="no-groups">
                  할당된 그룹이 없습니다.
                </div>
              </div>
            </div>
          </template>
        </div>
        <div v-else class="no-selection">
          Collection을 선택해주세요.
        </div>
      </div>

      <!-- 이동 버튼 그룹 -->
      <div class="button-group">
        <button 
          @click="moveUp" 
          :disabled="!selectedCollection || selectedAvailableGroups.length === 0"
          class="action-button">
          위로
        </button>
        <button 
          @click="moveDown" 
          :disabled="!selectedCollection || selectedUserGroups.length === 0"
          class="action-button">
          아래로
        </button>
      </div>

      <!-- User 그룹 섹션 -->
      <div class="available-groups">
        <h2>이용자그룹</h2>
        <div class="group-table">
          <div class="table-header">
            <div class="header-cell checkbox-cell"></div>
            <div class="header-cell">그룹명</div>
            <div class="header-cell">설명</div>
          </div>
          <div class="table-body">
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
                           :disabled="!selectedCollection">
                    <span class="checkmark"></span>
                  </label>
                </div>
                <div class="cell">{{ group.name }}</div>
                <div class="cell">{{ group.description }}</div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>



<script>
import { inject, ref, computed, onMounted } from 'vue';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

export default {
  name: 'CollectionPermission',
  emits: ['refresh-data'],
  
  setup(props, { emit }) {
    const collections = ref([]);
    const selectedCollection = ref(null);
    const userGroups = ref([]);
    const availableGroups = ref([]);
    const isLoading = ref(false);
    const originalUserGroups = ref([]);
    const userGroupsState = ref([]);
    const availableGroupsState = ref([]);
    const authContext = inject('authContext')

    const selectedAvailableGroups = computed(() => availableGroupsState.value);
    const selectedUserGroups = computed(() => userGroupsState.value);

    const hasChanges = computed(() => {
      if (!originalUserGroups.value.length && !userGroups.value.length) return false;
      
      // 그룹 ID 비교
      const originalIds = originalUserGroups.value.map(g => g.id).sort();
      const currentIds = userGroups.value.map(g => g.id).sort();
      
      // 그룹 구성이 변경되었는지 확인
      if (JSON.stringify(originalIds) !== JSON.stringify(currentIds)) {
        return true;
      }
      
      // 권한 변경 확인
      return userGroups.value.some(currentGroup => {
        const originalGroup = originalUserGroups.value.find(g => g.id === currentGroup.id);
        if (!originalGroup) return true;
        
        return (
          currentGroup.permissions.read !== originalGroup.permissions.read ||
          currentGroup.permissions.write !== originalGroup.permissions.write ||
          currentGroup.permissions.delete !== originalGroup.permissions.delete
        );
      });
    });

    const loadCollections = async () => {
      try {
        const username = authContext.value.username
        console.log('Fetching collections for username:', username)

        const userResponse = await axios.get(`${API_BASE_URL}/api/user/id`, {
          params: { username }
        })

        console.log('User ID response:', userResponse.data)
        const userId = userResponse.data.user_id

        const response = await axios.get(`${API_BASE_URL}/api/collections`, {
          params: { user_id: userId },
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.data.success) {
          collections.value = response.data.collections.map(collection => ({
            id: collection[0],            
            name: collection[1]
          }));           
        } else {
          console.error('컬렉션 조회 실패:', response.data.message);
          collections.value = [];
        }
      } catch (error) {
        console.error('컬렉션 fetching 에러:', error);
        collections.value = [];
      }
    };

    const selectCollection = async (collectionId) => {
      selectedCollection.value = collectionId;
      userGroupsState.value = [];
      availableGroupsState.value = [];
      await loadCollectionGroups(collectionId);
    };

    const loadCollectionGroups = async (collectionId) => {
      isLoading.value = true;
      
      try {
        // 1. 사용 가능한 그룹 로드
        const availableResponse = await axios.get(`${API_BASE_URL}/api/auth/groups`);
        let allGroups = [];
        if (availableResponse.data?.groups) {
          allGroups = availableResponse.data.groups;
        }

        // 2. 할당된 그룹 정보 로드
        const response = await axios.post(
          `${API_BASE_URL}/api/auth/permissionlist`,
          { collection_id: collectionId },
          { headers: { 'Content-Type': 'application/json' } }
        );

        console.log('Permission list response:', response.data);

        if (response.data.success && response.data.groups) {
          // 실제 그룹 데이터 추출
          let groupsData = [];
          if (Array.isArray(response.data.groups)) {
            // response.data.groups가 배열인 경우, 각 요소의 groups 배열을 확인
            groupsData = response.data.groups.flatMap(item => 
              Array.isArray(item.groups) ? item.groups : [item]
            );
          } else if (response.data.groups.groups) {
            // 단일 객체이고 내부에 groups 배열이 있는 경우
            groupsData = response.data.groups.groups;
          } else {
            // 직접 그룹 데이터인 경우
            groupsData = [response.data.groups];
          }

          console.log('추출된 그룹 데이터:', groupsData);

          const assignedGroups = groupsData
            .filter(group => group && group.id)
            .map(group => ({
              id: group.id,
              name: group.name,
              description: group.description,
              permissions: {
                read: group.permissions?.read ?? true,
                write: group.permissions?.write ?? false,
                delete: group.permissions?.delete ?? false
              }
            }));

          console.log('매핑된 그룹:', assignedGroups);

          // 할당된 그룹이 있는 경우만 설정
          if (assignedGroups.length > 0) {
            userGroups.value = assignedGroups;
            originalUserGroups.value = JSON.parse(JSON.stringify(assignedGroups));

            // 할당된 그룹 ID 목록
            const assignedGroupIds = new Set(assignedGroups.map(group => group.id));
            // 사용 가능한 그룹 필터링
            availableGroups.value = allGroups.filter(group => !assignedGroupIds.has(group.id));
          } else {
            userGroups.value = [];
            originalUserGroups.value = [];
            availableGroups.value = allGroups;
          }

          console.log('최종 userGroups:', userGroups.value);
        }
      } catch (error) {
        console.error('그룹 로딩 실패:', error);
        userGroups.value = [];
        originalUserGroups.value = [];
        availableGroups.value = [];
      } finally {
        isLoading.value = false;
      }
    };

    const isUserGroupSelected = (group) => {
      return userGroupsState.value.some(g => g.id === group.id);
    };

    const isAvailableGroupSelected = (group) => {
      return availableGroupsState.value.some(g => g.id === group.id);
    };

    const toggleUserGroupSelection = (group) => {
      const index = userGroupsState.value.findIndex(g => g.id === group.id);
      
      if (index !== -1) {
        userGroupsState.value = userGroupsState.value.filter(g => g.id !== group.id);
      } else {
        userGroupsState.value.push({ ...group });
      }
    };

    const toggleAvailableGroupSelection = (group) => {
      const index = availableGroupsState.value.findIndex(g => g.id === group.id);
      
      if (index !== -1) {
        availableGroupsState.value = availableGroupsState.value.filter(g => g.id !== group.id);
      } else {
        availableGroupsState.value.push({ ...group });
      }
    };

    const moveUp = () => {
      try {
        if (!selectedCollection.value || selectedAvailableGroups.value.length === 0) return;
        
        // 선택된 사용 가능한 그룹들을 userGroups에 추가
        const updatedUserGroups = [...userGroups.value];
        selectedAvailableGroups.value.forEach(group => {
          if (!updatedUserGroups.some(g => g.id === group.id)) {
            updatedUserGroups.push({
              ...group,
              permissions: {
                read: true,
                write: false,
                delete: false
              }
            });
          }
        });

        // userGroups 업데이트
        userGroups.value = updatedUserGroups;
        
        // availableGroups에서 선택된 그룹들 제거
        availableGroups.value = availableGroups.value.filter(
          group => !selectedAvailableGroups.value.some(g => g.id === group.id)
        );
        
        // 선택 상태 초기화
        availableGroupsState.value = [];
      } catch (error) {
        console.error('이동 실패:', error);
        alert(error.response?.data?.message || '이동에 실패했습니다.');
      }
    };

    const moveDown = () => {
      try {
        if (!selectedCollection.value || selectedUserGroups.value.length === 0) return;
        
        // 선택된 그룹들을 availableGroups로 이동
        const movedGroups = selectedUserGroups.value.map(group => ({
          id: group.id,
          name: group.name,
          description: group.description
        }));
        
        availableGroups.value = [...availableGroups.value, ...movedGroups];
        
        // userGroups에서 선택된 그룹들 제거
        userGroups.value = userGroups.value.filter(
          group => !selectedUserGroups.value.some(g => g.id === group.id)
        );
        
        // 선택 상태 초기화
        userGroupsState.value = [];
      } catch (error) {
        console.error('이동 실패:', error);
        alert(error.response?.data?.message || '이동에 실패했습니다.');
      }
    };

    const saveGroups = async () => {
      if (!selectedCollection.value) {
        alert('Collection을 선택해주세요.');
        return;
      }

      const groups = userGroups.value
        .map(group => ({
          group_id: group.id,
          permissions: group.permissions
        }))
        .filter(group => group.group_id != null && group.group_id !== undefined);

      if (groups.length === 0) {
        alert('최소 1개 이상의 그룹을 지정해야 합니다.');
        return;
      }

      isLoading.value = true;
      try {
        const requestData = {
          collection_id: selectedCollection.value,
          group_permissions: groups          
        };

        console.log('저장 요청 데이터:', requestData);

        const response = await axios.post(
          `${API_BASE_URL}/api/auth/permissionsave`,
          // 두 번째 인자: 요청 본문 데이터
          {
            collection_id: selectedCollection.value,
            group_permissions: groups
          },
          // 세 번째 인자: 설정 객체
          {
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json'
            }
          }
        );

       
        
        if (response.data && response.data.success) {
          originalUserGroups.value = JSON.parse(JSON.stringify(userGroups.value));
          alert('그룹 설정이 성공적으로 저장되었습니다.');
          emit('refresh-data');
        } else {
          throw new Error(response.data?.message || '그룹 설정 저장에 실패했습니다.');
        }
      } catch (error) {
        console.error('그룹 저장 실패:', error);
        const errorMessage = error.response?.data?.message || 
                            error.message || 
                            '그룹 설정 저장 중 오류가 발생했습니다.';
        alert(errorMessage);
      } finally {
        isLoading.value = false;
      }
    };

    const updatePermissions = (group) => {
      try {
        // 해당 그룹 찾기
        const index = userGroups.value.findIndex(g => g.id === group.id);
        if (index !== -1) {
          // 그룹의 권한이 변경되었음을 표시하기 위해 userGroups 상태 업데이트
          const updatedGroups = [...userGroups.value];
          updatedGroups[index] = {
            ...group,
            permissions: {
              read: group.permissions.read,
              write: group.permissions.write,
              delete: group.permissions.delete
            }
          };
          userGroups.value = updatedGroups;
          
          console.log('권한 업데이트됨:', {
            groupId: group.id,
            permissions: group.permissions
          });
        }
      } catch (error) {
        console.error('권한 업데이트 중 오류 발생:', error);
      }
    };

    onMounted(() => {
      loadCollections();
    });

    return {
      collections,
      selectedCollection,
      userGroups,
      availableGroups,
      hasChanges,
      isLoading,
      selectCollection,
      isUserGroupSelected,
      isAvailableGroupSelected,
      toggleUserGroupSelection,
      toggleAvailableGroupSelection,
      moveUp,
      moveDown,
      saveGroups,
      selectedAvailableGroups,
      selectedUserGroups,
      updatePermissions
    };
  }
};
</script>


<style scoped>
.permission-container {
  display: flex;
  gap: 2rem;
  padding: 1rem;
  height: calc(100vh - 2rem);
}

.collection-list {
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

.collection-item {
  padding: 0.75rem;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 0.5rem;
}

.collection-item:hover {
  background: #e9ecef;
}

.collection-item.active {
  background: #e7f5ff;
  border-left: 4px solid #339af0;
}

.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.button-group {
  display: flex;
  justify-content: center;
  gap: 1rem;
  padding: 1rem;
}

.action-button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  color: white;
  min-width: 80px;
}

/* 기본 상태 */
.action-button {
  background-color: #e9ecef;
  color: #495057;
}

/* 버튼 활성화 상태 (체크박스가 선택되었을 때) */
.action-button:not(:disabled) {
  background-color: #339af0;
  color: white;
}

/* 버튼 비활성화 상태 */
.action-button:disabled {
  background-color: #e9ecef;
  color: #adb5bd;
  cursor: not-allowed;
}

/* 활성화된 버튼 호버 상태 */
.action-button:not(:disabled):hover {
  background-color: #228be6;
}

/* 저장 버튼 스타일은 따로 유지 */
.action-button.save {
  background-color: #40c057;
}

.action-button.save:disabled {
  background-color: #adb5bd;
}
.group-table {
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  background: white;
}

.header-cell, .cell {
  padding: 12px;
  display: flex;
  align-items: center;
}

/* 테이블 레이아웃 */
.table-header {
  display: grid;
  grid-template-columns: 50px minmax(100px, 1fr) minmax(300px, 2fr) minmax(150px, 2fr);
  background-color: #f3f4f6;
  border-bottom: 1px solid #e5e7eb;
}

.table-row {
  display: grid;
  grid-template-columns: 50px minmax(100px, 1fr) minmax(300px, 2fr) minmax(150px, 2fr);
  border-bottom: 1px solid #e5e7eb;
  min-height: 60px;
}

/* 체크박스 기본 스타일 */
.checkbox-container {
  display: flex;
  align-items: center;
  position: relative;
  padding-left: 25px;
  cursor: pointer;
  height: 24px;
}

.checkbox-cell {
  justify-content: center;
}

.checkbox-container .checkmark {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  left: 0;
  height: 18px;
  width: 18px;
  background-color: #fff;
  border: 1px solid #010101e1;
  border-radius: 4px;
}

.checkbox-container .checkmark::after {
  content: "";
  position: absolute;
  display: none;
  left: 5px;
  top: 1px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.checkbox-container input {
  position: absolute;
  opacity: 0;
  cursor: pointer;
}

.checkbox-container input:checked ~ .checkmark {
  background-color: #2563eb;
  border-color: #2563eb;
}

.checkbox-container input:checked ~ .checkmark::after {
  display: block;
}

/* 권한 체크박스 스타일 */
.permissions-cell {
  padding: 12px;
}

.permissions-header {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.permission-types {
  display: flex;
  justify-content: space-around;
  width: 100%;
  margin-top: 4px;
  font-size: 0.8rem;
}

.permissions-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding: 4px 0;
}

.permission-item {
  flex: 0 1 auto;
  min-width: 80px;
}

.permission-checkbox-container {
  display: flex;
  align-items: center;
  position: relative;
  padding-left: 25px;
  cursor: pointer;
  height: 24px;
}

.permission-checkbox-container .checkmark {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  left: 0;
  height: 18px;
  width: 18px;
  background-color: #fff;
  border: 1px solid #010101e1;
  border-radius: 4px;
}

.permission-checkbox-container .checkmark::after {
  content: "";
  position: absolute;
  display: none;
  left: 5px;
  top: 1px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.permission-checkbox-container input {
  position: absolute;
  opacity: 0;
  cursor: pointer;
}

.permission-checkbox-container input:checked ~ .checkmark {
  background-color: #2563eb;
  border-color: #2563eb;
}

.permission-checkbox-container input:checked ~ .checkmark::after {
  display: block;
}

.permission-label {
  display: inline-block;
  margin-left: 8px;
  font-size: 0.8rem;
  color: #4b5563;
  line-height: 18px;
  vertical-align: middle;
  white-space: nowrap;
}

/* 설명 셀 스타일 */
.cell:last-child {
  word-break: break-word;
  white-space: pre-wrap;
  align-items: flex-start;
  line-height: 1.4;
}

/* 상태 메시지 스타일 */
.loading, .no-selection, .no-groups {
  padding: 20px;
  text-align: center;
  color: #6b7280;
}

/* 이용자 그룹 테이블 스타일 */
.available-groups .table-header,
.available-groups .table-row {
  grid-template-columns: 50px minmax(100px, 1fr) minmax(150px, 2fr);
}
</style>