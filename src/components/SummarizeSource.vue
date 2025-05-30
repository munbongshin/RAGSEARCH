<template>
  <div class="container" :style="containerStyle">
    <!-- Left Sidebar -->
    <div class="sidebar">
      <div class="sidebar-header">
        <h2>문서 목록</h2>
        <button class="maximize-btn">
          <span class="icon">⧉</span>
        </button>
      </div>

      <div class="source-list">        
        <div v-for="(sources, collection) in sourcesByCollection" 
             :key="collection" 
             class="collection-group">
          <div class="collection-header">
            {{ collection }}
          </div>
          
          <div v-for="source in sources" 
               :key="source.id"
               class="source-item"
               :class="{ 'selected': source.selected }"
               @click="selectSource(source.id)">
            <input 
              type="checkbox" 
              class="checkbox"
              :checked="source.selected"
              @change.stop="toggleSource(source.id)"
            >
            <div class="source-info">
              <span :class="['type-badge', getTypeColor(source.type)]">
                {{ source.type.toUpperCase() }}
              </span>
              <span class="source-title">{{ source.title }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Center Panel: Document Content -->
    <div class="center-panel">
      <div class="notebook-header">
        <div class="header-content">
          <div class="notebook-icon"></div>
          <h1 class="notebook-title">
            <span class="highlight">선택한 문서 분석</span>
          </h1>
        </div>
        <div class="source-count">문서{{ selectedSources.length }}개</div>
      </div>

      <div class="content-wrapper">
        <!-- Document View -->
        <div class="document-view">
          <div v-if="selectedSource" class="source-content">
            <span class="title">{{ selectedSource.title }}</span>
            <span class="page-info">({{ currentPage }} / {{ pages?.length || 1 }}페이지)</span>
            
            <div class="page-navigation">
              <!-- 처음/이전 버튼 -->
              <button 
                class="page-btn nav-btn"
                @click="setCurrentPage(1)"
                :disabled="currentPage === 1"
              >
                ≪
              </button>
              <button 
                class="page-btn nav-btn"
                @click="setCurrentPage(currentPage - 1)"
                :disabled="currentPage === 1"
              >
                ＜
              </button>

              <!-- 페이지 번호 -->
              <template v-for="pageNum in displayedPages" :key="pageNum">
                <span v-if="pageNum === '...'" class="page-ellipsis">...</span>
                <button 
                  v-else
                  class="page-btn"
                  :class="{ active: currentPage === pageNum }"
                  @click="setCurrentPage(pageNum)"
                >
                  {{ pageNum }}
                </button>
              </template>

              <!-- 다음/끝 버튼 -->
              <button 
                class="page-btn nav-btn"
                @click="setCurrentPage(currentPage + 1)"
                :disabled="currentPage === totalPages"
              >
                ＞
              </button>
              <button 
                class="page-btn nav-btn"
                @click="setCurrentPage(totalPages)"
                :disabled="currentPage === totalPages"
              >
                ≫
              </button>
            </div>
            
            <div class="page-content" v-html="renderedPageContent || '선택된 문서 페이지의 내용이 여기에 표시됩니다.'"></div>
          </div>
        </div>

        <!-- Summary Panel (이제 center-panel 내부에 위치) -->
        <div class="summary-panel" :class="{ 'collapsed': isPanelCollapsed }">
          <div class="panel-header">
            <h3 v-if="!isPanelCollapsed">문서분석결과</h3>
            <div class="panel-controls">
              <button class="control-btn" @click="togglePanel" title="패널 토글">
                <span class="icon">{{ isPanelCollapsed ? '▶' : '◀' }}</span>
              </button>
              <div v-if="!isPanelCollapsed" class="resize-handle" @mousedown="startResize"></div>
            </div>
          </div>

          <div class="action-buttons">
            <div class="button-group">
              <button class="action-btn">
                <span class="icon">📌</span>
                <span>메모에 저장</span>
              </button>
              <button class="action-btn icon-only">
                <span class="icon">📱</span>
              </button>
            </div>

            <div class="button-group">
              <button class="action-btn">
                <span class="icon">📄</span>
                <span>메모 추가</span>
              </button>
              <button class="action-btn">
                <span class="icon">📚</span>
                <span>브리핑 문서</span>
              </button>
            </div>
          </div>

          <div class="panel-content">
            <div class="summarize-container">
              <button 
                class="summarize-btn"
                @click="showSummary"
                :disabled="isLoading"
              >
                <span class="icon">{{ isLoading ? '⌛' : '📚' }}</span>
                <span>{{ isLoading ? '분석 중...' : '선택한 문서 분석하기' }}</span>
              </button>
            </div>

            <!-- 진행 상태 표시 -->
            <div v-if="isLoading" class="progress-container">
              <div v-if="currentDocument" class="current-document">
                처리 중: {{ currentDocument }}
              </div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progress + '%' }">
                  <span class="progress-text">{{ progress.toFixed(1) }}%</span>
                </div>
              </div>
            </div>

            <!-- 분석 결과 -->
            <div v-if="topSummary" class="top-summary">
              <h3>문서 분석</h3>
              <div 
                class="summary-content"
                :class="{ 'expanded': isExpanded }"
                ref="summaryContent"
              >
                <div v-html="safeMarkdownParse(topSummary)"></div>
                <div v-if="hasOverflow && !isExpanded" class="fade-overlay"></div>
              </div>
              <button 
                v-if="hasOverflow"
                class="expand-btn" 
                @click="toggleExpand"
              >
                {{ isExpanded ? '접기' : '더 보기' }}
              </button>
            </div>

            <!-- 에러 메시지 -->
            <div v-if="error" class="error-message">
              {{ error }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useStore } from 'vuex'
