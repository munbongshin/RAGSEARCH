<template>
  <div class="messages-container">
    <div 
      v-for="(message, index) in messages" 
      :key="index"
      :class="['message-container', `${message.role.toLowerCase()}-message`]"
    >
      <div class="message-role">{{ message.role }}</div>
      <div class="message-content markdown-content" v-html="markdownToHtml(message.content)"></div>
    </div>
  </div>
</template>

<script>
import { defineComponent } from 'vue';
import { marked } from 'marked';

export default defineComponent({
  name: 'ChatMessages',
  props: {
    messages: {
      type: Array,
      required: true
    }
  },
  methods: {
    markdownToHtml(content) {
      // marked 설정을 수정하여 불필요한 줄바꿈 제거
      marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        xhtml: false,
        mangle: false
      });
      
      // 연속된 줄바꿈 제거
      let processedContent = content.replace(/\n\s*\n/g, '\n');
      processedContent = processedContent.trim();
      return marked(processedContent);
    }
  }
});
</script>

<style scoped>
.messages-container {
  width: 100%;
  padding: 10px;
  line-height: 1.3;
}

.message-container {
  width: 100%;
  line-height: 1.3;
  padding: 10px;
  margin: 0; /* 마진 제거 */
}

.message-role {
  font-weight: bold;
  color: #fa5421;
  font-size: 0.9em;
  line-height: 1.3;
  margin: 0; /* 마진 제거 */
  padding: 10px 15px; /* 패딩 제거 */
}

.message-content {
  background-color: #1a1a1a;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
  max-width: 100%;
  line-height: 1.3;
  margin: 0; /* 마진 제거 */
}

/* 마크다운 컨텐츠에서 추가 여백 제거 */
.markdown-content :deep(*) {
  line-height: 1.2; /* 줄간격 축소 */
  margin: 0; /* 상하 마진 제거 */
  padding: 0; /* 패딩 제거 */
}

.markdown-content :deep(p) {
  margin: 0 0 0.5em 0; /* 문단 간격 축소 */
  line-height: 1.2; /* 문단 내 줄간격 축소 */
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0.5em 0; /* 리스트 마진 축소 */
  padding-left: 1.5em; /* 리스트 들여쓰기 조정 */
}

.markdown-content :deep(li) {
  margin: 0; /* 리스트 아이템 마진 제거 */
  line-height: 1.2; /* 리스트 아이템 줄간격 축소 */
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin: 0.5em 0; /* 제목 마진 축소 */
  line-height: 1.2; /* 제목 줄간격 축소 */
}

/* 코드 블록 스타일 조정 */
.markdown-content :deep(pre),
.markdown-content :deep(code) {
  margin: 0.5em 0; /* 코드 블록 마진 축소 */
  line-height: 1.2; /* 코드 블록 줄간격 축소 */
}

/* 메시지 간 최소한의 간격만 유지 */
.message-container + .message-container {
  margin-top: 0;
}

/* 시스템 메시지도 동일하게 처리 */
.system-message {
  margin: 0;
}

.system-message .message-content {
  margin: 0;
  padding: 10px;
}
</style>