export const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'
const authBase = import.meta.env.VITE_AUTH_API_URL || 'http://localhost:8080'
const aiBase = import.meta.env.VITE_AI_API_URL || import.meta.env.VITE_RAG_API_URL || 'http://localhost:8001'
const searchBase = import.meta.env.VITE_SEARCH_API_URL || 'http://localhost:8002'
// Compatibility with existing UI callers; authentication is now an HttpOnly cookie.
// Ending the server session requires the backend logout API, not JS cookie deletion.
export const clearToken = () => {}
const serverErrorMessage = '서버에 일시적인 문제가 있습니다. 잠시 후 다시 시도해 주세요.'
async function request(base, path, body, method='POST', timeoutMs=45000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(base.replace(/\/$/, '') + path, {
      method, credentials: 'include', signal: controller.signal,
      headers: method==='GET'?{}:{ 'Content-Type': 'application/json' },
      ...(method==='GET'?{}:{body:JSON.stringify(body)})
    })
    if (response.status >= 500) {
      const error = new Error(serverErrorMessage)
      error.status = response.status
      throw error
    }
    const data = await response.json().catch(() => {
      if (response.ok) throw new Error(serverErrorMessage)
      return {}
    })
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error(serverErrorMessage)
    if (!response.ok||data.ok===false) {
      const messages = {400:'아이디와 비밀번호를 확인해 주세요.',401:'아이디 또는 비밀번호가 올바르지 않거나 로그인이 만료됐어요.',403:'접근 권한이 없어요.',409:'이미 사용 중인 아이디예요. 다른 아이디를 입력해 주세요.',422:'입력한 내용을 다시 확인해 주세요.',429:'요청이 많아요. 잠시 후 다시 시도해 주세요.',503:'서버가 준비 중이에요. 잠시 후 다시 시도해 주세요.'}
      const codes={ID_EXISTS:messages[409],INVALID_CREDENTIALS:messages[401],VALIDATION_ERROR:messages[400]}
      const error = new Error(codes[data.error?.code]||messages[response.status]||data.error?.message||'요청을 처리하지 못했어요. 다시 시도해 주세요.')
      error.status = response.status
      throw error
    }
    return data
  } catch (error) {
    if (error.name === 'AbortError' || error instanceof TypeError) throw new Error(serverErrorMessage)
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
export function buildSearchProfile(profile) {
  if(!profile||typeof profile!=='object'||Array.isArray(profile))throw new Error('설문 정보를 먼저 입력해 주세요.')
  if(!Number.isInteger(profile.age)||profile.age<12||profile.age>49)throw new Error('만 나이는 12~49 사이의 정수로 입력해 주세요.')
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
// Display labels only; preserve the server status and eligibility decision.
// Components can opt in to this helper when their badge rendering is updated.
export function getPolicyStatusLabel(status) {
  switch (status) {
    case 'candidate':
      return '정책 후보'
    case 'needs_review':
      return '추가 확인 필요'
    case 'not_eligible':
      return '조건 불일치'
    default:
      return '상태 확인 필요'
  }
}

// Preserve the complete server response and add aliases used by existing views.
// Benefit, application period and other absent facts must come from the server.
function adaptSearchResponse(data) {
  if (!Array.isArray(data.policies)) return data
  return {
    ...data,
    policies: data.policies.map(policy => ({
      ...policy,
      name: policy.policy_name ?? policy.name,
      recommendation_reason: policy.reason ?? policy.recommendation_reason,
    })),
  }
}
export async function searchPolicies(profile) {
  // Search integration is independent of the login/chat preview mode.
  // Only send fields actually collected by the survey; never invent income data.
  const payload = buildSearchProfile(profile)
  const data = await request(searchBase, '/search', { profile: payload }, 'POST', 150000)
  return adaptSearchResponse(data)
}
export function buildConversationContext(messages = [], recommendation = null) {
  const completed = messages.filter(m => !m.pending && !m.error && typeof m.question === 'string' && typeof m.answer === 'string' && m.question.trim() && m.answer.trim())
  const turns = recommendation?.answer ? [recommendation, ...completed] : completed
  return turns.slice(-4).map(turn => ({
    question: String(turn.question || turn.prompt || '설문 기반 정책 추천').slice(0, 1000),
    answer: turn.answer.slice(0, 4000),
  }))
}

export async function ask(question, profile, policyContext = [], history = []) {
  if(typeof question!=='string')throw new Error('질문을 입력해 주세요.')
  const value=question.trim()
  if(value.length<2||value.length>1000)throw new Error('질문은 앞뒤 공백을 제외하고 2~1,000자로 입력해 주세요.')
  if (!profile || !profile.region || !profile.statuses?.length || !profile.interests?.length) throw new Error('맞춤 답변을 위해 먼저 설문을 완료해 주세요.')
  const payload = buildSearchProfile(profile)
  const policy_context = [...new Set(policyContext.filter(name => typeof name === 'string' && name.trim() && name.length <= 200).map(name => name.trim()))].slice(0, 5)
  const data = await request(searchBase, '/search', { prompt: value, profile: payload, policy_context, history: buildConversationContext(history) }, 'POST', 150000)
  return adaptSearchResponse(data)
}
