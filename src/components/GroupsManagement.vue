<template>
  <div class="groups-management">
    <div v-if="isLoading" class="loading-overlay">
      <div class="spinner-border" role="status">
        <span class="sr-only">Loading...</span>
      </div>
    </div>

    <div class="function-tabs">
      <div class="tabs-container">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="tab.id === 'add' ? handleAdd() : currentFunction = tab.id"
          :class="['tab-button', currentFunction === tab.id ? 'active' : '']"
        >
          {{ tab.name }}
        </button>
      </div>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th><input 
              type="checkbox" 
              :checked="allSelected" 
              @change="handleSelectAll"
              :disabled="currentFunction === 'edit' || currentFunction === 'list'"
              :class="{ 'checked-mode': currentFunction === 'delete' }"
            ></th>
            <th>ID</th>
            <th>그룹명</th>
            <th>설명</th>
            <th>생성일</th>
            <th>작업</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="isAdding" key="new-row">
            <td></td>
            <td>(자동생성)</td>
            <td class="editable-cell">
              <input 
                v-model="newGroup.name"
                @input="$event.target.value = $event.target.value.replace(/[^A-Za-z0-9-_]/g, '')"
                class="edit-input"
                placeholder="그룹명 입력"
                title="영어, 숫자, 하이픈(-), 언더스코어(_)만 입력 가능합니다"
                style="font-size: 14px; padding: 8px;"
              >
            </td>
            <td class="editable-cell">
              <textarea
                v-model="newGroup.description"
                class="edit-input"
                rows="2"
                placeholder="설명 입력"
              ></textarea>
            </td>
            <td>(자동생성)</td>
            <td>
              <button @click="handleAddSubmit" class="save-btn">저장</button>
              <button @click="cancelAdd" class="cancel-btn">취소</button>
            </td>
          </tr>
          <tr v-for="group in groups" :key="group.id">
            <td><input 
                  type="checkbox" 
                  :checked="isSelected(group.id)" 
                  @change="event => handleSelect(group.id, event)"
                  :disabled="currentFunction === 'edit' || currentFunction === 'list'"
                  :class="{ 'checked-mode': currentFunction === 'delete' }"
                  >
            </td>
            
            <td>{{ group.id }}</td>
            <td @click="startEditing(group.id, 'name')" class="editable-cell">
              <div v-if="editingCell.id === group.id && editingCell.field === 'name'" class="editing-cell">
                <input
                  v-model="editingCell.value"
                  @blur="handleEditComplete(group)"
                  @keyup.enter="handleEditComplete(group)"
                  @keyup.esc="cancelEdit"
                  class="edit-input"
                >
              </div>
              <div v-else>{{ group.name }}</div>
            </td>
            <td @click="startEditing(group.id, 'description')" class="editable-cell">
              <div v-if="editingCell.id === group.id && editingCell.field === 'description'" class="editing-cell">
                <textarea
                  v-model="editingCell.value"
                  @blur="handleEditComplete(group)"
                  @keyup.enter="handleEditComplete(group)"
                  @keyup.esc="cancelEdit"
                  class="edit-input"
                  rows="2"
                ></textarea>
              </div>
              <div v-else>{{ group.description }}</div>
            </td>
            <td>{{ formatDate(group.created_at) }}</td>
            <td>
              <div class="action-buttons">
                <button v-if="currentFunction === 'edit'" @click="startEditing(group.id, 'name')" class="edit-btn">수정</button>
                <button v-if="currentFunction === 'delete'" @click="confirmDelete(group)" class="delete-btn">삭제</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="selectedGroups.length > 0" class="selected-info">
      <span>{{ selectedGroups.length }}개 선택됨</span>
      <button 
        v-if="currentFunction === 'delete'"
        @click="deleteSelected"
        class="delete-selection-btn"
      >
        선택 항목 삭제
      </button>
    </div>
  </div>
</template>


