<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Brand from '../components/Brand.vue'
import ChatAttachments from '../components/ChatAttachments.vue'
import { emptyProfile, loadProfile, saveProfile, clearProfile } from '../api/profileSession'
import { demoMode, login, signup, ask, clearToken, searchPolicies, checkAuth, logoutSession } from '../api/youth'

const currentRoute = useRoute()
const router = useRouter()
const route = computed(() => currentRoute.path)
const go = (path) => router.push(path)
const user = ref(null)
const loginId=ref('')
const logoutError=ref('')
let authEpoch=0
onMounted(async()=>{
 const epoch=authEpoch
 try{const session=await checkAuth();if(epoch!==authEpoch||!session?.ok)return;user.value={id:session.id,nickname:session.id};restoreSurvey(session.id)}
 catch(e){if(epoch===authEpoch&&e.status===401){user.value=null;loginId.value=''}}
})
const username=ref(''), password=ref(''), showPassword=ref(false), error=ref(''), success=ref(''), busy=ref(false)
const isSignup=computed(()=>route.value==='/signup')
const authPage=computed(()=>['/login','/signup'].includes(route.value))
const surveyPage=computed(()=>route.value.startsWith('/survey'))
const step=computed(()=>Math.min(5,Math.max(1,Number(route.value.split('/')[2])||1)))
const regions=['서울','부산','대구','인천','광주','대전','울산','세종','경기','강원','충북','충남','전북','전남','경북','경남','제주']
const profile=ref(emptyProfile())
const householdInput=ref('')
const profileError=ref('')
function restoreSurvey(id){
 loginId.value=''
 try{profile.value=loadProfile(sessionStorage,id)}catch{profile.value=emptyProfile()}
 householdInput.value=profile.value.household_size===null?'':String(profile.value.household_size)
 loginId.value=id
}
watch(profile,value=>{try{saveProfile(sessionStorage,loginId.value,value)}catch{}},{deep:true,flush:'sync'})

