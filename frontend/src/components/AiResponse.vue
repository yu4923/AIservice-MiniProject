<script setup>
import AnswerActions from './AnswerActions.vue'
defineProps({ loading: Boolean, text: { type:String, default:'' } })
</script>

<template>
  <div class="ai-response" :aria-busy="loading">
    <span class="avatar-glass"><svg class="response-avatar" :class="{ 'is-thinking': loading }" viewBox="0 0 60 60" role="img" aria-label="Youth Compass AI">
      <circle cx="30" cy="30" r="25" fill="white" stroke="#17151d" stroke-width="6"/>
      <g class="compass-needle"><path d="M15 39 39 15 45 21 21 45Z" fill="#8739ee"/></g>
    </svg></span>
    <div class="response-content">
      <p v-if="loading" class="response-thinking" role="status">답변을 준비하고 있어요…</p>
      <div v-else class="response-answer"><slot /></div>
      <AnswerActions v-if="!loading && text" :text="text" />
    </div>
  </div>
</template>

<style scoped>
.ai-response { display:grid; grid-template-columns:42px minmax(0,1fr); gap:16px; align-items:start; }
.avatar-glass { display:grid; place-items:center; width:42px; height:42px; box-sizing:border-box; border:1px solid #ffffffd9; border-radius:14px; background:linear-gradient(135deg,#ffffffd9,#e7dcf580 60%,#d9c9ef66); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); box-shadow:0 3px 10px #5b34831a,inset 0 1px 1px #fff; }
.response-avatar { position:static; display:block; width:27px; height:27px; flex-shrink:0; }
.response-content { min-width:0; overflow-wrap:anywhere; }
.response-answer { animation:answer-arrive 360ms cubic-bezier(.16,1,.3,1) both; }
@keyframes answer-arrive { from { opacity:.35; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
.response-thinking { margin:0; color:#654582; font-size:14px; line-height:1.7; }
.compass-needle { transform-origin:30px 30px; }
.is-thinking .compass-needle { animation:compass-thinking 1.8s cubic-bezier(.45,0,.25,1) infinite; }
@keyframes compass-thinking { to { transform:rotate(360deg); } }
@media(max-width:600px) { .ai-response { grid-template-columns:36px minmax(0,1fr); gap:10px; } .avatar-glass { width:36px; height:36px; border-radius:12px; } .response-avatar { width:24px; height:24px; } }
@media(prefers-reduced-motion:reduce) { .is-thinking .compass-needle { animation:none; } }
@media(prefers-reduced-motion:reduce) { .response-answer { animation:none; } }
</style>
