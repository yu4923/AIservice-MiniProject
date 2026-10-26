<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../api/markdown'
const props = defineProps({ text: { type: String, default: '' } })
const html = computed(() => renderMarkdown(props.text))
</script>

<template><div class="markdown-answer" v-html="html"></div></template>

<style scoped>
.markdown-answer { overflow-wrap:anywhere; line-height:1.8; }
.markdown-answer :deep(p) { margin:0 0 1em; white-space:normal; }
.markdown-answer :deep(h1), .markdown-answer :deep(h2), .markdown-answer :deep(h3) { margin:1.2em 0 .5em; font-size:1.15em; }
.markdown-answer :deep(ul), .markdown-answer :deep(ol) { padding-left:1.5em; margin:.5em 0 1em; }
.markdown-answer :deep(pre) { overflow-x:auto; padding:12px; background:#f3eef8; border-radius:8px; }
.markdown-answer :deep(table) { display:block; overflow-x:auto; border-collapse:collapse; }
.markdown-answer :deep(th), .markdown-answer :deep(td) { border:1px solid #d8d2df; padding:6px 10px; }
.markdown-answer :deep(a) { text-decoration:underline; }
</style>
