import { ref } from 'vue'

const isMobileNavOpen = ref(false)

export function useMobileNav() {
  function openMobileNav() {
    isMobileNavOpen.value = true
  }

  function closeMobileNav() {
    isMobileNavOpen.value = false
  }

  function toggleMobileNav() {
    isMobileNavOpen.value = !isMobileNavOpen.value
  }

  return {
    isMobileNavOpen,
    openMobileNav,
    closeMobileNav,
    toggleMobileNav,
  }
}
