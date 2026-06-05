import { ref } from 'vue'

import type { Thread } from '@mail/types'

// The thread currently opened in ThreadView, and the id of the mailbox it was
// opened from (needed by set_seen). We hand these to the detail page through a
// shared ref rather than $navigateTo `props`, which doesn't work reliably in
// nativescript-vue 3 (the navigated page mounts without a native view).
export const selectedThread = ref<Thread | null>(null)
export const selectedThreadMailbox = ref<string>('')