import axios from 'axios'
import { marked } from 'marked'

function formatContent(content) {
  if (!content) return '';
  
  try {
    const text = typeof content === 'object' ? JSON.stringify(content) : String(content);
    
    let markdownContent = text
      .replace(/\n{3,}/g, '\n\n')
      .replace(/^(\d+)\.\s*(.+)$/gm, '**$1. $2**')
      .replace(/^(.+):$/gm, '**$1:**')
      .trim();
    
    return markdownContent;
  } catch (error) {
    console.error('Content formatting error:', error);
    return String(content);
  }
}

function safeMarkdownParse(content) {
  if (!content) return '';

  try {
    const formattedContent = formatContent(content);
    
    marked.setOptions({
      breaks: true,
      gfm: true,
      headerIds: false,
      sanitize: false,
      mangle: false,
      headerPrefix: '',
      smartypants: true
    });
    
    const escaped = formattedContent
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
    
    return marked.parse(escaped);
  } catch (error) {
    console.error('Markdown parsing error:', error);
    return '';
  }
}

export { safeMarkdownParse, formatContent };

export default {
  props: {
    selectedCollectionsSources: {
      type: Object,
      required: true,
      default: () => ({
        sources: [],
        collections: []
      })
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
    const store = useStore()
    const API_BASE_URL = computed(() => store.getters.getApiBaseUrl)

    // Reactive state
    const eventSource = ref(null)
    const selectedSource = ref(null)
    const currentPage = ref(1)
    const isLoading = ref(false)
    const summary = ref('')
    const page_content = ref('')
    const progress = ref(0)
    const error = ref('')
    const currentDocument = ref('')
    const topSummary = ref('')
    const currentPageDetail = ref('')
    const pages = ref([1])
    const isPanelCollapsed = ref(false)
    const windowWidth = ref(window.innerWidth)
    const sidebarWidth = ref(280)
    const panelWidth = ref(400)
    const isExpanded = ref(false)
    const hasOverflow = ref(false)

    // Computed properties
    const containerStyle = computed(() => {
      const summaryPanelWidth = isPanelCollapsed.value ? 40 : panelWidth.value;
      
      return {
        display: 'flex',
        width: '100%',
        height: '100vh',
        overflow: 'hidden',
        paddingRight: `${summaryPanelWidth}px`
      }
    })

    const centerPanelStyle = computed(() => {
      const summaryPanelWidth = isPanelCollapsed.value ? 40 : panelWidth.value;
      const centerPanelWidth = Math.max(
        500, 
        windowWidth.value - sidebarWidth.value - summaryPanelWidth
      );
      
      return {
        width: `${centerPanelWidth}px`,
        minWidth: '500px',
        flex: '1',
        overflowY: 'auto'
      }
    })

    const sources = computed(() => {
      const { sources } = props.selectedCollectionsSources;
      return sources.map(source => ({
        id: `${source.collection}-${source.source}`,
        type: source.source.split('.').pop().toLowerCase(),
        title: source.source,
        collection: source.collection,
        collection_id: parseInt(source.collection_id, 10),
        selected: true
      }));
    })

    const selectedSources = computed(() => 
      sources.value.filter(s => s.selected)
    )

    const renderedPageContent = computed(() => {
      if (page_content.value) {
        return safeMarkdownParse(page_content.value);
      }
      if (topSummary.value) {
        return safeMarkdownParse(topSummary.value);
      }
      return '선택된 문서 페이지의 내용이 여기에 표시됩니다.';
    })

    const sourcesByCollection = computed(() => {
      const grouped = {};
      sources.value.forEach(source => {
        if (!grouped[source.collection]) {
          grouped[source.collection] = [];
        }
        grouped[source.collection].push(source);
      });
      return grouped;
    })

    const totalPages = computed(() => pages.value?.length || 1)

    const displayedPages = computed(() => {
      const total = totalPages.value;
      const current = currentPage.value;
      const range = 5;

      if (total <= 1) return [1];

      let start = Math.max(current - Math.floor(range / 2), 1);
      let end = Math.min(start + range - 1, total);

      // Adjust start if we're near the end
      if (end === total) {
        start = Math.max(total - range + 1, 1);
      }

      const pages = [];

      // Add first page and ellipsis if needed
      if (start > 1) {
        pages.push(1);
        if (start > 2) pages.push('...');
      }

      // Add page numbers in the current range
      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      // Add last page and ellipsis if needed
      if (end < total) {
        if (end < total - 1) pages.push('...');
        pages.push(total);
      }

      return pages;
    })

    // Methods
    const toggleExpand = () => {
      isExpanded.value = !isExpanded.value;
    }

    const checkOverflow = () => {
      if (document.querySelector('.summary-content')) {
        const element = document.querySelector('.summary-content');
        hasOverflow.value = element.scrollHeight > element.clientHeight;
      }
    }

    const handleResize = () => {
      windowWidth.value = window.innerWidth;
    }

    const toggleAllSources = () => {
      const currentState = sources.value.every(s => s.selected);
      sources.value.forEach(source => {
        source.selected = !currentState;
      });
    }

    const toggleSource = (id) => {
      const source = sources.value.find(s => s.id === id);
      if (source) {
        source.selected = !source.selected;
      }
    }

    const togglePanel = () => {
      isPanelCollapsed.value = !isPanelCollapsed.value;
    }

    const startResize = (event) => {
      const startX = event.clientX;
      const startWidth = panelWidth.value;

      const doDrag = (e) => {
        const newWidth = startWidth - (e.clientX - startX);
        panelWidth.value = Math.min(Math.max(newWidth, 300), 800);
      };

      const stopDrag = () => {
        document.removeEventListener('mousemove', doDrag);
        document.removeEventListener('mouseup', stopDrag);
      };

      document.addEventListener('mousemove', doDrag);
      document.addEventListener('mouseup', stopDrag);
    }

    const selectSource = async (id) => {
      selectedSource.value = sources.value.find(s => s.id === id);
      if (selectedSource.value) {
        try {
          const response = await axios.post(`${API_BASE_URL.value}/api/get-document-pages`, {
            collection_id: parseInt(selectedSource.value.collection_id, 10),
            source: encodeURIComponent(selectedSource.value.title)
          });

          if (response.data.success) {
            const documentInfo = response.data.documents;
            if (documentInfo && documentInfo.pages) {
              pages.value = Array.from({ length: documentInfo.pages }, (_, i) => i + 1);
              currentPage.value = 1;
              
              await fetchPageContent(currentPage.value);
            }
          } else {
            console.error('Failed to get document pages:', response.data.error);
            error.value = '페이지 정보를 가져오는데 실패했습니다.';
          }
        } catch (err) {
          console.error('Error fetching document information:', err);
          error.value = '문서 정보를 가져오는 중 오류가 발생했습니다.';
        }
      }     
    }

    const getTypeColor = (type) => {
      const colors = {
        pdf: 'type-pdf',
        doc: 'type-doc',
        txt: 'type-txt'
      };
      return colors[type] || 'type-default';
    }

    const setCurrentPage = async (page) => {
      await fetchPageContent(page);
      currentPageDetail.value = `${page_content.value}`;
    }

    const fetchPageContent = async (page) => {
      currentPage.value = page;
      if (selectedSource.value) {
        try {
          const response = await axios.post(`${API_BASE_URL.value}/api/page-content`, {
            collection_id: parseInt(selectedSource.value.collection_id, 10),
            source: selectedSource.value.title,
            page_num: page.toString(),
            llm_name: props.llmName,
            llm_model: props.llmModel
          });

          if (response.data.success) {
            page_content.value = response.data.pages;
          } else {
            console.error('Failed to get page content:', response.data.error);
            error.value = '페이지 내용을 가져오는데 실패했습니다.';
          }
        } catch (err) {
          console.error('Error fetching page content:', err);
          error.value = '페이지 내용을 가져오는 중 오류가 발생했습니다.';
        }
      }
    }

    const showSummary = () => {
      if (!selectedSource.value) {
        error.value = '선택된 문서가 없습니다.';
        return;
      }
      
      // 상태 초기화
      topSummary.value = '';
      isExpanded.value = false;

      isLoading.value = true;
      progress.value = 0;
      summary.value = '';
      error.value = '';
      currentDocument.value = '';
      
      startSummarizeSource();
    }

    const startSummarization = () => {
      if (selectedSources.value.length === 0) {
        error.value = '선택된 문서가 없습니다.';
        return;
      }     

      try {
        const { sources } = props.selectedCollectionsSources;
        const documentsWithCollections = sources.map(source => ({
          collection: source.collection,
          source: source.source
        }));

        const collections = [...new Set(sources.map(s => s.collection))];

        const params = new URLSearchParams({
          collections: JSON.stringify(collections),
          documents: JSON.stringify(documentsWithCollections),
          llm_name: props.llmName,
          llm_model: props.llmModel
        });

        eventSource.value = new EventSource(`${API_BASE_URL.value}/api/summarize-sse?${params}`);
        
        eventSource.value.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'progress') {
              progress.value = data.progress;
              if (data.document) {
                currentDocument.value = data.document;
              }
            } else if (data.type === 'summary') {
              summary.value = data.value;
              isLoading.value = false;
              closeEventSource();
            } else if (data.type === 'error') {
              throw new Error(data.value);
            }
          } catch (err) {
            console.error('Error processing SSE data:', err);
            error.value = err.message || '데이터 처리 중 오류가 발생했습니다.';
            closeEventSource();
          }
        };

        eventSource.value.onerror = (err) => {
          console.error('SSE Error:', err);
          error.value = '요약 중 오류가 발생했습니다. 서버 연결을 확인해주세요.';
          isLoading.value = false;
          closeEventSource();
        };

      } catch (err) {
        console.error('Error in startSummarization:', err);
        error.value = err.message || '요약 중 오류가 발생했습니다.';
        isLoading.value = false;
      }
    }

    const closeEventSource = () => {
      if (eventSource.value) {
        eventSource.value.close();
        eventSource.value = null;
      }
    }

    const startSummarizeSource = async () => {
      if (!selectedSource.value) {
        error.value = '선택된 문서가 없습니다.';
        return;
      }

      if (!currentPage.value) {
        error.value = '페이지가 선택되지 않았습니다.';
        return;
      }

      try {
        isLoading.value = true;
        error.value = '';

        const response = await axios.post(`${API_BASE_URL.value}/api/summarize-page-content`, {
          collection_id: parseInt(selectedSource.value.collection_id, 10),
          source: selectedSource.value.title,
          page_num: currentPage.value.toString(),
          llm_name: props.llmName,
          llm_model: props.llmModel
        });

        if (response.data.success) {
          topSummary.value = response.data.pages;
        } else {          
          error.value = '페이지 내용을 가져오는데 실패했습니다.';
        }
      } catch (err) {        
        error.value = '요약 중 오류가 발생했습니다.';
      } finally {
        isLoading.value = false;
      }
    }

    // Lifecycle hooks
    onMounted(() => {
      window.addEventListener('resize', checkOverflow);
      checkOverflow();
    })

    onUnmounted(() => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('resize', checkOverflow);
      closeEventSource();
    })


    return {
      // Reactive state and computeds
      containerStyle,
      centerPanelStyle,
      selectedSource,
      currentPage,
      isLoading,
      error,
      page_content,
      pages,
      topSummary,
      sources,
      sourcesByCollection,
      selectedSources,
      renderedPageContent,
      totalPages,
      displayedPages,
      
      // UI State
      isPanelCollapsed,
      windowWidth,
      sidebarWidth,
      panelWidth,
      isExpanded,
      hasOverflow,
      progress,
      currentDocument,
      
      // Methods
      selectSource,
      fetchPageContent,
      setCurrentPage,
      getTypeColor,
      toggleExpand,
      checkOverflow,
      handleResize,
      toggleAllSources,
      toggleSource,
      togglePanel,
      startResize,
      showSummary,
      startSummarization,
      startSummarizeSource,
      closeEventSource,
      
      // Utility functions
      safeMarkdownParse
    };
  }
}
</script>

