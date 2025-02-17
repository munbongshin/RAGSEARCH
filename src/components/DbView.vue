<template>
  <div class="db-view">
    <h4>Collection 관리</h4>
    <div class="flex gap-2">
      <!-- Create 버튼 -->
      <button 
        class="flex flex-col items-center bg-black border border-blue-950 rounded hover:bg-blue-920"
        @click="handleDbAction('create')"
      >
        <div class="mt-2">
          <svg viewBox="0 0 20 30" width="20" height="30" fill="none" :stroke="selectedAction === 'create' ? 'red' : 'blue'" stroke-width="2">
            <circle cx="10" cy="15" r="7"/>
            <line x1="10" y1="11" x2="10" y2="19"/>
            <line x1="6" y1="15" x2="14" y2="15"/>
          </svg>
        </div>
        <span :class="['text-xs mb-2', selectedAction === 'create' ? 'text-red-500' : 'text-blue-500']">
          생성
        </span>
      </button>

      <!-- Delete 버튼 -->
      <button 
        class="flex flex-col items-center justify-between gap-1 px-2 py-1 bg-black border border-blue-950 rounded hover:bg-gray-900 min-w-[60px] h-[70px]"
        @click="handleDbAction('delete')"
      >
        <div class="mt-2">
          <svg viewBox="0 0 20 30" width="20" height="30" fill="none" :stroke="selectedAction === 'delete' ? 'red' : 'blue'" stroke-width="2">
            <path d="M3 12h14"/>
            <path d="M14 12v10a1 1 0 0 1-1 1h-6a1 1 0 0 1-1-1V12m2 0V10a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2"/>
          </svg>
        </div>
        <span :class="['text-xs mb-2', selectedAction === 'delete' ? 'text-red-500' : 'text-blue-500']">
          삭제
        </span>
      </button>

      <!-- Search 버튼 -->
      <button 
        class="flex flex-col items-center justify-between gap-1 px-2 py-1 bg-black border border-blue-950 rounded hover:bg-gray-900 min-w-[60px] h-[70px]"
        @click="handleDbAction('search')"
      >
        <div class="mt-2">
          <svg viewBox="0 0 20 30" width="20" height="30" fill="none" :stroke="selectedAction === 'search' ? 'red' : 'blue'" stroke-width="2">
            <circle cx="10" cy="15" r="6"/>
            <line x1="14" y1="20" x2="17" y2="23"/>
          </svg>
        </div>
        <span :class="['text-xs mb-2', selectedAction === 'search' ? 'text-red-500' : 'text-blue-500']">
          검색
        </span>
      </button>

      <!-- View 버튼 -->
      <button 
        class="flex flex-col items-center justify-between gap-1 px-2 py-1 bg-black border border-blue-950 rounded hover:bg-gray-900 min-w-[60px] h-[70px]"
        @click="handleDbAction('view')"
      >
        <div class="mt-2">
          <svg viewBox="0 0 20 30" width="20" height="30" fill="none" :stroke="selectedAction === 'view' ? 'red' : 'blue'" stroke-width="2">
            <path d="M4 8h12v14H4z"/>
            <path d="M4 13h12"/>
            <path d="M4 18h12"/>
            <path d="M8 8v14"/>
            <path d="M12 8v14"/>
          </svg>
        </div>
        <span :class="['text-xs mb-2', selectedAction === 'view' ? 'text-red-500' : 'text-blue-500']">
          조회
        </span>
      </button>
    </div>
    
    <div class="mt-4 text-white">
      선택된 메뉴: {{ getSelectedActionLabel() }}
    </div>

    <component 
      :is="currentDbComponent" 
      @perform-action="performDbAction"
      @embedding-completed="handleEmbeddingCompleted"
    />
    <FileUploadDialog 
      :show="showFileUploadDialog" 
      :selected-collection="currentCollection"
      @close="closeFileUploadDialog"
      @embedding-completed="handleEmbeddingCompleted"
    />
  </div>
</template>

<script>
import CreateDB from './CreateDB.vue';
import DeleteDB from './DeleteDB.vue';
import SearchDB from './SearchDB.vue';
import ViewDB from './ViewDB.vue';
import FileUploadDialog from './FileUploadDialog.vue';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

