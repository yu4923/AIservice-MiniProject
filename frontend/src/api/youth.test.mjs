import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import { test } from 'node:test'

const source = readFileSync(new URL('./youth.js', import.meta.url), 'utf8')
  .replaceAll('import.meta.env', "({ VITE_DEMO_MODE: 'false' })")
const api = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
const profile = () => ({ age: 25, region: '울산', statuses: ['unemployed'], interests: ['employment', 'housing'], details: ['면접 지원', '월세·주거비'] })

test('recommendation and chat preserve server fields while supplying existing card fields', async () => {
  const response = {
    question: '월세 지원을 알려주세요', answer: '확인이 필요한 정책입니다.',
    prompt: '월세 지원을 알려주세요', response: '확인이 필요한 정책입니다.',
    status: 'answered', sources: ['policy.pdf'],
    citations: [{ evidence_id: 'V1', source: 'policy.pdf', title: '주거 정책', page: 3, origin: 'vector_db' }],
    policies: ['candidate', 'needs_review', 'not_eligible'].map(status => ({
      policy_name: '청년 월세 지원', reason: '소득 조건 확인 필요', status,
      missing_fields: ['income'], evidence_ids: ['V1'], extra_policy_field: 'preserve',
      benefit: '월 최대 20만원 지원', application_period: { display: '2026. 3. 1. ~ 2026. 3. 31.' },
    })),
    missing_fields: ['income'], follow_up_question: '소득을 알려주세요.',
    needs_review: true, handoff: false, api_status: 'not_used',
    node_path: ['collect_profile', 'generate'], latency_ms: 1234,
    extra_response_field: { value: 'preserve' },
  }
  const original = structuredClone(response)
  globalThis.fetch = async () => ({ ok: true, json: async () => response })
  for (const result of [await api.searchPolicies(profile()), await api.ask(response.question, profile())]) {
    for (const [key, value] of Object.entries(original)) {
      if (key !== 'policies') assert.deepEqual(result[key], value)
    }
    result.policies.forEach((policy, index) => {
      for (const [key, value] of Object.entries(original.policies[index])) assert.deepEqual(policy[key], value)
      assert.equal(policy.name, '청년 월세 지원')
      assert.equal(policy.recommendation_reason, '소득 조건 확인 필요')
      assert.equal(`${policy.name}의 신청 방법과 준비 서류를 알려주세요.`, '청년 월세 지원의 신청 방법과 준비 서류를 알려주세요.')
      assert.equal(policy.benefit, '월 최대 20만원 지원')
      assert.equal(policy.application_period.display, '2026. 3. 1. ~ 2026. 3. 31.')
      for (const key of ['eligibility_summary', 'application_method', 'policy_id']) {
        assert.equal(key in policy, false)
      }
    })
  }
  assert.deepEqual(response, original)
})

test('existing card-format fields and any supplied policy details are retained', async () => {
  const policy = {
    name: '기존 정책명', recommendation_reason: '기존 사유', policy_id: 'policy-1',
    benefit: '공식 자료의 지원 내용', application_period: { display: '공고 확인' },
    eligibility_summary: '공식 대상 조건', application_method: '공식 신청 방법',
  }
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ policies: [policy] }) })
  assert.deepEqual((await api.searchPolicies(profile())).policies, [policy])
})

test('empty recommendation results retain status and follow-up information', async () => {
  for (const policies of [[], undefined]) {
    const response = { status: 'insufficient', answer: '근거 부족', follow_up_question: '조건 확인', ...(policies ? { policies } : {}) }
    globalThis.fetch = async () => ({ ok: true, json: async () => response })
    assert.deepEqual(await api.searchPolicies(profile()), response)
  }
})

test('survey recommendation sends question and validated profile with cookies', async () => {
  let sent
  globalThis.fetch = async (url, options) => {
    sent = { url, ...options }
    return { ok: true, json: async () => ({ status: 'needs_profile' }) }
  }
  const response = await api.searchPolicies({ ...profile(), id: 99, JWT: 'must-not-send' })
  assert.equal(response.status, 'needs_profile')
  assert.equal(sent.url, 'http://localhost:8002/search')
  assert.equal(sent.method, 'POST')
  assert.equal(sent.credentials, 'include')
  assert.deepEqual(sent.headers, { 'Content-Type': 'application/json' })
  const body = JSON.parse(sent.body)
  assert.deepEqual(Object.keys(body), ['profile'])
  assert.equal(body.question, undefined)
  assert.equal(body.profile.income, null)
  assert.equal(body.profile.employment_status, null)
  assert.equal(body.profile.household_size, null)
  assert.equal('JWT' in body.profile, false)
  assert.equal('id' in body.profile, false)
})

test('cookie login accepts a successful response without a JWT', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url,'http://localhost:8080/api/login')
    assert.deepEqual(JSON.parse(options.body),{id:'testuser',password:'Test1234!'})
    assert.equal(options.credentials, 'include')
    return { ok: true, json: async () => ({ok:true,redirect:'/home',expires_in:3600}) }
  }
  const response = await api.login('testuser', 'Test1234!')
  assert.equal(response.ok,true)
})

