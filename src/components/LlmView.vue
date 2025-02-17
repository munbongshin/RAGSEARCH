<template>
  <div class="llm-view">
    <h3>LLM 소스 선택:</h3>
    <div class="llm-source-selection">
      <label :class="{ 'selected': llmSource === 'Ollama' }">
        <input type="radio" v-model="llmSource" value="Ollama" @change="updateModelList">
        Ollama
      </label>
      <label :class="{ 'selected': llmSource === 'Groq' }">
        <input type="radio" v-model="llmSource" value="Groq" @change="updateModelList">
        Groq
      </label>
    </div>
    <div v-if="llmSource === 'Ollama'">
      <h4>사용할 Ollama 모델을 선택하세요:</h4>
      <select v-model="selectedModel" class="model-select" @change="updateModelSelection">
        <option v-for="model in ollamaModels" :key="model" :value="model">{{ model }}</option>
      </select>
    </div>
    <div v-else-if="llmSource === 'Groq'">
      <h4>사용할 Groq 모델을 선택하세요:</h4>
      <select v-model="selectedModel" class="model-select" @change="updateModelSelection">
        <option v-for="model in groqModels" :key="model" :value="model">{{ model }}</option>
      </select>
      <button @click="showApiKeyDialog = true" class="api-key-button">Set Groq API Key</button>
      <p v-if="groqApiKey" class="api-key-status">API Key is set</p>
    </div>
    <p class="selected-model">선택한 모델: {{ selectedModel }}</p>

    <ApiKeyDialog 
      :show="showApiKeyDialog"
      @submit-api-key="setGroqApiKey"
      @cancel="showApiKeyDialog = false"
    />
  </div>
</template>

<script>
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import ApiKeyDialog from './ApiKeyDialog.vue'

export default {
  name: 'LlmView',
  components: {
    ApiKeyDialog
  },
  setup() {
    const store = useStore()
    const showApiKeyDialog = ref(false)

    const llmSource = computed({
      get: () => store.state.llmSource,
      set: (value) => store.commit('setLlmSource', value)
    })
    const selectedModel = computed({
      get: () => store.state.selectedModel,
      set: (value) => store.commit('setSelectedModel', value)
    })
    const ollamaModels = computed(() => store.state.ollamaModels)
    const groqModels = computed(() => store.state.groqModels)
    const groqApiKey = computed(() => store.state.groqApiKey)

    const updateModelList = () => {
      const newModel = llmSource.value === 'Ollama' ? ollamaModels.value[0] : groqModels.value[0]
      store.dispatch('updateModelSelection', { source: llmSource.value, model: newModel })
    }

    const updateModelSelection = () => {
      store.dispatch('updateModelSelection', { source: llmSource.value, model: selectedModel.value })
    }

    const setGroqApiKey = async (apiKey) => {
      await store.dispatch('setGroqApiKey', apiKey)
      showApiKeyDialog.value = false
    }

    return {
      llmSource,
      selectedModel,
      ollamaModels,
      groqModels,
      groqApiKey,
      showApiKeyDialog,
      updateModelList,
      updateModelSelection,
      setGroqApiKey
    }
  }
}
</script>
  
  <style scoped>
  .llm-view {
    padding: 10px;
    margin-right: 10px;
    margin-top: 10px;
    color: white;
    background-color: #1e1e1e;
  }
  
  h3, h4 {
    margin-bottom: 10px;
  }
  
  .llm-source-selection {
    margin-bottom: 15px;
    margin-top: 15px;
    margin-right: 15px;
  }
  
  .llm-source-selection label {
    display: inline-block;
    margin-right: 15px;
    padding: 5px 10px;
    border-radius: 5px;
    cursor: pointer;
    transition: background-color 0.3s;
  }
  
  .llm-source-selection label.selected {
    background-color: #FFA500; /* 주황색 */
    color: #000000; /* 텍스트 색상을 검정색으로 변경 (가독성을 위해) */
  }
  
  .llm-source-selection input[type="radio"] {
    display: none; /* 라디오 버튼 숨기기 */
  }
  
  .model-select {
    width: 90%;
    padding: 5px;
    margin-bottom: 10px;
    background-color: #2c2c2c;
    color: white;
    border: 1px solid #444;
  }
  
  .selected-model {
    width: 90%;
    margin-top: 10px;
    font-weight: bold;
  }

  .api-key-button {
  margin-top: 10px;
  padding: 5px 10px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 3px;
  cursor: pointer;
}

.api-key-button:hover {
  background-color: #45a049;
}

.api-key-status {
  margin-top: 5px;
  color: #4CAF50;
}
  </style>