<script setup>
import { ref } from 'vue'
const photos = ref(null)
const documents = ref(null)
const files = ref([])
const notice = ref('')
function selectFiles(event) {
  const selected = [...event.target.files]
  notice.value = ''
  for (const file of selected) {
    if (files.value.some(item => item.name === file.name && item.size === file.size)) continue
    if (files.value.length >= 5 || file.size > 10 * 1024 * 1024) {
      notice.value = '파일은 개당 10MB 이하, 최대 5개까지 선택할 수 있어요.'
      continue
    }
    files.value.push(file)
  }
  event.target.value = ''
}
</script>

<template>
  <div class="attachments">
    <div class="attachment-controls">
      <button type="button" aria-label="사진 첨부" title="사진 첨부" @click="photos.click()"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r="1.5"/><path d="m3 16 5-5 4 4 3-3 6 6"/></svg></button>
      <button type="button" aria-label="파일 첨부" title="파일 첨부" @click="documents.click()"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m8 13 7-7a3 3 0 0 1 4.24 4.24L10 19.49a5 5 0 0 1-7.07-7.07l9.19-9.19M6 15l8-8"/></svg></button>
    </div>
    <input ref="photos" type="file" accept="image/*" multiple hidden @change="selectFiles">
    <input ref="documents" type="file" multiple hidden @change="selectFiles">
    <ul v-if="files.length" class="attachment-list" aria-label="선택한 첨부파일">
      <li v-for="(file, index) in files" :key="file.name + file.size"><span>{{ file.name }}</span><button type="button" :aria-label="`${file.name} 첨부 삭제`" @click="files.splice(index, 1)">×</button></li>
    </ul>
    <p v-if="files.length" role="status">파일 선택만 가능해요. 현재 대화에는 입력한 글만 전송돼요.</p>
    <p v-if="notice" role="alert">{{ notice }}</p>
  </div>
</template>

<style scoped>
.attachments { color:#563089; }
.attachment-controls { display:flex; gap:4px; }
.attachment-controls button { display:grid; place-items:center; width:38px; height:38px; padding:0; border:0; border-radius:50%; background:transparent; color:inherit; cursor:pointer; }
.attachment-controls button:hover { background:#8739ee18; }
button:focus-visible { outline:2px solid #8739ee; outline-offset:2px; }
svg { position:static; display:block; width:21px; height:21px; stroke:currentColor; stroke-width:1.6; stroke-linecap:round; stroke-linejoin:round; }
.attachment-list { display:flex; flex-wrap:wrap; gap:6px; list-style:none; padding:0; margin:8px 0; }
li { display:flex; align-items:center; gap:6px; max-width:100%; padding:4px 8px; border-radius:8px; background:#ffffff80; font-size:12px; }
li span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
li button { border:0; background:none; color:inherit; min-width:28px; min-height:28px; font-size:20px; cursor:pointer; }
p { font-size:12px; margin:6px 0 0; line-height:1.5; }
</style>