const ageWheel=ref(null)
const ages=Array.from({length:121},(_,i)=>120-i)
function selectAge(age){profile.value.age=age;const wheel=ageWheel.value;if(wheel)wheel.scrollTo({top:(120-age)*wheel.clientHeight/3,behavior:'smooth'})}
function scrollAge(event){const wheel=event.target;profile.value.age=Math.max(0,Math.min(120,120-Math.round(wheel.scrollTop/(wheel.clientHeight/3))))}
watch([step,ageWheel],async()=>{await nextTick();const wheel=ageWheel.value;if(step.value===1&&wheel)wheel.scrollTop=(120-profile.value.age)*wheel.clientHeight/3},{flush:'post'})
const vReveal={mounted(el){
 if(matchMedia('(prefers-reduced-motion: reduce)').matches||!('IntersectionObserver' in window))return
 const category=el.matches('.category-row')
 const targets=category?[...el.querySelectorAll(':scope > div > strong,:scope > div > h2,:scope > div > p,:scope > img')]:el.matches('section')?[...el.children].filter(x=>!x.matches('.star,.sr-only')):[el]
 const animations=new Map()
 // The page transition already introduces initially visible content.
 targets.forEach(target=>{const rect=target.getBoundingClientRect();if(rect.top<innerHeight&&rect.bottom>0)animations.set(target,null)})
 const compact=matchMedia('(max-width:700px)').matches
 const observer=new IntersectionObserver(entries=>{for(const entry of entries){
  if(entry.isIntersecting&&!animations.has(entry.target)){
   const target=entry.target
   const illustration=target.matches('img:not(.star)')
   const direction=category?(el.matches(':nth-child(even)')?-1:1):1
   const distance=compact?26:64
   const x=category?(illustration?direction:-direction)*distance:0
   const from=illustration?`translate(${x}px, ${compact?24:44}px) scale(.92) rotate(${direction*1.8}deg)`:`translate(${x*.6}px, ${compact?24:42}px)`
   const order=category?illustration?2:target.matches('strong')?0:target.matches('h2')?1:2:target.matches('h1,h2')?0:illustration?2:1
   const animation=target.animate([
    {opacity:.08,transform:from,filter:illustration?'blur(2px)':'blur(1px)'},
    {opacity:1,transform:'translate(0,0) scale(1) rotate(0deg)',filter:'blur(0px)'}
   ],{duration:illustration?950:760,delay:order*70,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'})
   animations.set(entry.target,animation)
  }else if(!entry.isIntersecting&&Math.abs(entry.boundingClientRect.top)>80){animations.get(entry.target)?.cancel();animations.delete(entry.target)}
 }},{threshold:.12,rootMargin:'0px 0px -5% 0px'})
 targets.forEach(target=>observer.observe(target))
 el._revealCleanup=()=>{observer.disconnect();animations.forEach(animation=>animation?.cancel())}
},unmounted(el){el._revealCleanup?.()}}
const vOrbMotion={mounted(el){
 let visible=true
 const update=()=>el.classList.toggle('orb-running',visible&&!document.hidden)
 const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;update()})
 observer.observe(el);document.addEventListener('visibilitychange',update);update()
 el._orbCleanup=()=>{observer.disconnect();document.removeEventListener('visibilitychange',update)}
},unmounted(el){el._orbCleanup?.()}}
const titles=['현재 만 나이를 알려주세요','현재 어디에 거주하고 있나요?','현재 어떤 상황에 해당하나요?','어떤 지원이 가장 필요한가요?','어떤 도움이 필요한지 조금 더 알려주세요!']
const descriptions=['정책마다 지원 가능한 나이가 달라요.','주민등록상 거주 지역을 선택해 주세요.','나의 상황과 관련된 정책을 찾아드릴게요.\n해당 항목을 모두 체크해 주세요.','관심 있는 분야를 모두 선택해 주세요.','관심 있는 지원을 모두 선택해 주세요.\n아직 정하지 못했다면 건너뛰어도 괜찮아요.']
const statuses=[{id:'student',label:'재학 중',sub:'대학교'},{id:'employed',label:'재직 중',sub:'회사'},{id:'unemployed',label:'구직·취업\n준비 중'},{id:'self_employed',label:'자영업·사업\n운영 중'},{id:'freelance',label:'프리랜서\n아르바이트'},{id:'none',label:'해당 사항\n없음'}]
const interests=[{id:'employment',label:'취업 지원',icon:'802fe.svg'},{id:'housing',label:'주거 지원',icon:'43370.svg'},{id:'education',label:'교육 지원',icon:'d0fce.svg'},{id:'startup',label:'창업 지원',icon:'fa6c2.svg'},{id:'unknown',label:'아직\n모르겠어요'}]
const detailOptions=[{label:'취업 준비 비용',icon:'93ff2.svg'},{label:'면접 지원',icon:'cb119.svg'},{label:'일 경험·인턴',icon:'da826.svg'},{label:'직무 교육',icon:'ffae8.svg'}]
const categories=[{id:'employment',title:'취업 지원',number:'01',image:'6871f.png',description:'취업 준비에 필요한 비용부터 직무 경험까지,\n새로운 시작을 돕는 정책을 찾아보세요.'},{id:'housing',title:'주거 지원',number:'02',image:'f8359.png',description:'월세와 주거비 등, 안정적인 생활에\n도움이 되는 정책을 살펴보세요.'},{id:'education',title:'교육 지원',number:'03',image:'f44b3.png',description:'배우고 싶은 분야와 키우고 싶은 역량,\n나의 성장을 위한 교육 기회를 찾아보세요.'},{id:'startup',title:'창업 지원',number:'04',image:'fd6ab.png',description:'아이디어를 사업으로 이어가는 과정,\n창업 준비에 필요한 지원을 확인해 보세요.'}]
const examples=[['월세를 내고 있는데, 주거비 지원을 받을 수 있나요?','청년 대상 월세·주거비 지원정책을 찾아볼 수 있어요. 거주지역과 나이, 소득 등 조건에 따라 대상이 달라져요.'],['자격증 시험 응시료를 지원받을 수 있나요?','지원하는 시험과 신청 조건은 공고마다 달라요. 거주지역과 응시하려는 시험을 알려주세요.'],['이 정책을 신청하려면 어떤 서류가 필요한가요?','궁금한 정책을 선택해 주시면 공식 공고를 바탕으로 준비 서류와 제출 방법을 안내해 드릴게요.'],['취업 준비 중인데 어떤 지원을 찾아볼 수 있나요?','취업 준비 비용, 면접 지원, 직무교육, 일 경험 관련 정책을 찾아볼 수 있어요.']]
function start(){go(user.value?'/survey/1':'/login')}
function toggle(field,id,exclusive){const arr=profile.value[field];profile.value[field]=arr.includes(id)?arr.filter(x=>x!==id):id===exclusive?[id]:[...arr.filter(x=>x!==exclusive),id];if(field==='interests')profile.value.details=[]}
const stepValid=computed(()=>[Number.isInteger(Number(profile.value.age))&&Number(profile.value.age)>=0&&Number(profile.value.age)<=120,regions.includes(profile.value.region),profile.value.statuses.length>0,profile.value.interests.length>0,true][step.value-1])
async function submitAuth(){
 if(busy.value)return
 authEpoch++
 error.value='';success.value=''
 username.value=username.value.trim()
 if(!username.value||!password.value){error.value='아이디와 비밀번호를 입력해 주세요.';return}
 if(isSignup.value){
  if(!/^[a-z][a-z0-9]{4,19}$/.test(username.value)){error.value='아이디는 영문 소문자로 시작하는 영문·숫자 5~20자예요.';return}
  const p=password.value;const kinds=[/[a-z]/,/[A-Z]/,/[0-9]/,/[!@#$%^&*()_+=\-]/].filter(x=>x.test(p)).length
  if(p.length<8||p.length>64||!/^[a-zA-Z0-9!@#$%^&*()_+=\-]+$/.test(p)||kinds<2){error.value='비밀번호는 공백 없이 8~64자, 영문·숫자·특수문자 중 2종류 이상 입력해 주세요.';return}
 }
 busy.value=true
 try{if(isSignup.value){await signup(username.value,password.value);password.value='';go('/login');success.value=demoMode?'데모 가입 화면 확인 완료! 실제 계정은 생성되지 않았어요.':'가입이 완료됐어요. 로그인해 주세요.'}else{const data=await login(username.value,password.value);user.value=data.user||{nickname:username.value};restoreSurvey(username.value);try{sessionStorage.setItem('youth-compass:display-id',loginId.value)}catch{/* display name storage is optional */}password.value='';go('/home')}}catch(e){error.value=e.message}finally{busy.value=false}
}
function next(){if(!stepValid.value)return;if(step.value===5||step.value===4&&!profile.value.interests.includes('employment'))finish();else go('/survey/'+(step.value+1))}
const policies=ref([]),result=ref(null),question=ref(''),messages=ref([]),chatBusy=ref(false),searchBusy=ref(false),searchError=ref(''),chatError=ref(''),source=ref('web')
const demoPolicies=computed(()=>categories.filter(x=>!profile.value.interests.length||profile.value.interests.includes('unknown')||profile.value.interests.includes(x.id)).map(x=>({name:`${x.title} 정책 카드 예시`,policy_id:x.id,recommendation_reason:`선택하신 ${x.title} 관심 분야를 반영한 화면 예시입니다.`,benefit:'실제 지원 내용은 API 연결 후 표시됩니다.',application_period:{display:'공식 공고 확인 필요'},demo:true})))
const needsProfile=computed(()=>result.value?.status==='needs_profile'||result.value?.needs_profile===true)
async function submitExtraProfile(){
 profileError.value=''
 if(!profile.value.income?.trim()||!profile.value.employment_status?.trim()){profileError.value='검색을 계속하려면 소득과 취업 상태를 입력해 주세요.';return}
 const value=householdInput.value.trim()
 if(value!==''&&(!/^\d+$/.test(value)||Number(value)<1||Number(value)>30)){profileError.value='가구원 수는 1~30 사이의 정수로 입력해 주세요.';return}
 profile.value.household_size=value===''?null:Number(value)
 await search()
}
async function finish(){if(searchBusy.value)return;await go('/chat');await search()}
async function search(){if(searchBusy.value)return;searchError.value='';result.value=null;policies.value=[];searchBusy.value=true;try{const r=await searchPolicies(profile.value);result.value=r;policies.value=Array.isArray(r.policies)?r.policies:[]}catch(e){searchError.value=e.message;if(e.status===401){clearToken();user.value=null}}finally{searchBusy.value=false}}
async function sendQuestion(text){if(chatBusy.value)return;const q=(text||question.value).trim();if(!q)return;chatError.value='';if(q.length>1000){chatError.value='질문은 1000자 이하로 입력해 주세요.';return}question.value=q;chatBusy.value=true;try{const r=await ask(q,profile.value);messages.value.push({question:q,...r});question.value=''}catch(e){chatError.value=e.message;if(e.status===401){clearToken();user.value=null}}finally{chatBusy.value=false}}
const selectedPolicy=ref(null)
const voiceNotice=ref('')
function onChatKeydown(event){
 if(event.key!=='Enter'||event.shiftKey||event.isComposing||event.keyCode===229||event.repeat)return
 event.preventDefault()
 if(!chatBusy.value&&question.value.trim())sendQuestion()
}
const exampleRows=[[0,1,0,1],[3,2,3,2]]
const vMovingStrip={mounted(el){
 let visible=false
 const update=()=>el.classList.toggle('strip-running',visible&&!document.hidden)
 const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;update()})
 observer.observe(el);document.addEventListener('visibilitychange',update)
 el._stripCleanup=()=>{observer.disconnect();document.removeEventListener('visibilitychange',update)}
},unmounted(el){el._stripCleanup?.()}}
function sourceText(s){return typeof s==='string'?s:(s.title||s.document_id||'참고 자료')+(s.page?` · ${s.page}쪽`:'')}
function sourceUrl(s){const value=typeof s==='string'?s:s.url;try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:null}catch{return null}}
async function logout(){
 if(busy.value)return
 busy.value=true;logoutError.value='';authEpoch++
 try{await logoutSession();clearToken();user.value=null;loginId.value='';try{clearProfile(sessionStorage)}catch{};username.value='';password.value='';try{sessionStorage.removeItem('youth-compass:display-id')}catch{/* optional storage */}messages.value=[];policies.value=[];result.value=null;profile.value=emptyProfile();householdInput.value='';await go('/')}
 catch(e){logoutError.value=e.message}
 finally{busy.value=false}
}
function showHow(){if(currentRoute.path==='/home'&&currentRoute.hash==='#how'){document.getElementById('how')?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})}else router.push({path:'/home',hash:'#how'})}
watch(route,()=>{error.value='';showPassword.value=false})

