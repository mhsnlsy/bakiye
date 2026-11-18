const FX="https://kur.doviz.com/";
const TLREF="https://www.borsaistanbul.com/endeksler/tlref";
const TLREF_FALLBACK="https://borsa.doviz.com/endeksler/tlref-turk-lirasi-gecelik-referans-faiz-orani/tarihsel-veri";
const STOCKS=["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"];
const SOURCE_SYMBOL={"ZPLIB.F":"ZPLIB"};
const FXC=["USD","EUR","GBP"];
const H={"content-type":"application/json;charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"};

function num(v){let s=String(v??"").replace(/[^0-9,.-]/g,"").trim();if(!s)return null;if(s.includes(","))s=s.replace(/\./g,"").replace(",",".");let n=Number(s);return Number.isFinite(n)?n:null}
function text(h){return h.replace(/<script[\s\S]*?<\/script>/gi," ").replace(/<style[\s\S]*?<\/style>/gi," ").replace(/<[^>]+>/g," ").replace(/&nbsp;/gi," ").replace(/&/gi,"&").replace(/\s+/g," ").trim()}
function cells(h){return [...h.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)].map(m=>[...m[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].map(x=>text(x[1])).filter(Boolean)).filter(r=>r.length)}
function stockQuote(h,s){
 const rows=cells(h);
 for(const r of rows){
   if(r.length>=8 && /^\d{2}:\d{2}:\d{2}$/.test(r[r.length-1].trim())){
     const price=num(r[0]);
     if(price!=null&&price>0)return {price,time:r[r.length-1].trim()};
   }
 }
 const t=text(h);
 const m=t.match(/Son\s+Fark\s+Değişim\s+Alış\s+Satış\s+Taban\s+Tavan\s+Saat\s+([0-9]+(?:[.,][0-9]+)?)\s+[-+0-9.,%]+\s+[-+0-9.,%]+\s+[-+0-9.,%]+\s+[-+0-9.,%]+\s+[-+0-9.,%]+\s+[-+0-9.,%]+\s+(\d{2}:\d{2}:\d{2})/i);
 if(m){const p=num(m[1]);if(p!=null&&p>0)return {price:p,time:m[2]}}
 for(const re of [/\bSon\b\s*[:：]\s*([0-9]+(?:[.,][0-9]+)?)/i,/\bSon Fiyat\b\s*[:：]\s*([0-9]+(?:[.,][0-9]+)?)/i]){
   const x=t.match(re);if(x){const p=num(x[1]);if(p!=null&&p>0)return {price:p,time:(t.match(/\b(\d{2}:\d{2}:\d{2})\b/)||[])[1]||null}}
 }
 return {price:null,time:null};
}
function fx(h,c){const rows=cells(h),target=String(c).trim().toUpperCase();for(const r of rows){const i=r.findIndex(x=>x.trim().toUpperCase().startsWith(target+" "));if(i>=0){for(let j=i+1;j<r.length;j++){const p=num(r[j]);if(p!=null)return p}}}const t=text(h),m=t.match(new RegExp("\\b"+target+"\\s+[^0-9]{1,80}?([0-9]+(?:[.,][0-9]+)?)","i"));return m?num(m[1]):null}
function tl(h){let a=[],seen=new Set(),m,r=/(\d{2}\.\d{2}\.\d{4})\s+(?:\|\s*)?([0-9]{2,3}[.,]\d{4})/g,t=text(h);while((m=r.exec(t))){let d=m[1].split(".").reverse().join("-");if(!seen.has(d)){seen.add(d);a.push({date:d,rate:num(m[2])/100})}}return a.sort((a,b)=>a.date.localeCompare(b.date))}
async function get(u,retries=2){const bust=(u.includes("?")?"&":"?")+"_ts="+Date.now();const headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"tr-TR,tr;q=0.9,en;q=0.8","Cache-Control":"no-cache","Pragma":"no-cache"};let lastErr;for(let i=0;i<=retries;i++){try{const r=await fetch(u+bust,{cf:{cacheTtl:0,cacheEverything:false},headers,cache:"no-store",signal:AbortSignal.timeout(15000)});if(!r.ok)throw new Error(u+" HTTP "+r.status);return await r.text()}catch(e){lastErr=e;if(i<retries)await new Promise(res=>setTimeout(res,800*(i+1)))}}throw lastErr}
async function read(env,k,path){let x=await env.BAKIYE_DATA.get(k);if(x){const s=await x.text();return s?JSON.parse(s):null}let r=await env.ASSETS.fetch(new Request("https://assets.local"+path));return r.ok?await r.json():null}
async function put(env,k,v){await env.BAKIYE_DATA.put(k,JSON.stringify(v,null,2))}
async function stockSources(env){return await read(env,"stock-sources.json","/data/stock-sources.json")||{stocks:{}}}
async function liveQuotes(env){
 const old=await read(env,"quotes.json","/data/quotes.json")||{quotes:{},fx:{}};
 const cfg=await stockSources(env), pages=cfg.stocks||{};
 const q={...old.quotes},f={...old.fx},quoteTimes={...(old.quoteTimes||{})},missing=[],errors=[];
 const results=await Promise.allSettled(STOCKS.map(s=>pages[s]?get(pages[s]):Promise.reject(new Error("OYAK URL eksik"))));
 let fulfilled=0;
 for(let i=0;i<STOCKS.length;i++){
   const s=STOCKS[i],r=results[i];
   if(r.status==="fulfilled"){const x=stockQuote(r.value,SOURCE_SYMBOL[s]||s);if(x.price!=null&&x.price>0){q[s]=x.price;if(x.time)quoteTimes[s]=x.time;fulfilled++}else{missing.push(s);errors.push("OYAK fiyatı ayrıştırılamadı: "+s)}}
   else{missing.push(s);errors.push("OYAK "+s+": "+String(r.reason?.message||r.reason))}
 }
 const fr=await Promise.allSettled([get(FX)]);
 if(fr[0].status==="fulfilled"){for(const c of FXC){const p=fx(fr[0].value,c);if(p!=null)f[c+"TRY"]=p;else missing.push(c+"TRY")}}else errors.push("Döviz.com: "+String(fr[0].reason?.message||fr[0].reason));
 if(fulfilled<STOCKS.length)throw Error("OYAK canlı hisse verileri eksik: "+missing.filter(x=>STOCKS.includes(x)).join(", "));
 const now=new Date().toISOString();
 return {...old,source:"OYAK Yatırım hisse sayfaları + Döviz.com serbest piyasa",sourceUrl:"OYAK Yatırım",stockSourceUrls:pages,fxSourceUrl:FX,asOf:now.slice(0,10),lastRefresh:now,quotes:q,quoteTimes,fx:f,missing,errors,sourceStatus:{oyak:fulfilled===STOCKS.length?"fulfilled":"partial",doviz:fr[0].status,refreshMethod:"Worker live fetch · individual OYAK pages"}};
}
function tlrefCostAddedForPosition(p,tl){const base=Number(p.avgCost)||0,start=p.realCostBaseDate||p.purchaseDate||null,end=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(new Date()),history=Array.isArray(tl?.historical)?tl.historical:[];if(!base||!start||!end||!history.length||start>=end)return 0;const byDate=new Map(history.map(x=>[x.date,Number(x.rate)])),firstRate=Number(history[0]?.rate)||0;if(!firstRate)return 0;let value=base,d=new Date(start+"T00:00:00Z");const endMs=Date.parse(end+"T00:00:00Z");while(d.getTime()<endMs){const key=d.toISOString().slice(0,10);let rate=byDate.get(key);if(rate==null){for(let i=history.length-1;i>=0;i--){if(history[i].date<=key){rate=Number(history[i].rate);break}}if(rate==null)rate=firstRate}value*=1+(rate*(1-(Number(tl?.stopaj??.175))))/365;d.setUTCDate(d.getUTCDate()+1)}return Math.max(0,value-base)}
async function tlref(env){let old=await read(env,"tlref.json","/data/tlref.json")||{historical:[],stopaj:.175,startDate:"2025-08-24"};const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(new Date());let fresh=[],sourceUsed=TLREF;try{fresh=tl(await get(TLREF))}catch(_){}if(!fresh.length||!fresh.some(x=>x.date===today)){try{const fallback=tl(await get(TLREF_FALLBACK));if(fallback.length){fresh=fallback;sourceUsed=TLREF_FALLBACK}}catch(_){}}if(!fresh.length)throw Error("TLREF ayrıştırılamadı");let map=new Map((old.historical||[]).map(x=>[x.date,Number(x.rate)]));for(const x of fresh)map.set(x.date,x.rate);let historical=[...map].sort(([a],[b])=>a.localeCompare(b)).map(([date,rate])=>({date,rate})),last=historical.at(-1),stopaj=Number(old.stopaj??.175);const v={...old,source:sourceUsed===TLREF?"Borsa İstanbul TLREF":"Borsa İstanbul TLREF · doğrulama kaynağı",sourceUrl:TLREF,verificationUrl:sourceUsed===TLREF?null:TLREF_FALLBACK,asOf:last.date,grossAnnualRate:last.rate,stopaj,netAnnualRate:last.rate*(1-stopaj),historical,updatedAt:new Date().toISOString(),method:"Günlük net TLREF fırsat maliyeti; brüt TLREF üzerinden %17,5 stopaj düşülür ve günlük bileşiklenir.",todayAvailable:historical.some(x=>x.date===today),sourceUsed};ctx.waitUntil(put(env,"tlref.json",v).catch(()=>{}));return v}
function out(v,s=200){return new Response(JSON.stringify(v),{status:s,headers:H})}
export default{async fetch(req,env,ctx){const u=new URL(req.url);if(u.pathname==="/api/quotes"){try{const v=await liveQuotes(env);ctx.waitUntil(put(env,"quotes.json",v).catch(()=>{}));return out(v)}catch(e){return out({error:"quotes_not_ready",message:String(e?.message||e),source:"OYAK Yatırım",sourceStatus:{refreshMethod:"OYAK live fetch only",liveError:String(e?.message||e)}},503)}}if(u.pathname==="/api/tlref"){try{return out(await tlref(env))}catch(e){const v=await read(env,"tlref.json","/data/tlref.json");return v?out({...v,sourceStatus:{refreshMethod:"R2 fallback",liveError:String(e?.message||e)}}):out({error:"tlref_not_ready",message:String(e?.message||e)},503)}}if(u.pathname==="/api/balance"){const v=await read(env,"balance.json","/data/balance.json");return v?out(v):out({error:"balance_not_ready"},503)}if(u.pathname==="/api/positions"){const v=await read(env,"positions.json","/data/positions.json");return v?out(v):out({error:"positions_not_ready"},503)}if(u.pathname==="/api/history"){const v=await read(env,"history.json","/data/history.json");return v?out(v):out({error:"history_not_ready"},503)}if(u.pathname==="/api/closing-history"){const v=await read(env,"history/stock-closing.json","/data/history/stock-closing.json");return v?out(v):out({version:1,retentionDays:30,entries:[]})}if(u.pathname==="/api/health")return out({ok:true,service:"bakiye",time:new Date().toISOString()});const mount="/bakiye";if(u.pathname===mount||u.pathname.startsWith(mount+"/")){const assetPath=u.pathname.slice(mount.length)||"/",assetUrl=new URL(req.url);assetUrl.pathname=assetPath;const assetReq=new Request(assetUrl,req),asset=await env.ASSETS.fetch(assetReq);if(assetPath==="/"||assetPath==="/index.html"){const headers=new Headers(asset.headers);headers.set("cache-control","no-store, no-cache, must-revalidate");headers.set("pragma","no-cache");headers.set("expires","0");return new Response(asset.body,{status:asset.status,statusText:asset.statusText,headers})}return asset}const asset=await env.ASSETS.fetch(req);if(u.pathname==="/"||u.pathname==="/index.html"){const headers=new Headers(asset.headers);headers.set("cache-control","no-store, no-cache, must-revalidate");headers.set("pragma","no-cache");headers.set("expires","0");return new Response(asset.body,{status:asset.status,statusText:asset.statusText,headers})}return asset},async scheduled(event,env,ctx){ctx.waitUntil((async()=>{try{const v=await liveQuotes(env);await put(env,"quotes.json",v);console.log("Cron refresh OK",v.lastRefresh)}catch(e){console.error("Cron refresh failed:",e?.message||e)}})())}};
