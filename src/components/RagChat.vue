<template>  
  <div class="ragchat-container">
    <div v-if="isLoading" class="global-loading-overlay">
      <div class="progress-bar"></div>
    </div>
    <div class="main-content">
      <aside :class="['sidebar', { 'collapsed': isSidebarCollapsed }]">
        <div class="sidebar-content" v-show="!isSidebarCollapsed">
          <button 
            v-for="view in views" 
            :key="view.name"
            class="sidebar-button" 
            @click="setView(view.name)" 
            :class="{ active: currentView === view.name }"
          >
            {{ view.label }}
          </button>
        </div>
      </aside>
      <div v-if="currentView !== 'docsimilar'" :class="['control-group', { 'collapsed': isControlGroupCollapsed }]">        
        <div class="control-group-content" v-show="!isControlGroupCollapsed">
          <component 
            :is="currentViewComponent" 
            @update-selected-sources="updateSelectedSources"
            @embedding-completed="handleEmbeddingCompleted" 
          />
        </div>
      </div>
      <main class="content" v-if="currentView !== 'docsimilar'">
        <div class="current-model-info">
          현재 사용 중인 모델: {{ currentLlmSource }} - {{ currentLlmModel }}
        </div>
        <div class="footer-content">
          <div class="input-row">
            <div class="score-input-container">
              <br>
              유사도 &ensp;
              <input 
                type="number" 
                class="score-input"
                v-model="isScore_threshold"
                placeholder="Score (0.0-1.0)"
                step="0.1"
                min="0"
                max="1"
                :disabled="isLoading"
              >
            </div>
            <button 
              class="search-button" 
              @click="sendMessage" 
              :disabled="isLoading"
            >
              검색
            </button>
            <input 
              type="text" 
              class="chat-input" 
              placeholder="검색어를 입력하세요" 
              v-model="inputMessage"
              @keyup.enter="sendMessage"
              :disabled="isLoading"
            >
          </div>
        </div>
         
        <div class="splitter-container">
          <div class="chat-messages-container">
            <ChatMessages :messages="chatMessages" />
          </div>
          <div class="resizer" @mousedown="startResize"></div>
          <details class="docs-list-details" :open="isDocsListOpen">
            <summary class="docs-summary">
              <div class="docs-title">
                <span class="triangle-icon">▼</span>
                <span @click.stop="toggleDocsList">참고 문서</span>
              </div>
              <button 
                class="summarize-docs-button"
                @click.stop="summarizeSelectedDocs"
                :disabled="!hasSelectedDocs"
              >
                첨부요약
              </button>
              <div class="line-input-container">               
              <input 
                type="number" 
                class="line-input"
                v-model="isLine_threshold"
                placeholder="문장수(1-30)"
                step="1"
                min="0"
                max="30"
                :disabled="isLoading"              >
                Line
            </div>
            </summary>
            <div class="docs-list-container">
              <ul>
                <li v-for="doc in docsList" :key="`${doc.title}-${doc.page}`">
                  <div class="doc-item">
                    <input 
                      type="checkbox" 
                      :id="`doc-${doc.title}-${doc.page}`"
                      :checked="isDocSelected(doc)"
                      @change="toggleDocSelection(doc)"
                    >
                    <label 
                      :for="`doc-${doc.title}-${doc.page}`"
                      @click="selectDoc(doc)"
                    >
                      문서명: {{ doc.title }} - Page {{ doc.page }}
                    </label>
                  </div>
                </li>
              </ul>
            </div>
          </details>
        </div>        
        <div v-if="isLoading" class="progress-bar"></div> 
      </main>
      <div v-else class="doc-similarity-container">
        <DocSimilarity />
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, defineComponent, watch, nextTick} from 'vue';
import axios from 'axios';
import ChatView from './ChatView.vue';
import DbView from './DbView.vue';
import LlmView from './LlmView.vue';
import DocSimilarity from './DocSimilarity.vue';
import ChatMessages from './ChatMessages.vue';
import SystemMessage from './SystemMessage.vue';
import { marked } from 'marked'
import { useStore} from 'vuex';



