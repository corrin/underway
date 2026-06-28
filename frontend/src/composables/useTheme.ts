import { ref } from 'vue'

type Theme = 'light' | 'dark' | 'auto'

const STORAGE_KEY = 'theme'

// localStorage can hold any string; reject stale/corrupt values and fall back
// to 'auto'. The pre-paint bootstrap in index.html applies the same whitelist.
function parseTheme(value: string | null): Theme {
  return value === 'light' || value === 'dark' || value === 'auto' ? value : 'auto'
}

const theme = ref<Theme>(parseTheme(localStorage.getItem(STORAGE_KEY)))

function applyTheme() {
  document.documentElement.dataset.theme = theme.value
}

function setTheme(value: Theme) {
  theme.value = value
  localStorage.setItem(STORAGE_KEY, value)
  applyTheme()
}

applyTheme()

export function useTheme() {
  return { theme, setTheme }
}
