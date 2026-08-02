import { createApp } from 'vue'
import '@fontsource/fraunces/latin-600.css'
import '@fontsource/source-sans-3/latin-400.css'
import '@fontsource/source-sans-3/latin-600.css'
import './styles/tokens.css'
import './style.css'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')

function deferFonts(): void {
  void Promise.all([
    import('@fontsource/fraunces/latin-500.css'),
    import('@fontsource/literata/latin-400.css'),
    import('@fontsource/literata/latin-400-italic.css'),
    import('@fontsource/source-sans-3/latin-700.css'),
  ])
}

const idleWindow = window as Window & {
  requestIdleCallback?: (callback: () => void) => number
}
if (typeof idleWindow.requestIdleCallback === 'function') {
  idleWindow.requestIdleCallback(deferFonts)
} else {
  window.setTimeout(deferFonts, 1)
}
