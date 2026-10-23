export const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'
const authBase = import.meta.env.VITE_AUTH_API_URL || 'http://localhost:8080'
const aiBase = import.meta.env.VITE_AI_API_URL || import.meta.env.VITE_RAG_API_URL || 'http://localhost:8001'
const recommendBase = import.meta.env.VITE_RECOMMEND_API_URL || 'http://localhost:8002'
// Compatibility with existing UI callers; authentication is now an HttpOnly cookie.
// Ending the server session requires the backend logout API, not JS cookie deletion.
export const clearToken = () => {}
async function request(base, path, body, method='POST') {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 45000)
  try {
    const response = await fetch(base.replace(/\/$/, '') + path, {
      method, credentials: 'include', signal: controller.signal,
      headers: method==='GET'?{}:{ 'Content-Type': 'application/json' },
      ...(method==='GET'?{}:{body:JSON.stringify(body)})
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok||data.ok===false) {
      const messages = {400:'아이디와 비밀번호를 확인해 주세요.',401:'아이디 또는 비밀번호가 올바르지 않거나 로그인이 만료됐어요.',403:'접근 권한이 없어요.',409:'이미 사용 중인 아이디예요. 다른 아이디를 입력해 주세요.',422:'입력한 내용을 다시 확인해 주세요.',429:'요청이 많아요. 잠시 후 다시 시도해 주세요.',503:'서버가 준비 중이에요. 잠시 후 다시 시도해 주세요.'}
      const codes={ID_EXISTS:messages[409],INVALID_CREDENTIALS:messages[401],VALIDATION_ERROR:messages[400]}
      const error = new Error(codes[data.error?.code]||messages[response.status]||data.error?.message||'요청을 처리하지 못했어요. 다시 시도해 주세요.')
      error.status = response.status
      throw error
    }
    return data
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('응답 시간이 길어지고 있어요. 잠시 후 다시 시도해 주세요.')
    if (error instanceof TypeError) throw new Error('서버에 연결하지 못했어요. 서버 주소와 실행 상태를 확인해 주세요.')
    throw error
  } finally { clearTimeout(timer) }
}
export async function login(id, password) {
  if (demoMode) return {user:{id,nickname:id},demo:true}
  const data = await request(authBase, import.meta.env.VITE_LOGIN_PATH || '/api/login', {id:id.trim(),password})
  return data
}
export async function signup(id,password) {
  if (demoMode) return {created:true,demo:true}
  return request(authBase, import.meta.env.VITE_SIGNUP_PATH || '/api/signup', {id:id.trim(),password})
}
export async function checkAuth(){
  if(demoMode)return null
  return request(authBase,import.meta.env.VITE_AUTH_CHECK_PATH||'/api/auth/check',undefined,'GET')
}
export async function logoutSession(){
  if(demoMode)return {ok:true,demo:true}
  return request(authBase,import.meta.env.VITE_LOGOUT_PATH||'/api/logout',{})
}
const regions=['서울','부산','대구','인천','광주','대전','울산','세종','경기','강원','충북','충남','전북','전남','경북','경남','제주']
const statusValues=['student','employed','unemployed','self_employed','freelance','none']
const detailValues={employment:['취업 준비 비용','면접 지원','일 경험·인턴','직무 교육'],housing:['월세·주거비','임대주택','주거 상담'],education:['시험 응시료','직무교육','학습비'],startup:['사업화 자금','교육·멘토링','창업 공간'],unknown:[]}
function validateArray(value,min,max,allowed,label){
  if(!Array.isArray(value)||value.length<min||value.length>max||new Set(value).size!==value.length||value.some(item=>typeof item!=='string'||!allowed.includes(item)))throw new Error(`${label} 선택값을 확인해 주세요.`)
}
export function buildRecommendProfile(profile) {
  if(!profile||typeof profile!=='object'||Array.isArray(profile))throw new Error('설문 정보를 먼저 입력해 주세요.')
  if(!Number.isInteger(profile.age)||profile.age<0||profile.age>120)throw new Error('만 나이는 0~120 사이의 정수로 입력해 주세요.')
  if(!regions.includes(profile.region))throw new Error('거주 지역을 선택해 주세요.')
  validateArray(profile.statuses,1,5,statusValues,'현재 상황')
  if(profile.statuses.includes('none')&&profile.statuses.length!==1)throw new Error('해당 없음은 단독으로 선택해 주세요.')
  validateArray(profile.interests,1,4,Object.keys(detailValues),'관심 분야')
  if(profile.interests.includes('unknown')&&profile.interests.length!==1)throw new Error('아직 모르겠어요는 단독으로 선택해 주세요.')
  const details=profile.details??[]
  validateArray(details,0,13,profile.interests.flatMap(key=>detailValues[key]),'세부 지원')
  const optionalText=(value,max,label)=>{
    if(value===undefined||value===null)return null
    if(typeof value!=='string'||value.length>max)throw new Error(`${label}은 ${max}자 이하의 문자열로 입력해 주세요.`)
    return value.trim()||null
  }
  const income=optionalText(profile.income,200,'소득')
  const employment_status=optionalText(profile.employment_status,100,'취업 상태')
  const household_size=profile.household_size??null
  if(household_size!==null&&(!Number.isInteger(household_size)||household_size<1||household_size>30))throw new Error('가구원 수는 1~30 사이의 정수로 입력해 주세요.')
  return {age:profile.age,region:profile.region,statuses:[...profile.statuses],interests:[...profile.interests],details:[...details],income,employment_status,household_size}
}
export async function recommendPolicies(profile) {
  // Recommendation integration is independent of the login/chat preview mode.
  // Only send fields actually collected by the survey; never invent income data.
  const payload = buildRecommendProfile(profile)
  return request(recommendBase, '/recommend', { question: '설문에서 선택한 조건과 관심 분야에 맞는 청년 정책을 추천해 주세요.', profile: payload })
}
export async function ask(question, profile) {
  if(typeof question!=='string')throw new Error('질문을 입력해 주세요.')
  const value=question.trim()
  if(value.length<2||value.length>1000)throw new Error('질문은 앞뒤 공백을 제외하고 2~1,000자로 입력해 주세요.')
  if (!profile || !profile.region || !profile.statuses?.length || !profile.interests?.length) throw new Error('맞춤 답변을 위해 먼저 설문을 완료해 주세요.')
  const payload = buildRecommendProfile(profile)
  return request(recommendBase, '/recommend', { question: value, profile: payload })
}
