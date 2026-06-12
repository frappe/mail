import { ref } from 'vue'

import type { ComposeMailData } from '@mail/types'

// Pre-fill for the next ComposeView: reply/forward data, or null for a blank new compose.
// Set this before navigating to ComposeView (mirrors how `selectedThread` feeds ThreadView);
// ComposeView reads it once on mount and clears it.
export const composeContext = ref<ComposeMailData | null>(null)