function formatContent(content) {
  if (!content) return '';
  
  try {
    let text = typeof content === 'object' ? JSON.stringify(content) : String(content);
    
    // 1. 기본 텍스트 정리
    text = text
      // 특수문자 정리
      .replace(/[•]/g, '-')
      .replace(/∼/g, '-')
      // 불필요한 공백 제거
      .replace(/\s+/g, ' ')
      // 줄바꿈 정규화
      .replace(/\n\s*\n/g, '\n');

    // 2. 헤더 포맷팅 (모든 헤더에 대해 한 줄바꿈 및 간격 조정)
    text = text.replace(/^(#{2,})\s*([^\n]+)/gm, (match, hashes, content) => {
      return `\n${hashes} ${content.trim()}\n`;
    });

    // 3. 테이블 정리 및 구조화
    text = text.replace(/\|[^\n]+\|/g, (match) => {
      const cells = match.split('|')
        .map(cell => cell.trim())
        .filter(cell => cell !== '');
      
      // 첫 번째 줄이면 구분선 추가
      if (cells.length > 0) {
        const separatorLine = cells.map(() => '---').join('|');
        return `| ${cells.join(' | ')} |\n| ${separatorLine} |`;
      }
      
      return match;
    });

    // 4. 구조적 정리
    text = text
      // 목록 항목 포맷팅
      .replace(/^[-•]\s*([^\n]+)/gm, '- $1')
      // 시간 포맷팅
      .replace(/(\d{2})[-∼](\d{2})/g, '$1:00-$2:00')
      // 괄호 내용 정리
      .replace(/\(\s*([^)]+)\s*\)/g, '($1)')
      // 연속된 공백 줄 제거
      .replace(/\n{3,}/g, '\n\n');

    // 5. 최종 정리
    return text
      .split('\n')
      .map(line => line.trim())
      .filter(line => line !== '')
      .join('\n')
      .trim();

  } catch (error) {
    console.error('Content formatting error:', error);
    return String(content);
  }
}

// 안전한 마크다운 파싱
function safeMarkdownParse(content) {
  if (!content) return '';

  try {
    const formattedContent = formatContent(content);
    
    marked.setOptions({
      breaks: true,         // \n을 <br>로 변환
      gfm: true,           // GitHub Flavored Markdown 활성화
      headerIds: false,     // 헤더 ID 비활성화
      mangle: false,       // 이메일 주소 변환 방지
      smartypants: true,   // 스마트 문장 부호 변환
      tables: true,        // 테이블 지원
      xhtml: true,         // XHTML 스타일 태그
      pedantic: false,     // 엄격하지 않은 마크다운 처리
      sanitize: false      // HTML 허용
    });
    
    return marked.parse(formattedContent);
  } catch (error) {
    console.error('Markdown parsing error:', error);
    return '';
  }
}

export { safeMarkdownParse, formatContent };


