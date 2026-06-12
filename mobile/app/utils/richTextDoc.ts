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

// Toolbar icons — mirror the design's compose.jsx FmtIcons (stroke 1.75 line set).
const ICON: Record<string, string> = {
	bold: '<path d="M8 5h5a3.25 3.25 0 0 1 0 6.5H8zM8 11.5h6a3.25 3.25 0 0 1 0 6.5H8z" stroke-width="2.1"/><path d="M8 5v13" stroke-width="2.1"/>',
	italic: '<path d="M11 5h7M6 19h7M14.5 5l-5 14"/>',
	highlight:
		'<path d="m13.5 6.5 4 4L9 19H5v-4z"/><path d="m11.5 8.5 4 4"/><path d="M16 4l4 4"/>',
	h2: '<path d="M3 6v12M10 6v12M3 12h7"/><path d="M14 11a2.6 2.6 0 0 1 5 1c0 2.2-5 3.5-5 6h5" stroke-width="1.6"/>',
	ul: '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4.5" cy="6" r="1" fill="currentColor" stroke="none"/><circle cx="4.5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="4.5" cy="18" r="1" fill="currentColor" stroke="none"/>',
	ol: '<path d="M10 6h11M10 12h11M10 18h11"/><path d="M4 5l1.5-1v4M3.8 10.8a1.4 1.4 0 0 1 2.7.5c0 1.1-2.6 1.7-2.6 2.7h2.8M3.8 16.4h2a1.1 1.1 0 0 1 0 2.2h-.9a1.1 1.1 0 0 1 .1 2.2H3.7" stroke-width="1.3"/>',
	link: '<path d="M10.5 13.5a4.2 4.2 0 0 0 6 0l2.6-2.6a4.24 4.24 0 1 0-6-6l-1.3 1.3"/><path d="M13.5 10.5a4.2 4.2 0 0 0-6 0l-2.6 2.6a4.24 4.24 0 1 0 6 6l1.3-1.3"/>',
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

export function buildEditorDocument(initialHtml: string, placeholder: string): string {
	const nonce = Math.random().toString(36).slice(2)
	const csp =
		"default-src 'none'; img-src http: https: data: cid:; style-src 'unsafe-inline'; " +
		`font-src data: https:; script-src 'nonce-${nonce}';`

	const toolbar =
		`<div class="toolbar">` +
		btn('bold', 'bold') +
		btn('italic', 'italic') +
		btn('highlight', 'hiliteColor', '#fde68a', true) +
		`<span class="sep"></span>` +
		btn('h2', 'formatBlock', 'H2', false) +
		btn('ul', 'insertUnorderedList') +
		btn('ol', 'insertOrderedList') +
		`<span class="sep"></span>` +
		btn('link', 'createLink', '', false) +
		`</div>`

	const script = `
		(function () {
			var e = document.getElementById('e');
			var timer = null;
			// Post messages to native through a hidden iframe, NOT a top-level
			// location change: navigating the main frame blurs the contenteditable
			// (dismissing the keyboard) and blanks the document. The iframe's
			// navigation is intercepted natively while the editor keeps focus.
			var bridge = document.createElement('iframe');
			bridge.setAttribute('aria-hidden', 'true');
			bridge.style.cssText = 'position:absolute;left:-9999px;width:0;height:0;border:0';
			document.body.appendChild(bridge);
			function sync() {
				try { bridge.src = 'x-rt-sync:' + encodeURIComponent(e.innerHTML); } catch (_) {}
			}
			// Tracks whether the keyboard is up *for this editor* — set only on real
			// focus/blur, never on resize, so layout reflows can't toggle it.
			var kbOpen = false;
			e.addEventListener('input', function () {
				if (timer) clearTimeout(timer);
				timer = setTimeout(function () { sync(); refresh(); }, 300);
			});
			e.addEventListener('focus', function () { kbOpen = true; placeToolbar(); });
			e.addEventListener('blur', function () {
				kbOpen = false;
				if (timer) { clearTimeout(timer); timer = null; }
				sync();
				placeToolbar();
			});
			document.addEventListener('selectionchange', refresh);

			// Coming from a native field, the first tap on the WebView only dismisses
			// that field's keyboard and leaves the editor unfocused (needing a second
			// tap). Re-assert focus across the whole gesture: touchstart is too early
			// (the WebView isn't first responder yet), so focus again on touchend —
			// by then the tap has made the WebView first responder and the keyboard
			// comes up the first time.
			function inToolbar(ev) {
				return ev.target && ev.target.closest && ev.target.closest('.toolbar');
			}
			document.addEventListener('touchstart', function (ev) {
				if (inToolbar(ev)) return;
				if (document.activeElement !== e) e.focus();
			}, true);
			document.addEventListener('touchend', function (ev) {
				if (inToolbar(ev)) return;
				e.focus();
			}, false);
			document.addEventListener('mousedown', function (ev) {
				if (inToolbar(ev)) return;
				if (document.activeElement !== e) e.focus();
			}, true);

			// Keep the toolbar docked just above the soft keyboard. NativeScript
			// doesn't resize the WebView for the keyboard, but iOS/Android shrink
			// the visual viewport — lift the fixed toolbar by that occluded height.
			var toolbar = document.querySelector('.toolbar');
			var vv = window.visualViewport;
			function placeToolbar() {
				// Only lift the toolbar while the keyboard is up for this editor. The
				// kbOpen flag flips only on real focus/blur, so a layout reflow (e.g.
				// toggling Cc/Bcc, which resizes the WebView and fires a resize with
				// innerHeight/visualViewport briefly out of sync) can't produce the
				// transient inset that flickered the toolbar up and down.
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
					if (cmd === 'createLink') {
						var url = window.prompt('Link URL', 'https://');
						if (!url) return;
						arg = url;
					}
					try { document.execCommand('styleWithCSS', false, true); } catch (_) {}
					document.execCommand(cmd, false, arg);
					sync();
					refresh();
				});
			});
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
	<div id="e" contenteditable="true" data-ph="${escapeAttr(placeholder)}">${initialHtml}</div>
	${toolbar}
	<script nonce="${nonce}">${script}</script>
</body>
</html>`
}
