<template>  
  <div class="chat-view" :class="{ 'modal-open': showModal }">
    <p class="current-model-info">현재 사용 중인 모델: {{ currentModelInfo.source }} - {{ currentModelInfo.model }}</p>
    
    <!-- 모드 선택 -->
    <div class="mode-selection">
      <label>
        <input type="radio" v-model="state.selectedMode" value="RAG" @change="updateSelectedMode">
        RAG
      </label>
      <label>
        <input type="radio" v-model="state.selectedMode" value="RAG+LLM" @change="updateSelectedMode">
        RAG+LLM
      </label>
    </div>
 
    <!-- 트리 구조의 Collection & Documents -->
    <div class="tree-container">
      <div class="tree-header">
        <h3>Collections & Documents</h3>
      </div>
      <!-- 작업 버튼들 -->
      <div class="action-buttons">
        <button 
          @click="summarizeSources" 
          class="summarize-button" 
          :disabled="!hasSelectedDocuments"
        >
          {{ isLoading ? `요약 중... ${progress.toFixed(2)}%` : '문서요약' }}
        </button>
        <button 
          @click="deleteSelectedSources" 
          class="delete-button"
          :disabled="!hasSelectedDocuments || !hasDeletePermissionForSelected"
          :class="{ 'disabled-btn': !hasSelectedDocuments || !hasDeletePermissionForSelected }"
        >
          문서삭제
        </button>
      </div>
      <!-- 전체 Collection 선택 -->
      <div class="collection-select-all">
        <input 
          type="checkbox" 
          id="select-all-collections"
          v-model="state.selectAllCollections"
          @change="handleSelectAllCollections"
        >
        <label for="select-all-collections">전체 Collection 선택</label>
      </div>
      
      <div class="tree-view">
        <div v-for="collection in state.collections" :key="collection" class="tree-item">
          <!-- Collection 레벨 -->
          <div class="collection-item">
            <div class="collection-content">
              <span class="expand-icon" @click="toggleCollection(collection)">
                {{ isCollectionExpanded(collection) ? '▼' : '▶' }}
              </span>
              <input 
                type="checkbox" 
                :id="`collection-${collection}`"
                v-model="state.selectedCollections"
                :value="collection"
                @change="handleCollectionSelect"
              >
              <label :for="`collection-${collection}`">{{ collection }}</label>
            </div>
            <button 
              class="collection-upload-btn"
              @click="showFileUploadDialogForCollection(collection)"
              :disabled="!hasWritePermission(collection)"
              :class="{ 'disabled-btn': !hasWritePermission(collection) }"
              title="이 Collection에 파일 추가"
            >
              +
            </button>
          </div>
          
          <!-- Documents 레벨 -->
          <div v-if="isCollectionExpanded(collection) && isCollectionSelected(collection)" 
               class="documents-list">
            <!-- 현재 Collection의 전체 Document 선택 -->
            <div class="document-select-all">
              <input 
                type="checkbox" 
                :id="`select-all-docs-${collection}`"
                v-model="state.selectAllDocuments[collection]"
                @change="handleSelectAllDocuments(collection)"
              >
              <label :for="`select-all-docs-${collection}`">전체 Documents 선택</label>
            </div>
            
            <div v-for="document in getDocumentsForCollection(collection)" 
                :key="`${collection}-${document}`" 
                class="document-item">
              <input 
                type="checkbox" 
                :id="`doc-${collection}-${document}`"
                :checked="isDocumentSelected(collection, document)"
                @change="(e) => handleDocumentSelect(collection, document, e.target.checked)"
              >
              <label :for="`doc-${collection}-${document}`">{{ document }}</label>
            </div>
          </div>
        </div>
      </div>
    </div>
 
    <!-- 경고 메시지 -->
    <div v-if="state.showWarning" class="warning-message">
      컬렉션을 선택해주세요.
    </div>
    <!-- 간단한 커스텀 알림창 -->
    <div v-if="showAlert" class="simple-alert">
      <div class="alert-box">
        <div class="alert-message">{{ alertMessage }}</div>
        <div class="alert-buttons">
          <button 
            v-if="alertType === 'confirm'" 
            class="alert-button confirm-button" 
            @click="handleConfirm"
          >
            예
          </button>
          <button 
            v-if="alertType === 'confirm'" 
            class="alert-button cancel-button" 
            @click="handleCancel"
          >
            아니오
          </button>
          <button 
            v-if="alertType === 'alert'" 
            class="confirm-button" 
            @click="closeAlert"
          >
            확인
          </button>
        </div>
      </div>
    </div>

    <!-- 모달 컴포넌트 -->
    <AppModal
      v-if="showModal"
      :show="showModal"
      @close="closeModal"
      :initialWidth="1600"
      :initialHeight="1000"
      :minWidth="800"
      :minHeight="600"
    >
      <template #header>
        <h3>문서 분석하기</h3>
      </template>
      <template #body>
        <SummarizeSource
          :selectedCollectionsSources="{
            sources: state.selectedSources.map(src => ({
              collection: src.collection,
              source: src.source,
              collection_id: src.collection_id
            })),
            collections: state.selectedCollections
          }"
          :llm-name="currentModelInfo.source"
          :llm-model="currentModelInfo.model"
        />
      </template>
    </AppModal>

    <!-- 파일 업로드 다이얼로그 -->
    <FileUploadDialog 
      v-if="state.showDialog" 
      @close="closeFileUploadDialog" 
      @embedding-completed="handleEmbeddingCompleted"
      :show="state.showDialog"
      :selectedCollection="state.selectedOption"
      class="file-upload-dialog"
    />
  </div>