<script>
import { ref, computed, nextTick, onMounted } from 'vue'
import axios from 'axios'

const API_BASE_URL = 'http://localhost:5001'

export default {
  name: 'GroupsManagement',
  setup() {
    const isLoading = ref(false)
    const currentFunction = ref('list')
    const groups = ref([])
    const selectedGroups = ref([])
    const editingCell = ref({ id: null, field: null, value: null })
    const isAdding = ref(false)
    const newGroup = ref({
      name: '',
      description: ''
    })

    const tabs = [
      { id: 'list', name: '조회' },
      { id: 'add', name: '추가' },
      { id: 'edit', name: '수정' },
      { id: 'delete', name: '삭제' }
    ]

    const fetchGroups = async () => {
      isLoading.value = true
      try {
        const token = sessionStorage.getItem('token')
        if (!token) {
          throw new Error('인증 토큰이 없습니다.')
        }

        const response = await axios.get(`${API_BASE_URL}/api/auth/groups`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          withCredentials: true
        })
        
        if (response.data && response.data.groups) {
          groups.value = response.data.groups.map(group => ({
            id: group.id,
            name: group.name || '미지정 그룹',
            description: group.description || '설명 없음',
            created_at: group.created_at || new Date().toISOString()
          }))
        } else {
          throw new Error('데이터를 불러올 수 없습니다.')
        }
      } catch (error) {
        console.error('조회 실패:', error)
        groups.value = []
        handleError(error)
      } finally {
        isLoading.value = false
      }
    }

    const handleError = (error) => {
      if (error.response) {
        switch (error.response.status) {
          case 401:
            alert('인증이 만료되었습니다. 다시 로그인해주세요.')
            break
          case 403:
            alert('해당 작업을 수행할 권한이 없습니다.')
            break
          default:
            alert(error.response.data.message || '작업 중 오류가 발생했습니다.')
        }
      } else if (error.request) {
        alert('서버와 연결할 수 없습니다. 네트워크 연결을 확인해주세요.')
      } else {
        alert('요청 중 오류가 발생했습니다.')
      }
    }

    const allSelected = computed(() => {
      return groups.value.length > 0 && selectedGroups.value.length === groups.value.length
    })

    const isSelected = (groupId) => {
      return selectedGroups.value.includes(groupId)
    }

    const handleSelectAll = (event) => {
      if (event.target.checked) {
        selectedGroups.value = groups.value.map(group => group.id)
      } else {
        selectedGroups.value = []
      }
    }

    const handleSelect = (groupId, event) => {
      if (event.target.checked) {
        selectedGroups.value = [...selectedGroups.value, groupId]
      } else {
        selectedGroups.value = selectedGroups.value.filter(id => id !== groupId)
      }
    }

    const handleAdd = () => {
      isAdding.value = true
    }

    const cancelAdd = () => {
      isAdding.value = false
      newGroup.value = {
        name: '',
        description: ''
      }
    }

    const handleAddSubmit = async () => {
      if (!newGroup.value.name.trim()) {
        alert('그룹명을 입력해주세요.');
        return;
      }
      if (!confirm('새 그룹을 생성하시겠습니까?')) {
        return;
      }

      isLoading.value = true;
      try {
        const token = sessionStorage.getItem('token');
        const response = await axios.post(`${API_BASE_URL}/api/auth/groups/create`, {
          name: newGroup.value.name,
          description: newGroup.value.description
        }, {
          headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          withCredentials: true
        });

        if (response.data.success) {
          await fetchGroups();
          cancelAdd();
          alert(response.data.message || '그룹이 생성되었습니다.');
        }
      } catch (error) {
        handleError(error);
      } finally {
        isLoading.value = false;
      }
    };

    const startEditing = async (id, field) => {
      if (field !== 'name' && field !== 'description' || currentFunction.value !== 'edit') return
      
      const group = groups.value.find(g => g.id === id)
      if (!group) return

      editingCell.value = {
        id,
        field,
        value: group[field]
      }

      await nextTick()
      const activeInput = document.querySelector('.editing-cell input, .editing-cell textarea')
      if (activeInput) {
        activeInput.focus()
      }
    }

    const handleEditComplete = async (group) => {
      if (editingCell.value.value === group[editingCell.value.field]) {
        cancelEdit();
        return;
      } 
      isLoading.value = true;
      try {
        const token = sessionStorage.getItem('token');
        const updatedData = {
          group_id: group.id,
          [editingCell.value.field]: editingCell.value.value
        };

        const response = await axios.post(`${API_BASE_URL}/api/auth/groups/update`, 
          updatedData,
          {
            headers: { 
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            withCredentials: true
          }
        );

        if (response.data.success) {
          await fetchGroups();
          cancelEdit();
        }
      } catch (error) {
        handleError(error);
      } finally {
        isLoading.value = false;
      }
    };

    const cancelEdit = () => {
      editingCell.value = { id: null, field: null, value: null }
    }

    const confirmDelete = async (group) => {
      if (!confirm(`'${group.name}' 그룹을 삭제하시겠습니까?`)) return;
      
      isLoading.value = true;
      try {
        const token = sessionStorage.getItem('token');
        const response = await axios.post(`${API_BASE_URL}/api/auth/groups/delete`, {
          group_id: group.id
        }, {
          headers: { 'Authorization': `Bearer ${token}` },
          withCredentials: true
        });
        
        if (response.data.success) {
          await fetchGroups();
          selectedGroups.value = selectedGroups.value.filter(id => id !== group.id);
          alert('삭제되었습니다.');
        }
      } catch (error) {
        console.error('삭제 실패:', error);
        handleError(error);
      } finally {
        isLoading.value = false;
      }
    };

    const deleteSelected = async () => {
      if (!selectedGroups.value.length || !confirm(`선택한 ${selectedGroups.value.length}개의 그룹을 삭제하시겠습니까?`)) return;

      isLoading.value = true;
      try {
        const token = sessionStorage.getItem('token');
        const promises = selectedGroups.value.map(groupId => 
          axios.post(`${API_BASE_URL}/api/auth/groups/delete`, {
            group_id: groupId
          }, {
            headers: { 'Authorization': `Bearer ${token}` },
            withCredentials: true
          })
        );
        
        await Promise.all(promises);
        await fetchGroups();
        selectedGroups.value = [];
        alert('선택한 그룹이 삭제되었습니다.');
      } catch (error) {
        console.error('삭제 실패:', error);
        handleError(error);
      } finally {
        isLoading.value = false;
      }
    };

    const formatDate = (dateString) => {
      if (!dateString) return ''
      try {
        const date = new Date(dateString)
        return new Intl.DateTimeFormat('ko-KR', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        }).format(date)
      } catch (error) {
        console.warn('Invalid date format:', dateString)
        return dateString
      }
    }

    onMounted(fetchGroups)

    return {
      isLoading,
      currentFunction,
      tabs,
      groups,
      selectedGroups,
      editingCell,
      isAdding,
      newGroup,
      allSelected,
      isSelected,
      handleSelectAll,
      handleSelect,
      startEditing,
      handleEditComplete,
      cancelEdit,
      formatDate,
      fetchGroups,
      confirmDelete,
      deleteSelected,
      handleAdd,
      cancelAdd,
      handleAddSubmit
    }
  }
}
</script>