export default {
  name: 'DbView',
  components: {
    CreateDB,
    DeleteDB,
    SearchDB,
    ViewDB,
    FileUploadDialog
  },
  data() {
    return {
      selectedAction: 'create',
      dbAction: 'create',
      showFileUploadDialog: false,
      currentCollection: '',
      files: [],
    }
  },
  computed: {
    currentDbComponent() {
      switch(this.dbAction) {
        case 'create': return CreateDB;
        case 'delete': return DeleteDB;
        case 'search': return SearchDB;
        case 'view': return ViewDB;
        default: return CreateDB;
      }
    }
  },
  methods: {
    handleDbAction(actionId) {
      this.selectedAction = actionId;
      this.dbAction = actionId;
      this.handleDbActionChange();
    },
    handleDbActionChange() {
      console.log('DB action changed to:', this.dbAction);
    },
    getSelectedActionLabel() {
      const labels = {
        'create': '생성',
        'delete': '삭제',
        'search': '검색',
        'view': '조회'
      };
      return labels[this.selectedAction];
    },
    performDbAction(action, data) {
      console.log('Performing DB action:', action, 'with data:', data);
      this.$emit('perform-db-action', action, data);
    },
    async handleEmbeddingCompleted() {
      await this.fetchCollectionFiles();
      this.$store.dispatch('updateSelectedSources', []);
      this.closeFileUploadDialog();
    },
    closeFileUploadDialog() {
      this.showFileUploadDialog = false;
    },
    async fetchCollectionFiles() {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/collection_files/${this.currentCollection}`);
        if (response.data.success) {
          this.files = response.data.files;
        }
      } catch (error) {
        console.error('Error fetching collection files:', error);
      }
    }
  }
}
</script>

<style scoped>

.db-view {
padding: 10px;
color: white;
}

.header {
background-color: #000000;
padding: 10px;
border-bottom: 1px solid #333;
}

.header h1 {
margin: 0;
font-size: 18px;
font-weight: normal;
}

.main-content {
display: flex;
flex-grow: 1;
}

.sidebar {
width: 120px;
background-color: #000000;
padding: 10px;
border-right: 1px solid #333;
}

.sidebar-button {
display: block;
width: 100%;
padding: 10px;
margin-bottom: 10px;
background-color: #000000;
color: white;
border: 1px solid #333;
cursor: pointer;
text-align: center;
}

.sidebar-button.active {
background-color: #333;
}

.control-group {
padding: 10px;
margin-right: 10px;
margin-top: 10px;
color: white;
background-color: #1e1e1e;
}

.combobox, .db-input {
width: 90%;
padding: 5px;
margin-bottom: 10px;
background-color: #111;
color: white;
border: 1px solid #333;
}

.embedding-container {
display: flex;
align-items: center;
margin-bottom: 10px;
}

.add-button {
width: 30px;
height: 30px;
background-color: #111;
color: white;
border: 1px solid #333;
cursor: pointer;
display: flex;
justify-content: center;
align-items: center;
font-size: 20px;
margin-right: 10px;
}

.embedding-text {
color: white;
}

.select-box {
width: 100%;
background-color: #111;
padding: 10px;
border: 1px solid #333;
flex-grow: 1;
display: flex;
align-items: center;
justify-content: center;
}

.db-input-container {
display: flex;
flex-direction: column;
}

.db-action-button {
padding: 5px;
background-color: #1a3a5a;
color: white;
border: none;
cursor: pointer;
margin-top: 5px;
}

.content {
flex-grow: 1;
display: flex;
flex-direction: column;
}

.chat-area {
flex-grow: 1;
background-color: #000000;
border-left: 1px solid #333;
overflow-y: auto;
}

.footer {
display: flex;
padding: 10px;
background-color: #000000;
border-top: 1px solid #333;
}

.chat-input {
flex-grow: 1;
padding: 10px;
margin-right: 10px;
background-color: #111;
color: white;
border: 1px solid #333;
}

.search-button {
padding: 10px 20px;
background-color: #1a3a5a;
color: white;
border: none;
cursor: pointer;
}
</style>