// Shared UI types for mailbox navigation (kept out of <script setup>, which
// can't contain ES module exports).

import type { MailboxData } from '@mail/types'

// The mailbox currently shown by MailboxScreen. `id` is a mailbox id or the
// literal "starred"; `total` is the thread count for the header (null hides it).
export interface ActiveMailbox {
	id: string
	label: string
	role: string | null
	total: number | null
}

// What the nav drawer emits when an item is tapped.
export type NavSelection =
	| { kind: 'mailbox'; mailbox: MailboxData }
	| { kind: 'starred' }
	| { kind: 'view'; label: string }
