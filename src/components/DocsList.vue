<template>
  <div v-if="docsList.length > 0" class="docs-list">
    <div class="docs-list-header">참고문서:</div>
    <ul>
      <li 
        v-for="doc in docsList" 
        :key="doc.id" 
        @click="selectDoc(doc)"
        class="doc-item"
      >
        <div class="doc-title">
          <span class="doc-name">문서명: {{ doc.title }}</span>
          <span class="doc-page">Page {{ doc.page }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'DocsList',
  props: {
    docsList: {
      type: Array,
      required: true,
      default: () => []
    }
  },
  setup(props, { emit }) {
    const selectDoc = (doc) => {
      emit('select-doc', doc);
    };

    return { selectDoc };
  }
});
</script>

<style scoped>
.docs-list {
  margin-top: 8px;
  padding: 10px;
  background-color: #1a1a1a;
  border-radius: 4px;
}

.docs-list-header {
  font-weight: bold;
  color: #fa5421;
  margin-bottom: 8px;
}

.docs-list ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.doc-item {
  cursor: pointer;
  padding: 8px 12px;
  margin: 4px 0;
  background-color: #0b0b0b;
  border-radius: 4px;
  transition: background-color 0.2s ease;
  border: 1px solid #333;
}

.doc-item:hover {
  background-color: #2a2a2a;
}

.doc-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
  /* 텍스트 줄바꿈 설정 */
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
  line-height: 1.4;
}

.doc-name {
  font-weight: 500;
  /* 긴 제목 처리 */
  max-width: 100%;
  overflow-wrap: break-word;
  word-wrap: break-word;
  hyphens: auto;
}

.doc-page {
  color: #888;
  font-size: 0.9em;
}
</style>