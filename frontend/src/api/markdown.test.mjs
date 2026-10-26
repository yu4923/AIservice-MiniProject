import assert from 'node:assert/strict'
import { test } from 'node:test'
import { renderMarkdown } from './markdown.js'
test('renders Markdown formatting and blocks raw HTML and executable links', () => {
 assert.match(renderMarkdown('**조건**\n\n- 서울 거주'), /<strong>조건<\/strong>/)
 assert.match(renderMarkdown('- 서울 거주'), /<li>서울 거주<\/li>/)
 assert.doesNotMatch(renderMarkdown('<script>alert(1)</script>'), /<script>/)
 assert.doesNotMatch(renderMarkdown('[클릭](javascript:alert(1))'), /href="javascript:/)
})
