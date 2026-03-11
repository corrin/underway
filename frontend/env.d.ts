/// <reference types="vite/client" />

interface GoogleAccountsId {
  initialize(config: {
    client_id: string
    callback?: (response: { credential: string }) => void
    ux_mode?: 'popup' | 'redirect'
    login_uri?: string
  }): void
  renderButton(element: HTMLElement, config: { theme?: string; size?: string; width?: number }): void
}

interface Window {
  google: {
    accounts: {
      id: GoogleAccountsId
    }
  }
}