</template>

<script>
import { inject, reactive, computed, watch, onMounted, onUnmounted, ref, defineComponent } from 'vue'
import { useStore } from 'vuex'
import axios from 'axios'
import FileUploadDialog from './FileUploadDialog.vue'
import AppModal from './AppModal.vue'
import SummarizeSource from './SummarizeSource.vue'

import { marked } from 'marked';
import DOMPurify from 'dompurify';

const API_BASE_URL = 'http://localhost:5001'

export default defineComponent({
 name: 'ChatView',
 components: {
    FileUploadDialog,
    AppModal,
    SummarizeSource
  },
  emits: [
    'update-selected-sources',
    'openModal',
    'closeModal',
    'update-selected-mode'
  ], 
 setup(props, { emit }) {
  const store = useStore()
  const showAlert = ref(false);
  const alertMessage = ref('');
  const alertType = ref('alert'); // 'alert' 또는 'confirm'
  const alertCallback = ref(null);

  // state에서 alert 관련 속성 제거
  const state = reactive({
    selectedOption: '',
    selectAll: false,
    collections: [],
    showDialog: false,
    showWarning: false,
    documentSources: [],
    selectedSources: [], 
    selectedMode: 'RAG',
    selectAllCollections: false,
    selectAllDocuments: {},
    selectedCollections: [],
    expandedCollections: new Set(),
    documentsMap: new Map(),
    collectionsWithPermissions: {}
  });

  const error = ref('')
  const progress = ref(0)
  const summary = ref('')
  const isLoading = ref(false)
  const showModal = ref(false)
  const eventSource = ref(null)
  const authContext = inject('authContext')

  watch(() => showModal.value, (newValue) => {
    if (newValue) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
  });

  const openModal = () => {
    showModal.value = true;
    emit('openModal');
  };


  const showConfirmAlert = (message, callback) => {
    alertType.value = 'confirm';
    alertMessage.value = message;
    alertCallback.value = callback;
    showAlert.value = true;
  };

  const handleConfirm = () => {
    if (alertCallback.value) {
      alertCallback.value(true);
    }
    showAlert.value = false;
  };

  const handleCancel = () => {
    if (alertCallback.value) {
      alertCallback.value(false);
    }
    showAlert.value = false;
  };

  const showCustomAlert = (message) => {
    alertMessage.value = message;
    showAlert.value = true;
  };

  const closeAlert = () => {
    showAlert.value = false;
    alertMessage.value = '';
  };

  const closeModal = () => {
    if (eventSource.value) {
      eventSource.value.close();
      eventSource.value = null;
    }
    showModal.value = false;
    emit('closeModal');
    isLoading.value = false;
    progress.value = 0;
    summary.value = '';
    error.value = '';
  };
   

   const currentModelInfo = computed(() => ({
     source: store.state.currentLlmSource,
     model: store.state.currentLlmModel,
     collection: store.state.currentCollection
   }))

   const selectedCollections = computed({
     get: () => state.selectedCollections,
     set: (value) => {
       state.selectedCollections = value;
       store.dispatch('updateSelectedCollections', value);
     }
   });

   // 권한이 있는 컬렉션을 가져오는 함수, 관리자는 모두가져옴
   const fetchCollections = async () => {
     try {
       const username = authContext.value.username
       console.log('Fetching collections for username:', username)

       // 1. user_id 조회
       const userResponse = await axios.get('/api/user/id', {
         params: { username }
       })

       if (!userResponse.data.user_id) {
         throw new Error('사용자 ID를 가져올 수 없습니다.')
       }

       const userId = userResponse.data.user_id
       console.log('User ID:', userId)

       // 2. 컬렉션과 권한 정보를 가져오기
       const response = await axios.get('/api/collections', {
         params: { 
           username,
           user_id: userId
         },
         headers: {
           'Content-Type': 'application/json'
         }
       })
       
       console.log('Collections API full response:', response.data)
       
       if (response.data.success && response.data.collections) {
         const collectionsWithPermissions = {}
         const uniqueCollections = new Set()

         for (const collection of response.data.collections) {
           const [collection_id, collection_name, can_read, can_write, can_delete] = collection

           if (!collection_name) continue

           uniqueCollections.add(collection_name)

           collectionsWithPermissions[collection_id] = {
             id: collection_id,
             name: collection_name,
             permissions: {
               read: can_read || false,
               write: can_write || false,
               delete: can_delete || false
             }
           }
         }

         state.collections = Array.from(uniqueCollections)
         state.collectionsWithPermissions = collectionsWithPermissions
         
         console.log('Processed collections:', state.collections)
         console.log('Collections with permissions:', state.collectionsWithPermissions)

         if (state.collections.length > 0) {
           state.selectedCollections = [...state.collections]
           state.selectAllCollections = true
           
           state.collections.forEach(collection => {
             state.expandedCollections.add(collection)
           })
           
           await fetchDocumentsForCollections(state.collections)
           store.dispatch('updateSelectedCollections', state.selectedCollections)
         } else {
           console.log('No collections found for the user')
           state.selectedCollections = []
           state.selectAllCollections = false
           store.dispatch('updateSelectedCollections', [])
         }
       } else {
         console.error('컬렉션 조회 실패:', response.data.message)
       }
     } catch (error) {
       console.error('컬렉션 fetching 에러:', error)
       state.collections = []
       state.selectedCollections = []
       state.selectAllCollections = false
       state.collectionsWithPermissions = {}
     }
   }

   const fetchDocumentsForCollections = async (collections) => {
     if (!collections || collections.length === 0) {
       console.log('No collections provided to fetch documents');
       return;
     }

     try {
       const params = new URLSearchParams();
       collections.forEach(collection => {
         params.append('collection_name[]', collection);
       });

       console.log('Fetching documents with params:', params.toString());

       const response = await axios.get(`${API_BASE_URL}/api/get-all-documents-source`, {
         params: params,
         paramsSerializer: params => {
           return params.toString();
         }
       });
       
       console.log('Documents source response:', response.data);
       
       if (response.data.success) {
         for (const collection of collections) {
           const collectionData = response.data.collections[collection];
           if (collectionData && !collectionData.error) {
             const sources = collectionData.documents.map(doc => doc.source);
             console.log(`Documents for ${collection}:`, sources);
             state.documentsMap.set(collection, sources);
           } else {
             console.error(`Error for collection ${collection}:`, collectionData?.error);
             state.documentsMap.set(collection, []);
           }
         }
       }
     } catch (error) {
       console.error(`Error fetching documents for collections:`, error);
       collections.forEach(collection => {
         state.documentsMap.set(collection, []);
       });
     }
   }

   const isDocumentSelected = (collection, document) => {
     return state.selectedSources.some(
       s => s.collection === collection && s.source === document
     );
   };

   const handleSelectAllCollections = async () => {
     if (state.selectAllCollections) {
       state.selectedCollections = [...state.collections];
       await fetchDocumentsForCollections(state.selectedCollections);
     } else {
       state.selectedCollections = [];
       state.selectedSources = [];
       state.collections.forEach(collection => {
         state.documentsMap.set(collection, []);
       });
     }
     
     store.dispatch('updateSelectedCollections', state.selectedCollections);
     emitSelectedSources();
   };

   const isCollectionSelected = (collection) => {
     return state.selectedCollections.includes(collection);
   }

   const handleCollectionSelect = async () => {
     state.selectAllCollections = 
       selectedCollections.value.length === state.collections.length;
     console.log('Selected collections:', state.selectedCollections);
     
     store.dispatch('updateSelectedCollections', [...state.selectedCollections]);
     if (selectedCollections.value.length > 0) {
       await fetchDocumentsForCollections(state.selectedCollections);
     }
     
     // 선택된 collections의 문서만 유지
     state.selectedSources = state.selectedSources.filter(doc => 
       selectedCollections.value.includes(doc.collection)
     );
     
     emitSelectedSources();
   };

  const handleSelectAllDocuments = (collection) => {
    const documents = getDocumentsForCollection(collection);
    const collectionInfo = Object.values(state.collectionsWithPermissions).find(
      c => c.name === collection
    );
    
    if (state.selectAllDocuments[collection]) {
      // 해당 collection의 모든 문서 선택
      documents.forEach(doc => {
        if (!isDocumentSelected(collection, doc)) {
          state.selectedSources.push({
            collection,
            source: doc,
            collection_id: collectionInfo?.id || 1  // collection_id 추가
          });
        }
      });
    } else {
      // 해당 collection의 모든 문서 선택 해제
      state.selectedSources = state.selectedSources.filter(
        s => s.collection !== collection
      );
    }
    emitSelectedSources();
  }

   const handleDocumentSelect = (collection, document, checked) => {
      const collectionInfo = Object.values(state.collectionsWithPermissions).find(
        c => c.name === collection
      );

      if (checked) {
        state.selectedSources.push({
          collection,
          source: document,
          collection_id: collectionInfo?.id || 1  // collection_id 추가
        });
      } else {
        state.selectedSources = state.selectedSources.filter(
          s => !(s.collection === collection && s.source === document)
        );
      }
      
      // 각 collection별로 전체 선택 상태 업데이트
      for (const col of state.selectedCollections) {
        const documents = getDocumentsForCollection(col);
        state.selectAllDocuments[col] = documents.every(doc => 
          isDocumentSelected(col, doc)
        );
      }
      emitSelectedSources();
    };

   const updateSelectedMode = () => {
     console.log('ChatView: Updating selectedMode:', state.selectedMode)
     emit('update-selected-mode', state.selectedMode)
     store.dispatch('updateSelectedMode', state.selectedMode)
   }

   const emitUpdatedData = () => {
     if (state.selectedOption) {
       store.dispatch('updateCurrentCollection', state.selectedOption)
     }
   }

   const emitSelectedSources = () => {
     console.log('ChatView: Emitting selectedSources:', state.selectedSources);
     emit('update-selected-sources', state.selectedSources);
     store.dispatch('updateSelectedSources', state.selectedSources);
   };

   const toggleCollection = async (collection) => {
     if (state.expandedCollections.has(collection)) {
       state.expandedCollections.delete(collection);
     } else {
       state.expandedCollections.add(collection);
       if (state.selectedCollections.includes(collection)) {
         await fetchDocumentsForCollections([collection]);
       }
     }
   }

   const isCollectionExpanded = (collection) => {
     return state.expandedCollections.has(collection);
   }

   const getDocumentsForCollection = (collection) => {
     return state.documentsMap.get(collection) || [];
   }

   const hasSelectedDocuments = computed(() => {
     return state.selectedSources.length > 0;
   })

   const showFileUploadDialogForCollection = (collection) => {
     state.selectedOption = collection;
     state.showDialog = true;
   }

   const closeFileUploadDialog = () => {
     state.showDialog = false;
   }

   const handleEmbeddingCompleted = async (collection) => {
     await fetchDocumentsForCollections([collection]);
   }

   const renderedSummary = computed(() => {
     return DOMPurify.sanitize(marked(summary.value));
   })
  

  const summarizeSources = () => {
    if (state.selectedSources.length === 0) {
      error.value = '선택된 문서가 없습니다.';
      return;
    }
    showModal.value = true;
  }



  const deleteSelectedSources = async () => {
    if (state.selectedSources.length === 0) {
      state.showWarning = true;
      setTimeout(() => {
        state.showWarning = false;
      }, 3000);
      return;
    }

    showConfirmAlert(`선택한 ${state.selectedSources.length}개의 문서를 삭제하시겠습니까?`, async (confirmed) => {
      if (!confirmed) return;

      isLoading.value = true;
      try {
        const documentsWithCollections = state.selectedSources.map(source => {
          const collection = state.selectedCollections.find(collection => 
            getDocumentsForCollection(collection).includes(source)
          );
          return {
            collection,
            source
          };
        });

        const response = await axios.post(`${API_BASE_URL}/api/delete-sources`, {
          collections: state.selectedCollections,
          documents: documentsWithCollections
        });

        if (response.data.success) {
          await fetchDocumentsForCollections(state.selectedCollections);
          state.selectedSources = [];
          alertType.value = 'alert';
          alertMessage.value = '선택한 문서들이 성공적으로 삭제되었습니다.';
          showAlert.value = true;
        } else {
          throw new Error(response.data.message || '문서 삭제 중 오류가 발생했습니다.');
        }
      } catch (error) {
        console.error('문서 삭제 중 오류:', error);
        alertType.value = 'alert';
        alertMessage.value = '문서 삭제 중 오류가 발생했습니다: ' + (error.response?.data?.message || error.message);
        showAlert.value = true;
      } finally {
        isLoading.value = false;
      }
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && showModal.value) {
      closeModal();
    }
  }

  // 컬렉션의 권한을 확인하는 함수들 추가
  const hasWritePermission = (collectionName) => {
    // collectionsWithPermissions에서 해당 컬렉션 찾기
    const collection = Object.values(state.collectionsWithPermissions).find(
      c => c.name === collectionName
    );
    return collection?.permissions?.write || false;
  };

  const hasDeletePermission = (collectionName) => {
    // collectionsWithPermissions에서 해당 컬렉션 찾기
    const collection = Object.values(state.collectionsWithPermissions).find(
      c => c.name === collectionName
    );
    return collection?.permissions?.delete || false;
  };

  // 선택된 컬렉션들에 대한 삭제 권한 확인
  const hasDeletePermissionForSelected = computed(() => {
    return state.selectedCollections.some(collection => hasDeletePermission(collection));
  });

  watch(() => state.selectedOption, emitUpdatedData);
   watch(currentModelInfo, emitUpdatedData, { deep: true });
   watch(() => state.selectedSources, (newSources) => {
     console.log('Selected sources changed:', newSources);
   }, { deep: true });
   watch(() => state.selectedMode, updateSelectedMode);

   onMounted(async () => {
     await fetchCollections();
     if (state.collections.length > 0) {
       state.selectedCollections = [...state.collections];
       state.selectAllCollections = true;
       
       state.collections.forEach(collection => {
         state.expandedCollections.add(collection);
       });
       
       await fetchDocumentsForCollections(state.collections);
       store.dispatch('updateSelectedCollections', state.selectedCollections);
     }
     document.addEventListener('keydown', handleKeyDown);
   });

   onUnmounted(() => {
     if (eventSource.value) {
       eventSource.value.close();
       eventSource.value = null;
     }
     document.removeEventListener('keydown', handleKeyDown);
     document.body.classList.remove('modal-open');
   });

   return {
    state,
    currentModelInfo,
    toggleCollection,
    isCollectionExpanded,
    getDocumentsForCollection,
    handleCollectionSelect,
    hasSelectedDocuments,
    showFileUploadDialogForCollection,
    closeFileUploadDialog,
    summarizeSources,
    deleteSelectedSources,
    isLoading,
    summary,
    showModal,
    error,
    progress,
    openModal,
    closeModal,
    renderedSummary,
    handleEmbeddingCompleted,
    handleSelectAllCollections,
    isCollectionSelected,
    handleSelectAllDocuments,
    selectedCollections,
    authContext,
    handleDocumentSelect,
    isDocumentSelected,
    hasWritePermission,
    hasDeletePermission,
    hasDeletePermissionForSelected,     
    showAlert,
    alertMessage,
    closeAlert,
    showCustomAlert,
    alertType,
    handleConfirm,
    handleCancel,
    showConfirmAlert
  }
}});
</script>


<style scoped>
.disabled-btn {
  opacity: 0.5;
  cursor: not-allowed !important;
  background-color: #666 !important;
}

.collection-upload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: #666;
}

