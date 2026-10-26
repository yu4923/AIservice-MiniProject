const key = owner => `youth-compass:chat-v1:${encodeURIComponent(owner)}`
export function loadChat(storage, owner) {
 if(!owner)return null
 try {
  const raw=storage.getItem(key(owner))
  if(!raw||raw.length>2000000)return null
  const saved=JSON.parse(raw)
  if(saved.owner!==owner||!Array.isArray(saved.messages)||saved.messages.length>30||saved.messages.some(m=>typeof m.question!=='string'||typeof m.answer!=='string'))return null
  return saved
 }catch{return null}
}
export function saveChat(storage, owner, data) {
 if(!owner)return false
 try {
  const raw=JSON.stringify({...data,messages:data.messages.slice(-30),owner})
  if(raw.length>2000000)return false
  storage.setItem(key(owner),raw)
  return true
 }catch{return false}
}
