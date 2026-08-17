import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'
import { setupFrappeRealtime } from './lib/frappeRealtime'
import { registerVertoServiceWorker } from './pwa/registerServiceWorker'
import { applyVertoPwaHeadTags } from './pwa/applyPwaHeadTags'

setupFrappeRealtime()

const app = createApp(App)

app.use(router)

app.mount('#app')
registerVertoServiceWorker()
applyVertoPwaHeadTags(router)