test('signup sends id/password and preserves 201 response',async()=>{
 globalThis.fetch=async(url,options)=>{
  assert.equal(url,'http://localhost:8080/api/signup')
  assert.deepEqual(JSON.parse(options.body),{id:'testuser',password:'Test1234!'})
  assert.equal(options.credentials,'include')
  return {ok:true,status:201,json:async()=>({ok:true,id:'testuser',no:'1'})}
 }
 assert.equal((await api.signup('testuser','Test1234!')).id,'testuser')
})

test('auth check uses GET and cookies without sending credentials in body',async()=>{
 globalThis.fetch=async(url,options)=>{
  assert.equal(url,'http://localhost:8080/api/auth/check')
  assert.equal(options.method,'GET')
  assert.equal(options.credentials,'include')
  assert.equal('body' in options,false)
  return {ok:true,json:async()=>({ok:true,id:'testuser',no:'1',via:'jwt'})}
 }
 assert.equal((await api.checkAuth()).id,'testuser')
})

test('logout sends POST with cookies to clear the backend session',async()=>{
 globalThis.fetch=async(url,options)=>{
  assert.equal(url,'http://localhost:8080/api/logout')
  assert.equal(options.method,'POST')
  assert.equal(options.credentials,'include')
  assert.deepEqual(JSON.parse(options.body),{})
  return {ok:true,json:async()=>({ok:true})}
 }
 assert.equal((await api.logoutSession()).ok,true)
})

test('duplicate id and invalid login are reported as Korean errors',async()=>{
 for(const [code,status,pattern] of [['ID_EXISTS',409,/이미 사용 중/],['INVALID_CREDENTIALS',401,/아이디 또는 비밀번호/]]){
  globalThis.fetch=async()=>({ok:false,status,json:async()=>({ok:false,error:{code,message:'backend message'}})})
  await assert.rejects(api.login('testuser','Test1234!'),pattern)
 }
})

test('chat sends trimmed question and actual survey profile with cookies', async () => {
  globalThis.fetch=async(url,options)=>{
    assert.equal(url,'http://localhost:8002/search')
    assert.equal(options.method,'POST')
    assert.equal(options.credentials,'include')
    assert.deepEqual(JSON.parse(options.body),{prompt:'면접 지원 조건이 궁금해요',profile:api.buildSearchProfile(profile()),policy_context:['서울 청년수당']})
    assert.deepEqual(options.headers,{'Content-Type':'application/json'})
    return {ok:true,json:async()=>({answer:'서버 응답'})}
  }
  assert.equal((await api.ask('  면접 지원 조건이 궁금해요  ',profile(),['서울 청년수당'])).answer,'서버 응답')
})

test('chat rejects blank, short, non-string and oversized questions', async () => {
  for(const value of ['', '  ', '가', null, '가'.repeat(1001)])await assert.rejects(api.ask(value))
})

test('normalizes optional text and keeps exact detail spacing', () => {
  const result = api.buildSearchProfile({ ...profile(), income: ' 월 소득 0원 ', employment_status: ' 미취업 ', household_size: 1 })
  assert.equal(result.income, '월 소득 0원')
  assert.equal(result.employment_status, '미취업')
  assert.equal(result.household_size, 1)
  assert.deepEqual(api.buildSearchProfile({ ...profile(), interests: ['education'], details: ['직무교육'] }).details, ['직무교육'])
})

for (const [label, values] of [
  ['string age', { age: '25' }],
  ['fractional age', { age: 25.5 }],
  ['age over 120', { age: 121 }],
  ['unknown region', { region: '울산광역시' }],
  ['empty statuses', { statuses: [] }],
  ['exclusive none', { statuses: ['none', 'student'] }],
  ['duplicate statuses', { statuses: ['student', 'student'] }],
  ['exclusive unknown', { interests: ['unknown', 'housing'] }],
  ['duplicate interests', { interests: ['housing', 'housing'] }],
  ['detail in another category', { interests: ['housing'], details: ['면접 지원'] }],
  ['detail spacing', { interests: ['education'], details: ['직무 교육'] }],
  ['unknown detail', { interests: ['unknown'], details: ['면접 지원'] }],
  ['duplicate details', { details: ['면접 지원', '면접 지원'] }],
  ['too long income', { income: 'a'.repeat(201) }],
  ['too long employment', { employment_status: 'a'.repeat(101) }],
  ['string household', { household_size: '1' }],
  ['zero household', { household_size: 0 }],
  ['household over 30', { household_size: 31 }],
]) test(`rejects ${label}`, () => assert.throws(() => api.buildSearchProfile({ ...profile(), ...values })))

test('chat requires a completed profile before making a request', async () => {
  let called = false
  globalThis.fetch = async () => { called = true; throw new Error('unexpected request') }
  for (const value of [undefined, {...profile(), region:''}, {...profile(), statuses:[]}]) {
    await assert.rejects(api.ask('월세 지원을 알려주세요', value), /설문/)
  }
  assert.equal(called, false)
})
