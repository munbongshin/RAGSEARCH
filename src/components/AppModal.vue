<template>
  <div 
    v-if="show" 
    class="modal-overlay" 
    @click.self="$emit('close')"
  >
    <div 
      class="modal-container" 
      :style="{
        width: `${width}px`,
        height: `${height}px`,
        minWidth: `${minWidth}px`,
        minHeight: `${minHeight}px`,
        maxWidth: '90vw',
        maxHeight: '90vh'
      }"
    >
      <div class="modal-header">
        <div class="header-content">
          <slot name="header">
            <h3>Default Header</h3>
          </slot>
        </div>
        <button class="close-btn" @click="$emit('close')">&times;</button>
      </div>
      <div class="modal-body">
        <slot name="body">
          <p>Default body content</p>
        </slot>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';

export default {
  name: 'AppModal',
  props: {
    show: {
      type: Boolean,
      required: true
    },
    initialWidth: {
      type: Number,
      default: 1600
    },
    initialHeight: {
      type: Number,
      default: 1000
    },
    minWidth: {
      type: Number,
      default: 800
    },
    minHeight: {
      type: Number,
      default: 600
    }
  },

  emits: ['close'],

  setup(props, { emit }) {
    const width = ref(props.initialWidth);
    const height = ref(props.initialHeight);

    const adjustModalSize = () => {
      const maxWidth = window.innerWidth * 0.9;
      const maxHeight = window.innerHeight * 0.9;
      
      width.value = Math.min(props.initialWidth, maxWidth);
      height.value = Math.min(props.initialHeight, maxHeight);
      
      width.value = Math.max(width.value, props.minWidth);
      height.value = Math.max(height.value, props.minHeight);
    };

    // ESC 키로 모달 닫기
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && props.show) {
        emit('close');
      }
    };

    // show prop이 변경될 때마다 body 클래스 처리
    watch(() => props.show, (newValue) => {
      if (newValue) {
        document.body.classList.add('modal-open');
      } else {
        document.body.classList.remove('modal-open');
      }
    });

    onMounted(() => {
      if (props.show) {
        document.body.classList.add('modal-open');
      }
      adjustModalSize();
      window.addEventListener('resize', adjustModalSize);
      document.addEventListener('keydown', handleKeyDown);
    });

    onBeforeUnmount(() => {
      document.body.classList.remove('modal-open');
      window.removeEventListener('resize', adjustModalSize);
      document.removeEventListener('keydown', handleKeyDown);
    });

    return {
      width,
      height
    };
  }
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 99999;
  pointer-events: auto;
}

.modal-container {
  position: relative;
  background: #1a1a1a;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.33);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  z-index: 100000;
}

.modal-header {
  padding: 1rem;
  border-bottom: 1px solid #333;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #2a2a2a;
}

.header-content {
  flex: 1;
}

.header-content h3 {
  margin: 0;
  color: #fff;
  font-size: 1.25rem;
  font-weight: 500;
}

.close-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0.5rem;
  margin-left: 1rem;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.close-btn:hover {
  color: #fff;
  background-color: rgba(255, 255, 255, 0.1);
}

.modal-body {
  flex: 1;
  overflow: auto;
  padding: 1.5rem;
  color: #e0e0e0;
}

/* 스크롤바 스타일링 */
.modal-body::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-track {
  background: #1a1a1a;
}

.modal-body::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: #444;
}

/* 애니메이션 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

/* modal이 열려있을 때 body 스크롤 방지를 위한 전역 스타일 */
:global(body.modal-open) {
  overflow: hidden;
}
</style>