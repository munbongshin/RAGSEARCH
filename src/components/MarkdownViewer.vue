// MarkdownViewer.vue
<template>
  <div class="markdown-content" v-html="renderedContent"></div>
</template>

<script>
import MarkdownIt from 'markdown-it';
import MarkdownItAnchor from 'markdown-it-anchor';
import MarkdownItToc from 'markdown-it-toc-done-right';
import MarkdownItContainer from 'markdown-it-container';
import hljs from 'highlight.js';

export default {
  name: 'MarkdownViewer',
  
  props: {
    content: {
      type: String,
      default: ''
    }
  },

  data() {
    return {
      md: null
    };
  },

  created() {
    // 마크다운 파서 초기화
    this.md = new MarkdownIt({
      html: true,           // HTML 태그 허용
      linkify: true,        // URL을 자동으로 링크로 변환
      typographer: true,    // 스마트 문장 부호
      breaks: true,         // 줄바꿈 활성화
      highlight: function (str, lang) {
        if (lang && hljs.getLanguage(lang)) {
          try {
            return hljs.highlight(str, { language: lang }).value;
          } catch (error) {console.error('데이터 로딩 실패:', error)}
        }
        return '';
      }
    })
    .use(MarkdownItAnchor, {
      permalink: true,
      permalinkBefore: true,
      permalinkSymbol: '§'
    })
    .use(MarkdownItToc)
    .use(MarkdownItContainer, 'info')
    .use(MarkdownItContainer, 'warning')
    .use(MarkdownItContainer, 'danger');

    // 테이블 처리 개선
    this.md.renderer.rules.table_open = () => '<div class="table-wrapper"><table>';
    this.md.renderer.rules.table_close = () => '</table></div>';
  },

  computed: {
    renderedContent() {
      if (!this.content) {
        return '';
      }
      return this.md.render(this.content);
    }
  }
};
</script>

<style scoped>
.markdown-content {
  font-size: 1rem;
  line-height: 1.8;
  color: #e0e0e0;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin: 2rem 0 1rem;
  line-height: 1.4;
  color: #fff;
  font-weight: 600;
}

.markdown-content :deep(.header-anchor) {
  float: left;
  margin-left: -1.2em;
  padding-right: 0.2em;
  opacity: 0;
  transition: opacity 0.2s;
  text-decoration: none;
  color: #4a9eff;
}

.markdown-content :deep(.header-anchor:hover) {
  opacity: 1;
}

.markdown-content :deep(h1:hover) .header-anchor,
.markdown-content :deep(h2:hover) .header-anchor,
.markdown-content :deep(h3:hover) .header-anchor,
.markdown-content :deep(h4:hover) .header-anchor,
.markdown-content :deep(h5:hover) .header-anchor,
.markdown-content :deep(h6:hover) .header-anchor {
  opacity: 0.5;
}

.markdown-content :deep(h1) { font-size: 2rem; }
.markdown-content :deep(h2) { font-size: 1.75rem; }
.markdown-content :deep(h3) { font-size: 1.5rem; }
.markdown-content :deep(h4) { font-size: 1.25rem; }
.markdown-content :deep(h5) { font-size: 1.1rem; }
.markdown-content :deep(h6) { font-size: 1rem; }

.markdown-content :deep(.table-wrapper) {
  overflow-x: auto;
  margin: 1rem 0;
  border-radius: 4px;
  background: #1e1e1e;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
  line-height: 1.5;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 0.75rem;
  border: 1px solid #333;
  text-align: left;
  vertical-align: top;
}

.markdown-content :deep(th) {
  background: #2a2a2a;
  font-weight: 600;
  white-space: nowrap;
}

.markdown-content :deep(tr:nth-child(even)) {
  background: #1a1a1a;
}

.markdown-content :deep(tr:hover) {
  background: #2a2a2a;
}

.markdown-content :deep(p) {
  margin: 1rem 0;
  line-height: 1.8;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 2rem;
  margin: 1rem 0;
}

.markdown-content :deep(li) {
  margin: 0.5rem 0;
  line-height: 1.6;
}

.markdown-content :deep(code) {
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 0.9em;
  padding: 0.2em 0.4em;
  border-radius: 3px;
  background: #2a2a2a;
}

.markdown-content :deep(pre) {
  padding: 1rem;
  margin: 1rem 0;
  border-radius: 4px;
  background: #2a2a2a;
  overflow-x: auto;
}

.markdown-content :deep(pre code) {
  padding: 0;
  background: none;
}

.markdown-content :deep(blockquote) {
  margin: 1rem 0;
  padding: 0.5rem 1rem;
  border-left: 4px solid #4a9eff;
  background: #2a2a2a;
  color: #aaa;
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid #333;
  margin: 2rem 0;
}

.markdown-content :deep(.info),
.markdown-content :deep(.warning),
.markdown-content :deep(.danger) {
  padding: 1rem;
  margin: 1rem 0;
  border-radius: 4px;
}

.markdown-content :deep(.info::before),
.markdown-content :deep(.warning::before),
.markdown-content :deep(.danger::before) {
  font-weight: 600;
  display: block;
  margin-bottom: 0.5rem;
}

.markdown-content :deep(.info) {
  background: rgba(74, 158, 255, 0.1);
  border-left: 4px solid #4a9eff;
}

.markdown-content :deep(.info::before) {
  content: 'Info';
  color: #4a9eff;
}

.markdown-content :deep(.warning) {
  background: rgba(255, 197, 23, 0.1);
  border-left: 4px solid #ffc517;
}

.markdown-content :deep(.warning::before) {
  content: 'Warning';
  color: #ffc517;
}

.markdown-content :deep(.danger) {
  background: rgba(255, 68, 68, 0.1);
  border-left: 4px solid #ff4444;
}

.markdown-content :deep(.danger::before) {
  content: 'Danger';
  color: #ff4444;
}
</style>