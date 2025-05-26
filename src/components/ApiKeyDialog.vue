<template>
    <div class="api-key-dialog" v-if="show">
      <div class="dialog-content">
        <h2>Enter Groq API Key</h2>
        <input 
          type="password" 
          v-model="apiKey" 
          placeholder="Enter your Groq API Key"
        >
        <div class="button-group">
          <button @click="submitApiKey">Submit</button>
          <button @click="cancel">Cancel</button>
        </div>
      </div>
    </div>
  </template>
  
  <script>
  export default {
    name: 'ApiKeyDialog',
    props: {
      show: Boolean
    },
    data() {
      return {
        apiKey: ''
      }
    },
    methods: {
      submitApiKey() {
        this.$emit('submit-api-key', this.apiKey);
        this.apiKey = '';
      },
      cancel() {
        this.$emit('cancel');
        this.apiKey = '';
      }
    }
  }
  </script>
  
  <style scoped>
  .api-key-dialog {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
  }
  
  .dialog-content {
    background-color: #1e1e1e;
    padding: 20px;
    border-radius: 5px;
    width: 300px;
  }
  
  h2 {
    color: white;
    margin-bottom: 15px;
  }
  
  input {
    width: 100%;
    padding: 10px;
    margin-bottom: 15px;
    background-color: #333;
    color: white;
    border: none;
    border-radius: 3px;
  }
  
  .button-group {
    display: flex;
    justify-content: space-between;
  }
  
  button {
    padding: 10px 20px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
  }
  
  button:hover {
    background-color: #45a049;
  }
  </style>