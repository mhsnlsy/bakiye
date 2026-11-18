const STOCK_SOURCE="https://uzmanpara.milliyet.com.tr/canli-borsa/bist-TUM-hisseleri/";
const FX="https://kur.doviz.com/";
const TLREF="https://www.borsaistanbul.com/endeksler/tlref";
const TLREF_FALLBACK="https://borsa.doviz.com/endeksler/tlref-turk-lirasi-gecelik-referans-faiz-orani/tarihsel-veri";
const STOCKS=["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"];
const SOURCE_SYMBOL={"ZPLIB.F":"ZPLIB"};
const FXC=["USD","EUR","GBP"];
const H={"content-type":"application/json;charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"};

function num(v){let s=String(v??"").replace(/[^0-9,.-]/g,"").trim();if(!s)return null;if(s.includes(","))s=s.replace(/\./g,"").replace(",",".");let n=Number(s);return Number.isFinite(n)?n:null}
function text(h){return h.replace(/<script[\s\S]*?<\/script>/gi," ").replace(/<style[\s\S]*?<\/style>/gi," ").replace(/<[^>]+>/g," ").replace(/&nbsp;/gi," ").replace(/&/gi,"&").replace(/\s+/g," ").trim()}
function cells(h){return [...h.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)].map(m=>[...m[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map(x=>text(x[1])).filter(Boolean)).filter(r=>r.length)}
function stock(h,s){
 const rows=cells(h);
 const target=String(s).trim().toUpperCase();
 for(const r of rows){
   const i=r.findIndex(x=>x.trim().toUpperCase()===target);
   if(i>=0){
     for(let j=i+1;j<r.length;j++){const p=num(r[j]);if(p!=null)return p}
   }
 }
 const t=text(h);
 const m=t.match(new RegExp("(?:^|\\s)"+target.replace(/[.*+?^()|[\\]\\\\]/g,"\\\\$&")+"\\s+([0-9]+(?:[.,][0-9]+)?)","i"));
 return m?num(m[1]):null;
}
function fx(h,c){
 const rows=cells(h);
 const target=String(c).trim().toUpperCase();
 for(const r of rows){
   const i=r.findIndex(x=>x.trim().toUpperCase().startsWith(target+" "));
   if(i>=0){
     for(let j=i+1;j<r.length;j++){const p=num(r[j]);if(p!=null)return p}
   }
 }
 const t=text(h);
 const m=t.match(new RegExp("\\b"+target+"\\s+[^0-9]{1,80}?([0-9]{1,3}(?:[.,]\\d{3})*(?:,[0-9]+)?|[0-9]+(?:[.,][0-9]+)?)","i"));
 return m?num(m[1]):null;
}
function tl(h){let a=[],seen=new Set(),m,r=/(\d{2}\.\d{2}\.\d{4})\s+(?:\|\s*)?([0-9]{2,3}[.,]\d{4})/g,t=text(h);while((m=r.exec(t))){let d=m[1].split(".").reverse().join("-");if(!seen.has(d)){seen.add(d);a.push({date:d,rate:num(m[2])/100})}}return a.sort((a,b)=>a.date.localeCompare(b.date))}
async function get(u, retries = 2) {
  const bust = (u.includes("?") ? "&" : "?") + "_ts=" + Date.now();
  const headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
  };
  let lastErr;
  for (let i = 0; i <= retries; i++) {
    try {
      const r = await fetch(u + bust, {
        cf: { cacheTtl: 0, cacheEverything: false },
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(15000)
      });
      if (!r.ok) throw new Error(u + " HTTP " + r.status);
      return await r.text();
    } catch (e) {
      lastErr = e;
      if (i < retries) await new Promise(res => setTimeout(res, 800 * (i + 1)));
    }
  }
  throw lastErr;
}
async function read(env,k,path){let x=await env.BAKIYE_DATA.get(k);if(x){const s=await x.text();return s?JSON.parse(s):null}let r=await env.ASSETS.fetch(new Request("https://assets.local"+path));return r.ok?await r.json():null}
async function put(env,k,v){await env.BAKIYE_DATA.put(k,JSON.stringify(v,null,2))}
async function liveQuotes(env){
 const old=await read(env,"quotes.json","/data/quotes.json")||{quotes:{},fx:{}};
 const q={...old.quotes},f={...old.fx},missing=[],errors=[];
 const [mr,fr]=await Promise.allSettled([get(STOCK_SOURCE),get(FX)]);
 if(mr.status==="fulfilled"){
   for(const s of STOCKS){
     const p=stock(mr.value,SOURCE_SYMBOL[s]||s);
     if(p!=null&&p>0)q[s]=p;else missing.push(s);
   }
 }else errors.push("Uzmanpara: "+String(mr.reason?.message||mr.reason));
 if(fr.status==="fulfilled"){
   for(const c of FXC){
     const p=fx(fr.value,c);
     if(p!=null)f[c+"TRY"]=p;else missing.push(c+"TRY");
   }
 }else errors.push("Döviz.com: "+String(fr.reason?.message||fr.reason));
 if(mr.status!=="fulfilled"&&fr.status!=="fulfilled")throw Error("Uzmanpara ve Döviz.com canlı verileri alınamadı");
 const now=new Date().toISOString();
 return {...old,source:"Uzmanpara Son fiyat (15 dk gecikmeli) + Döviz.com serbest piyasa",sourceUrl:STOCK_SOURCE,fxSourceUrl:FX,asOf:now.slice(0,10),lastRefresh:now,quotes:q,fx:f,missing,errors,sourceStatus:{uzmanpara:mr.status,doviz:fr.status,refreshMethod:"Worker live fetch"}};
}
async function quotes(env){
 const old=await read(env,"quotes.json","/data/quotes.json")||{quotes:{},fx:{}};
 const q={...old.quotes},f={...old.fx},missing=[],errors=[];
 const [mr,fr]=await Promise.allSettled([get(STOCK_SOURCE),get(FX)]);
 const stockMissing=[];
 if(mr.status==="fulfilled"){
   for(const s of STOCKS){const p=stock(mr.value,SOURCE_SYMBOL[s]||s);if(p!=null&&p>0)q[s]=p;else {missing.push(s);stockMissing.push(s)}}
 }else errors.push("Uzmanpara: "+String(mr.reason?.message||mr.reason));
 if(mr.status!=="fulfilled"||stockMissing.length)throw Error("Uzmanpara fiyatları eksik: "+stockMissing.join(", "));
 if(fr.status==="fulfilled"){
   for(const c of FXC){const p=fx(fr.value,c);if(p!=null)f[c+"TRY"]=p;else missing.push(c+"TRY")}
 }else errors.push("Döviz.com: "+String(fr.reason?.message||fr.reason));
 const now=new Date().toISOString();
 const v={...old,source:"Uzmanpara Son fiyat (15 dk gecikmeli) + Döviz.com serbest piyasa",sourceUrl:STOCK_SOURCE,fxSourceUrl:FX,asOf:now.slice(0,10),lastRefresh:now,quotes:q,fx:f,missing,errors,sourceStatus:{uzmanpara:mr.status,doviz:fr.status}};
 await put(env,"quotes.json",v);
 return v;
}
function tlrefCostAddedForPosition(p,tl){
 const base=Number(p.avgCost)||0;
 const start=p.realCostBaseDate||p.purchaseDate||null;
 const end=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(new Date());
 const history=Array.isArray(tl?.historical)?tl.historical:[];
 if(!base||!start||!end||!history.length||start>=end)return 0;
 const byDate=new Map(history.map(x=>[x.date,Number(x.rate)]));
 const firstRate=Number(history[0]?.rate)||0;
 if(!firstRate)return 0;
 let value=base;
 let d=new Date(start+"T00:00:00Z");
 const endMs=Date.parse(end+"T00:00:00Z");
 while(d.getTime()<endMs){
   const key=d.toISOString().slice(0,10);
   let rate=byDate.get(key);
   if(rate==null){
     for(let i=history.length-1;i>=0;i--){if(history[i].date<=key){rate=Number(history[i].rate);break}}
     if(rate==null)rate=firstRate;
   }
   value*=1+(rate*(1-(Number(tl?.stopaj??.175))))/365;
   d.setUTCDate(d.getUTCDate()+1);
 }
 return Math.max(0,value-base);
}
async function tlref(env){
 let old=await read(env,"tlref.json","/data/tlref.json")||{historical:[],stopaj:.175,startDate:"2025-08-24"};
 const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(new Date());
 let fresh=[],sourceUsed=TLREF;
 try{fresh=tl(await get(TLREF));}catch(_){}
 if(!fresh.length || !fresh.some(x=>x.date===today)){
   try{
     const fallback=tl(await get(TLREF_FALLBACK));
     if(fallback.length) { fresh=fallback; sourceUsed=TLREF_FALLBACK; }
   }catch(_){}
 }
 if(!fresh.length)throw Error("TLREF ayrıştırılamadı");
 let map=new Map((old.historical||[]).map(x=>[x.date,Number(x.rate)]));for(const x of fresh)map.set(x.date,x.rate);
 let historical=[...map].sort(([a],[b])=>a.localeCompare(b)).map(([date,rate])=>({date,rate})),last=historical.at(-1),stopaj=Number(old.stopaj??.175);
 const v={...old,source:sourceUsed===TLREF?"Borsa İstanbul TLREF":"Borsa İstanbul TLREF · doğrulama kaynağı",sourceUrl:TLREF,verificationUrl:sourceUsed===TLREF?null:TLREF_FALLBACK,asOf:last.date,grossAnnualRate:last.rate,stopaj,netAnnualRate:last.rate*(1-stopaj),historical,updatedAt:new Date().toISOString(),method:"Günlük net TLREF fırsat maliyeti; brüt TLREF üzerinden %17,5 stopaj düşülür ve günlük bileşiklenir.",todayAvailable:historical.some(x=>x.date===today),sourceUsed};
 ctx.waitUntil(put(env,"tlref.json",v).catch(()=>{}));return v;
}
function out(v,s=200){return new Response(JSON.stringify(v),{status:s,headers:H})}
export default{
 async fetch(req,env,ctx){const u=new URL(req.url);
  if(u.pathname==="/api/quotes"){
    try{
      const v=await liveQuotes(env);
      ctx.waitUntil(put(env,"quotes.json",v).catch(()=>{}));
      return out(v);
    }catch(e){
      const cached=await read(env,"quotes.json","/data/quotes.json");
      if(cached){
        return out({...cached,sourceStatus:{...(cached.sourceStatus||{}),refreshMethod:"R2 fallback",liveError:String(e?.message||e)}});
      }
      return out({error:"quotes_not_ready",message:String(e?.message||e)},503);
    }
  }
  if(u.pathname==="/api/tlref"){
    try{
      const fresh=await tlref(env);
      return out(fresh);
    }catch(e){
      const v=await read(env,"tlref.json","/data/tlref.json");
      return v?out({...v,sourceStatus:{refreshMethod:"R2 fallback",liveError:String(e?.message||e)}}):out({error:"tlref_not_ready",message:String(e?.message||e)},503);
    }
  }
  if(u.pathname==="/api/balance"){const v=await read(env,"balance.json","/data/balance.json");return v?out(v):out({error:"balance_not_ready"},503)}
  if(u.pathname==="/api/positions"){const v=await read(env,"positions.json","/data/positions.json");return v?out(v):out({error:"positions_not_ready"},503)}
  if(u.pathname==="/api/history"){const v=await read(env,"history.json","/data/history.json");return v?out(v):out({error:"history_not_ready"},503)}
  if(u.pathname==="/api/closing-history"){const v=await read(env,"history/stock-closing.json","/data/history/stock-closing.json");return v?out(v):out({version:1,retentionDays:30,entries:[]})}
  if(u.pathname==="/api/health")return out({ok:true,service:"bakiye",time:new Date().toISOString()});
  const mount="/bakiye";
  if(u.pathname===mount || u.pathname.startsWith(mount+"/")){
    const assetPath=u.pathname.slice(mount.length)||"/";
    const assetUrl=new URL(req.url);
    assetUrl.pathname=assetPath;
    const assetReq=new Request(assetUrl,req);
    const asset=await env.ASSETS.fetch(assetReq);
    if(assetPath==="/"||assetPath==="/index.html"){
      const headers=new Headers(asset.headers);
      headers.set("cache-control","no-store, no-cache, must-revalidate");
      headers.set("pragma","no-cache");
      headers.set("expires","0");
      return new Response(asset.body,{status:asset.status,statusText:asset.statusText,headers});
    }
    return asset;
  }
  const asset=await env.ASSETS.fetch(req);
  if(u.pathname==="/"||u.pathname==="/index.html"){const headers=new Headers(asset.headers);headers.set("cache-control","no-store, no-cache, must-revalidate");headers.set("pragma","no-cache");headers.set("expires","0");return new Response(asset.body,{status:asset.status,statusText:asset.statusText,headers})}
  return asset;
 },
 async scheduled(event, env, ctx) {
  ctx.waitUntil((async () => {
    try {
      const v = await liveQuotes(env);
      await put(env, "quotes.json", v);
      console.log("Cron refresh OK", v.lastRefresh);
    } catch (e) {
      console.error("Cron refresh failed:", e?.message || e);
    }
  })());
}
};