<style scoped>
.groups-management {
  min-height: 100%;
  background-color: #1f2937; /* 배경색을 어두운 회색으로 변경 */
}

/* 스크롤바 스타일링 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #1f2937; /* 스크롤바 트랙 배경색 변경 */
}

::-webkit-scrollbar-thumb {
  background: #4b5563; /* 스크롤바 색상 변경 */
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #6b7280; /* 스크롤바 hover 색상 변경 */
}

/* 로딩 스피너 스타일 */
.spinner-border {
  width: 3rem;
  height: 3rem;
  border: 0.25em solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spinner-border 0.75s linear infinite;
}

@keyframes spinner-border {
  to { transform: rotate(360deg); }
}

/* 편집 가능한 셀 스타일 */
.editable-cell {
  cursor: pointer;
  transition: background-color 0.2s;
  background-color: #374151; /* 편집 가능한 셀 배경색 변경 */
  color: #e5e7eb; /* 편집 가능한 셀 텍스트 색상 변경 */
}

.editable-cell:hover {
  background-color: #4b5563; /* 편집 가능한 셀 hover 배경색 변경 */
}

/* 편집 중인 셀 스타일 */
.editing-cell {
  padding: 0 !important;
}

.editing-cell input,
.editing-cell textarea {
  width: 100%;
  padding: 0.5rem;
  background-color: #374151; /* 편집 중인 셀 배경색 변경 */
  border: 1px solid #4b5563; /* 편집 중인 셀 border 색상 변경 */
  border-radius: 4px;
  color: #e5e7eb; /* 편집 중인 셀 텍스트 색상 변경 */
  outline: none;
}

