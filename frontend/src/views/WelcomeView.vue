<script setup>
import { useRouter } from 'vue-router'
import logoSvg from '../../public/figma/23425.svg?raw'
const router = useRouter()
// Rotate only the rectangle about its own centre in the original SVG coordinates.
const welcomeLogo = matchMedia('(prefers-reduced-motion: reduce)').matches ? logoSvg : logoSvg.replace(
  /<path id="Rectangle 498"[^>]*\/>/,
  path => `<g><animateTransform attributeName="transform" type="rotate" values="0 595.6395 47.3723;-18 595.6395 47.3723;378 595.6395 47.3723;354 595.6395 47.3723;360 595.6395 47.3723" keyTimes="0;0.16;0.77;0.9;1" calcMode="spline" keySplines=".4 0 .6 1;.6 0 .15 1;.2 0 .4 1;.2 0 .3 1" begin="0.3s" dur="2.3s" repeatCount="1" fill="freeze"/>${path}</g>`
)
</script>

<template>
  <main class="welcome" id="main">
    <div class="welcome-background" aria-hidden="true"></div>
    <div class="welcome-shade" aria-hidden="true"></div>
    <section class="welcome-content" aria-label="청년정책 나침반">
      <h1 aria-label="YOUTH COMPASS"><span class="welcome-logo" aria-hidden="true" v-html="welcomeLogo"></span></h1>
      <p>청년들을 위한 맞춤형 정책 검색 서비스</p>
      <button type="button" @click="router.push('/login')">
        시작하기 <img src="/figma/2058e.svg" alt="" aria-hidden="true">
      </button>
    </section>
  </main>
</template>

<style scoped>
.welcome {
  min-height: 100svh;
  display: grid;
  place-items: center;
  background: #44218b;
  color: white;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  font-family: Pretendard, 'Apple SD Gothic Neo', Inter, sans-serif;
}
.welcome-background {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 150vmax;
  height: 150vmax;
  background: url('/figma/994a3.png') center / cover no-repeat;
  transform: translate(-50%, -50%) rotate(90deg);
  z-index: -2;
  animation: welcome-drift 12s ease-in-out infinite alternate;
}
.welcome-shade { position: absolute; inset: 0; background: #0000004d; z-index: -1; animation: welcome-darken 900ms ease 3s both; }
.welcome-content { width: 100%; text-align: center; padding: 0 24px; transform: translateY(5.5svh); }
h1 { margin: 0 auto; width: min(76.2vw, 1061px); line-height: 1; animation: welcome-logo-settle 900ms cubic-bezier(.16,1,.3,1) 3s both; }
h1 img { width: 100%; height: auto; display: block; }
.welcome-logo { display:block; }
.welcome-logo :deep(svg) { display:block; width:100%; height:auto; overflow:visible; }
p { margin: 54px 0 0; font-size: clamp(17px, 2.5vw, 36px); font-weight: 600; line-height: 1.45; word-break: keep-all; animation: welcome-arrive 850ms cubic-bezier(.16,1,.3,1) 3.5s both; }
button {
  display: inline-flex;
  gap: 14px;
  justify-content: center;
  align-items: center;
  border: 1px solid #ffffff24;
  border-radius: 40px;
  min-width: 234px;
  min-height: 70px;
  margin-top: 60px;
  padding: 18px 40px;
  color: white;
  background: #ffffff1a;
  font: 600 24px/1.3 Pretendard, 'Apple SD Gothic Neo', sans-serif;
  cursor: pointer;
  transition: background 180ms ease;
  animation: welcome-arrive 700ms cubic-bezier(.16,1,.3,1) 4.3s both;
}
button img { width: 18px; height: 32px; transform: rotate(90deg); }
button:hover { background: #ffffff2e; }
button:focus-visible { outline: 3px solid white; outline-offset: 6px; }
@media(max-width: 700px) {
  h1 { width: 87vw; }
  p { margin-top: 28px; }
  button { margin-top: 38px; min-height: 52px; min-width: 175px; font-size: 17px; padding: 12px 25px; }
  button img { width: 13px; height: 24px; }
}
@keyframes welcome-drift {
  from { transform: translate(-51%,-49%) rotate(90deg) scale(1); }
  to { transform: translate(-49%,-51%) rotate(93deg) scale(1.04); }
}
@keyframes welcome-darken { from { opacity:0; } to { opacity:1; } }
@keyframes welcome-logo-settle { from { transform:translateY(100px); } to { transform:translateY(0); } }
@keyframes welcome-arrive {
  from { opacity:0; visibility:hidden; transform:translateY(24px); }
  to { opacity:1; visibility:visible; transform:translateY(0); }
}
@media(prefers-reduced-motion:reduce) {
  .welcome-background,.welcome-shade,h1,p,button { animation:none; }
  .welcome-logo :deep(path[id="Rectangle 498"]) { animation:none; }
  button { transition:none; }
}
</style>
