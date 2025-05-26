<template>
  <div>
    <button @click="summarizeSource" :disabled="isLoading" class="summarize-button">
      {{ isLoading ? '요약 중...' : '선택한 소스 요약하기' }}
    </button>
    
    <div v-if="isLoading" class="progress-container">
      <div class="progress-info">
        <div class="current-document" v-if="currentDocument">
          처리 중: {{ currentDocument }}
        </div>
        <div class="progress-bar">
          <div class="progress-bar-fill" :style="{ width: `${progress}%` }">
            <span class="progress-text">{{ progress.toFixed(1) }}%</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="error" class="error">
      {{ error }}
    </div>

    <div v-if="summary" class="summary">
      <h3>요약:</h3>
      <div v-html="renderedSummary"></div>
    </div>
  </div>
</template>

<script>
import { ref, onUnmounted, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useStore} from 'vuex';



export default {
  props: {
    selectedSources: {
      type: Array,
      required: true
    },
    collectionName: {
      type: String,
      required: true
    },
    llmName: {
      type: String,
      required: true
    },
    llmModel: {
      type: String,
      required: true
    }
  },


  setup(props) {
    const isLoading = ref(false)
    const summary = ref('')
    const progress = ref(0)
    const error = ref('')
    const currentDocument = ref('')
    let eventSource = null
    const store = useStore();
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl);

    const renderedSummary = computed(() => {
      return DOMPurify.sanitize(marked(summary.value))
    })

    const processStreamData = (data) => {
      try {
        const parsedData = JSON.parse(data)
        console.log('Received data:', parsedData)
        
        switch (parsedData.type) {
          case 'progress':
            progress.value = parsedData.progress
            if (parsedData.document) {
              currentDocument.value = parsedData.document
            }
            break
          case 'summary':
            summary.value = parsedData.value
            break
          case 'complete':
            isLoading.value = false
            progress.value = 100
            if (eventSource) {
              eventSource.close()
            }
            break
          case 'error':
            error.value = parsedData.value
            isLoading.value = false
            if (eventSource) {
              eventSource.close()
            }
            break
        }
      } catch (err) {
        console.error('데이터 파싱 오류:', err)
        error.value = '데이터 처리 중 오류가 발생했습니다.'
      }
    }

    const summarizeSource = () => {
      if (props.selectedSources.length === 0) {
        error.value = '선택된 소스가 없습니다.'
        return
      }

      isLoading.value = true
      progress.value = 0
      summary.value = ''
      error.value = ''
      currentDocument.value = ''

      try {
        const params = new URLSearchParams({
          collections: JSON.stringify([props.collectionName]),
          documents: JSON.stringify(props.selectedSources),
          llm_name: props.llmName,
          llm_model: props.llmModel
        })

        eventSource = new EventSource(`${apiBaseUrl.value}/api/summarize-sse?${params}`)

        eventSource.onmessage = (event) => processStreamData(event.data)

        eventSource.onerror = (err) => {
          console.error('SSE Error:', err)
          error.value = '요약 중 오류가 발생했습니다. 서버 연결을 확인해주세요.'
          isLoading.value = false
          eventSource.close()
        }

        eventSource.onopen = () => {
          console.log('SSE connection opened')
        }

      } catch (err) {
        console.error('Error in summarizeSource:', err)
        error.value = err.message || '요약 중 오류가 발생했습니다.'
        isLoading.value = false
      }
    }

    onUnmounted(() => {
      if (eventSource) {
        eventSource.close()
      }
    })

    return {
      isLoading,
      summary,
      progress,
      error,
      currentDocument,
      renderedSummary,
      summarizeSource
    }
  }
}
</script>

<style scoped>
.summarize-button {
  padding: 10px 20px;
  background-color: #1a3a5a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.summarize-button:hover:not(:disabled) {
  background-color: #254b73;
}

.summarize-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.progress-container {
  margin-top: 20px;
}

.progress-info {
  background: #1e1e1e;
  padding: 15px;
  border-radius: 8px;
}

.current-document {
  margin-bottom: 10px;
  color: #fff;
  font-size: 14px;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: #2a2a2a;
  border-radius: 10px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #1a3a5a, #254b73);
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.progress-text {
  color: white;
  font-size: 12px;
  text-shadow: 1px 1px 1px rgba(0,0,0,0.5);
}

.error {
  margin-top: 15px;
  padding: 10px;
  color: #ff5252;
  background: #1e1e1e;
  border-radius: 4px;
}

.summary {
  margin-top: 20px;
  padding: 20px;
  background: #1e1e1e;
  border-radius: 8px;
  color: white;
}

.summary h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #fff;
}
</style>