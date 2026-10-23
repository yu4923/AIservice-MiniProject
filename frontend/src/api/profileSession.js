const KEY = 'youth-compass:survey-v1'
export const emptyProfile = () => ({age:24,region:'',statuses:[],interests:[],details:[],income:null,employment_status:null,household_size:null})
export function clearProfile(storage) { try { storage.removeItem(KEY) } catch {} }
export function saveProfile(storage, owner, profile) {
  if (!owner) return
  try { storage.setItem(KEY, JSON.stringify({owner,profile})) } catch {}
}
export function loadProfile(storage, owner) {
  try {
    const saved = JSON.parse(storage.getItem(KEY))
    if (!saved || saved.owner !== owner) { clearProfile(storage); return emptyProfile() }
    const p = saved.profile
    if (!p || !Number.isInteger(p.age) || p.age < 0 || p.age > 120 ||
        typeof p.region !== 'string' || p.region.length > 20 ||
        !['statuses','interests','details'].every(k => Array.isArray(p[k]) && p[k].length <= 13 && p[k].every(v => typeof v === 'string' && v.length <= 100)) ||
        !['income','employment_status'].every(k => p[k] === null || typeof p[k] === 'string' && p[k].length <= 200) ||
        !(p.household_size === null || Number.isInteger(p.household_size) && p.household_size >= 1 && p.household_size <= 30)) throw new Error('Invalid saved survey')
    return Object.fromEntries(Object.keys(emptyProfile()).map(k => [k,p[k]]))
  } catch { clearProfile(storage); return emptyProfile() }
}