export default defineComponent({
  name: 'RagChat',
  components: {
    ChatView,
    DbView,
    LlmView,
    DocSimilarity,
    ChatMessages,
    SystemMessage
  },

  setup() {
    const store = useStore();
    const currentView = ref('chat');
    const inputMessage = ref('');
    const isSidebarCollapsed = ref(false);
    const isControlGroupCollapsed = ref(false);
    const chatMessages = ref([]);
    const isLoading = ref(false);
    const docsList = ref([]);
    const selectedDoc = ref(null);
    const isDocsListOpen = ref(true);
    const isScore_threshold = ref(0.6);
    const isLine_threshold = ref(10);
    const selectedDocs = ref(new Set());
    const isResizing = ref(false);
    const chatMessagesHeight = ref('60%'); // 초기 높이
    const apiBaseUrl = computed(() => store.getters.getApiBaseUrl); 

    const startResize = (event) => {
      event.preventDefault();
      isResizing.value = true;
      
      const splitterContainer = document.querySelector('.splitter-container');
      const containerHeight = splitterContainer.offsetHeight;
      const initialY = event.clientY;
      const chatContainer = document.querySelector('.chat-messages-container');
      const initialChatHeight = chatContainer.offsetHeight;

      const handleMouseMove = (e) => {
        if (!isResizing.value) return;
        
        const deltaY = e.clientY - initialY;
        const newChatHeight = Math.min(Math.max(
          containerHeight * 0.2, // 최소 20%
          initialChatHeight + deltaY
        ), containerHeight * 0.8); // 최대 80%
        
        const chatHeightPercent = (newChatHeight / containerHeight) * 100;
        chatMessagesHeight.value = `${chatHeightPercent}%`;
      };

      const handleMouseUp = () => {
        isResizing.value = false;
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = 'default';
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'row-resize';
    };

    const resize = (event) => {
      if (!isResizing.value) return;
      
      const containerHeight = event.currentTarget.offsetHeight;
      const newHeight = Math.min(Math.max(
        20, // 최소 20% 
        (event.clientY / containerHeight) * 100
      ), 80); // 최대 80%
      
      chatMessagesHeight.value = `${newHeight}%`;
    };

    const stopResize = () => {
      isResizing.value = false;
      document.removeEventListener('mousemove', resize);
      document.removeEventListener('mouseup', stopResize);
    };

    const isDocSelected = (doc) => {
      return selectedDocs.value.has(`${doc.title}-${doc.page}`);
    };

    const toggleDocSelection = (doc) => {
      const docKey = `${doc.title}-${doc.page}`;
      if (selectedDocs.value.has(docKey)) {
        selectedDocs.value.delete(docKey);
      } else {
        selectedDocs.value.add(docKey);
      }
    };

    const selectedSources = computed(() => {
      const sources = store.getters.getSelectedSources;
      if (sources && Array.isArray(sources)) {
        return sources.map(source => ({
          ...source,
          id: `${source.collection}-${source.source}`
        }));
      }
      return [];
    });

    const handleDocSelection = (doc) => {
      doc.selected = !doc.selected;
    };

    const selectedCollections = computed(() => {
      return store.state.selectedCollections.length > 0 
        ? store.state.selectedCollections 
        : store.state.currentCollection ? [store.state.currentCollection] : [];
    });

    const selectedMode = computed(() => store.getters.getSelectedMode);
    const currentCollection = computed(() => store.state.currentCollection);
    const currentLlmSource = computed(() => store.state.currentLlmSource);
    const currentLlmModel = computed(() => store.state.currentLlmModel);

    watch(selectedSources, (newSources) => {
      console.log('RagChat: selectedSources updated:', 
        newSources.map(s => ({
          collection: s.collection,
          source: s.source,
          id: s.id
        }))
      );
    }, { deep: true });

    watch(chatMessages, () => {
      nextTick(() => {
        scrollToBottom();
      });
    }, { deep: true });

    const views = [
      { name: 'chat', label: '채팅' },
      { name: 'docsimilar', label: '문서비교'},
      { name: 'db', label: 'DB 관리' },
      { name: 'llm', label: 'LLM 설정' },
      { name: 'sysMsg', label: 'System Messages 설정'}
    ];

    const currentViewComponent = computed(() => {
      switch (currentView.value) {
        case 'chat': return ChatView;
        case 'docsimilar': return DocSimilarity;
        case 'db': return DbView;
        case 'llm': return LlmView;
        case 'sysMsg': return SystemMessage;      
        default: return null;
      }
    });

    const updateSelectedSources = (sources) => {
      const processedSources = sources.map(source => ({
        collection: source.collection,
        source: source.source,
        id: `${source.collection}-${source.source}`
      }));
      console.log('RagChat: Updating selectedSources:', processedSources);
      store.dispatch('updateSelectedSources', processedSources);
    };

    const handleEmbeddingCompleted = async () => {
      console.log('RagChat: Embedding completed');
      store.dispatch('updateSelectedSources', []);
    };    

    const setView = (view) => {
      currentView.value = view;
    };

    const toggleDocsList = () => {
      isDocsListOpen.value = !isDocsListOpen.value;
    };

    const scrollToBottom = () => {
      const container = document.querySelector('.chat-messages-container');
      if (container) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth'
        });
      }
    };

    const resetDocsList = () => {
      docsList.value = [];
      selectedDoc.value = null;
      isDocsListOpen.value = false;
      
      chatMessages.value.push({
        role: 'System',
        content: '참고 문서 목록이 초기화되었습니다.'
      });
    };

    const handleDocs = (docs) => {
      if (docs && Array.isArray(docs)) {
        const uniqueDocs = new Map();
        docs.forEach((doc, index) => {
          const title = doc.title || `Document ${index + 1}`;
          const key = `${title}-${doc.page}`;
          if (!uniqueDocs.has(key)) {
            uniqueDocs.set(key, {
              title: title,
              page: doc.page,
              content: doc.content
            });
          }
        });
        docsList.value = Array.from(uniqueDocs.values());
      }
    };

    const selectDoc = (doc) => {
      selectedDoc.value = doc;
      const markdownContent = `#### ${doc.title} - Page ${doc.page}
<div class="message-content">${doc.content}</div>`;

      chatMessages.value.push({
        role: 'System',
        content: markdownContent
      });

      nextTick(() => {
        scrollToBottom();
      });
    };

    const sendMessage = async () => {
      if (!inputMessage.value.trim() || isLoading.value) return;
      
      const scoreValue = parseFloat(isScore_threshold.value);
      if (isNaN(scoreValue) || scoreValue < 0 || scoreValue > 1) {
        chatMessages.value.push({
          role: 'System',
          content: 'Score 값은 0.0에서 1.0 사이의 숫자여야 합니다.'
        });
        return;
      }

      isLoading.value = true;
      isDocsListOpen.value = true;
      resetDocsList();
      
      const query = inputMessage.value.trim();
      chatMessages.value.push({ role: 'User', content: query });

      try {
        const collections = store.state.selectedCollections.length > 0
          ? [...store.state.selectedCollections]
          : [store.state.currentCollection];

        console.log('Sending collections:', collections);
        
        // sources 처리 로직 수정
        const sources = Array.isArray(selectedSources.value) 
          ? selectedSources.value
              .filter(source => source.collection && source.source)
              .map(source => ({
                collection: source.collection,
                source: source.source
              }))
              .filter((source, index, self) => 
                index === self.findIndex(s => 
                  s.collection === source.collection && 
                  s.source === source.source
                )
              ) 
          : [];

          console.log('Vuex 스토어 상태:', store.state);
          console.log('현재 시스템 메시지:', store.getters.getCurrentSystemMessage);
          
          const currentSystemMessage = store.getters.getCurrentSystemMessage;
          
          console.log('currentSystemMessage 타입:', typeof currentSystemMessage);
          console.log('currentSystemMessage 값:', currentSystemMessage);
        const response = await axios.post(`${apiBaseUrl.value}/api/process_query`, {
          query: query,
          system_message: currentSystemMessage && currentSystemMessage.message 
            ? currentSystemMessage.message 
            : null,
          collections: collections,
          llm_name: currentLlmSource.value,
          llm_model: currentLlmModel.value,
          select_sources: sources,
          ragmode: selectedMode.value || 'RAG',
          score_threshold: scoreValue
        });          
      
        let content = '';
        if (typeof response.data === 'string') {
          content = response.data;
        } else if (typeof response.data === 'object') {
          if (response.data.result) {
            content = response.data.result;
          } else if (response.data.content) {
            content = response.data.content;
          } else if (response.data.error) {
            throw new Error(response.data.error);
          } else {
            content = JSON.stringify(response.data);
          }
        } else {
          throw new Error('Unexpected response type');
        }

        if (response.data.docs && response.data.docs.length > 0) {
          handleDocs(response.data.docs);
        }

        chatMessages.value.push({ role: 'Assistant', content: content });

      } catch (error) {
        console.error('Error processing query:', error);
        let errorMessage = 'An error occurred while processing the query.';
        if (error.response) {
          console.log('Error response:', error.response.data);
          errorMessage = `Server error: ${error.response.data.error || error.response.statusText}`;
        } else if (error.request) {
          errorMessage = 'No response received from the server.';
        } else {
          errorMessage = error.message;
        }
        
        chatMessages.value.push({ role: 'System', content: errorMessage });
      } finally {
        isLoading.value = false;
        inputMessage.value = '';
      }
    };

    const hasSelectedDocs = computed(() => {
      return selectedDocs.value.size > 0;
    });

    const summarizeSelectedDocs = async () => {
      if (!hasSelectedDocs.value || isLoading.value) return;

      const lineValue = parseFloat(isLine_threshold.value);
      if (isNaN(lineValue) || lineValue < 0 || lineValue > 30) {
        chatMessages.value.push({
          role: 'System',
          content: '문장수 값은 1에서 30 사이의 숫자여야 합니다.'
        });
        return;
      }

      isLoading.value = true; // Start loading

      const selectedDocsList = Array.from(selectedDocs.value).map(docKey => {
        return docsList.value.find(doc => 
          `${doc.title}-${doc.page}` === docKey
        );
      }).filter(Boolean);

      if (selectedDocsList.length === 0) {
        isLoading.value = false;
        return;
      }

      const selectedContents = selectedDocsList.map(doc => doc.content).join('\n\n');
      
      chatMessages.value.push({
        role: 'System',
        content: '선택된 문서 요약을 생성 중입니다...'
      });

      try {
        const response = await axios.post(`${apiBaseUrl.value}/api/summarize-selectdocs`, {
          documents: selectedContents,
          lines: lineValue,
          llm_name: currentLlmSource.value,
          llm_model: currentLlmModel.value
        });

        if (response.data.success) {
          chatMessages.value.push({
            role: 'Assistant',
            content: `📝 선택된 문서 요약:\n\n${safeMarkdownParse(response.data.result)}`
          });
        } else {
          throw new Error(response.data.error || '요약 생성에 실패했습니다.');
        }
      } catch (error) {
        console.error('요약 처리 중 오류:', error);
        
        if (error.response) {
          console.error('서버 응답 오류:', error.response.data);
          chatMessages.value.push({
            role: 'System',
            content: `서버 오류: ${error.response.data.error || '알 수 없는 오류'}`
          });
        } else if (error.request) {
          console.error('요청 오류:', error.request);
          chatMessages.value.push({
            role: 'System',
            content: '서버에 연결할 수 없습니다.'
          });
        } else {
          console.error('오류:', error.message);
          chatMessages.value.push({
            role: 'System',
            content: error.message
          });
        }
      } finally {
        isLoading.value = false; // Stop loading when done
      }
    };

    return {
      currentView,
      inputMessage,
      isSidebarCollapsed,
      isControlGroupCollapsed,
      chatMessages,
      views,
      currentViewComponent,
      currentCollection,
      currentLlmSource,
      currentLlmModel,
      setView,
      isLoading,
      selectedSources,
      updateSelectedSources,
      sendMessage,
      docsList,
      selectDoc, 
      isDocsListOpen,
      toggleDocsList,
      selectedCollections,      
      handleEmbeddingCompleted,
      resetDocsList,
      isScore_threshold,
      isLine_threshold,
      handleDocSelection,
      isDocSelected,
      toggleDocSelection,
      selectedDocs,
      hasSelectedDocs,
      summarizeSelectedDocs,
      chatMessagesHeight,
      startResize,
      apiBaseUrl,
      stopResize
    };
  }
});
</script>