</script>

<template>
 <div class="youth-shell">
 <p v-if="logoutError" class="logout-error" role="alert">로그아웃하지 못했어요. {{logoutError}} <button class="text-button" @click="logout">다시 시도</button></p>
 <a class="skip-link" href="#main">본문으로 바로가기</a>
 <main v-if="authPage" id="main" class="auth-page">
  <section class="auth-card">
   <button class="auth-close" type="button" aria-label="로그인 창 닫기" @click="go('/')"><svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true"><path d="M5 5L23 23M23 5L5 23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
   <div class="auth-art" data-node-id="16:473"><button class="back-home" aria-label="홈으로" @click="go('/home')"><img src="/figma/69102.svg" alt=""></button></div>
   <div class="auth-content"><button class="brand-button" @click="go('/home')"><img class="auth-wordmark" src="/figma/03dfe.svg" alt="YOUTH COMPASS"></button><form @submit.prevent="submitAuth" novalidate>
    <h1>{{isSignup?'Sign Up':'Login'}}</h1>
    <label for="username">아이디</label><input id="username" v-model="username" autocomplete="username" :maxlength="isSignup?20:100" :aria-invalid="!!error" :disabled="busy" required>
    <label for="password">비밀번호</label><div class="password-field"><input id="password" v-model="password" :type="showPassword?'text':'password'" :autocomplete="isSignup?'new-password':'current-password'" maxlength="64" :disabled="busy" :aria-describedby="error?'auth-error':undefined" required><button type="button" :aria-label="showPassword?'비밀번호 숨기기':'비밀번호 보기'" :aria-pressed="showPassword" @click="showPassword=!showPassword"><img src="/figma/9ae49.svg" alt=""></button></div>
    <p v-if="error" id="auth-error" class="error" role="alert">{{error}}</p><p v-if="success" class="success" role="status">{{success}}</p>
    <button class="auth-submit" :disabled="busy">{{busy?'처리 중…':isSignup?'가입하기':'로그인'}}</button>
    <p class="auth-switch"><template v-if="!isSignup">아직 계정이 없으신가요? <RouterLink to="/signup">회원가입</RouterLink></template><RouterLink v-else to="/login">로그인으로 돌아가기</RouterLink></p>
   </form></div>
  </section>
 </main>
 <template v-else>
  <header v-if="surveyPage||route==='/search'||route==='/chat'" class="app-header"><button class="brand-button" @click="go('/home')"><Brand white compact/></button><nav v-if="route==='/chat'" class="ai-header-nav"><button @click="go('/categories')">정책 분야</button><button @click="go('/chat')">AI 튜터와 대화하기</button><button @click="showHow()">이용 방법</button><button @click="logout">로그아웃</button></nav><button v-else-if="user" class="header-link" @click="logout">로그아웃</button></header>
  <main v-if="surveyPage" id="main" class="survey-page">
   <img class="survey-glow glow-one" src="/figma/f58fd.svg" alt=""><img class="survey-glow glow-two" src="/figma/f58fd.svg" alt="">
   <section class="survey-content"><span class="step-badge">STEP 0{{step}}</span><h1>{{titles[step-1]}} <small>{{step}} / 5</small></h1><p class="survey-description">{{descriptions[step-1]}}</p>
    <div v-if="step===1" class="age-picker age-picker-wheel"><span>만</span><div ref="ageWheel" class="age-wheel" role="spinbutton" aria-label="만 나이 · 위아래로 스크롤하거나 방향키로 선택" tabindex="0" :aria-valuenow="profile.age" :aria-valuemin="0" :aria-valuemax="120" @scroll="scrollAge" @keydown.up.prevent="selectAge(Math.min(120,profile.age+1))" @keydown.down.prevent="selectAge(Math.max(0,profile.age-1))" @keydown.home.prevent="selectAge(120)" @keydown.end.prevent="selectAge(0)"><button v-for="age in ages" :key="age" tabindex="-1" :class="{active:profile.age===age}" @click="selectAge(age)">{{age}}</button></div><span>세</span></div>
    <div v-else-if="step===2" class="region-fields region-single"><label for="region">지역</label><select id="region" v-model="profile.region" required><option disabled value="">거주지역을 선택해 주세요</option><option v-for="region in regions" :key="region" :value="region">{{region}}</option></select></div>
    <div v-else-if="step===3" class="choice-grid"><button v-for="item in statuses" :key="item.id" type="button" class="choice-card" :class="{selected:profile.statuses.includes(item.id)}" :aria-pressed="profile.statuses.includes(item.id)" @click="toggle('statuses',item.id,'none')"><small v-if="item.sub">{{item.sub}}</small><strong>{{item.label}}</strong></button></div>
    <div v-else-if="step===4" class="choice-grid interests-grid"><button v-for="item in interests" :key="item.id" class="choice-card" :class="{selected:profile.interests.includes(item.id)}" :aria-pressed="profile.interests.includes(item.id)" @click="toggle('interests',item.id,'unknown')"><img v-if="item.icon" :src="'/figma/'+item.icon" alt=""><strong>{{item.label}}</strong></button></div>
    <div v-else class="choice-grid detail-grid"><button v-for="item in detailOptions" :key="item.label" class="choice-card" :class="{selected:profile.details.includes(item.label)}" :aria-pressed="profile.details.includes(item.label)" @click="toggle('details',item.label)"><img v-if="item.icon" :src="'/figma/'+item.icon" alt=""><strong>{{item.label}}</strong></button></div>
   </section>
   <nav class="survey-navigation" aria-label="설문 단계"><button v-if="step>1" class="pill" @click="go('/survey/'+(step-1))"><span>←</span> 이전</button><button v-else class="text-button" @click="go('/home')">← 홈으로</button><div><button class="pill" :disabled="!stepValid" @click="next">{{step===5?'내 맞춤 정책 보기':'다음'}} <span>→</span></button><button v-if="step===5" class="skip-survey" @click="profile.details=[];finish()">건너뛰고 검색하기</button></div></nav>
  </main>
  <main v-else-if="route==='/chat'" id="main" class="ai-conversation" data-node-id="18:1111">
   <img class="ai-glow ai-glow-right" src="/figma/f58fd.svg" alt=""><img class="ai-glow ai-glow-left" src="/figma/f58fd.svg" alt="">
   <h1>안녕하세요 {{loginId||'청년'}}님, 환영합니다!</h1>
   <div v-orb-motion class="ai-orb" aria-hidden="true"><img class="orb-glow" src="/figma/94e57.svg" alt=""><div class="orb-texture"></div><img class="orb-ring-inner" src="/figma/ce02e.svg" alt=""><img class="orb-ring-outer" src="/figma/39a8d.svg" alt=""><span class="orb-star"><img src="/figma/glass-star.svg" alt=""></span></div>
   <form v-if="needsProfile" class="ai-extra-profile" @submit.prevent="submitExtraProfile">
    <h2>맞춤 검색을 위해 조금만 더 알려주세요</h2><p>소득과 취업 상태가 필요해요. 모르는 정보는 임의로 입력하지 말고 확인 후 작성해 주세요.</p>
    <label for="profile-income">소득 <span>(필수 · 최대 200자)</span></label><input id="profile-income" v-model="profile.income" type="text" maxlength="200" placeholder="예: 월 소득 0원" required :disabled="searchBusy">
    <label for="profile-employment">현재 취업 상태 <span>(필수)</span></label><select id="profile-employment" v-model="profile.employment_status" required :disabled="searchBusy"><option :value="null" disabled>선택해 주세요</option><option>미취업</option><option>재직</option><option>자영업</option><option>프리랜서</option><option>기타</option></select>
    <label for="profile-household">가구원 수 <span>(선택 · 본인 포함 1~30명)</span></label><input id="profile-household" v-model="householdInput" type="text" inputmode="numeric" maxlength="2" placeholder="미입력 시 보내지 않음" :disabled="searchBusy">
    <p v-if="profileError" class="error" role="alert">{{profileError}}</p><button class="pill" :disabled="searchBusy">{{searchBusy?'검색 요청 중…':'입력하고 검색하기'}}</button>
   </form>
   <section v-if="searchBusy||searchError||result" class="ai-messages" aria-live="polite"><p v-if="searchBusy" role="status">입력하신 조건으로 정책을 찾고 있어요…</p><p v-if="searchError" class="error" role="alert">{{searchError}} <button type="button" class="text-button" @click="search">다시 시도</button></p><article v-if="result?.answer"><p class="answer-text">{{result.answer}}</p><ul v-if="result.sources?.length" class="sources"><li v-for="(s,i) in result.sources" :key="i"><a v-if="sourceUrl(s)" :href="sourceUrl(s)" target="_blank" rel="noopener noreferrer">{{sourceText(s)}}</a><span v-else>{{sourceText(s)}}</span></li></ul></article><article v-for="(policy,i) in policies" :key="policy.policy_id||i"><h2>{{policy.name}}</h2><p>{{policy.recommendation_reason}}</p><p>{{policy.benefit}}</p></article><p v-if="result&&!needsProfile&&!result.answer&&!policies.length">검색 응답을 받았어요. 표시할 정책이 없거나 응답 형식 확인이 필요해요.</p></section>
   <section v-if="messages.length" class="ai-messages" aria-label="AI 대화 내역" aria-live="polite"><article v-for="(m,i) in messages" :key="i"><p class="user-question">{{m.question}}</p><p class="answer-text">{{m.answer}}</p><ul v-if="m.sources?.length" class="sources"><li v-for="(s,j) in m.sources" :key="j"><a v-if="sourceUrl(s)" :href="sourceUrl(s)" target="_blank" rel="noopener noreferrer">{{sourceText(s)}}</a><span v-else>{{sourceText(s)}}</span></li></ul></article></section>
   <form class="ai-composer" @submit.prevent="sendQuestion()"><label for="ai-question" class="sr-only">정책 질문</label><textarea id="ai-question" v-model="question" @keydown="onChatKeydown" placeholder="질문하거나 말하거나 파일을 보내세요." maxlength="1000" rows="2" :disabled="chatBusy"></textarea><div class="ai-composer-footer"><ChatAttachments class="ai-attachments" /><div class="ai-composer-actions"><button type="button" class="ai-mic" aria-label="음성 입력 안내" @click="voiceNotice='음성 대화는 백엔드의 STT·음성 API 연결 후 이용할 수 있어요.'"><img src="/figma/f1e12.svg" alt=""></button><button v-if="question.trim()" class="ai-send" type="submit" :disabled="chatBusy" :aria-label="chatBusy?'답변 작성 중':'질문 보내기'"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3.5 3.5L21 12L3.5 20.5L6.5 13L15 12L6.5 11L3.5 3.5Z" fill="currentColor"/></svg></button><button class="ai-talk" type="button" @click="voiceNotice='음성 대화는 백엔드의 STT·음성 API 연결 후 이용할 수 있어요.'">Youth Compass Ai와 말하기 <img src="/figma/220e0.svg" alt=""></button></div></div><p v-if="voiceNotice" class="ai-notice" role="status">{{voiceNotice}}</p><p v-if="chatError" class="error" role="alert">{{chatError}}</p></form>
  </main>
  <main v-else-if="route==='/search'" id="main" class="results-page">
   <template v-if="route==='/search'">
   <div class="results-heading"><span class="step-badge">YOUR COMPASS</span><h1>{{user?.nickname||'청년'}}님을 위한 정책 후보</h1><p>내 상황에 맞는 지원, 근거와 함께 살펴보세요.</p><div class="profile-chips"><span>만 {{profile.age}}세</span><span>{{profile.region}}</span><span v-for="i in interests.filter(x=>profile.interests.includes(x.id))" :key="i.id">{{i.label}}</span><button @click="go('/survey/1')">조건 수정 ↗</button></div></div>
   <p v-if="demoMode" class="demo-banner">현재 데모 화면입니다. 아래 카드는 실제 정책 검색이 아닌 가상 예시예요.</p>
   <div class="source-control"><label>검색 자료 <select v-model="source"><option value="web">웹 정책 자료</option><option value="pdf">PDF 정책 자료</option></select></label><button class="text-button" :disabled="searchBusy" @click="search">다시 찾기 ↻</button></div>
   <p v-if="searchBusy" class="loading" role="status">관련 정책과 근거를 찾고 있어요…</p><p v-if="searchError" class="error" role="alert">{{searchError}} <button @click="search">다시 시도</button><a v-if="!user" href="/login">로그인하기</a></p>
   <div class="policy-grid"><article v-for="p in policies" :key="p.policy_id||p.name" class="policy-card"><span class="step-badge">{{p.demo?'가상 예시':'정책 후보'}}</span><h2>{{p.name}}</h2><p>{{p.recommendation_reason}}</p><div class="policy-benefit">{{p.benefit}}</div><small>{{p.application_period?.display||'신청 기간 확인 필요'}}</small><button class="outline-button" @click="selectedPolicy=p">상세보기 <span>↗</span></button></article></div>
   <section v-if="result" class="answer-panel"><h2>찾은 정책을 정리했어요</h2><p class="answer-text">{{result.answer}}</p><ul class="sources"><li v-for="(s,i) in result.sources||[]" :key="i"><a v-if="sourceUrl(s)" :href="sourceUrl(s)" target="_blank" rel="noopener noreferrer">{{sourceText(s)}} ↗</a><span v-else>{{sourceText(s)}}</span></li></ul><p v-if="!policies.length&&!result.sources?.length">확인 가능한 정책 근거가 없어요. 조건을 바꾸거나 다른 질문을 입력해 주세요.</p></section>
   </template>
   <div v-if="route==='/chat'" class="results-heading"><h1>나에게 맞는 정책, AI와 함께 찾아보세요</h1><p>설문에서 선택한 조건을 바탕으로 질문해 보세요.</p><button class="text-button" @click="go('/survey/1')">설문 조건 수정하기 →</button><p v-if="demoMode" class="demo-banner">프론트엔드 체험 화면입니다. 실제 AI 응답은 백엔드 연결 후 제공돼요.</p></div>
   <section class="chat-panel"><img src="/figma/52188.png" alt="" class="chat-robot"><span class="step-badge">ASK AI</span><h2>궁금한 정책, 더 물어보세요.</h2><p>입력한 조건과 정책 자료를 바탕으로 답변해 드려요.</p><div class="suggested-questions"><button v-for="q in examples.slice(0,2)" :key="q[0]" @click="question=q[0]">{{q[0]}}</button></div><div v-for="(m,i) in messages" :key="i" class="chat-message"><p class="user-question">{{m.question}}</p><p class="answer-text">{{m.answer}}</p><ul class="sources"><li v-for="(s,j) in m.sources||[]" :key="j"><a v-if="sourceUrl(s)" :href="sourceUrl(s)" target="_blank" rel="noopener noreferrer">{{sourceText(s)}} ↗</a><span v-else>{{sourceText(s)}}</span></li></ul><p v-if="m.needs_review||m.handoff" class="muted">세부 조건은 공식 공고 및 담당기관에서 확인해 주세요.</p></div><p v-if="chatBusy" role="status" class="loading">근거를 확인하며 답변을 작성하고 있어요…</p><p v-if="chatError" role="alert" class="error">{{chatError}}</p><form class="chat-input" @submit.prevent="sendQuestion()"><textarea v-model="question" aria-label="정책에 대한 질문" placeholder="정책에 대해 궁금한 점을 입력해 주세요" maxlength="1000" rows="2"></textarea><button class="pill" :disabled="chatBusy||!question.trim()">질문하기 ↑</button></form><p class="muted">음성 입력은 STT API 연결 후 제공할 예정이에요.</p></section>
   <p class="disclaimer">검색 결과는 정책 탐색을 돕기 위한 안내예요. 지원 자격과 신청 가능 여부는 공식 공고 및 담당기관에서 최종 확인해 주세요.</p>
  </main>
  <main v-else id="main" class="landing">
   <section class="hero"><nav class="site-nav"><button class="home-nav-button" @click="go('/home')"><img src="/figma/0170c.svg" alt="" width="15.2" height="14.2">HOME</button><div><button @click="go('/categories')">정책 분야</button><button @click="go('/chat')">AI 튜터와 대화하기</button><button @click="showHow()">이용 방법</button><button v-if="!user" @click="go('/login')">로그인</button><button v-else @click="start">내 맞춤 정책</button></div></nav><img class="hero-logo" src="/figma/a7989.svg" alt="YOUTH COMPASS"><p>청년들을 위한 맞춤형 정책 검색 서비스</p><button class="hero-start" @click="start">내 맞춤 정책 찾기</button></section>
   <template v-if="route==='/categories'">
    <section v-reveal class="category-intro"><h1>정책 분야</h1><div class="vertical-dots"><img src="/figma/c667a.svg" alt=""><img src="/figma/30e60.svg" alt=""><img src="/figma/144ad.svg" alt=""></div><h2>지금 나에게 필요한 지원은 무엇인가요?<br>관심 있는 분야부터 살펴보세요.</h2></section>
    <section class="category-list"><article v-reveal v-for="c in categories" :key="c.id" class="category-row"><div><strong class="category-number">{{c.number}}</strong><h2>{{c.title}}</h2><p>{{c.description}}</p></div><img :src="'/figma/'+c.image" :alt="c.title+' 일러스트'"></article><button class="pill" @click="start">나에게 맞는 정책 확인하기 →</button></section>
   </template>
   <template v-else>
    <section v-reveal class="landing-section first-section"><h1>나에게 맞는 청년정책, 헤매지 말고 찾아보세요.</h1><div class="vertical-dots"><img src="/figma/c667a.svg" alt=""><img src="/figma/30e60.svg" alt=""><img src="/figma/144ad.svg" alt=""></div><p>취업부터 주거, 교육, 창업까지<br>간단한 질문에 답하고 나와 관련된 지원정책을 확인해 보세요.</p><img class="landing-illustration approval" src="/figma/a897d.png" alt="정책 검색을 나타내는 상자와 엄지손가락"><button class="pill" @click="start">내 맞춤 정책 찾기 →</button><img class="star star-left" src="/figma/41de5.svg" alt=""><img class="star star-right" src="/figma/41de5.svg" alt=""></section>
    <section v-reveal id="how" class="landing-section ai-section"><h2>공고를 읽다가 궁금해졌다면, AI에게 물어보세요!</h2><div class="vertical-dots"><img src="/figma/c667a.svg" alt=""><img src="/figma/30e60.svg" alt=""><img src="/figma/144ad.svg" alt=""></div><p>지원 대상부터 신청 방법, 준비 서류까지.<br>찾은 정책 자료를 바탕으로 답변하고 근거와 출처를 함께 안내해요.</p><img class="landing-illustration robot" src="/figma/52188.png" alt="노트북을 사용하는 AI 로봇"><img class="star star-left" src="/figma/41de5.svg" alt=""></section>
    <section class="example-section"><span class="sr-only">AI 상담 예시</span><div class="example-strips"><div v-for="(row,rowIndex) in exampleRows" :key="rowIndex" v-moving-strip class="example-strip" tabindex="0" role="region" :aria-label="`AI 상담 예시 ${rowIndex+1}번째 줄 · 왼쪽으로 흐르는 카드`"><div class="example-track"><div v-for="cycle in 2" :key="cycle" class="example-cycle" :aria-hidden="cycle===2"><article v-for="(i,cardIndex) in row" :key="cardIndex" :aria-hidden="cycle===2||cardIndex>=2"><img :src="'/figma/'+['e22b6.svg','b26c7.svg','7b7da.svg','e395f.svg'][i]" alt=""><div><h3>“{{examples[i][0]}}”</h3><p>{{examples[i][1]}}</p></div></article></div></div></div></div><button class="pill" @click="start">AI와 내 맞춤 정책 찾기 →</button><small>위 대화는 서비스 이용을 설명하는 예시입니다.</small></section>
   </template>
   <footer>Youth Compass는 정책 탐색을 돕는 서비스입니다.<br>지원 자격과 신청 가능 여부는 공식 공고 및 담당기관에서 최종 확인해 주세요.</footer>
  </main>
 </template>
 <div v-if="selectedPolicy" class="modal-backdrop" @click.self="selectedPolicy=null"><section class="policy-modal" role="dialog" aria-modal="true" aria-labelledby="policy-title"><button class="modal-close" aria-label="닫기" @click="selectedPolicy=null">×</button><span class="step-badge">{{selectedPolicy.demo?'가상 예시':'정책 상세'}}</span><h2 id="policy-title">{{selectedPolicy.name}}</h2><p>{{selectedPolicy.recommendation_reason}}</p><h3>지원 내용</h3><p>{{selectedPolicy.benefit}}</p><h3>지원 대상</h3><p>{{selectedPolicy.eligibility_summary||'공식 공고에서 세부 조건을 확인해 주세요.'}}</p><h3>신청 방법</h3><p>{{selectedPolicy.application_method||'서버 연결 후 실제 신청 정보를 확인할 수 있어요.'}}</p><button class="pill" @click="question=selectedPolicy.name+'의 신청 방법과 준비 서류를 알려주세요.';selectedPolicy=null">이 정책에 대해 질문하기 →</button></section></div>
 </div>