.editing-cell input:focus,
.editing-cell textarea:focus {
  border-color: #6b7280; /* 편집 중인 셀 focus 시 border 색상 변경 */
  box-shadow: 0 0 0 2px rgba(107, 114, 128, 0.5); /* 편집 중인 셀 focus 시 box-shadow 변경 */
}

.table-container {
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

tbody tr {
  background-color: #1c1c1c;
  border-bottom: 1px solid #333;
}

tbody tr:hover {
  background-color: #2d2d2d;
}

td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #4a5568;
}

input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  background: white;
}

.delete-btn {
  background: #dc2626;
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
}

.delete-btn:hover {
  background: #b91c1c;
}

.groups-management {
  padding: 1rem;
}

.loading-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.function-tabs {
  margin-bottom: 1rem;
}

.tabs-container {
  display: flex;
  gap: 0.25rem;
  background-color: #1f2937;
  padding: 0.25rem;
  border-radius: 0.25rem;
}

.tab-button {
  padding: 0.5rem 1rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #1c437e;
  transition: all 0.2s;
}

.tab-button:hover {
  color:  #f12525;
}

.tab-button.active {
  background-color: #2563eb;
  color: white;
}

.description-text {
  margin-bottom: 1rem;
  color: #f8fafe;
  font-size: 0.875rem;
}

.add-button {
  margin-bottom: 1rem;
}

.add-group-btn {
  background-color: #2563eb;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 0.25rem;
}

.add-group-btn:hover {
  background-color: #1d4ed8;
}

.editable-cell {
  cursor: pointer;
  padding: 0.75rem 1rem;
}

.editable-cell:hover {
  background-color: #2d2d2d;
}

.editing-cell {
  padding: 0 !important;
}

.editing-cell input,
.editing-cell textarea {
  width: 100%;
  padding: 0.5rem;
  background-color: #2d2d2d;
  border: 1px solid #404040;
  border-radius: 0.25rem;
  color: white;
}

.editing-cell input:focus,
.editing-cell textarea:focus {
  outline: none;
  border-color: #2563eb;
}

.save-btn, .cancel-btn {
  padding: 0.25rem 0.75rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
  margin-right: 0.5rem;
}

.save-btn {
  background: #2563eb;
  color: white;
}

.save-btn:hover {
  background: #1d4ed8;
}

.cancel-btn {
  background: #4b5563;
  color: white;
}

.cancel-btn:hover {
  background: #374151;
}
.selected-info {
 margin-top: 1rem;
 display: flex;
 gap: 0.5rem;
 color: #ffffff;
}

.delete-selection-btn {
 background: #dc2626;
 color: white;
 padding: 0.25rem 0.75rem;
 border-radius: 0.25rem;
 font-size: 0.875rem;
}

.delete-selection-btn:hover {
 background: #b91c1c;
}
</style>