<style scoped>
/* Container and Layout */
.container {
  display: flex;
  height: 100vh;
  background-color: #1a1a1a;
  color: #e0e0e0;
  position: relative;
  overflow: hidden;
}

/* Sidebar Styles */
.sidebar {
  width: 280px;
  min-width: 280px;
  border-right: 1px solid #333;
  display: flex;
  flex-direction: column;
  background-color: #1a1a1a;
  z-index: 10;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #333;
}

.maximize-btn {
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  padding: 0.5rem;
  transition: color 0.2s ease;
}

.maximize-btn:hover {
  color: #fff;
}

/* Source List Styles */
.source-list {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.collection-group {
  margin-bottom: 1.5rem;
}

.collection-header {
  font-size: 0.875rem;
  font-weight: 500;
  color: #888;
  padding: 0.5rem;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid #333;
}

.source-item {
  display: flex;
  align-items: center;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.source-item:hover {
  background-color: #2a2a2a;
}

.source-item.selected {
  background-color: #2a2a2a;
}

.checkbox {
  margin-right: 0.75rem;
  cursor: pointer;
}

.source-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.source-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Center Panel Styles */
.center-panel {
  flex: 1;
  min-width: 500px;
  padding: 2rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background-color: #1a1a1a;
  position: relative;
  height: 100vh;
}

.content-wrapper {
  display: flex;
  gap: 2rem;
  height: calc(100vh - 140px); /* 헤더 높이 등 고려 */
}

.document-view {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}

.notebook-header {
  margin-bottom: 2rem;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.notebook-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #fff;
}

.source-count {
  font-size: 0.875rem;
  color: #888;
}

/* Source Content Styles */
.source-content {
  background-color: #1e1e1e;
  border-radius: 8px;
  padding: 1.5rem;
  margin-top: 1rem;
}

.title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #fff;
  margin-right: 1rem;
}

.page-info {
  font-size: 0.875rem;
  color: #888;
}

/* Page Content */
.page-content {
  margin-top: 1rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* Summary Panel Styles */
.summary-panel {
  width: 400px;
  min-width: 300px;
  max-width: 800px;
  background-color: #1e1e1e;
  border-left: 1px solid #333;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  height: 100%;
  position: relative;
}

.summary-panel.collapsed {
  width: 40px;
  min-width: 40px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background-color: #2a2a2a;
  border-bottom: 1px solid #333;
  min-height: 60px;
}

.panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 1rem;
  gap: 1rem;
}

/* Summarize Container */
.summarize-container {
  position: sticky;
  top: 0;
  z-index: 10;
  background-color: #1e1e1e;
  padding-bottom: 1rem;
}

/* Action Buttons */
.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  border-bottom: 1px solid #333;
}

