<template>
  <div v-if="show" class="modal-overlay">
    <div class="modal-content">
      <div class="modal-header">
        <h3>파일을 선택해주세요 ({{ selectedCollection }})</h3>
        <button class="close-button" @click="closeDialog">&times;</button>
      </div>
      <div class="modal-body">
        <div class="file-upload-container">
          <div 
            ref="dropZoneRef"
            class="file-selector"
          >
            <input 
              type="file" 
              @change="onFileSelected" 
              multiple 
              ref="fileInputRef" 
              accept=".hwp,.pdf,.ppt,.pptx,.doc,.docx,.md,.html,.txt,.xls,.xlsx,.csv"
              style="display:none;"
            >
            <button @click="triggerFileInput" class="select-files-btn">파일 선택</button>
            <p>또는 파일을 여기에 드래그 앤 드롭하세요</p>
            <p class="file-types">허용된 파일 형식: hwp, pdf, ppt, doc, md, html, txt</p>
          </div>
          <div class="selected-files">
            <h4>선택된 파일</h4>
            <ul class="file-list">
              <li v-for="(file, index) in selectedFiles" :key="file.name + index">
                <span>{{ file.name }}</span>
                <button @click="removeFile(index)" class="remove-file-btn">-</button>
              </li>
            </ul>
          </div>
          <div class="action-buttons">
            <button 
              class="embed-button" 
              @click="startEmbedding" 
              :disabled="selectedFiles.length === 0 || isEmbedding"
            >
              {{ isEmbedding ? '임베딩 중...' : '임베딩 시작' }}
            </button>
          </div>

          <!-- 커스텀 알림창 추가 -->
          <div v-if="showAlert" class="custom-alert">
            <div class="alert-content">
              <div class="alert-message">{{ alertMessage }}</div>
              <button class="alert-button" @click="closeAlert">확인</button>
            </div>
          </div>

          <div v-if="isEmbedding" class="embedding-overlay">
            <div class="progress-container">
              <div class="progress-bar"></div>
              <div class="progress-text">
                {{ Math.round(embeddingProgress) }}% 완료<br>
                ({{ completedFiles }}/{{ totalFiles }} 파일)
              </div>
            </div>
          </div>

          <div v-if="errorMessage" class="error-message">
            {{ errorMessage }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import axios from 'axios';
import { useStore } from 'vuex';

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

export default {
  name: 'FileUploadDialog',
  props: {
    show: {
      type: Boolean,
      default: false
    },
    selectedCollection: {
      type: String,
      default: ''
    }
  },

  emits: ['close', 'embedding-completed', 'files-dropped'],
  setup(props, { emit }) {
    const dropZoneRef = ref(null);
    const fileInputRef = ref(null);
    const selectedFiles = ref([]);
    const allowedExtensions = ['hwp', 'pdf', 'ppt', 'pptx', 'doc', 'docx', 'md', 'html', 'txt', 'xls', 'csv', 'xlsx'];
    const embeddingProgress = ref(0);
    const isEmbedding = ref(false);
    const completedFiles = ref(0);
    const totalFiles = ref(0);
    const errorMessage = ref('');
    const isUploading = ref(false);
    const cancelTokenSources = ref([]);
    const showAlert = ref(false);
    const alertMessage = ref('');
 
    const store = useStore();
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);

    const formatFileSize = (bytes) => {
      if (bytes < 1024) return bytes + ' B';
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
      return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    };

    const handleDragOver = (e) => {
      e.preventDefault();
      e.stopPropagation();
    };

    const handleDrop = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const files = Array.from(e.dataTransfer.files);
      addFiles(files);
    };

    const triggerFileInput = () => {
      if (fileInputRef.value) {
        fileInputRef.value.click();
      }
    };

    const onFileSelected = (event) => {
      const newFiles = Array.from(event.target.files);
      addFiles(newFiles);
    };

    const addFiles = (files) => {
      files.forEach(file => {
        if (!isValidFileType(file)) {
          alertMessage.value = `지원하지 않는 파일 형식입니다: ${file.name}`;
          showAlert.value = true;
          return;
        }
        
        if (file.size > MAX_FILE_SIZE) {
          alertMessage.value = `파일 크기가 제한(${formatFileSize(MAX_FILE_SIZE)})을 초과했습니다: ${file.name} (${formatFileSize(file.size)})`;
          showAlert.value = true;
          return;
        }

        if (!selectedFiles.value.some(f => f.name === file.name)) {
          selectedFiles.value.push(file);
        }
      });
    };

    const removeFile = (index) => {
      selectedFiles.value.splice(index, 1);
    };

    const isValidFileType = (file) => {
      const extension = file.name.split('.').pop().toLowerCase();
      return allowedExtensions.includes(extension);
    };

    const closeAlert = () => {
      showAlert.value = false;
      
      if (alertMessage.value.includes('성공적으로 완료')) {
        resetState();
        emit('close');
      }
    };

    const startEmbedding = async () => {
      if (isUploading.value) return;
      
      isUploading.value = true;
      isEmbedding.value = true;
      embeddingProgress.value = 0;
      completedFiles.value = 0;
      totalFiles.value = selectedFiles.value.length;
      errorMessage.value = '';
      cancelTokenSources.value = []; // Reset cancel token sources
      let hasError = false;

      // 전체 파일 크기 체크
      const totalSize = selectedFiles.value.reduce((acc, file) => acc + file.size, 0);
      if (totalSize > MAX_FILE_SIZE) {
        errorMessage.value = `전체 파일 크기(${formatFileSize(totalSize)})가 제한(${formatFileSize(MAX_FILE_SIZE)})을 초과했습니다.`;
        isEmbedding.value = false;
        isUploading.value = false;
        return;
      }
      
      try {
        for (const file of selectedFiles.value) {
          try {
            const cancelTokenSource = axios.CancelToken.source();
            cancelTokenSources.value.push(cancelTokenSource);
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('collection', props.selectedCollection);

            const response = await axios.post(`${apiBaseUrl.value}/api/upload_and_embed`, formData, {
              headers: {
                'Content-Type': 'multipart/form-data'
              },
              timeout: 600000, // 10분
              maxContentLength: MAX_FILE_SIZE,
              maxBodyLength: MAX_FILE_SIZE,
              cancelToken: cancelTokenSource.token,
              onUploadProgress: (progressEvent) => {
                if (progressEvent.lengthComputable) {
                  const percentCompleted = Math.round(
                    (progressEvent.loaded * 100) / progressEvent.total
                  );
                  updateProgress(percentCompleted);
                }
              }
            });

            if (response.data.success) {
              console.log(`Embedded ${response.data.chunks_stored} chunks for file: ${file.name}`);
              completedFiles.value++;
              updateProgress(100);
            } else {
              throw new Error(response.data.error || 'Unknown error occurred');
            }
          } catch (error) {
            if (axios.isCancel(error)) {
              console.log('Upload cancelled');
              errorMessage.value = '업로드가 취소되었습니다.';
            } else {
              let errorMsg = '파일 처리 중 오류가 발생했습니다.';
              if (error.response) {
                errorMsg = error.response.data.message || error.response.data.error || errorMsg;
              } else if (error.request) {
                errorMsg = '서버 연결에 실패했습니다. 네트워크 상태를 확인해주세요.';
              } else {
                errorMsg = error.message || errorMsg;
              }
              console.error(`Error processing file ${file.name}:`, error);
              errorMessage.value = `Error processing file ${file.name}: ${errorMsg}`;
              hasError = true;
              break;
            }
          }
        }
      } finally {
        isUploading.value = false;
        isEmbedding.value = false;
      }

      if (!hasError) {
        emit('embedding-completed', props.selectedCollection);
        alertMessage.value = '임베딩이 성공적으로 완료되었습니다.';
        showAlert.value = true;
      } else {
        alertMessage.value = '임베딩 중 에러가 발생했습니다. 에러 메시지를 확인하세요!';
        showAlert.value = true;
      }
    };

    const updateProgress = (fileProgress) => {
      const totalProgress = ((completedFiles.value / totalFiles.value) * 100) + 
                          (fileProgress / totalFiles.value);
      embeddingProgress.value = Math.min(totalProgress, 100);
    };

    const cancelUpload = () => {
      cancelTokenSources.value.forEach(source => {
        if (source) {
          source.cancel('Upload cancelled by user');
        }
      });
      cancelTokenSources.value = [];
    };

    const resetState = () => {
      embeddingProgress.value = 0;
      selectedFiles.value = [];
      isEmbedding.value = false;
      isUploading.value = false;
      completedFiles.value = 0;
      totalFiles.value = 0;
      errorMessage.value = '';
      showAlert.value = false;
      alertMessage.value = '';
      
      // Safe way to reset file input
      if (fileInputRef.value) {
        try {
          fileInputRef.value.value = '';
        } catch (e) {
          console.warn('Could not reset file input', e);
        }
      }
      
      // Cancel any ongoing uploads
      cancelUpload();
    };

    const closeDialog = () => {
      if (isUploading.value) {
        alertMessage.value = '업로드가 진행 중입니다. 정말로 취소하시겠습니까?';
        showAlert.value = true;
        return;
      }
      resetState();
      emit('close');
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && props.show) {
        closeDialog();
      }
    };

    onMounted(() => {
      if (dropZoneRef.value) {
        dropZoneRef.value.addEventListener('dragover', handleDragOver);
        dropZoneRef.value.addEventListener('drop', handleDrop);
      }
      document.addEventListener('keydown', handleKeyDown);
    });

    onUnmounted(() => {
      document.removeEventListener('keydown', handleKeyDown);
      if (dropZoneRef.value) {
        dropZoneRef.value.removeEventListener('dragover', handleDragOver);
        dropZoneRef.value.removeEventListener('drop', handleDrop);
      }
      cancelUpload();
    });

    return {
      dropZoneRef,
      fileInputRef,
      selectedFiles,
      embeddingProgress,
      isEmbedding,
      completedFiles,
      totalFiles,
      errorMessage,
      triggerFileInput,
      onFileSelected,
      removeFile,
      startEmbedding,
      closeDialog,
      formatFileSize,
      showAlert,
      alertMessage,
      closeAlert
    };
  }
}
</script>
  
