import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
const source=await readFile(new URL('./chatHistory.js',import.meta.url),'utf8')
const {loadChat,saveChat}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
const memory=()=>{const map=new Map();return {getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v)}}
test('restores same account and isolates other accounts',()=>{
 const storage=memory(),data={messages:[{question:'질문',answer:'답변'}],result:{answer:'정책'},profile:{region:'울산'}}
 assert.equal(saveChat(storage,'user-a',data),true)
 assert.equal(loadChat(storage,'user-a').result.answer,'정책')
 assert.equal(loadChat(storage,'user-b'),null)
 saveChat(storage,'user-b',{messages:[],result:null})
 assert.equal(loadChat(storage,'user-a').messages.length,1)
})
test('caps messages and supports resetting current chat',()=>{
 const storage=memory()
 saveChat(storage,'a',{messages:Array.from({length:40},()=>({question:'q',answer:'a'}))})
 assert.equal(loadChat(storage,'a').messages.length,30)
 saveChat(storage,'a',{messages:[],result:null})
 assert.equal(loadChat(storage,'a').messages.length,0)
})
test('unavailable storage does not crash',()=>{
 const storage={getItem(){throw Error()},setItem(){throw Error()}}
 assert.equal(loadChat(storage,'a'),null)
 assert.equal(saveChat(storage,'a',{messages:[]}),false)
})
