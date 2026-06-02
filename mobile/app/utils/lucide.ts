// Lucide icons rendered as a font (app/fonts/lucide.ttf, family "lucide").
// Use a Label with the `lucide` font-family and set its text to the glyph.

import { LUCIDE_CODEPOINTS } from './lucide-codepoints'

// Returns the glyph for a Lucide icon name (resolves any name on the fly), or
// '' if unknown.
export function lucide(name: string): string {
	const cp = LUCIDE_CODEPOINTS[name]
	return cp ? String.fromCharCode(cp) : ''
}

// Mirrors frontend FOLDER_ICON_MAP (constants.ts) so mobile matches the web app.
const FOLDER_ICON_MAP: Record<string, string> = {
	inbox: 'inbox',
	sent: 'send',
	trash: 'trash-2',
	junk: 'mail-warning',
	drafts: 'pencil-line',
	archive: 'archive',
	important: 'bookmark',
}

// Mirrors frontend getIcon(): a folder's own icon wins, then a role default,
// then a plain folder. The icon string is a Lucide name resolved via lucide().
export function mailboxIcon(mailbox: { icon?: string; role?: string | null }): string {
	if (mailbox.icon) return mailbox.icon
	if (mailbox.role && FOLDER_ICON_MAP[mailbox.role]) return FOLDER_ICON_MAP[mailbox.role]
	return 'folder'
}

// Mirrors frontend FOLDER_ICON_COLOR_MAP — maps a folder colour to an icon class.
const COLOR_CLASS: Record<string, string> = {
	Blue: 'nd-ic-blue',
	Green: 'nd-ic-green',
	Amber: 'nd-ic-amber',
	Red: 'nd-ic-red',
	Purple: 'nd-ic-purple',
}

export function folderColorClass(color?: string | null): string {
	return color ? (COLOR_CLASS[color] ?? '') : ''
}
