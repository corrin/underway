import { ref } from 'vue'

type Theme = 'light' | 'dark' | 'auto'

const STORAGE_KEY = 'theme'
const theme = ref<Theme>((localStorage.getItem(STORAGE_KEY) as Theme) || 'auto')

function applyTheme() {
  document.documentElement.dataset.theme = theme.value
}

function setTheme(value: Theme) {
  theme.value = value
  localStorage.setItem(STORAGE_KEY, value)
  applyTheme()
}

// Apply on first import
applyTheme()

export function useTheme() {
  return { theme, setTheme }
}
