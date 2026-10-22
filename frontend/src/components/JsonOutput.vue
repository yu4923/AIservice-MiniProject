<script setup>
defineProps({ value: { required: true } })
const pretty = (value) => typeof value === 'string' ? value : JSON.stringify(value, null, 2)
</script>

<template>
  <pre class="code">{{ pretty(value) }}</pre>
</template>