.button-group {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  flex: 1;
  padding: 0.75rem;
  background-color: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #e0e0e0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s ease;
  font-size: 0.875rem;
}

.action-btn:hover {
  background-color: #333;
  border-color: #444;
}

.action-btn .icon {
  font-size: 1.1em;
}

/* Summarize Button */
.summarize-btn {
  width: 100%;
  padding: 1rem;
  background-color: #1a3a5a;
  border: none;
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: background-color 0.2s ease;
  font-size: 1rem;
}

.summarize-btn:hover:not(:disabled) {
  background-color: #254b73;
}

.summarize-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* Top Summary Styles */
.top-summary {
  background-color: #1e1e1e;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.top-summary h3 {
  margin: 0 0 1rem 0;
  padding: 0.5rem 0;
  color: #fff;
  font-size: 1.1rem;
}

.summary-content {
  position: relative;
  height: 100%;
  overflow-y: auto;
  padding: 1rem;
  margin: 0;
  background-color: #1e1e1e;
}

.summary-content.expanded {
  max-height: none;
}

/* Fade Overlay */
.fade-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 60px;
  background: linear-gradient(transparent, #1e1e1e);
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.summary-content.expanded .fade-overlay {
  opacity: 0;
}

/* Progress Styles */
.progress-container {
  margin-top: 0;
  padding: 1rem;
  background-color: #2a2a2a;
  border-radius: 6px;
}

.current-document {
  font-size: 0.875rem;
  color: #888;
  margin-bottom: 0.5rem;
}

.progress-bar {
  height: 8px;
  background-color: #1a1a1a;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1a3a5a, #254b73);
  transition: width 0.3s ease;
  position: relative;
}

.progress-text {
  position: absolute;
  right: 8px;
  top: -18px;
  font-size: 0.75rem;
  color: #888;
}

/* Expand Button */
.expand-btn {
  width: 100%;
  padding: 0.75rem;
  margin-top: 0.5rem;
  background-color: #2a2a2a;
  border: 1px solid #333;
  border-radius: 4px;
  color: #e0e0e0;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.expand-btn:hover {
  background-color: #333;
}

/* Page Navigation */
.page-navigation {
  display: flex;
  gap: 0.25rem;
  margin: 1rem 0;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
}

.page-btn {
  padding: 0.5rem 0.75rem;
  background-color: #2a2a2a;
  border: 1px solid #333;
  border-radius: 4px;
  color: #e0e0e0;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-btn.active {
  background-color: #1a3a5a;
  border-color: #1a3a5a;
}

.page-btn:not(:disabled):hover {
  background-color: #333;
  border-color: #444;
}

.nav-btn {
  font-size: 1.2rem;
  padding: 0.5rem;
}

.page-ellipsis {
  padding: 0.5rem;
  color: #666;
}

/* Type Badges */
.type-badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  text-transform: uppercase;
}

