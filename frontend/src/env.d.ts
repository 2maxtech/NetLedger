/// <reference types="vite/client" />

interface Window {
  Tawk_API?: { showWidget?: () => void; hideWidget?: () => void }
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
