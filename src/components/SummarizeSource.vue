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
import { marked } from 'marked'
import axios from 'axios';

function formatContent(content) {
  if (!content) return '';
  
  try {
    // 1. 문자열로 변환
    const text = typeof content === 'object' ? JSON.stringify(content) : String(content);
    
    // 2. 마크다운 형식으로 변환
    let markdownContent = text
      // 연속된 줄바꿈 유지 (2줄까지만)
      .replace(/\n{3,}/g, '\n\n')
      // 머리글 스타일링
      .replace(/^(\d+)\.\s*(.+)$/gm, '**$1. $2**')
      // 콜론으로 시작하는 줄 강조
      .replace(/^(.+):$/gm, '**$1:**')
      // 불필요한 앞뒤 공백만 제거
      .trim();
    
    // 3. 긴 문단 보존
    const paragraphs = markdownContent.split('\n\n');
    return paragraphs.join('\n\n');
  } catch (error) {
    console.error('Content formatting error:', error);
    return String(content);
  }
}

function safeMarkdownParse(content) {
  if (!content) return '';

  try {
    const formattedContent = formatContent(content);
    
    // marked 옵션 수정
    marked.setOptions({
      breaks: true,        // \n을 <br>로 변환
      gfm: true,          // GitHub Flavored Markdown 활성화
      headerIds: false,    // 헤더 ID 비활성화
      sanitize: false,     // XSS는 다른 방법으로 처리
      mangle: false,      // 이메일 주소 변환 방지
      headerPrefix: '',    // 헤더 접두사 제거
      smartypants: true    // 더 나은 문자 렌더링
    });
    
    // XSS 방지를 위한 기본적인 이스케이프 처리
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
  name: 'SummarizeSource',
  
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

  data() {
    return {
      API_BASE_URL: 'http://localhost:5001',
      eventSource: null,
      selectedSource: null,
      currentPage: 1,
      isLoading: false,
      summary: '',
      page_content: '',
      progress: 0,
      error: '',
      currentDocument: '',
      topSummary: '',
      currentPageDetail: '',
      pages: [],
      isPanelCollapsed: false,
      windowWidth: window.innerWidth,
      sidebarWidth: 280,
      panelWidth: 400,
      isExpanded: false,
      hasOverflow: false
    }
  },

  computed: {
    containerStyle() {
      const summaryPanelWidth = this.isPanelCollapsed ? 40 : this.panelWidth;
      
      return {
        display: 'flex',
        width: '100%',
        height: '100vh',
        overflow: 'hidden',
        paddingRight: `${summaryPanelWidth}px`
      };
    },
    
    centerPanelStyle() {
      const summaryPanelWidth = this.isPanelCollapsed ? 40 : this.panelWidth;
      const centerPanelWidth = Math.max(
        500, 
        this.windowWidth - this.sidebarWidth - summaryPanelWidth
      );
      
      return {
        width: `${centerPanelWidth}px`,
        minWidth: '500px',
        flex: '1',
        overflowY: 'auto'
      };
    },

    sources() {
      const { sources } = this.selectedCollectionsSources;
      return sources.map(source => ({
        id: `${source.collection}-${source.source}`,
        type: source.source.split('.').pop().toLowerCase(),
        title: source.source,
        collection: source.collection,
        collection_id: parseInt(source.collection_id, 10),
        selected: true
      }));
    },

    selectedSources() {
      return this.sources.filter(s => s.selected);
    },

    renderedPageContent() {
      // page_content가 있으면 우선 사용
      if (this.page_content) {
        return safeMarkdownParse(this.page_content);
      }
      // topSummary가 있으면 다음으로 사용
      if (this.topSummary) {
        return safeMarkdownParse(this.topSummary);
      }
      // 둘 다 없으면 기본 메시지 표시
      return '선택된 문서 페이지의 내용이 여기에 표시됩니다.';
    },
    sourcesByCollection() {
      const grouped = {};
      this.sources.forEach(source => {
        if (!grouped[source.collection]) {
          grouped[source.collection] = [];
        }
        grouped[source.collection].push(source);
      });
      return grouped;
    },

    totalPages() {
      return this.pages?.length || 1;
    },

    displayedPages() {
      const total = this.totalPages;
      const current = this.currentPage;
      const range = 5;

      if (total <= 1) return [1];

      let start = Math.max(current - range, 1);
      let end = Math.min(current + range, total);

      const pages = [];

      if (start > 1) {
        pages.push(1);
        if (start > 2) pages.push('...');
      }

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      if (end < total) {
        if (end < total - 1) pages.push('...');
        pages.push(total);
      }

      return pages;
    }
  },

  methods: {
    toggleExpand() {
      this.isExpanded = !this.isExpanded;
    },
    
    checkOverflow() {
      if (this.$refs.summaryContent) {
        const element = this.$refs.summaryContent;
        this.hasOverflow = element.scrollHeight > element.clientHeight;
      }
    },
    handleResize() {
      this.windowWidth = window.innerWidth;
    },

    safeMarkdownParse(content) {
      return safeMarkdownParse(content);
    },

    toggleAllSources() {
      const newSelected = !this.allSourcesSelected;
      this.sources.forEach(source => {
        source.selected = newSelected;
      });
    },

    toggleSource(id) {
      const source = this.sources.find(s => s.id === id);
      if (source) {
        source.selected = !source.selected;
      }
    },

    togglePanel() {
      this.isPanelCollapsed = !this.isPanelCollapsed;
    },

    startResize(event) {
      const startX = event.clientX;
      const startWidth = this.panelWidth;

      const doDrag = (e) => {
        const newWidth = startWidth - (e.clientX - startX);
        this.panelWidth = Math.min(Math.max(newWidth, 300), 800);
      };

      const stopDrag = () => {
        document.removeEventListener('mousemove', doDrag);
        document.removeEventListener('mouseup', stopDrag);
      };

      document.addEventListener('mousemove', doDrag);
      document.addEventListener('mouseup', stopDrag);
    },

    async selectSource(id) {
      this.selectedSource = this.sources.find(s => s.id === id);
      if (this.selectedSource) {
        try {
          const response = await axios.post(`${this.API_BASE_URL}/api/get-document-pages`, {
            collection_id: parseInt(this.selectedSource.collection_id, 10),
            source: encodeURIComponent(this.selectedSource.title)
          });

          if (response.data.success) {
            const documentInfo = response.data.documents;
            if (documentInfo && documentInfo.pages) {
              this.pages = Array.from({ length: documentInfo.pages }, (_, i) => i + 1);
              this.currentPage = 1;
              
              await this.fetchPageContent(this.currentPage);
            }
          } else {
            console.error('Failed to get document pages:', response.data.error);
            this.error = '페이지 정보를 가져오는데 실패했습니다.';
          }
        } catch (err) {
          console.error('Error fetching document information:', err);
          this.error = '문서 정보를 가져오는 중 오류가 발생했습니다.';
        }
      }     
    },

    getTypeColor(type) {
      const colors = {
        pdf: 'type-pdf',
        doc: 'type-doc',
        txt: 'type-txt'
      };
      return colors[type] || 'type-default';
    },

    async setCurrentPage(page) {
      await this.fetchPageContent(page);
      
      this.currentPageDetail = `${this.page_content}`;
    },

    async fetchPageContent(page) {
      this.currentPage = page;
      if (this.selectedSource) {
        try {
          const response = await axios.post(`${this.API_BASE_URL}/api/page-content`, {
            collection_id: parseInt(this.selectedSource.collection_id, 10),
            source: this.selectedSource.title,
            page_num: page.toString(),
            llm_name: this.llmName,
            llm_model: this.llmModel
          });

          if (response.data.success) {
            this.page_content = response.data.pages;
          } else {
            console.error('Failed to get page content:', response.data.error);
            this.error = '페이지 내용을 가져오는데 실패했습니다.';
          }
        } catch (err) {
          console.error('Error fetching page content:', err);
          this.error = '페이지 내용을 가져오는 중 오류가 발생했습니다.';
        }
      }
    },

    async showSummary() {
      if (!this.selectedSource) {
        this.error = '선택된 문서가 없습니다.';
        return;
      }
      // topSummary 초기화
      this.topSummary = '';
      // 상태 초기화
      this.isExpanded = false;


      this.isLoading = true
      this.progress = 0
      this.summary = ''
      this.error = ''
      this.currentDocument = ''
      this.startSummarizeSource()      
    },

    async startSummarization() {
      if (this.selectedSources.length === 0) {
        this.error = '선택된 문서가 없습니다.';
        return;
      }     

      try {
        const { sources } = this.selectedCollectionsSources;
        const documentsWithCollections = sources.map(source => ({
          collection: source.collection,
          source: source.source
        }));

        const collections = [...new Set(sources.map(s => s.collection))];

        const params = new URLSearchParams({
          collections: JSON.stringify(collections),
          documents: JSON.stringify(documentsWithCollections),
          llm_name: this.llmName,
          llm_model: this.llmModel
        });

        this.eventSource = new EventSource(`${this.API_BASE_URL}/api/summarize-sse?${params}`);
        
        this.eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'progress') {
              this.progress = data.progress;
              if (data.document) {
                this.currentDocument = data.document;
              }
            } else if (data.type === 'summary') {
              this.summary = data.value;
              this.isLoading = false;
              this.closeEventSource();
            } else if (data.type === 'error') {
              throw new Error(data.value);
            }
          } catch (err) {
            console.error('Error processing SSE data:', err);
            this.error = err.message || '데이터 처리 중 오류가 발생했습니다.';
            this.closeEventSource();
          }
        };

        this.eventSource.onerror = (err) => {
          console.error('SSE Error:', err);
          this.error = '요약 중 오류가 발생했습니다. 서버 연결을 확인해주세요.';
          this.isLoading = false;
          this.closeEventSource();
        };

      } catch (err) {
        console.error('Error in startSummarization:', err);
        this.error = err.message || '요약 중 오류가 발생했습니다.';
        this.isLoading = false;
      }
    },

    closeEventSource() {
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
    },

    summarizeSource() {
      this.startSummarizeSource();
    },

    async startSummarizeSource() {
      if (!this.selectedSource) {
        this.error = '선택된 문서가 없습니다.';
        return;
      }

      if (!this.currentPage) {
        this.error = '페이지가 선택되지 않았습니다.';
        return;
      }

      try {
        this.isLoading = true;
        this.error = '';

        const response = await axios.post(`${this.API_BASE_URL}/api/summarize-page-content`, {
          collection_id: parseInt(this.selectedSource.collection_id, 10),
          source: this.selectedSource.title,
          page_num: this.currentPage.toString(),
          llm_name: this.llmName,
          llm_model: this.llmModel
        });

        if (response.data.success) {
          this.topSummary = response.data.pages;
        } else {          
          this.error = '페이지 내용을 가져오는데 실패했습니다.';
        }
      } catch (err) {        
        this.error = '요약 중 오류가 발생했습니다.';
      } finally {
        this.isLoading = false;
      }
    }
  },

  watch: {
    selectedCollectionsSources: {
      handler(newVal) {
        console.log('Selected sources changed:', newVal);
      },
      deep: true
    },
    topSummary() {
      this.$nextTick(() => {
        this.checkOverflow();
      });
    }
  },

  mounted() {
    window.addEventListener('resize', this.checkOverflow);
    this.checkOverflow();
  },

  beforeUnmount() {
    window.removeEventListener('resize', this.handleResize);
    window.removeEventListener('resize', this.checkOverflow);
    this.closeEventSource();
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