.type-pdf { color: #ff4444; }
.type-doc { color: #4444ff; }
.type-txt { color: #44ff44; }
.type-default { color: #888; }

/* Resize Handle */
.resize-handle {
  width: 4px;
  height: 24px;
  background-color: #333;
  cursor: ew-resize;
  transition: background-color 0.2s ease;
}

.resize-handle:hover {
  background-color: #444;
}

/* Error Message */
.error-message {
  margin-top: 1rem;
  padding: 1rem;
  background-color: rgba(255, 68, 68, 0.1);
  border: 1px solid rgba(255, 68, 68, 0.2);
  border-radius: 6px;
  color: #ff4444;
}

/* Scrollbar Styles */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #1a1a1a;
}

::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #444;
}

/* Content Typography */
.summary-content :deep(h1),
.summary-content :deep(h2),
.summary-content :deep(h3) {
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  color: #fff;
  font-weight: 600;
}

.summary-content :deep(h1) { font-size: 1.5rem; }
.summary-content :deep(h2) { font-size: 1.25rem; }
.summary-content :deep(h3) { font-size: 1.125rem; }

.summary-content :deep(p) {
  margin-bottom: 1rem;
  line-height: 1.6;
}

.summary-content :deep(ul),
.summary-content :deep(ol) {
  padding-left: 1.5rem;
  margin-bottom: 1rem;
}

.summary-content :deep(li) {
  margin-bottom: 0.5rem;
}

.summary-content :deep(code) {
  background-color: #2a2a2a;
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: monospace;
}

.summary-content :deep(pre) {
  background-color: #2a2a2a;
  padding: 1rem;
  border-radius: 4px;
  overflow-x: auto;
  margin-bottom: 1rem;
}

.summary-content :deep(blockquote) {
  border-left: 4px solid #333;
  margin: 1rem 0;
  padding-left: 1rem;
  color: #888;
}

.summary-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
}

.summary-content :deep(th),
.summary-content :deep(td) {
  border: 1px solid #333;
  padding: 0.5rem;
  text-align: left;
}

.summary-content :deep(th) {
  background-color: #2a2a2a;
}

/* Responsive Adjustments */
@media (max-width: 1200px) {
  .content-wrapper {
    gap: 1rem;
  }
  
  .summary-panel:not(.collapsed) {
    width: 350px;
  }
}

@media (max-width: 992px) {
  .content-wrapper {
    flex-direction: column;
    height: auto;
  }
  
  .summary-panel {
    width: 100%;
    max-width: none;
    border-left: none;
    border-top: 1px solid #333;
  }
  
  .summary-panel.collapsed {
    width: 100%;
    height: 40px;
  }
}

@media (max-width: 768px) {
  .container {
    flex-direction: column;
  }
  
  .sidebar {
    width: 100%;
    min-width: 0;
    height: auto;
    border-right: none;
    border-bottom: 1px solid #333;
  }
  
  .center-panel {
    padding: 1rem;
    min-width: auto;
  }
  
  .summary-panel {
    position: fixed;
    right: 0;
    top: 0;
    height: 100vh;
    transform: translateX(100%);
  }
  
  .summary-panel:not(.collapsed) {
    transform: translateX(0);
    width: 100%;
    max-width: 400px;
  }

  .panel-content {
    padding: 0.5rem;
  }

  .action-buttons {
    padding: 0.5rem;
  }

  .button-group {
    flex-wrap: wrap;
  }

  .action-btn {
    padding: 0.5rem;
    font-size: 0.75rem;
  }

  .summarize-btn {
    padding: 0.75rem;
    font-size: 0.875rem;
  }

  .notebook-header {
    margin-bottom: 1rem;
  }

  .notebook-title {
    font-size: 1.25rem;
  }

  .title {
    font-size: 1rem;
  }
}

@media (max-width: 480px) {
  .source-info {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }

  .type-badge {
    font-size: 0.625rem;
  }

  .page-navigation {
    gap: 0.125rem;
  }

  .page-btn {
    min-width: 32px;
    padding: 0.375rem;
    font-size: 0.875rem;
  }

  .summary-panel:not(.collapsed) {
    width: 100%;
    max-width: none;
  }
}

/* Panel Collapsed State */
.summary-panel.collapsed .panel-content,
.summary-panel.collapsed .action-buttons,
.summary-panel.collapsed h3 {
  display: none;
}

.summary-panel.collapsed .panel-header {
  padding: 1rem 0.5rem;
  justify-content: center;
}

.summary-panel.collapsed .control-btn {
  transform: rotate(180deg);
}

/* Control Button */
.control-btn {
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  padding: 0.5rem;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.control-btn:hover {
  color: #fff;
  background-color: #333;
}

/* Panel Controls */
.panel-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.panel-controls.collapsed {
  width: 100%;
  justify-content: center;
}

/* Additional Typography Styles */
.summary-content :deep(strong) {
  color: #fff;
  font-weight: 600;
}

.summary-content :deep(em) {
  font-style: italic;
  color: #ddd;
}

.summary-content :deep(a) {
  color: #4a9eff;
  text-decoration: none;
  transition: color 0.2s ease;
}

.summary-content :deep(a:hover) {
  color: #77b7ff;
  text-decoration: underline;
}

.summary-content :deep(hr) {
  border: none;
  border-top: 1px solid #333;
  margin: 1.5rem 0;
}

/* Content Container Maximum Width */
.summary-content :deep(.content) {
  max-width: 100%;
  margin: 0 auto;
}

/* Print Styles */
@media print {
  .sidebar,
  .action-buttons,
  .summarize-container,
  .panel-header,
  .page-navigation {
    display: none;
  }

  .container {
    height: auto;
    overflow: visible;
  }

  .center-panel,
  .summary-panel {
    width: 100%;
    position: static;
    overflow: visible;
  }

  .summary-content {
    max-height: none;
  }

  .fade-overlay {
    display: none;
  }
}
</style>