</template>

<style scoped src="../assets/youth.css"></style>
<style scoped>
.region-single { padding-top: 90px; }
.region-single select { margin-top: 28px; }
.logout-error { margin:0; padding:14px 24px; background:#fff1f3; color:#a61b36; position:relative; z-index:10; }
.hero-start { position:relative; flex-shrink:0; margin:24px auto 28px; padding:15px 34px; min-height:54px; min-width:234px; border:1px solid #ffffff60; border-radius:40px; background:#ffffff12; color:white; font-size:20px; font-weight:600; line-height:1.3; transition:background 180ms ease; }
.hero-start:hover { background:#ffffff26; }
.hero>p { margin-bottom:0; }
.home-nav-button { display:inline-flex; align-items:center; gap:5px; }
.home-nav-button img { display:block; flex-shrink:0; object-fit:contain; }
.auth-card { position:relative; }
.auth-close { position:absolute; top:24px; right:30px; width:40px; height:40px; display:grid; place-items:center; background:none; color:#777; padding:6px; z-index:2; }
.auth-wordmark { display:block; width:296px; max-width:100%; height:auto; }
.password-field button { top:50%; transform:translateY(-50%); display:grid; place-items:center; padding:0; }
.password-field img { display:block; width:16px; height:13.6926px; object-fit:contain; flex-shrink:0; }
.category-list { width:100%; max-width:none; margin-inline:0; background:none; isolation:isolate; }
.category-row { max-width:1200px; margin-inline:auto; position:relative; }
.category-row::before { content:''; position:absolute; z-index:-1; pointer-events:none; width:100vw; height:150%; left:50%; top:-25%; transform:translateX(-50%); background:radial-gradient(ellipse at 0% 50%,#e6d3fa 0%,#f4ecfc 28%,transparent 68%); }
.category-row:nth-child(even)::before { background:radial-gradient(ellipse at 100% 50%,#e6d3fa 0%,#f4ecfc 28%,transparent 68%); }
.survey-page { min-height: calc(100svh - 73px); min-height: calc(100dvh - 73px); }
.glow-two { top: auto; bottom: -888px; }
.choice-card img { filter: brightness(0); }
.choice-card.selected img { filter: brightness(0) invert(1); }
.category-row { grid-template-columns: minmax(0,1fr) minmax(0,1fr); }
.category-row>div,.example-grid article>div { min-width:0; }
.category-row p { white-space:pre-line; overflow-wrap:normal; word-break:keep-all; line-height:1.7; font-size:clamp(16px,1.74vw,25px); margin:0; }
.category-row h2 { margin-top:32px; margin-bottom:48px; }
.category-row>img { min-width:0; max-width:100%; object-fit:contain; }
.example-grid { grid-template-columns:repeat(2,minmax(0,1fr)); padding-inline:clamp(24px,5vw,72px); }
.example-grid article:nth-child(n+3) { transform:none; }
.example-grid h3,.example-grid p { overflow-wrap:anywhere; word-break:keep-all; }
.star { object-fit:contain; }
.star-right { transform:rotate(180deg); }
.ai-conversation { position:relative; isolation:isolate; overflow:hidden; min-height:calc(100dvh - 73px); display:flex; flex-direction:column; align-items:center; padding:clamp(90px,12vh,184px) 24px 48px; }
.ai-nav { position:absolute; top:-53px; right:36px; display:flex; gap:48px; z-index:4; }
.ai-nav button { background:none; color:white; font-size:16px; }
.ai-header-nav { display:flex; gap:48px; }
.ai-header-nav button { color:white; background:none; font-size:16px; }
.ai-conversation h1 { font-size:clamp(26px,2.92vw,42px); text-align:center; margin:0 0 100px; line-height:1.35; }
.ai-glow { position:absolute; width:2017px; height:2017px; max-width:none; z-index:-1; pointer-events:none; }
.ai-glow-right { top:-888px; left:calc(100% - 771px); }
.ai-glow-left { bottom:-1200px; left:-1192px; }
.ai-orb { width:184.21px; height:184.21px; position:relative; flex:none; margin-bottom:80px; }
.ai-orb img { position:absolute; max-width:none; }
.orb-glow { width:351px; height:351px; left:-83px; top:-83px; }
.orb-texture { position:absolute; width:157.431px; height:157.431px; top:13.8px; left:13.8px; background:url('/figma/994a3.png') center/cover; mask:url('/figma/ad20e.svg') center/contain no-repeat; transform:rotate(90deg); }
.orb-ring-inner { width:172.038px; height:172.038px; left:6.49px; top:6.49px; }
.orb-ring-outer { width:184.21px; height:184.21px; inset:0; }
.orb-ring-inner { animation:orb-breathe-inner 4s ease-in-out infinite; animation-play-state:paused; transform-origin:center; }
.orb-ring-outer { animation:orb-breathe-outer 4s ease-in-out .35s infinite; animation-play-state:paused; transform-origin:center; }
.orb-glow { filter:saturate(1.25); animation:orb-glow-breathe 4s ease-in-out infinite; animation-play-state:paused; }
.orb-running .orb-ring-inner,.orb-running .orb-ring-outer,.orb-running .orb-glow { animation-play-state:running; }
@keyframes orb-breathe-inner { 0%,100% { transform:scale(1); opacity:1; } 50% { transform:scale(1.045); opacity:.72; } }
@keyframes orb-breathe-outer { 0%,100% { transform:scale(1); opacity:1; } 50% { transform:scale(1.10); opacity:.52; } }
@keyframes orb-glow-breathe { 0%,100% { opacity:.85; transform:scale(.98); } 50% { opacity:1; transform:scale(1.06); } }
@media(prefers-reduced-motion:reduce) { .orb-ring-inner,.orb-ring-outer,.orb-glow { animation:none; } }
.orb-star { position:absolute; width:86.5461px; height:82.3103px; left:48.23px; top:47px; }
.orb-star::before { content:''; position:absolute; inset:0; background:#ffffff0a; backdrop-filter:blur(3px) saturate(1.25); -webkit-backdrop-filter:blur(3px) saturate(1.25); clip-path:polygon(50% 0%,61.8% 38.2%,100% 38.2%,69.1% 61.8%,80.9% 100%,50% 76.4%,19.1% 100%,30.9% 61.8%,0% 38.2%,38.2% 38.2%); }
.orb-star img { inset:0; width:86.5461px; height:82.3103px; }
.ai-composer { position:relative; margin-top:auto; width:min(893px,100%); padding:24px 22px 20px; background:#8739ee33; border-radius:25px; }
.ai-composer textarea { width:100%; resize:vertical; min-height:40px; border:0; background:none; color:#3d207d; font-size:24px; line-height:1.5; padding:0 8px; }
.ai-composer textarea::placeholder { color:#3d207d; opacity:1; }
.ai-composer-actions { display:flex; align-items:center; justify-content:flex-end; gap:8px; }
.ai-composer-footer { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; flex-wrap:wrap; }
.ai-attachments { flex:1; min-width:80px; }
.ai-composer-actions { margin-left:auto; flex-wrap:wrap; }
.ai-mic { display:grid; place-items:center; padding:0; background:none; width:38px; height:38px; flex-shrink:0; line-height:0; }
.ai-mic img { position:static; display:block; width:34px; height:34px; object-fit:contain; }
.ai-talk { display:flex; align-items:center; justify-content:center; gap:8px; border-radius:29px; background:var(--purple); color:white; padding:0 18px; font-size:16px; height:38px; min-height:38px; line-height:1; }
.ai-talk img { position:static; display:block; width:18px; height:18px; object-fit:contain; flex-shrink:0; }
.ai-send { display:grid; place-items:center; width:56px; height:38px; border-radius:24px; background:var(--purple); color:white; padding:0; line-height:0; flex-shrink:0; order:1; }
.ai-send svg { position:static; display:block; width:24px; height:24px; margin:0; }
.ai-send:hover:not(:disabled) { background:#7425dc; }
.ai-messages { width:min(893px,100%); margin-bottom:32px; }
.ai-extra-profile { width:min(893px,100%); margin:0 0 32px; padding:28px; border-radius:20px; background:#f4edff; }
.ai-extra-profile h2 { margin:0 0 12px; font-size:24px; }
.ai-extra-profile>p { font-size:14px; color:#563875; }
.ai-extra-profile label { display:block; margin:20px 0 8px; font-weight:600; }
.ai-extra-profile label span { font-size:13px; font-weight:400; color:#64427d; }
.ai-extra-profile input,.ai-extra-profile select { width:100%; min-height:46px; padding:10px 14px; border:1px solid #bfa6dd; border-radius:9px; background:white; color:#1d2630; }
.ai-extra-profile>.pill { margin-top:24px; font-size:16px; min-height:48px; }
.ai-messages article { background:#ffffffb3; border-radius:16px; padding:20px; margin-bottom:16px; }
.ai-notice { font-size:13px; color:#563089; margin:12px 0 0; }
.example-strips { display:grid; gap:28px; container-type:inline-size; mask-image:linear-gradient(to right,#0008 0%,#000 4%,#000 96%,#0008 100%); }
.example-strip { --strip-gap:32px; --strip-card:42cqw; --strip-offset:0px; overflow:hidden; padding-block:4px; }
.example-strip:nth-child(2) { --strip-offset:calc(var(--strip-card)*.9); }
.example-track { display:flex; width:max-content; transform:translateX(calc(-1*var(--strip-offset))); animation:example-flow-left 58s linear infinite; animation-play-state:paused; }
.example-cycle { display:flex; gap:var(--strip-gap); padding-right:var(--strip-gap); }
.strip-running .example-track { animation-play-state:running; }
.example-strip:hover .example-track,.example-strip:focus-within .example-track { animation-play-state:paused; }
@keyframes example-flow-left { from { transform:translateX(calc(-1*var(--strip-offset))); } to { transform:translateX(calc(-50% - var(--strip-offset))); } }
@media(prefers-reduced-motion:reduce) {
 .example-strip { overflow-x:auto; }
 .example-track { animation:none; transform:none; }
 .example-cycle[aria-hidden="true"] { display:none; }
}
.example-strip::-webkit-scrollbar { display:none; }
.example-strip article { flex:0 0 var(--strip-card); width:var(--strip-card); min-height:180px; display:flex; align-items:center; gap:24px; padding:30px 34px; border-radius:20px; background:var(--purple); color:white; text-align:left; }
.example-strip article>img { flex:none; width:44px; height:44px; object-fit:contain; }
.example-strip article>div { min-width:0; }
.example-strip h3 { font-size:18px; line-height:1.5; margin:0 0 12px; word-break:keep-all; }
.example-strip p { font-size:14px; line-height:1.65; margin:0; word-break:keep-all; }
.example-cycle article { background:var(--purple); }
.age-picker-wheel { height:auto; padding-top:24px; overflow:visible; align-items:center; }
.age-picker-wheel>span { padding-top:0; }
.age-wheel { --age-row:150px; height:calc(var(--age-row)*3); width:300px; overflow-y:auto; overscroll-behavior:contain; scroll-snap-type:y mandatory; scrollbar-width:none; padding-block:var(--age-row); mask-image:linear-gradient(transparent,#000 24%,#000 76%,transparent); }
.age-wheel::-webkit-scrollbar { display:none; }
.age-wheel button { display:block; width:100%; height:var(--age-row); padding:0; background:none; font-size:150px; line-height:1; font-weight:750; letter-spacing:-.04em; color:#e6d6fb; scroll-snap-align:center; scroll-snap-stop:always; }
.age-wheel button.active { color:var(--purple); }
@media (max-width: 700px) {
  .hero:has(.hero-start) { height:350px; }
  .hero-start { min-width:185px; min-height:46px; padding:12px 24px; margin-top:24px; font-size:15px; }
  .auth-close { top:22px; right:22px; background:#ffffffdd; border-radius:50%; }
  .auth-wordmark { width:220px; }
  .ai-conversation { min-height:calc(100dvh - 62px); padding:70px 20px 28px; }
  .ai-conversation h1 { font-size:25px; margin-bottom:70px; }
  .ai-orb { margin-bottom:65px; }
  .ai-composer { padding:20px 14px 14px; border-radius:20px; }
  .ai-composer textarea { font-size:16px; }
  .ai-talk { font-size:12px; padding:0 12px; }
  .ai-nav { right:18px; top:-42px; gap:18px; }
  .ai-nav button { font-size:12px; }
  .ai-header-nav { gap:12px; }
  .ai-header-nav button { font-size:11px; }
  .app-header:has(.ai-header-nav) { height:auto; min-height:62px; flex-wrap:wrap; gap:16px; }
  .category-row { gap:24px; grid-template-columns:minmax(0,1fr); padding-block:45px; }
  .category-row:nth-child(even)>div,.category-row:nth-child(even)>img { order:initial; text-align:left; }
  .category-row>img { width:min(100%,350px); justify-self:center; }
  .category-row p { font-size:16px; white-space:pre-line; }
  .category-row h2 { margin-top:18px; margin-bottom:26px; }
  .example-grid { grid-template-columns:minmax(0,1fr); padding-inline:20px; }
  .example-strip { --strip-gap:16px; --strip-card:84cqw; }
  .example-track { animation-duration:52s; }
  .example-strip article { min-height:190px; padding:24px; gap:16px; }
  .example-strip article>img { width:32px; height:32px; }
  .example-strip h3 { font-size:15px; }
  .example-strip p { font-size:13px; }
  .age-picker-wheel { height:auto; gap:12px; padding-top:0; }
  .age-wheel { --age-row:112px; width:210px; }
  .age-wheel button { font-size:112px; }
  .age-picker-wheel>span { padding-top:0; }
  .survey-page { min-height: calc(100svh - 62px); min-height: calc(100dvh - 62px); }
  .region-single { padding-top: 50px; }
}
</style>