.collection-upload-btn:disabled:hover {
  background-color: #666;
}


/* 트리 구조 스타일 */
.tree-container {
  background-color: #1e1e1e;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 15px;
  margin-bottom: 15px;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.tree-view {
  background-color: #2a2a2a;
  border-radius: 4px;
  padding: 10px;
}

.tree-item {
  margin-bottom: 5px;
}

.collection-item {
  display: flex;
  align-items: center;
  padding: 5px;
  background-color: #333;
  border-radius: 4px;
  cursor: pointer;
}

.collection-item:hover {
  background-color: #444;
}

.collection-content {
  display: flex;
  align-items: center;
  flex: 1;
}

.expand-icon {
  cursor: pointer;
  margin-right: 5px;
  user-select: none;
  width: 20px;
  text-align: center;
  color: #888;
}

.documents-list {
  margin-left: 25px;
  padding: 5px 0;
}

.document-item {
  display: flex;
  align-items: center;
  padding: 3px 5px;
  margin: 2px 0;
  border-radius: 3px;
}

.document-item:hover {
  background-color: #3a3a3a;
}

.collection-select-all {
  padding: 10px;
  margin-bottom: 10px;
  background-color: #2a2a2a;
  border-radius: 4px;
}

.document-select-all {
  padding: 5px 0;
  margin-bottom: 5px;
  border-bottom: 1px solid #444;
}

/* 체크박스 스타일 */
input[type="checkbox"] {
  margin-right: 8px;
  cursor: pointer;
}

/* 버튼 스타일 */
.collection-upload-btn {
  width: 24px;
  height: 24px;
  background-color: #1a3a5a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 16px;
  margin-left: 10px;
  transition: background-color 0.2s;
}

.collection-upload-btn:hover {
  background-color: #254b73;
}

/* 모델 정보 */
.current-model-info {
  font-size: 14px;
  color: #888;
  margin-bottom: 10px;
}

/* 경고 메시지 */
.warning-message {
  color: #ff6b6b;
  margin-top: 10px;
}

/* 작업 버튼 */
.action-buttons {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  gap: 10px;
}

.summarize-button,
.delete-button {
  width: 48%;
  padding: 10px;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.summarize-button {
  background-color: #1a3a5a;
}

.summarize-button:hover {
  background-color: #254b73;
}

.delete-button {
  background-color: #a63232;
}

.delete-button:hover {
  background-color: #bf3a3a;
}

.summarize-button:disabled,
.delete-button:disabled {
  background-color: #444;
  cursor: not-allowed;
}

/* 모드 선택 */
.mode-selection {
  margin-bottom: 15px;
}

.mode-selection label {
  margin-right: 15px;
  color: white;
}

.mode-selection input[type="radio"] {
  margin-right: 5px;
  appearance: none;
  width: 16px;
  height: 16px;
  border: 2px solid rgb(255, 253, 252);
  border-radius: 50%;
  outline: none;
  cursor: pointer;
}

.mode-selection input[type="radio"]:checked {
  background-color: rgb(240, 111, 5);
  box-shadow: inset 0 0 0 3px #1e1e1e;
}

/* 로딩 및 에러 상태 */
.loading, .error {
  padding: 20px;
  text-align: center;
  font-size: 18px;
}

.error {
  color: #ff6b6b;
}

/* 진행바 */
.progress-bar {
  width: 100%;
  background-color: #ddd;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 10px;
}

.progress-bar-fill {
  height: 20px;
  background-color: #4CAF50;
  transition: width 0.3s ease-in-out;
}

/* 모달 관련 스타일 추가 */
.large-modal {
  max-width: 90vw;
  max-height: 90vh;
}

.large-modal :deep(.modal-container) {
  width: 100%;
  height: 100%;
}

.large-modal :deep(.modal-body) {
  padding: 20px;
  height: calc(100% - 60px);
}

.chat-view {
  position: relative;
  padding: 10px;
  margin-right: 10px;
  margin-top: 10px;
  color: white;
  background-color: #1e1e1e;
}

/* 모달이 열려있을 때 채팅 뷰 영역 클릭 방지 */
.chat-view.modal-open::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 9998;
  pointer-events: auto;
}

:deep(.modal-overlay) {
  z-index: 9999;
}

:deep(.modal-container) {
  z-index: 10000;
}

.simple-alert {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 10000;
}

.alert-box {
  background-color: #2c2c2c;
  padding: 20px;
  border-radius: 8px;
  min-width: 300px;
  text-align: center;
}

.alert-message {
  color: rgb(255, 255, 255);
  margin-bottom: 15px;
}


.confirm-button {
  background-color: #4CAF50;
  border: none;
  padding: 8px 20px;
  border-radius: 4px;
  cursor: pointer;
  min-width: 80px;
}

.cancel-button {
  background-color: #f44336;
}

.alert-button {
  color: white;
  border: none;
  padding: 8px 20px;
  border-radius: 4px;
  cursor: pointer;
  min-width: 80px;
}

.alert-button:hover {
  opacity: 0.9;
}
</style>