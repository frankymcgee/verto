import { createApp } from 'vue'
import { Button } from 'frappe-ui'
import App from './App.vue'
import './style.css'

createApp(App).component('Button', Button).mount('#app')
