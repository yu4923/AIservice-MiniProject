<script setup>
import { onMounted, onBeforeUnmount } from 'vue'

const emit = defineEmits(['complete'])
let fallbackTimer
let completed = false
function finish() {
  if (completed) return
  completed = true
  clearTimeout(fallbackTimer)
  emit('complete')
}
function onKeydown(event) {
  if (event.key === 'Escape') finish()
}
function onAnimationEnd(event) {
  if (event.target === event.currentTarget && event.animationName.includes('intro-depart')) finish()
}
onMounted(() => {
  // Always release the overlay, even if animations are disabled by browser settings.
  fallbackTimer = setTimeout(finish, 3600)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  clearTimeout(fallbackTimer)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <section class="intro-splash" aria-label="Youth Compass 시작 화면" @animationend="onAnimationEnd">
    <div class="intro-texture" aria-hidden="true"></div>
    <div class="intro-light intro-light-one" aria-hidden="true"></div>
    <div class="intro-light intro-light-two" aria-hidden="true"></div>
    <img class="intro-logo" src="/figma/a7989.svg" alt="YOUTH COMPASS" fetchpriority="high">
    <button class="intro-skip" autofocus @click="finish">건너뛰기 <span aria-hidden="true">→</span></button>
  </section>
</template>

<style scoped>
.intro-splash {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  overflow: hidden;
  isolation: isolate;
  background: #6933c6;
  animation: intro-depart 550ms cubic-bezier(.4, 0, .2, 1) 2650ms both;
}
.intro-texture {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 150vmax;
  height: 150vmax;
  z-index: -3;
  background: url('/figma/994a3.png') center / cover no-repeat;
  transform: translate(-50%, -50%) rotate(90deg);
  animation: intro-drift 7s ease-in-out alternate infinite;
}
.intro-light {
  position: absolute;
  inset: -20%;
  pointer-events: none;
  mix-blend-mode: soft-light;
}
.intro-light-one {
  z-index: -2;
  background: radial-gradient(ellipse at 70% 35%, #e7c9ffb3 0%, transparent 53%);
  animation: intro-light-drift 6s ease-in-out alternate infinite;
}
.intro-light-two {
  z-index: -1;
  background: radial-gradient(ellipse at 20% 75%, #42139b99 0%, transparent 58%);
  animation: intro-light-drift 7s ease-in-out alternate-reverse infinite;
}
.intro-logo {
  display: block;
  width: min(75%, 1061px);
  height: auto;
  animation: intro-logo-reveal 2650ms both;
}
.intro-skip {
  position: absolute;
  right: clamp(20px, 4vw, 60px);
  bottom: clamp(24px, 4vh, 50px);
  border: none;
  background: transparent;
  color: white;
  font: 500 14px/1.5 Pretendard, 'Apple SD Gothic Neo', sans-serif;
  padding: 10px 12px;
  cursor: pointer;
}
.intro-skip span { margin-left: 8px; }
.intro-skip:focus-visible { outline: 2px solid white; outline-offset: 4px; border-radius: 6px; }
@keyframes intro-drift {
  from { transform: translate(-51%, -49%) rotate(90deg) scale(1); }
  to { transform: translate(-48%, -52%) rotate(94deg) scale(1.06); }
}
@keyframes intro-light-drift {
  from { transform: translate(-4%, 2%); opacity: .65; }
  to { transform: translate(5%, -4%); opacity: 1; }
}
@keyframes intro-logo-reveal {
  0%, 6% { opacity: 0; transform: scale(.97); }
  32%, 72% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(1.015); }
}
@keyframes intro-depart {
  from { opacity: 1; }
  to { opacity: 0; }
}
@media (max-width: 700px) {
  .intro-logo { width: 86%; }
}
@media (prefers-reduced-motion: reduce) {
  .intro-texture, .intro-light, .intro-logo { animation: none; }
  .intro-splash { animation-duration: 150ms; animation-delay: 300ms; }
}
</style>
