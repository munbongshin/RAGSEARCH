import { createStore } from 'vuex'
import axios from 'axios'

const API_BASE_URL = 'http://localhost:5001'

export default createStore({
  state: {
    currentCollection: 'ragtest',
    currentLlmSource: 'Groq',
    currentLlmModel: 'llama-3.3-70b-versatile',
    llmSource: 'Groq',
    selectedModel: 'llama-3.3-70b-versatile',
    ollamaModels: ['llama3.2:3b','llama3.1:latest', 'jmpark333/exaone:latest', 'koesn/mistral-7b-instruct:latest','koesn/llama3-8b-instruct:latest'],
    groqModels: ['llama-3.3-70b-versatile','llama-3.1-70b-versatile', 'Llama-3.1-8b-Instant','Llama3-70b-8192'],
    groqApiKey: null,    
    selectedMode: 'RAG',
    selectedCollections: [],
    selectedSources: [],
  },
  mutations: {
    setLlmSource(state, source) {
      state.llmSource = source
      state.currentLlmSource = source
    },
    setSelectedModel(state, model) {
      state.selectedModel = model
      state.currentLlmModel = model
    },
    setOllamaModels(state, models) {
      state.ollamaModels = models
    },
    setGroqModels(state, models) {
      state.groqModels = models
    },
    setGroqApiKey(state, apiKey) {
      state.groqApiKey = apiKey
    },
    setCurrentCollection(state, collection) {
      state.currentCollection = collection
    },
    setCurrentLlmSource(state, source) {
      state.currentLlmSource = source
    },
    setCurrentLlmModel(state, model) {
      state.currentLlmModel = model
    },
    updateCurrentCollection(state, collection) {
      state.currentCollection = collection
    },
    updateLlmSource(state, source) {
      state.currentLlmSource = source
    },
    updateLlmModel(state, model) {
      state.currentLlmModel = model
    },
    SET_SELECTED_SOURCES(state, sources) {
      state.selectedSources = sources;
    },
    updateSelectedCollections(state, collections) {
      state.selectedCollections = collections;
      state.currentCollection = collections[0] || null;
    },
    updateSelectedSources(state, sources) {
      state.selectedSources = sources;
    },
    SET_SELECTED_MODE(state, mode) {
      state.selectedMode = mode;
    }
  },
  actions: {
    updateModelSelection({ commit }, { source, model }) {
      commit('setLlmSource', source)
      commit('setSelectedModel', model)
    },
    updateSelectedCollections({ commit }, collections) {
      commit('updateSelectedCollections', collections);
    },
    updateSelectedSources({ commit }, sources) {
      commit('updateSelectedSources', sources);
    },
    async setGroqApiKey({ commit }, apiKey) {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/set-groq-api-key`, { apiKey })
        if (response.data.success) {
          commit('setGroqApiKey', apiKey)
          return { success: true, message: 'Groq API key set successfully' }
        } else {
          return { success: false, message: 'Failed to set Groq API key' }
        }
      } catch (error) {
        console.error('Error setting Groq API key:', error)
        return { success: false, message: 'Error setting Groq API key' }
      }
    },
    updateCurrentCollection({ commit }, collection) {
      commit('updateCurrentCollection', collection)
    },
    updateCurrentLlmSource({ commit }, source) {
      commit('updateLlmSource', source)
    },
    updateCurrentLlmModel({ commit }, model) {
      commit('updateLlmModel', model)
    },
    updateLlmInfo({ commit }, { source, model }) {
      commit('updateLlmSource', source)
      commit('updateLlmModel', model)
    },
    updateSelectedMode({ commit }, mode) {
      commit('SET_SELECTED_MODE', mode);
    }
  },
  getters: {
    getSelectedCollections: state => {state.selectedCollections},
    getSelectedSources: (state) => {
      console.log('Vuex getter: Getting selectedSources:', state.selectedSources);
      return state.selectedSources;
    },
    getSelectedMode: (state) => {
      return state.selectedMode;
    },
    currentModelInfo(state) {
      return {
        source: state.llmSource,
        model: state.selectedModel
      }
    }
  }
})