import { ref, markRaw } from 'vue'

const showModal = ref(false)
const modalComponent = ref(null)
const modalProps = ref({})

export function useModal() {
  function openModal(component, props = {}) {
    modalComponent.value = markRaw(component)
    modalProps.value = props
    showModal.value = true
  }

  function closeModal() {
    showModal.value = false
  }

  return {
    showModal,
    modalComponent,
    modalProps,
    openModal,
    closeModal
  }
}