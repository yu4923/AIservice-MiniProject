<script setup>
import { ref, onBeforeUnmount } from 'vue'
const props = defineProps({ text: { type:String, default:'' } })
const rating=ref(null), speaking=ref(false), notice=ref('')
let utterance
function rate(value){ rating.value=rating.value===value?null:value; notice.value=rating.value?'평가를 선택했어요. 서버 저장은 아직 연결되지 않았어요.':'' }
function read(){
 if(!('speechSynthesis' in window)){notice.value='이 브라우저는 읽기 기능을 지원하지 않아요.';return}
 if(speaking.value){window.speechSynthesis.cancel();speaking.value=false;return}
 window.speechSynthesis.cancel()
 utterance=new SpeechSynthesisUtterance(props.text)
 utterance.lang='ko-KR'
 utterance.onend=()=>{speaking.value=false}
 utterance.onerror=()=>{speaking.value=false;notice.value='읽기를 완료하지 못했어요. 다시 시도해 주세요.'}
 speaking.value=true;notice.value='';window.speechSynthesis.speak(utterance)
}
async function copy(){try{await navigator.clipboard.writeText(props.text);notice.value='답변을 복사했어요.'}catch{notice.value='복사 권한을 확인해 주세요.'}}
onBeforeUnmount(()=>{if(speaking.value)window.speechSynthesis.cancel()})
</script>
<template>
 <div class="answer-actions">
  <div class="action-buttons">
   <button type="button" aria-label="좋은 응답" title="좋은 응답" :aria-pressed="rating==='good'" @click="rate('good')"><svg viewBox="0 0 24 24"><path d="M7 10h-4v11h4m0-11 5-7c2 0 3 1 2 4l-1 3h6a2 2 0 0 1 2 2l-2 7a3 3 0 0 1-3 2H7V10Z"/></svg></button>
   <button type="button" aria-label="나쁜 응답" title="나쁜 응답" :aria-pressed="rating==='bad'" @click="rate('bad')"><svg viewBox="0 0 24 24"><path d="M7 14H3V3h4m0 11 5 7c2 0 3-1 2-4l-1-3h6a2 2 0 0 0 2-2l-2-7a3 3 0 0 0-3-2H7v11Z"/></svg></button>
   <button type="button" :aria-label="speaking?'읽기 중지':'소리 내어 읽기'" :title="speaking?'읽기 중지':'소리 내어 읽기'" :aria-pressed="speaking" :disabled="!text" @click="read"><svg viewBox="0 0 24 24"><path d="M4 9h4l5-4v14l-5-4H4V9Zm12-1c2 2 2 6 0 8m3-11c4 4 4 10 0 14"/></svg></button>
   <button type="button" aria-label="답변 복사" title="복사" :disabled="!text" @click="copy"><svg viewBox="0 0 24 24"><rect x="4" y="8" width="12" height="13" rx="1"/><path d="M8 8V3h12v13h-4"/></svg></button>
  </div>
  <p v-if="notice" role="status">{{notice}}</p>
 </div>
</template>
<style scoped>
.answer-actions { margin-top:18px; }
.action-buttons { display:flex; align-items:center; gap:8px; }
button { display:grid; place-items:center; width:32px; height:32px; border:0; border-radius:8px; padding:0; background:transparent; color:#49404f; cursor:pointer; }
button:hover,button[aria-pressed=true] { color:#8739ee; background:#8739ee12; }
button:focus-visible { outline:2px solid #8739ee; outline-offset:2px; }
button:disabled { opacity:.4; cursor:default; }
svg { position:static; display:block; width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:1.5; stroke-linecap:round; stroke-linejoin:round; }
p { margin:6px 0 0; color:#654582; font-size:12px; line-height:1.5; }
</style>