<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}
  
.modal-content {
  background-color: #1e1e1e;
  width: 90%;
  height: 90%;
  max-width: 800px;
  max-height: 600px;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08);
}  

.modal-header {
  background-color: #333;
  padding: 10px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  color: white;
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  font-size: 24px;
  color: white;
  cursor: pointer;
}

.modal-body {
  flex-grow: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.file-upload-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 20px;
}

.file-selector {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  border: 2px dashed #444;
  border-radius: 4px;
  padding: 20px;
}

.select-files-btn {
  padding: 10px 20px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 10px;
}

.selected-files {
  flex-grow: 1;
  background-color: #2c2c2c;
  border: 1px solid #444;
  border-radius: 4px;
  overflow: auto;
  padding: 10px;
}

.file-list {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.file-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 10px;
  border-bottom: 1px solid #444;
}

.remove-file-btn {
  background-color: #f44336;
  color: white;
  border: none;
  padding: 2px 5px;
  border-radius: 2px;
  cursor: pointer;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
}

.embed-button {
  padding: 10px 20px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.embed-button:disabled {
  background-color: #555;
  cursor: not-allowed;
}

.file-types {
  font-size: 12px;
  color: #888;
  margin-top: 10px;
}

/* 수정된 프로그레스 컨테이너와 바 */
.progress-container {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10000;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.progress-bar {
  width: 80px;
  height: 80px;
  border: 5px solid #f3f3f3;
  border-top: 5px solid #4CAF50;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.progress-text {
  color: white;
  background-color: rgba(0, 0, 0, 0.7);
  padding: 10px 20px;
  border-radius: 4px;
  font-size: 14px;
  text-align: center;
}

.embedding-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 9999;
}

.error-message {
  color: #ff6b6b;
  margin-top: 10px;
  padding: 10px;
  background-color: #2c2c2c;
  border: 1px solid #ff6b6b;
  border-radius: 4px;
}

/* 커스텀 알림창 스타일 */
.custom-alert {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background-color: #2c2c2c;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 10001;
  min-width: 300px;
  max-width: 80%;
}

.alert-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.alert-message {
  color: white;
  text-align: center;
  font-size: 16px;
  line-height: 1.4;
}

.alert-button {
  background-color: #4CAF50;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  min-width: 100px;
  transition: background-color 0.3s;
}

.alert-button:hover {
  background-color: #45a049;
}

/* 반응형 디자인을 위한 미디어 쿼리 */
@media (max-width: 768px) {
  .select-files-btn {
    font-size: 14px;
    padding: 8px 16px;
  }
  
  .alert-message {
    font-size: 14px;
  }
  
  .alert-button {
    font-size: 12px;
    padding: 8px 16px;
  }
}

@media (max-width: 480px) {
  .custom-alert {
    min-width: 250px;
    padding: 15px;
  }
  
  .alert-message {
    font-size: 13px;
  }
  
  .alert-button {
    font-size: 11px;
    padding: 6px 12px;
  }
}
</style>