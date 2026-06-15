// Builds the single sandboxed HTML document for the compose rich-text editor,
// rendered inside one WebView. The editable area is a contenteditable div; the
// formatting toolbar lives *inside* the document (not as native chrome) so that
// tapping a button never blurs the editor — it preventDefaults and runs
// document.execCommand while the selection is preserved (the classic mobile
// WebView-editor pitfall). The doc posts content/focus changes back to native
// via an `x-rt-*` URL scheme that RichTextEditor.vue intercepts on loadStarted.

function escapeAttr(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/"/g, '&quot;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
}

// Toolbar icons — exact lucide path data (lucide-static v1.18.0), rendered at the
// wrapper's stroke 1.75 to match the rest of the app's lucide icon set. Names map to
// the lucide icons bold / italic / underline / list / list-ordered / remove-formatting.
const ICON: Record<string, string> = {
	bold: '<path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/>',
	italic: '<line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/><line x1="15" x2="9" y1="4" y2="20"/>',
	underline: '<path d="M6 4v6a6 6 0 0 0 12 0V4"/><line x1="4" x2="20" y1="20" y2="20"/>',
	ul: '<path d="M3 5h.01"/><path d="M3 12h.01"/><path d="M3 19h.01"/><path d="M8 5h13"/><path d="M8 12h13"/><path d="M8 19h13"/>',
	ol: '<path d="M11 5h10"/><path d="M11 12h10"/><path d="M11 19h10"/><path d="M4 4h1v5"/><path d="M4 9h2"/><path d="M6.5 20H3.4c0-1 2.6-1.925 2.6-3.5a1.5 1.5 0 0 0-2.6-1.02"/>',
	clear: '<path d="M4 7V4h16v3"/><path d="M5 20h6"/><path d="M13 4 8 20"/><path d="m15 15 5 5"/><path d="m20 15-5 5"/>',
}

function svg(name: string): string {
	return (
		`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ` +
		`stroke-linecap="round" stroke-linejoin="round">${ICON[name]}</svg>`
	)
}

// A toolbar button. `cmd`/`arg` drive document.execCommand; `data-toggle` marks
// buttons whose active state we reflect from queryCommandState.
function btn(name: string, cmd: string, arg = '', toggle = true): string {
	return (
		`<button class="tb" data-cmd="${cmd}" data-arg="${escapeAttr(arg)}"` +
		`${toggle ? ` data-toggle="${cmd}"` : ''}>${svg(name)}</button>`
	)
}