<style scoped>
.ragchat-container {
  position: relative;
  height: 100%;
  z-index: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 100%;
  background-color: #000000;
  color: white;
  font-family: Arial, sans-serif;
  font-size: 15px;
  margin: 0;
  padding: 0;
}

.global-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  z-index: 9999;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: not-allowed;
}

.main-content {
  display: flex;
  flex-grow: 1;
  width: 100%;
  height: 98vh;  
  font-size: 15px;
}

/* 사이드바 스타일 */
.sidebar {
  width: 120px;
  flex-shrink: 0;
  background-color: #000000;
  padding: 10px;
  border-right: 1px solid #333;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 15px;
}

.sidebar-button {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 40px;
  margin-bottom: 5px;
  background-color: #000000;
  color: white;
  border: none;
  cursor: pointer;
  text-align: center;
  transition: background-color 0.3s;
  font-size: 15px;
}

.sidebar-button:hover {
  background-color: #333;
}

.sidebar-button.active {
  background-color: #1a3a5a;
}

/* 컨트롤 그룹 스타일 */
.control-group {
  width: 300px;
  flex-shrink: 0;
  padding: 10px;
  margin-left: 10px;
  border-right: 1px solid #333;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  overflow-y: auto;
  background-color: #000000;
  font-size: 15px;
}

