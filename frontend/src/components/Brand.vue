<script setup>
defineProps({ white:Boolean, compact:Boolean })
</script>
<template>
  <span class="brand" :class="{compact}">
    <img v-if="!white" class="brand-mark" src="/figma/98542.svg" alt="">
    <img :src="white ? '/figma/f6e57.svg' : '/figma/03dfe.svg'" alt="YOUTH COMPASS" class="brand-word">
  </span>
</template>

<style scoped>
.brand{display:inline-flex;align-items:center;gap:13px;vertical-align:middle}.brand-mark{width:32px;height:32px}.brand-word{width:296px;height:auto;display:block}.brand.compact .brand-word{width:253px}@media(max-width:1100px){.brand-word{width:220px}.brand-mark{width:25px;height:25px}}@media(max-width:700px){.brand.compact .brand-word{width:195px}}
</style>
