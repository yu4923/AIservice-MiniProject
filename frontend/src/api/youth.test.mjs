import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import { test } from 'node:test'

const source = readFileSync(new URL('./youth.js', import.meta.url), 'utf8')
  .replaceAll('import.meta.env', "({ VITE_DEMO_MODE: 'false' })")
const api = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
const profile = () => ({ age: 25, region: '울산', statuses: ['unemployed'], interests: ['employment', 'housing'], details: ['면접 지원', '월세·주거비'] })

test('profile-only request uses cookies and excludes question, JWT and arbitrary fields', async () => {
  let sent
  globalThis.fetch = async (url, options) => {
    sent = { url, ...options }
    return { ok: true, json: async () => ({ status: 'needs_profile' }) }
  }
  const response = await api.recommendPolicies({ ...profile(), id: 99, JWT: 'must-not-send' })
  assert.equal(response.status, 'needs_profile')
  assert.equal(sent.url, 'http://localhost:8002/recommend')
  assert.equal(sent.method, 'POST')
  assert.equal(sent.credentials, 'include')
  assert.deepEqual(sent.headers, { 'Content-Type': 'application/json' })
  const body = JSON.parse(sent.body)
  assert.deepEqual(Object.keys(body), ['profile'])
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

test('chat sends only the trimmed question to recommend with cookies', async () => {
  globalThis.fetch=async(url,options)=>{
    assert.equal(url,'http://localhost:8002/recommend')
    assert.equal(options.method,'POST')
    assert.equal(options.credentials,'include')
    assert.deepEqual(JSON.parse(options.body),{question:'면접 지원 조건이 궁금해요'})
    assert.deepEqual(options.headers,{'Content-Type':'application/json'})
    return {ok:true,json:async()=>({answer:'서버 응답'})}
  }
  assert.equal((await api.ask('  면접 지원 조건이 궁금해요  ')).answer,'서버 응답')
})

test('chat rejects blank, short, non-string and oversized questions', async () => {
  for(const value of ['', '  ', '가', null, '가'.repeat(1001)])await assert.rejects(api.ask(value))
})

test('normalizes optional text and keeps exact detail spacing', () => {
  const result = api.buildRecommendProfile({ ...profile(), income: ' 월 소득 0원 ', employment_status: ' 미취업 ', household_size: 1 })
  assert.equal(result.income, '월 소득 0원')
  assert.equal(result.employment_status, '미취업')
  assert.equal(result.household_size, 1)
  assert.deepEqual(api.buildRecommendProfile({ ...profile(), interests: ['education'], details: ['직무교육'] }).details, ['직무교육'])
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
]) test(`rejects ${label}`, () => assert.throws(() => api.buildRecommendProfile({ ...profile(), ...values })))