/* 메인 컨텐츠 영역 */
.content {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #000000;
  font-size: 15px;
  width: 100%;
  overflow: hidden;
}

.current-model-info {
  font-size: 15px;
  color: #fa5421;
  padding: 10px;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
  line-height: 1.3;
  max-width: 100%;
}

/* 채팅 메시지 스타일 */
.chat-messages-container {
  height: v-bind(chatMessagesHeight);
  min-height: 20%;
  max-height: 80%;
  overflow-y: auto;
  padding: 10px;
  margin: 2px;
  background-color: #111;
  border: 1px solid #333;
  border-radius: 4px;
}

.splitter-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  height: calc(100% - 120px);
  position: relative;
}

.resizer {
  width: 100%;
  height: 8px;
  background-color: #333;
  cursor: row-resize;
  position: relative;
  margin: 2px 0;
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.resizer:hover {
  background-color: #4a4a4a;
}

.resizer::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 2px;
  background-color: #666;
  border-radius: 1px;
}

.text-wrap {
  margin: 2px;
  padding: 10px;
  white-space: pre-wrap !important;
  word-wrap: break-word !important;
  overflow-wrap: break-word !important;
  line-height: 1.3 !important;
  font-size: 15px;
}

/* 입력 영역 스타일 */
.footer-content {
  width: 100%;
  padding: 10px 15px;
}

