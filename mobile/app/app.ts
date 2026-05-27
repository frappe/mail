import { createApp } from 'nativescript-vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import './app.css'

const pinia = createPinia()

const app = createApp(App)
app.use(pinia)
app.start()
