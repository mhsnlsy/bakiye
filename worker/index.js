const MIDAS="https://uzmanpara.milliyet.com.tr/canli-borsa/?endex=xutum";
const FX="https://kur.doviz.com/";
const TLREF="https://www.borsaistanbul.com/endeksler/tlref";
const STOCKS=["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"];
const FXC=["USD","EUR","GBP"];
const H={"content-type":"application/json;charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"};

function num(v){let s=String(v??"").replace(/[^0-9,.-]/g,"").trim();if(!s)return null;if(s.includes(","))s=s.replace(/\./g,"").replace(",",".");let n=Number(s);return Number.isFinite(n)?n:null}
function text(h){return h.replace(/<script[\s\S]*?<\/script>/gi," ").replace(/<style[\s\S]*?<\/style>/gi," ").replace(/<[^>]+>/g," ").replace(/&nbsp;/gi," ").replace(/&amp;/gi,"&").replace(/\s+/g," ").trim()}
function cells(h){return [...h.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)].map(m=>[...m[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map(x=>text(x[1])).filter(Boolean)).filter(r=>r.length)}
function stock(h,s){
 const rows=cells(h);
 for(const r of rows){
   const i=r.findIndex(x=>x.trim().toUpperCase()===s);
   if(i>=0 && r[i+1]){const p=num(r[i+1]);if(p!=null)return p}
 }
 const t=text(h);
 const e=s.replace(/[.*+?^()|[\]\\]/g,"\\$&");
 const m=t.match(new RegExp("(?:^|\\s)"+e+"\\s*\\|\\s*([0-9]+(?:[.,][0-9]+)?)","i"));
 return m?num(m[1]):null;
}
function fx(h,c){
 const rows=cells(h);
 for(const r of rows){
   const i=r.findIndex(x=>x.toUpperCase().startsWith(c+" "));
   if(i>=0 && r[i+1]){const p=num(r[i+1]);if(p!=null)return p}
 }
 const t=text(h),m=t.match(new RegExp("(?:^|\\s)"+c+"(?:\\s+[^|]{0,50})?\\s*\\|\\s*([0-9]+(?:[.,][0-9]+)?)","i"));
 return m?num(m[1]):null;
}
function tl(h){let a=[],seen=new Set(),m,r=/(\\d{2}\\.\\d{2}\\.\\d{4})\\s+(?:\\|\\s*)?([0-9]{2,3}[.,]\\d{4})/g,t=text(h);while((m=r.exec(t))){let d=m[1].split(".").reverse().join("-");if(!seen.has(d)){seen.add(d);a.push({date:d,rate:num(m[2])/100})}}return a.sort((a,b)=>a.date.localeCompare(b.date))}
async function get(u){
 const r=await fetch(u,{headers:{"User-Agent":"Mozilla/5.0 (compatible; BakiyeWorker/1.0)","Accept":"text/html,application/xhtml+xml","Accept-Language":"tr-TR,tr;q=0.9"},signal:AbortSignal.timeout(12000)});
 if(!r.ok)throw Error(u+" HTTP "+r.status);
 return r.text();
}
async function read(env,k,path){let x=await env.BAKIYE_DATA.get(k);if(x)return JSON.parse(x);let r=await env.ASSETS.fetch(new Request("https://assets.local"+path));return r.ok?r.json():null}
async function put(env,k,v){await env.BAKIYE_DATA.put(k,JSON.stringify(v,null,2))}
async function quotes(env){
 const old=await read(env,"quotes.json","/data/quotes.json")||{quotes:{},fx:{}};
 const q={...old.quotes},f={...old.fx},missing=[],errors=[];
 const [mr,fr]=await Promise.allSettled([get(MIDAS),get(FX)]);
 if(mr.status==="fulfilled"){
   for(const s of STOCKS){const p=stock(mr.value,s);if(p!=null)q[s]=p;else missing.push(s)}
 }else errors.push("Midas: "+String(mr.reason?.message||mr.reason));
 if(fr.status==="fulfilled"){
   for(const c of FXC){const p=fx(fr.value,c);if(p!=null)f[c+"TRY"]=p;else missing.push(c+"TRY")}
 }else errors.push("Döviz.com: "+String(fr.reason?.message||fr.reason));
 const now=new Date().toISOString();
 const v={...old,source:"Uzmanpara Son fiyat (15 dk gecikmeli) + Döviz.com serbest piyasa",sourceUrl:MIDAS,fxSourceUrl:FX,asOf:now.slice(0,10),lastRefresh:now,quotes:q,fx:f,missing,errors,sourceStatus:{midas:mr.status,doviz:fr.status}};
 await put(env,"quotes.json",v);
 return v;
}
async function snapshot(env){
 let old=await read(env,"history.json","/data/history.json")||{version:1,frequency:"daily",startDate:"2026-11-16",retentionDays:365,snapshots:[]};
 let balance=await read(env,"balance.json","/data/balance.json")||{accounts:{}};
 let positions=await read(env,"positions.json","/data/positions.json")||[];
 let quotes=await read(env,"quotes.json","/data/quotes.json")||{quotes:{},fx:{}};
 let t={stocks:0,funds:0,try:0,cashFx:0,bankFx:0,gold:0,receivable:0};
 for(const p of positions){const v=Number(quotes.quotes?.[p.symbol]??p.snapshotPrice??0)*Number(p.qty||0);if(p.type==="fund")t.funds+=v;else t.stocks+=v}
 const a=balance.accounts||{};
 for(const x of Object.values(a)){
   const v=Number(x.value)||0;
   if(x.category==="try")t.try+=v;else if(x.category==="gold")t.gold+=v;else if(x.category==="receivable")t.receivable+=v;else if(x.category==="fx"){
     const isCash=x===a.doviz,rates=quotes.fx||{};
     for(const [code,qty] of Object.entries(x.currencies||{})){const rate=Number(rates[code+"TRY"]||0);if(rate){const amount=Number(qty||0)*rate;if(isCash)t.cashFx+=amount;else t.bankFx+=amount}}
   }
 }
 const total=t.stocks+t.funds+t.try+t.cashFx+t.bankFx+t.gold+t.receivable;
 const now=new Date(),date=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(now);
 const rows=(old.snapshots||[]).filter(x=>x.date!==date);rows.push({date,total,...t});
 const cutoffDate=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(new Date(now.getTime()-365*86400000));
 const kept=rows.filter(x=>{const weekday=new Date(x.date+"T12:00:00Z").getUTCDay();return weekday===0||x.date>=cutoffDate}).sort((a,b)=>a.date.localeCompare(b.date));
 const v={...old,version:1,frequency:"daily",startDate:old.startDate||date,retentionDays:365,updatedAt:now.toISOString(),snapshots:kept};
 await put(env,"history.json",v);return v;
}
async function tlref(env){
 let old=await read(env,"tlref.json","/data/tlref.json")||{historical:[],stopaj:.175,startDate:"2025-08-24"};
 let fresh=tl(await get(TLREF));if(!fresh.length)throw Error("TLREF ayrıştırılamadı");
 let map=new Map((old.historical||[]).map(x=>[x.date,Number(x.rate)]));for(const x of fresh)map.set(x.date,x.rate);
 let historical=[...map].sort(([a],[b])=>a.localeCompare(b)).map(([date,rate])=>({date,rate})),last=historical.at(-1),stopaj=Number(old.stopaj??.175);
 const v={...old,source:"Borsa İstanbul TLREF",sourceUrl:TLREF,asOf:last.date,grossAnnualRate:last.rate,stopaj,netAnnualRate:last.rate*(1-stopaj),historical,updatedAt:new Date().toISOString(),method:"Günlük net TLREF fırsat maliyeti; brüt TLREF üzerinden %17,5 stopaj düşülür ve günlük bileşiklenir."};
 await put(env,"tlref.json",v);return v;
}
function out(v,s=200){return new Response(JSON.stringify(v),{status:s,headers:H})}
export default{
 async fetch(req,env){const u=new URL(req.url);
  if(u.pathname==="/api/quotes"){const v=await read(env,"quotes.json","/data/quotes.json");return v?out(v):out({error:"quotes_not_ready"},503)}
  if(u.pathname==="/api/tlref"){const v=await read(env,"tlref.json","/data/tlref.json");return v?out(v):out({error:"tlref_not_ready"},503)}
  if(u.pathname==="/api/history"){const v=await read(env,"history.json","/data/history.json");return v?out(v):out({error:"history_not_ready"},503)}
  if(u.pathname==="/api/health")return out({ok:true,service:"bakiye",time:new Date().toISOString()});
  return env.ASSETS.fetch(req);
 },
 async scheduled(e,env,ctx){
   if(e.cron==="30 15 * * *")ctx.waitUntil((async()=>{await quotes(env);await tlref(env);await snapshot(env)})());
   else if(e.cron==="*/5 * * * *")ctx.waitUntil(quotes(env));
 }
};