.input-row {
  display: flex;
  gap: 0.5rem;
  width: 90%;
  max-width: 98%;
  align-items: center;
}

.chat-input {
  flex-grow: 1;
  padding: 10px;
  margin-right: 10px;
  background-color: #111;
  color: white;
  border: 1px solid #333;
  font-size: 15px;
  width: calc(100% - 100px);
}

.search-button {
  padding: 10px 20px;
  background-color: #1a3a5a;
  color: white;
  border: none;
  cursor: pointer;
  font-size: 15px;
  min-width: 80px;
}

/* Score 입력 스타일 */
.score-input-container {
  display: flex;
  align-items: center;
}

.score-input {
  width: 100px;
  padding: 10px;
  background-color: #111;
  color: white;
  border: 1px solid #333;
  border-radius: 4px;
  font-size: 15px;
  margin-right: 10px;
}

.score-input::-webkit-inner-spin-button,
.score-input::-webkit-outer-spin-button {
  opacity: 1;
}

/* line 입력 스타일 */
.line-input-container {
  display: flex;
  align-items: center;
}

.line-input {
  width: 50px;
  padding: 10px;
  background-color: #111;
  color: white;
  border: 1px solid #333;
  border-radius: 4px;
  font-size: 15px;
  margin-right: 10px;
}

.line-input::-webkit-inner-spin-button,
.line-input::-webkit-outer-spin-button {
  opacity: 1;
}

/* 프로그레스 바 스타일 */
.progress-bar {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 80px;
  height: 80px;
  border: 5px solid #f3f3f3;
  border-top: 5px solid #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  z-index: 1001;
}

@keyframes spin {
  0% { transform: translate(-50%, -50%) rotate(0deg); }
  100% { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 문서 리스트 스타일 */
.docs-list-details {
  background-color: #111;
  border-top: 1px solid #333;
  font-size: 15px;
  display: flex;
  flex-direction: column;
  height: calc(100% - v-bind(chatMessagesHeight));
  min-height: 20%;
  max-height: 80%;
  overflow: hidden;
}

.docs-summary {
  display: flex;
  align-items: center;
  gap: 30px;
  padding: 10px;
  background-color: #222;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
  z-index: 1;
}

.docs-list-container {
  flex: 1;
  height: calc(100% - 50px); /* 서머리 높이를 뺀 나머지 공간 */
  overflow-y: auto;
  padding: 10px;
  font-size: 15px;
  background-color: #111;
  scrollbar-width: thin;
  scrollbar-color: #666 #333;
}

.summarize-docs-button {
  background-color: #1a3a5a;
  color: white;
  border: none;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  min-width: 70px;
}

.summarize-docs-button:hover {
  background-color: #254b73;
}

.summarize-docs-button:disabled {
  background-color: #444;
  cursor: not-allowed;
}

.docs-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 리스트 아이템 스타일 */
.docs-list-container ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.docs-list-container li {
  cursor: pointer;
  padding: 10px;
  border-bottom: 1px solid #333;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
  line-height: 1.3;
  font-size: 15px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-item input[type="checkbox"] {
  cursor: pointer;
}

.doc-item label {
  cursor: pointer;
  flex-grow: 1;
  margin: 0;
  padding: 5px 0;
}

.doc-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

/* 스크롤바 스타일 */
.docs-list-container::-webkit-scrollbar {
  width: 8px;
}

.docs-list-container::-webkit-scrollbar-track {
  background: #333;
  border-radius: 4px;
}

.docs-list-container::-webkit-scrollbar-thumb {
  background: #666;
  border-radius: 4px;
}

.docs-list-container::-webkit-scrollbar-thumb:hover {
  background: #888;
}

/* 드래그 중 텍스트 선택 방지 */
.splitter-container.resizing * {
  user-select: none;
}

/* 비활성화 상태 스타일 */
.chat-input:disabled,
.search-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 반응형 디자인 */
@media (max-width: 768px) {
  .sidebar {
    width: 60px;
  }
  
  .control-group {
    width: 200px;
  }
  
  .search-button {
    padding: 10px;
    min-width: 60px;
  }
  
  .score-input {
    width: 80px;
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .sidebar {
    width: 40px;
  }
  
  .control-group {
    width: 150px;
  }
  
  .chat-input {
    font-size: 14px;
  }
  
  .search-button {
    font-size: 14px;
    min-width: 50px;
  }
  
  .score-input {
    width: 60px;
    font-size: 12px;
  }
}
</style>