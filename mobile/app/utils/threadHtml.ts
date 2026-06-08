// Builds the single sandboxed HTML document that renders an entire thread inside
// one WebView. NativeScript has no DOM, so we can't run DOMPurify in-app (as the
// web does in EmailContent.vue); instead the document carries a strict CSP that
// blocks all untrusted scripts, inline event handlers and javascript: URLs, and
// we additionally strip those with regex as a backstop. Only our nonce'd helper
// script (quote-collapse + external link handling) is allowed to run.

import { formatRecipients, formatTimeAgo } from '@/utils/format'
import { gravatarUrl } from '@/utils/gravatar'

import type { Mail } from '@mail/types'

export function escapeHtml(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;')
}

function initials(name: string): string {
	const parts = name.trim().split(/\s+/).filter(Boolean)
	if (parts.length === 0) return '?'
	if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
	return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// Mirrors the web hasHtmlContent (frontend/src/utils/index.ts).
export function hasHtmlContent(content?: string | null): boolean {
	if (!content) return false
	return /<(html|head|body|div|p|span|table|td|tr|a|img|br|hr|h[1-6]|ul|ol|li|strong|em|b|i|font|style)[^>]*>/i.test(
		content,
	)
}

// Regex backstop (the CSP is the real guard): drop scripts, inline event
// handlers, and javascript:/data:text/html URLs from an untrusted body.
function sanitizeBody(html: string): string {
	return html
		.replace(/<script\b[\s\S]*?<\/script>/gi, '')
		.replace(/\son\w+\s*=\s*"[^"]*"/gi, '')
		.replace(/\son\w+\s*=\s*'[^']*'/gi, '')
		.replace(/\son\w+\s*=\s*[^\s>]+/gi, '')
		.replace(/(href|src)\s*=\s*("|')\s*javascript:[^"']*\2/gi, '$1=$2#$2')
		.replace(/(href|src)\s*=\s*("|')\s*data:text\/html[^"']*\2/gi, '$1=$2#$2')
}

// Colored file-type badge as inline SVG (same look as the list's bundled PNGs),
// so chips need no external/bundled asset inside the WebView.
const BADGE = (symbol: string) =>
	`<svg width="16" height="16" viewBox="0 0 16 16" fill="none">${symbol}</svg>`
const FILE_ICONS: Record<string, string> = {
	image: BADGE(
		'<path fill-rule="evenodd" clip-rule="evenodd" d="M4 1C2.34315 1 1 2.34315 1 4V12C1 13.6569 2.34315 15 4 15H12C13.6569 15 15 13.6569 15 12V4C15 2.34315 13.6569 1 12 1H4ZM5.25002 7C6.21652 7 7.00002 6.2165 7.00002 5.25C7.00002 4.2835 6.21652 3.5 5.25002 3.5C4.28352 3.5 3.50002 4.2835 3.50002 5.25C3.50002 6.2165 4.28352 7 5.25002 7ZM3.67581 14C3.44371 14 3.33689 13.7112 3.51312 13.5602L9.7211 8.23906C9.88705 8.09682 10.1262 8.07885 10.3115 8.19469L13.765 10.3531C13.9112 10.4445 14 10.6047 14 10.7771V12C14 13.1046 13.1046 14 12 14H3.67581Z" fill="#3BBDE5"/>',
	),
	pdf: BADGE(
		'<path fill-rule="evenodd" clip-rule="evenodd" d="M4 1C2.34315 1 1 2.34315 1 4V12C1 13.6569 2.34315 15 4 15H12C13.6569 15 15 13.6569 15 12V4C15 2.34315 13.6569 1 12 1H4ZM5.80893 10.6773C4.63445 12.7569 4.02298 13 3.66401 13C3.48964 13 3.32827 12.9308 3.19736 12.7999C3.03677 12.6393 2.97231 12.4388 3.01087 12.22C3.14435 11.4651 4.55054 10.6893 5.4324 10.2721C5.74113 9.71489 6.06198 9.07811 6.3865 8.37778C6.67422 7.757 6.93539 7.12033 7.14466 6.52956C6.69545 5.46922 6.34749 4.03811 6.79536 3.35278C6.94617 3.122 7.17178 3 7.44773 3C7.69489 3 7.89782 3.10178 8.03485 3.29411C8.38115 3.78089 8.27179 4.86178 7.70989 6.50744C7.91738 6.96589 8.16155 7.39778 8.43672 7.79256C8.72956 8.21311 9.15365 8.61222 9.6671 8.95089C10.1745 8.87467 10.6485 8.836 11.0775 8.836C11.9395 8.836 12.5214 8.98744 12.8068 9.28622C12.9413 9.42689 13.0078 9.59978 12.9993 9.78656C12.993 9.92289 12.9118 10.3681 12.1247 10.3681C11.4129 10.3681 10.413 10.03 9.55263 9.50189C9.03074 9.58889 8.49662 9.71311 7.96295 9.87111C7.22857 10.0888 6.48574 10.3669 5.80893 10.6773ZM12.426 9.64967C12.3616 9.58222 12.074 9.36233 11.0774 9.36233C10.879 9.36233 10.6699 9.37122 10.4512 9.38878C11.1161 9.69889 11.7339 9.84167 12.1246 9.84167C12.3747 9.84167 12.4628 9.78422 12.4728 9.76867C12.4747 9.73267 12.4702 9.69578 12.426 9.64967ZM7.44773 3.52633C7.35182 3.52633 7.28847 3.56056 7.23612 3.64067C7.04864 3.92744 7.06575 4.717 7.40427 5.73189C7.77046 4.48589 7.76013 3.81611 7.60576 3.59911C7.57464 3.55544 7.53586 3.52633 7.44773 3.52633ZM7.4485 7.22411C7.27413 7.67544 7.07609 8.14167 6.86415 8.599C6.65 9.06144 6.43706 9.49711 6.22779 9.90133L6.24869 9.89156L6.23213 9.92122C6.74613 9.71222 7.28214 9.524 7.81347 9.36656C8.17722 9.25878 8.54163 9.16611 8.9026 9.08967L8.88004 9.07522L8.93283 9.067C8.56019 8.76833 8.24479 8.43822 8.00463 8.09333C7.81014 7.81411 7.63021 7.51789 7.46662 7.20767L7.45551 7.23978L7.4485 7.22411ZM4.93196 11.1197C4.02443 11.6269 3.57288 12.0651 3.52932 12.3116C3.52209 12.3526 3.52643 12.3846 3.56955 12.4279C3.60989 12.4681 3.63879 12.4737 3.66401 12.4737C3.74059 12.4737 4.11922 12.3991 4.93196 11.1197Z" fill="#E03636"/>',
	),
	video: BADGE(
		'<path fill-rule="evenodd" clip-rule="evenodd" d="M4 1C2.34315 1 1 2.34315 1 4V12C1 13.6569 2.34315 15 4 15H12C13.6569 15 15 13.6569 15 12V4C15 2.34315 13.6569 1 12 1H4ZM7.09287 10.8763L10.7212 8.47937C10.8945 8.37679 11 8.19537 11 8C11 7.80463 10.8945 7.62321 10.7212 7.52063L7.09287 5.12375C6.891 4.9855 6.62753 4.96127 6.40197 5.06021C6.17641 5.15916 6.02312 5.36619 6 5.60313V10.3969C6.02312 10.6338 6.17641 10.8408 6.40197 10.9398C6.62753 11.0387 6.891 11.0145 7.09287 10.8763Z" fill="#E86C13"/>',
	),
	audio: BADGE(
		'<path fill-rule="evenodd" clip-rule="evenodd" d="M4 1C2.34315 1 1 2.34315 1 4V12C1 13.6569 2.34315 15 4 15H12C13.6569 15 15 13.6569 15 12V4C15 2.34315 13.6569 1 12 1H4ZM9.99364 3.86769C10.2674 3.82819 10.5444 3.91261 10.7509 4.09842C10.9528 4.28078 11.0669 4.54233 11.0638 4.81589V10.3381C11.0638 11.0366 10.3629 11.6024 9.49922 11.6024C8.63555 11.6024 7.93461 11.0366 7.93461 10.3381C7.93461 9.6396 8.63555 9.07384 9.49922 9.07384C9.82973 9.07182 10.1544 9.16147 10.438 9.33302V5.64521L6.68293 6.18569V10.8776C6.68293 11.5761 5.98198 12.1418 5.11832 12.1418C4.25465 12.1418 3.55371 11.5761 3.55371 10.8776C3.55371 10.1791 4.25465 9.61332 5.11832 9.61332C5.44883 9.6113 5.77354 9.70094 6.05708 9.87249V5.26786C6.05245 4.79193 6.39784 4.38627 6.86442 4.31966L9.99364 3.86769Z" fill="#9C45E3"/>',
	),
	file: BADGE(
		'<path d="M4 1C2.34315 1 1 2.34315 1 4V12C1 13.6569 2.34315 15 4 15H12C13.6569 15 15 13.6569 15 12V4C15 2.34315 13.6569 1 12 1H4Z" fill="#A3A3A3"/>',
	),
}
function fileIconSvg(type: string): string {
	if (type.startsWith('image/')) return FILE_ICONS.image
	if (type === 'application/pdf') return FILE_ICONS.pdf
	if (type.startsWith('video/')) return FILE_ICONS.video
	if (type.startsWith('audio/')) return FILE_ICONS.audio
	return FILE_ICONS.file
}

// Mirrors the web filteredAttachments: real attachments (skip inline images).
function attachmentChips(mail: Mail): string {
	const atts = (mail.attachments || []).filter(
		(a) => a.filename && (a.disposition === 'attachment' || !a.type?.startsWith('image/')),
	)
	if (!atts.length) return ''
	const chips = atts
		.map(
			(a) =>
				`<div class="chip">${fileIconSvg(a.type || '')}<span>${escapeHtml(a.filename)}</span></div>`,
		)
		.join('')
	return `<div class="atts">${chips}</div>`
}

function messageHtml(mail: Mail, index: number): string {
	const name = mail.from_name || mail.from_email || '?'
	const avatar =
		`<div class="avatar"><span>${escapeHtml(initials(name))}</span>` +
		`<img src="${escapeHtml(gravatarUrl(mail.from_email || ''))}" alt=""></div>`
	const meta =
		`<div class="meta"><div class="from"><span class="from-name">${escapeHtml(name)}</span>` +
		`<span class="date">${escapeHtml(formatTimeAgo(mail.received_at))}</span></div>` +
		`<div class="to">${escapeHtml(formatRecipients(mail.recipients || []))}</div></div>`
	const more = `<span class="more" data-i="${index}">&#8942;</span>`
	const body = hasHtmlContent(mail.html_body)
		? `<div class="body">${sanitizeBody(mail.html_body)}</div>`
		: `<div class="body"><pre>${escapeHtml(mail.html_body || mail.text_body || '')}</pre></div>`
	return `<div class="msg"><div class="mhead">${avatar}${meta}${more}</div>${body}${attachmentChips(mail)}</div>`
}

export function buildThreadDocument(mails: Mail[], subject: string): string {
	// Per-load nonce so only our own inline script is allowed by the CSP.
	const nonce = Math.random().toString(36).slice(2)
	const messages = mails.map((m, i) => messageHtml(m, i)).join('<hr class="divider">')

	const csp =
		"default-src 'none'; img-src http: https: data: cid:; style-src 'unsafe-inline'; " +
		`font-src data: https:; script-src 'nonce-${nonce}';`

	const script = `
		(function () {
			// Reveal avatar images only once they load — a broken/404 gravatar stays
			// hidden so the initials underneath show (we can't use onerror under CSP).
			document.querySelectorAll('.avatar img').forEach(function (img) {
				function show() { if (img.naturalWidth > 0) img.style.display = 'block'; }
				if (img.complete) show(); else img.addEventListener('load', show);
			});
			document.querySelectorAll('.gmail_quote, .frappe_mail_quote').forEach(function (q) {
				q.classList.add('quote-hidden');
				var b = document.createElement('button');
				b.className = 'collapse-btn'; b.textContent = '\\u00b7\\u00b7\\u00b7';
				b.addEventListener('click', function () { q.classList.toggle('quote-hidden'); });
				q.parentNode && q.parentNode.insertBefore(b, q);
			});
			document.querySelectorAll('img[width="1"], img[height="1"]').forEach(function (i) {
				i.className += ' email-pixel';
			});
			document.querySelectorAll('.more').forEach(function (el) {
				el.addEventListener('click', function (e) {
					e.preventDefault();
					location.href = 'x-more:' + (el.getAttribute('data-i') || '');
				});
			});
			document.addEventListener('click', function (e) {
				var a = e.target && e.target.closest && e.target.closest('a');
				if (a && a.getAttribute('href')) {
					e.preventDefault();
					location.href = 'x-open:' + encodeURIComponent(a.href);
				}
			});
		})();
	`

	return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<style>
	* { box-sizing: border-box; }
	/* Guard our chrome from a message's own <style> (e.g. body{background}/body{color}),
	   which targets this single document's body since we render the thread in one doc. */
	html body { background-color: #ffffff !important; }
	body { font-family: -apple-system, system-ui, "Segoe UI", Roboto, sans-serif; font-size: 15px;
		line-height: 1.5; color: #171717; margin: 0; padding: 16px 16px 96px;
		-webkit-text-size-adjust: 100%; overflow-wrap: anywhere; }
	.subject { color: #171717; font-size: 22px; font-weight: 700; line-height: 1.3; margin: 4px 0 18px; }
	.msg { padding: 2px 0; }
	.mhead { display: flex; gap: 12px; align-items: center; margin: 14px 0 12px; }
	.avatar { position: relative; width: 40px; height: 40px; border-radius: 40px;
		background: #F3F3F3; flex-shrink: 0; overflow: hidden; }
	.avatar span { position: absolute; inset: 0; display: flex; align-items: center;
		justify-content: center; font-size: 14px; font-weight: 600; color: #525252; }
	.avatar img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
		display: none; }
	.meta { min-width: 0; flex: 1; }
	.from { display: flex; align-items: baseline; gap: 8px; }
	.from-name { flex: 1; min-width: 0; font-size: 15px; font-weight: 600; color: #171717;
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.date { flex-shrink: 0; font-size: 13px; font-weight: 400; color: #7c7c7c; }
	.to { font-size: 13px; color: #7c7c7c; margin-top: 2px; word-break: break-word; }
	.more { flex-shrink: 0; align-self: flex-start; width: 24px; height: 24px; margin-left: 2px;
		display: flex; align-items: center; justify-content: center; color: #7c7c7c;
		font-size: 17px; line-height: 1; border-radius: 24px; }
	.body { font-size: 15px; line-height: 1.6; color: #383838; }
	.body img { max-width: 100%; height: auto; }
	.body table { max-width: 100%; }
	blockquote { margin: 8px 0; padding-left: 12px; border-left: 2px solid #ededed; color: #525252; }
	pre, code { font-family: ui-monospace, Menlo, Courier, monospace; white-space: pre-wrap;
		overflow-wrap: anywhere; }
	.quote-hidden { display: none; }
	.email-pixel { display: none !important; width: 0 !important; height: 0 !important; }
	.divider { border: none; border-top: 1px solid #ededed; margin: 22px 0; }
	.atts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
	.chip { display: inline-flex; align-items: center; gap: 8px; border: 1px solid #e2e2e2;
		border-radius: 10px; padding: 7px 11px; font-size: 13px; color: #525252; max-width: 100%; }
	.chip svg { flex-shrink: 0; }
	.chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.collapse-btn { background: #F3F3F3; color: #383838; border: none; padding: 1px 8px;
		border-radius: 8px; margin: 12px 0; font-size: 14px; line-height: 1.4; }
	@media (max-width: 640px) {
		table[width="600"], table[width="600px"] { width: 100% !important; }
	}
</style>
</head>
<body>
	<div class="subject">${escapeHtml(subject || '[No subject]')}</div>
	${messages}
	<script nonce="${nonce}">${script}</script>
</body>
</html>`
}
