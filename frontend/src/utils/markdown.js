/**
 * Markdown rendering helper — wraps `marked` + DOMPurify so chat bubbles
 * can render assistant content safely.
 *
 * Bug #22: DOMPurify defaults already strip `<script>` and dangerous
 * handlers, but we lock the policy down explicitly so a future relaxation
 * of the defaults can't open us up to XSS via prompt injection. The
 * forbidden lists are purely defensive — markdown never needs them.
 */

import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

const SANITIZE_CONFIG = {
  USE_PROFILES: { html: true },
  FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form'],
  FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus', 'onblur', 'formaction'],
  ALLOW_DATA_ATTR: false,
}

/**
 * @param {string} content
 * @returns {string} sanitized HTML
 */
export function renderMarkdown(content) {
  if (!content) return ''
  const rawHtml = marked.parse(content)
  return DOMPurify.sanitize(rawHtml, SANITIZE_CONFIG)
}
