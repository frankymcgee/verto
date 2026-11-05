import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'
import { setupFrappeRealtime } from './lib/frappeRealtime'
import { registerVertoServiceWorker } from './pwa/registerServiceWorker'
import { applyVertoPwaHeadTags } from './pwa/applyPwaHeadTags'
import { installClientDiagnostics } from './lib/diagnostics'

setupFrappeRealtime()

const app = createApp(App)

installClientDiagnostics(app)

app.use(router)

app.mount('#app')
registerVertoServiceWorker()
applyVertoPwaHeadTags(router)