export function buildEditorDocument(
	initialHtml: string,
	placeholder: string,
	quotedHtml = '',
): string {
	const nonce = Math.random().toString(36).slice(2)
	const csp =
		"default-src 'none'; img-src http: https: data: cid:; style-src 'unsafe-inline'; " +
		`font-src data: https:; script-src 'nonce-${nonce}';`

	const toolbar =
		`<div class="toolbar">` +
		btn('bold', 'bold') +
		btn('italic', 'italic') +
		btn('underline', 'underline') +
		`<span class="sep"></span>` +
		btn('ul', 'insertUnorderedList') +
		btn('ol', 'insertOrderedList') +
		`<span class="sep"></span>` +
		btn('clear', 'removeFormat', '', false) +
		`</div>`

	// Reply/forward quoted text lives inside the editable area (so getHtml includes
	// it in the sent body) but starts collapsed behind an in-body ··· toggle. The
	// toggle is wrapped in a non-editable, getHtml-stripped element (.qt-wrap) so it
	// never leaks into the sent HTML. An empty line precedes it so there's room to
	// type above the quote.
	const editorBody = quotedHtml
		? `${initialHtml || '<div><br></div>'}` +
			`<div class="qt-wrap" contenteditable="false"><button class="qt" type="button">&middot;&middot;&middot;</button></div>` +
			quotedHtml
		: initialHtml

	const script = `
		(function () {
			var e = document.getElementById('e');
			var timer = null;
			// NO navigation-based messaging: NativeScript's Android WebView tries to
			// start an Activity for ANY custom-scheme navigation (top-level or iframe)
			// — "Failed to start activity for handling URL" — and the aborted
			// navigation kills the document (dead caret, dead toolbar, dead input).
			// Native PULLS the content instead via evaluateJavascript (RichTextEditor).
			// Tracks whether the keyboard is up *for this editor* — set only on real
			// focus/blur, never on resize, so layout reflows can't toggle it.
			var kbOpen = false;
			e.addEventListener('input', function () {
				if (timer) clearTimeout(timer);
				timer = setTimeout(refresh, 300);
			});
			e.addEventListener('focus', function () { kbOpen = true; placeToolbar(); });
			e.addEventListener('blur', function () {
				kbOpen = false;
				if (timer) { clearTimeout(timer); timer = null; }
				placeToolbar();
			});
			document.addEventListener('selectionchange', refresh);

			// Cross-field handoff: a native field's keyboard is up and the user taps
			// the body. Tapping won't reliably move focus into the contenteditable, so
			// grab it — but only when the tap comes from OUTSIDE the editor, so tapping
			// an already-focused editor never re-focuses (which can dismiss its kbd).
			function inToolbar(ev) {
				return ev.target && ev.target.closest && ev.target.closest('.toolbar');
			}
			var touchFromOutside = false;
			document.addEventListener('touchstart', function (ev) {
				if (inToolbar(ev)) { touchFromOutside = false; return; }
				touchFromOutside = document.activeElement !== e;
				if (touchFromOutside) e.focus();
			}, true);
			document.addEventListener('touchend', function (ev) {
				if (inToolbar(ev) || !touchFromOutside) return;
				e.focus();
				touchFromOutside = false;
			}, false);

			// Keep the toolbar docked just above the soft keyboard. NativeScript
			// doesn't resize the WebView for the keyboard, but iOS/Android shrink
			// the visual viewport — lift the fixed toolbar by that occluded height.
			var toolbar = document.querySelector('.toolbar');
			var vv = window.visualViewport;
			function placeToolbar() {
				// Lift the toolbar only while the keyboard is up for this editor. The
				// kbOpen flag flips only on real focus/blur, so a layout reflow (e.g.
				// toggling Cc/Bcc resizes the WebView and fires a transient resize)
				// can't flicker the toolbar.
				var inset = 0;
				if (vv && kbOpen) {
					inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
				}
				toolbar.style.transform = inset ? 'translateY(-' + inset + 'px)' : 'none';
			}
			if (vv) {
				vv.addEventListener('resize', placeToolbar);
				vv.addEventListener('scroll', placeToolbar);
			}
			window.addEventListener('resize', placeToolbar);
			placeToolbar();

			// Reflect active formatting on the toolbar buttons.
			function refresh() {
				var btns = document.querySelectorAll('.tb[data-toggle]');
				for (var i = 0; i < btns.length; i++) {
					var c = btns[i].getAttribute('data-toggle');
					var on = false;
					try { on = document.queryCommandState(c); } catch (_) {}
					btns[i].classList.toggle('on', !!on);
				}
			}

			// Toolbar: preventDefault on pointerdown keeps the editor focused (and the
			// selection alive) so execCommand applies to the current selection.
			document.querySelectorAll('.tb').forEach(function (b) {
				b.addEventListener('pointerdown', function (ev) { ev.preventDefault(); });
				b.addEventListener('click', function (ev) {
					ev.preventDefault();
					var cmd = b.getAttribute('data-cmd');
					var arg = b.getAttribute('data-arg') || null;
					e.focus();
					try { document.execCommand('styleWithCSS', false, true); } catch (_) {}
					document.execCommand(cmd, false, arg);
					refresh();
				});
			});

			// Quoted-text toggle: show/hide the quote in place (it stays in the DOM,
			// so it's always part of the sent body — collapsing is display-only).
			var qt = document.querySelector('.qt');
			if (qt) {
				qt.addEventListener('pointerdown', function (ev) { ev.preventDefault(); });
				qt.addEventListener('click', function (ev) {
					ev.preventDefault();
					var collapsed = e.classList.toggle('quote-collapsed');
					qt.classList.toggle('on', !collapsed);
				});
			}
		})();
	`

	return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<style>
	* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
	html, body { margin: 0; padding: 0; height: 100%; background: #ffffff;
		font-family: -apple-system, system-ui, "Segoe UI", Roboto, sans-serif; }
	/* Editor fills the WebView; bottom padding clears the floating toolbar. */
	#e { position: fixed; top: 0; left: 0; right: 0; bottom: 0; overflow-y: auto;
		-webkit-overflow-scrolling: touch; outline: none; padding: 16px 18px 64px;
		font-size: 15.5px; line-height: 1.6; color: #171717;
		-webkit-text-size-adjust: 100%; overflow-wrap: anywhere; }
	#e:empty:before { content: attr(data-ph); color: #9c9c9c; }
	#e img { max-width: 100%; height: auto; }
	#e h2 { font-size: 19px; font-weight: 700; margin: 12px 0 6px; }
	#e ul, #e ol { padding-left: 24px; margin: 8px 0; }
	#e blockquote { margin: 8px 0; padding-left: 12px; border-left: 2px solid #ededed; color: #525252; }
	#e .frappe_mail_quote, #e .frappe_mail_fwd { color: #525252; }
	#e.quote-collapsed .frappe_mail_quote, #e.quote-collapsed .frappe_mail_fwd { display: none; }
	/* In-body quoted-text toggle (a small pill on its own line). */
	.qt-wrap { margin: 6px 0; }
	.qt { display: inline-flex; align-items: center; justify-content: center; height: 24px; padding: 0 12px;
		border: none; border-radius: 12px; background: #f3f3f3; color: #7c7c7c;
		font-size: 16px; line-height: 1; letter-spacing: 1px; }
	.qt.on { color: #171717; }
	/* Pinned to the bottom; JS lifts it above the keyboard via the visual viewport. */
	.toolbar { position: fixed; left: 0; right: 0; bottom: 0; display: flex; align-items: center;
		gap: 2px; padding: 6px 10px; border-top: 1px solid #ededed; background: #f8f8f8;
		overflow-x: auto; will-change: transform; }
	.tb { width: 38px; height: 38px; border-radius: 9px; border: none; background: none; flex-shrink: 0;
		display: flex; align-items: center; justify-content: center; color: #7c7c7c; }
	.tb.on { background: #f3f3f3; color: #171717; }
	.sep { width: 1px; height: 20px; background: #ededed; margin: 0 4px; flex-shrink: 0; }
</style>
</head>
<body>
	<div id="e" contenteditable="true"${quotedHtml ? ' class="quote-collapsed"' : ''} data-ph="${escapeAttr(placeholder)}">${editorBody}</div>
	${toolbar}
	<script nonce="${nonce}">${script}</script>
</body>
</html>`
}
