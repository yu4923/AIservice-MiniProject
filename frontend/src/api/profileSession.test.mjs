import {test} from 'node:test'
import assert from 'node:assert/strict'
import {emptyProfile,loadProfile,saveProfile,clearProfile} from './profileSession.js'
const storage=()=>{const m=new Map();return {getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)}}
test('survey survives reload for same account including optional fields',()=>{const s=storage();const p={...emptyProfile(),age:29,region:'울산',statuses:['unemployed'],interests:['housing'],income:'미입력',household_size:2};saveProfile(s,'alice',p);assert.deepEqual(loadProfile(s,'alice'),p)})
test('partial survey survives reload',()=>{const s=storage();const p={...emptyProfile(),region:'서울'};saveProfile(s,'alice',p);assert.deepEqual(loadProfile(s,'alice'),p)})
test('different account cannot inherit survey',()=>{const s=storage();saveProfile(s,'alice',{...emptyProfile(),region:'울산'});assert.deepEqual(loadProfile(s,'bob'),emptyProfile());assert.deepEqual(loadProfile(s,'alice'),emptyProfile())})
test('logout clears saved survey',()=>{const s=storage();saveProfile(s,'alice',{...emptyProfile(),region:'울산'});clearProfile(s);assert.deepEqual(loadProfile(s,'alice'),emptyProfile())})
test('invalid saved JSON safely resets',()=>{const s=storage();s.setItem('youth-compass:survey-v1','{bad');assert.deepEqual(loadProfile(s,'alice'),emptyProfile())})
test('storage unavailable does not crash',()=>{const s={getItem(){throw Error()},setItem(){throw Error()},removeItem(){throw Error()}};saveProfile(s,'alice',emptyProfile());assert.deepEqual(loadProfile(s,'alice'),emptyProfile());clearProfile(s)})
