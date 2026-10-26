import MarkdownIt from 'markdown-it'

// 원문 HTML은 실행하지 않고 Markdown 서식만 렌더링한다.
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false })
export const renderMarkdown = text => markdown.render(typeof text === 'string' ? text : '')
