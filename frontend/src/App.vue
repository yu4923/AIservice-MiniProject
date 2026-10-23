<script setup>
import { nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
let activeTransition
const removeGuard = router.beforeResolve((to, from) => {
  if (!from.matched.length || to.path === from.path || !document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) return
  activeTransition?.skipTransition()
  return new Promise(resolve => {
    try {
      activeTransition = document.startViewTransition(() => new Promise(done => {
        let timer
        const finish = async () => { clearTimeout(timer); removeAfter(); await nextTick(); done() }
        const removeAfter = router.afterEach(finish)
        timer = setTimeout(finish, 1200)
        resolve()
      }))
      activeTransition.finished.catch(() => {})
    } catch { resolve() }
  })
})
onBeforeUnmount(() => { removeGuard(); activeTransition?.skipTransition() })
</script>

<template>
  <RouterView />
</template>

<style>
::view-transition { pointer-events:none; }
::view-transition-old(root) { animation: page-depart 180ms ease both; }
::view-transition-new(root) { animation: page-arrive 380ms cubic-bezier(.16,1,.3,1) both; }
@keyframes page-depart { to { opacity:0; } }
@keyframes page-arrive { from { opacity:0; } to { opacity:1; } }
@media(prefers-reduced-motion:reduce) {
  ::view-transition-old(root),::view-transition-new(root) { animation:none; }
}
</style>
