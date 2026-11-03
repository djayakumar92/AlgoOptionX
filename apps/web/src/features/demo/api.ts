import {apiFetch} from "../../shared/lib/http";
export async function demoApi<T>(path:string,body?:unknown):Promise<T> {
 const response=await apiFetch(`/api/demo/${path}`,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 let data:unknown;
 try { data=await response.json(); } catch {throw new Error('The demo returned an unreadable response. Retry after checking the local server.');}
 if(!response.ok) {
  const value=data as {detail?:unknown;error?:unknown};
  throw new Error(typeof value.detail==='string'?value.detail:typeof value.error==='string'?value.error:'The demo request was rejected. Check your inputs and retry.');
 }
 return data as T;
}
export const money=(n:number)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(n/100);
export const number=(n:number,digits=2)=>new Intl.NumberFormat('en-IN',{maximumFractionDigits:digits}).format(n);
export const clock=(iso:string)=>new Date(iso).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
export const strategyName=(value:string)=>({'bull-put':'Bull put credit spread','bear-call':'Bear call credit spread','iron-condor':'Iron condor'}[value]||value);
