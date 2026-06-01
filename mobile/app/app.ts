import { createApp } from 'nativescript-vue'
import { createPinia } from 'pinia'

import translationPlugin, { loadTranslations } from '@/utils/translation'
import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'

import App from './App.vue'
import './app.css'

const pinia = createPinia()

const app = createApp(App)
app.use(pinia)
app.use(translationPlugin)

// Restore the active site's session before the first render so the app starts
// on the right screen (app shell when already logged in, landing otherwise).
const site = siteStore(pinia)
const session = sessionStore(pinia)
if (site.activeSite) session.loadSession(site.activeSite.url)
void loadTranslations()

app.start()
