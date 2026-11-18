const FX="https://kur.doviz.com/";
const GOLD_URL="https://altin.doviz.com/serbest-piyasa/gram-altin";
const TLREF="https://www.borsaistanbul.com/endeksler/tlref";
const TLREF_FALLBACK="https://borsa.doviz.com/endeksler/tlref-turk-lirasi-gecelik-referans-faiz-orani/tarihsel-veri";
const STOCKS=["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"];
const SOURCE_SYMBOL={"ZPLIB.F":"ZPLIB"};
const FXC=["USD","EUR","GBP"];
const TCMB="https://www.tcmb.gov.tr/kurlar/today.xml";
function tcmbFx(x,c){const m=x.match(new RegExp("<Currency[^>]*CurrencyCode=\""+c+"\"[\\s\\S]*?<ForexBuying>([0-9.]+)</ForexBuying>","i"));const n=m?Number(m[1]):null;return Number.isFinite(n)&&n>0?n:null}
const H={"content-type":"application/json;charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"};

function num(v){let s=String(v??"").replace(/[^0-9,.-]/g,"").trim();if(!s)return null;if(s.includes(","))s=s.replace(/\./g,"").replace(",",".");let n=Number(s);return Number.isFinite(n)?n:null}
function text(h){return h.replace(/<script[\s\S]*?<\/script>/gi," ").replace(/<style[\s\S]*?<\/style>/gi," ").replace(/<[^>]+>/g," ").replace(/&nbsp;/gi," ").replace(/&/gi,"&").replace(/\s+/g," ").trim()}
function cells(h){return [...h.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)].map(m=>[...m[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].map(x=>text(x[1])).filter(Boolean)).filter(r=>r.length)}
function goldQuote(h){
 const rows=[...h.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)].map(x=>x[1]);
 const row=rows.find(x=>/data-socket-key=["']gram-altin["']/i.test(x))||h;
 const cells=[...row.matchAll(/<td\b([^>]*)>([\s\S]*?)<\/td>/gi)];
 const bid=cells.find(x=>/data-socket-key=["']gram-altin["']/i.test(x[1])&&/data-socket-attr=["'](?:sell|s)["']/i.test(x[1]));
 if(!bid)return {price:null,time:null};
 const price=num(text(bid[2]));
 const time=(row.match(/\b(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b/)||[])[0]||null;
 return {price:price!=null&&price>0?price:null,time};
}
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
const TR_MONTHS={ocak:1,"şubat":2,mart:3,nisan:4,"mayıs":5,haziran:6,temmuz:7,"ağustos":8,"eylül":9,ekim:10,"kasım":11,"aralık":12};
function tl(h){
 const t=text(h),seen=new Map();
 const add=(y,mo,d,raw)=>{const r=num(raw);if(r==null||!(r>20&&r<60))return;const iso=String(y).padStart(4,"0")+"-"+String(mo).padStart(2,"0")+"-"+String(d).padStart(2,"0");if(!seen.has(iso))seen.set(iso,r/100)};
 let m,a=/(\d{2})\.(\d{2})\.(\d{4})\s+(?:\|\s*)?%?\s*(\d{2}[.,]\d{2,4})(?!\d)/g;
 while((m=a.exec(t)))add(m[3],m[2],m[1],m[4]);
 let b=/(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(\d{4})\s+(?:\|\s*)?%?\s*(\d{2}[.,]\d{2,4})(?!\d)/gi;
 while((m=b.exec(t)))add(m[3],TR_MONTHS[m[2].toLocaleLowerCase("tr-TR")],m[1],m[4]);
 return [...seen].map(([date,rate])=>({date,rate})).sort((x,y)=>x.date.localeCompare(y.date));
}
async function get(u,retries=2,referer="https://www.oyakyatirim.com.tr/"){const headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"tr-TR,tr;q=0.9,en;q=0.8","Cache-Control":"no-cache","Pragma":"no-cache","Referer":referer};let lastErr;for(let i=0;i<=retries;i++){try{const bust=(u.includes("?")?"&":"?")+"_ts="+Date.now()+"_"+i;const r=await fetch(u+bust,{cf:{cacheTtl:0,cacheEverything:false},headers,redirect:"follow",signal:AbortSignal.timeout(15000)});if(!r.ok)throw new Error(u+" HTTP "+r.status);return await r.text()}catch(e){lastErr=e;if(i<retries)await new Promise(res=>setTimeout(res,800*(i+1)))}}throw lastErr}
async function read(env,k,path){let x=await env.BAKIYE_DATA.get(k);if(x){const s=await x.text();return s?JSON.parse(s):null}let r=await env.ASSETS.fetch(new Request("https://assets.local"+path));return r.ok?await r.json():null}
async function put(env,k,v){await env.BAKIYE_DATA.put(k,JSON.stringify(v,null,2))}
async function stockSources(env){return await read(env,"stock-sources.json","/data/stock-sources.json")||{stocks:{}}}
async function liveQuotes(env){
 const old=await read(env,"quotes.json","/data/quotes.json")||{quotes:{},fx:{}};
 const cfg=await stockSources(env), pages=cfg.stocks||{};
 // Preserve stale prices only when the previous cache proves they came from OYAK.
 const oldIsOyak=String(old.source||"").toLowerCase().includes("oyak") && old.sourceUrl==="OYAK Yatırım";
 const q=oldIsOyak?{...(old.quotes||{})}:{};
 const f={...(old.fx||{})};
 const quoteTimes=oldIsOyak?{...(old.quoteTimes||{})}:{};
 const quoteFetchedAt=oldIsOyak?{...(old.quoteFetchedAt||{})}:{};
 for(const s of STOCKS){if(Number.isFinite(Number(q[s]))&&Number(q[s])>0&&!quoteFetchedAt[s])quoteFetchedAt[s]=old.lastRefresh||null;}
 const quoteStatusBySymbol=oldIsOyak?{...(old.quoteStatusBySymbol||{})}:{};
 const missing=[],errors=[],now=new Date().toISOString();
 const results=await Promise.allSettled(STOCKS.map(async s=>{if(!pages[s])throw new Error("OYAK URL eksik");const urls=[pages[s],pages[s].replace("https://www.oyakyatirim.com.tr/","https://oyakyatirim.com.tr/")];let lastErr;for(const u of urls){try{return await get(u)}catch(e){lastErr=e}}throw lastErr||new Error("OYAK isteği başarısız")}));
 let fulfilled=0;
 for(let i=0;i<STOCKS.length;i++){
   const s=STOCKS[i],r=results[i];
   let price=null,quoteTime=null,error=null;
   if(r.status==="fulfilled"){const parsed=stockQuote(r.value,SOURCE_SYMBOL[s]||s);price=parsed.price;quoteTime=parsed.time;if(price==null||price<=0)error="OYAK fiyatı ayrıştırılamadı";}
   else error=String(r.reason?.message||r.reason||"OYAK isteği başarısız");
   if(price!=null&&price>0){
     q[s]=price;fulfilled++;if(quoteTime)quoteTimes[s]=quoteTime;quoteFetchedAt[s]=now;
     quoteStatusBySymbol[s]={status:"fresh",fetchedAt:now,error:null};
   }else{
     missing.push(s);errors.push("OYAK "+s+": "+error);
     const hasOyakPrice=oldIsOyak&&Number.isFinite(Number(q[s]))&&Number(q[s])>0;
     quoteStatusBySymbol[s]={status:hasOyakPrice?"stale":"unavailable",fetchedAt:quoteFetchedAt[s]||null,error};
   }
 }
 const fr=await Promise.allSettled([get(FX),get(GOLD_URL,2,"https://altin.doviz.com/")]);
 let fxStatus="rejected";
 if(fr[0].status==="fulfilled"){fxStatus="fulfilled";for(const c of FXC){const p=fx(fr[0].value,c);if(p!=null)f[c+"TRY"]=p;else errors.push("Döviz.com kur verisi ayrıştırılamadı: "+c)}}
 else errors.push("Döviz.com: "+String(fr[0].reason?.message||fr[0].reason));
 const fxNeed=FXC.filter(c=>!(Number(f[c+"TRY"])>0)||(fr[0].status!=="fulfilled"));
 let fxSourceUsed=fr[0].status==="fulfilled"?"Döviz.com":"önceki değer";
 if(fxNeed.length){try{const xml=await get(TCMB);for(const c of fxNeed){const p=tcmbFx(xml,c);if(p!=null){f[c+"TRY"]=p;fxSourceUsed="TCMB (yedek)"}}}catch(e){errors.push("TCMB yedek kur: "+String(e?.message||e))}}
 if(FXC.every(c=>Number(f[c+"TRY"])>0)&&fxStatus!=="fulfilled")fxStatus=fxSourceUsed.startsWith("TCMB")?"fallback":fxStatus;
 let newGoldPrice=null,goldPriceTime=null,goldPriceFetchedAt=null,goldPriceError=null;
  if(fr[1].status==="fulfilled"){
   const parsed=goldQuote(fr[1].value);
   if(parsed.price!=null){
    newGoldPrice=parsed.price;goldPriceTime=parsed.time||new Date(now).toLocaleTimeString("tr-TR",{timeZone:"Europe/Istanbul",hour:"2-digit",minute:"2-digit",second:"2-digit"});goldPriceFetchedAt=now;
   }else goldPriceError="Döviz.com Gram Altın satış fiyatı HTML içinden ayrıştırılamadı";
  }else goldPriceError="Döviz.com altın sayfası: "+String(fr[1].reason?.message||fr[1].reason||"istek başarısız");
  const oldGoldOk=old.goldPriceSource==="Döviz.com · Gram Altın satış"&&Number.isFinite(Number(old.goldGramTRY))&&Number(old.goldGramTRY)>0;
 const goldGramTRY=newGoldPrice??(oldGoldOk?Number(old.goldGramTRY):null);
 const goldPriceStatus=newGoldPrice!=null?"fresh":(goldGramTRY!=null?"stale":"unavailable");
 if(goldPriceError)errors.push(goldPriceError);
 const fxUpdatedAt=FXC.some(c=>Number(f[c+"TRY"])>0)&&(fxStatus==="fulfilled"||fxStatus==="fallback")?now:(old.fxUpdatedAt||null);
 const allFresh=fulfilled===STOCKS.length;
 const lastComplete=allFresh?now:(oldIsOyak?(old.lastSuccessfulRefresh||old.lastRefresh||null):null);
 const newestFetch=Object.values(quoteFetchedAt).filter(x=>x&&Number.isFinite(Date.parse(x))).sort().at(-1)||null;
 const fxMissing=FXC.filter(c=>!Number.isFinite(Number(f[c+"TRY"]))||Number(f[c+"TRY"])<=0);
 const status={oyak:allFresh?"fulfilled":(fulfilled>0?"partial":"failed"),doviz:fxStatus,refreshMethod:"Cloudflare Worker Cron · every 2 minutes"};
 return {...old,source:"OYAK Yatırım",sourceUrl:"OYAK Yatırım",stockSourceUrls:pages,fxSourceUrl:FX,goldPriceSource:"Döviz.com · Gram Altın satış",goldPriceUrl:GOLD_URL,goldGramTRY,goldPriceTime:goldPriceTime||(oldGoldOk?old.goldPriceTime||null:null),goldPriceFetchedAt:goldPriceFetchedAt||(oldGoldOk?old.goldPriceFetchedAt||null:null),goldPriceStatus,goldPriceError,asOf:allFresh?now.slice(0,10):(oldIsOyak?old.asOf||"":""),lastRefresh:newestFetch||lastComplete,lastSuccessfulRefresh:lastComplete,fxUpdatedAt,fxSourceUsed,lastAttempt:now,quotes:q,quoteTimes,quoteFetchedAt,quoteStatusBySymbol,fx:f,missing:[...missing,...fxMissing],errors,sourceStatus:{...status,gold:goldPriceStatus,staleCount:STOCKS.filter(s=>quoteStatusBySymbol[s]?.status!=="fresh").length}};
}
function tlrefCostAddedForPosition(p,tl){const base=Number(p.avgCost)||0,start=p.realCostBaseDate||p.purchaseDate||null,end=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(new Date()),history=Array.isArray(tl?.historical)?tl.historical:[];if(!base||!start||!end||!history.length||start>=end)return 0;const byDate=new Map(history.map(x=>[x.date,Number(x.rate)])),firstRate=Number(history[0]?.rate)||0;if(!firstRate)return 0;let value=base,d=new Date(start+"T00:00:00Z");const endMs=Date.parse(end+"T00:00:00Z");while(d.getTime()<endMs){const key=d.toISOString().slice(0,10);let rate=byDate.get(key);if(rate==null){for(let i=history.length-1;i>=0;i--){if(history[i].date<=key){rate=Number(history[i].rate);break}}if(rate==null)rate=firstRate}value*=1+(rate*(1-(Number(tl?.stopaj??.175))))/365;d.setUTCDate(d.getUTCDate()+1)}return Math.max(0,value-base)}
async function tlref(env,ctx){
 const old=await read(env,"tlref.json","/data/tlref.json")||{historical:[],stopaj:.175,startDate:"2025-08-24"};
 const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Istanbul"}).format(new Date());
 const checked=Date.parse(old.workerCheckedAt||"");
 if(Number.isFinite(checked)&&Date.now()-checked<15*60*1000&&Array.isArray(old.historical)&&old.historical.length)return old;
 const save=v=>{const p=put(env,"tlref.json",v).catch(()=>{});if(ctx&&ctx.waitUntil)ctx.waitUntil(p);return p};
 let fresh=[],sourceUsed=TLREF;const errs=[];
 try{fresh=tl(await get(TLREF));if(!fresh.length)errs.push("BIST: tabloda satır yok (sayfa JavaScript ile dolduruluyor)")}catch(e){errs.push("BIST: "+String(e?.message||e))}
 if(!fresh.length||!fresh.some(x=>x.date===today)){
  try{const fb=tl(await get(TLREF_FALLBACK));if(fb.length){fresh=fresh.length&&!fb.some(x=>x.date>fresh.at(-1).date)?fresh:fb;sourceUsed=fresh===fb?TLREF_FALLBACK:TLREF}else errs.push("Döviz.com: tabloda satır ayrıştırılamadı")}catch(e){errs.push("Döviz.com: "+String(e?.message||e))}
 }
 if(!fresh.length){await save({...old,workerCheckedAt:new Date().toISOString(),liveError:errs.join(" | ")});throw Error("TLREF ayrıştırılamadı · "+errs.join(" | "))}
 const map=new Map((old.historical||[]).map(x=>[x.date,Number(x.rate)]));
 // BIST rows (4 decimals) overwrite; the 2-decimal verification source only fills missing days.
 for(const x of fresh){if(sourceUsed===TLREF||!map.has(x.date))map.set(x.date,x.rate)}
 const historical=[...map].sort(([a],[b])=>a.localeCompare(b)).map(([date,rate])=>({date,rate})),last=historical.at(-1),stopaj=Number(old.stopaj??.175),now=new Date().toISOString();
 const v={...old,source:sourceUsed===TLREF?"Borsa İstanbul TLREF":"Borsa İstanbul TLREF · doğrulama kaynağı",sourceUrl:TLREF,verificationUrl:sourceUsed===TLREF?null:TLREF_FALLBACK,asOf:last.date,sourceDate:last.date,grossAnnualRate:last.rate,stopaj,netAnnualRate:last.rate*(1-stopaj),historical,updatedAt:now,fetchedAt:now,workerCheckedAt:now,liveError:null,method:"Günlük net TLREF fırsat maliyeti; brüt TLREF üzerinden %17,5 stopaj düşülür ve günlük bileşiklenir.",todayAvailable:historical.some(x=>x.date===today),sourceUsed};
 await save(v);return v}
function out(v,s=200){return new Response(JSON.stringify(v),{status:s,headers:H})}
export default{async fetch(req,env,ctx){if(req.method==="OPTIONS")return new Response(null,{status:204,headers:{...H,"access-control-allow-methods":"GET, OPTIONS","access-control-allow-headers":"Cache-Control, Pragma, Content-Type","access-control-max-age":"86400"}});const u=new URL(req.url);if(u.pathname==="/api/quotes"){
 const cached=await read(env,"quotes.json","/data/quotes.json");
 const age=cached?.lastAttempt?Date.now()-Date.parse(cached.lastAttempt):Infinity;
 const goldNeedsRefresh=cached?.goldPriceSource!=="Döviz.com · Gram Altın alış";
 if(age>=90000||goldNeedsRefresh){
   try{const fresh=await liveQuotes(env);ctx.waitUntil(put(env,"quotes.json",fresh).catch(()=>{}));return out(fresh)}
   catch(e){return out(cached||{source:"OYAK Yatırım",sourceUrl:"OYAK Yatırım",quotes:{},fx:{},quoteTimes:{},quoteFetchedAt:{},quoteStatusBySymbol:{},lastRefresh:null,lastAttempt:null,missing:STOCKS,errors:["OYAK verisi henüz alınmadı"],sourceStatus:{oyak:"unavailable",refreshMethod:"Cloudflare Worker · 2 dakika"}})}
 }
 return cached?out(cached):out({source:"OYAK Yatırım",sourceUrl:"OYAK Yatırım",quotes:{},fx:{},quoteTimes:{},quoteFetchedAt:{},quoteStatusBySymbol:{},lastRefresh:null,lastAttempt:null,missing:STOCKS,errors:["İlk OYAK verisi henüz alınmadı"],sourceStatus:{oyak:"unavailable",refreshMethod:"Cloudflare Worker · 2 dakika"}},200)
}if(u.pathname==="/api/tlref"){try{return out(await tlref(env,ctx))}catch(e){const v=await read(env,"tlref.json","/data/tlref.json");return v?out({...v,sourceStatus:{refreshMethod:"R2 fallback",liveError:String(e?.message||e)}}):out({error:"tlref_not_ready",message:String(e?.message||e)},503)}}if(u.pathname==="/api/balance"){const v=await read(env,"balance.json","/data/balance.json");return v?out(v):out({error:"balance_not_ready"},503)}if(u.pathname==="/api/positions"){const v=await read(env,"positions.json","/data/positions.json");return v?out(v):out({error:"positions_not_ready"},503)}if(u.pathname==="/api/history"){const v=await read(env,"history.json","/data/history.json");return v?out(v):out({error:"history_not_ready"},503)}if(u.pathname==="/api/closing-history"){const v=await read(env,"history/stock-closing.json","/data/history/stock-closing.json");return v?out(v):out({version:1,retentionDays:30,entries:[]})}if(u.pathname==="/api/health")return out({ok:true,service:"bakiye",time:new Date().toISOString()});const mount="/bakiye";if(u.pathname===mount||u.pathname.startsWith(mount+"/")){const assetPath=u.pathname.slice(mount.length)||"/",assetUrl=new URL(req.url);assetUrl.pathname=assetPath;const assetReq=new Request(assetUrl,req),asset=await env.ASSETS.fetch(assetReq);if(assetPath==="/"||assetPath==="/index.html"){const headers=new Headers(asset.headers);headers.set("cache-control","no-store, no-cache, must-revalidate");headers.set("pragma","no-cache");headers.set("expires","0");return new Response(asset.body,{status:asset.status,statusText:asset.statusText,headers})}return asset}const asset=await env.ASSETS.fetch(req);if(u.pathname==="/"||u.pathname==="/index.html"){const headers=new Headers(asset.headers);headers.set("cache-control","no-store, no-cache, must-revalidate");headers.set("pragma","no-cache");headers.set("expires","0");return new Response(asset.body,{status:asset.status,statusText:asset.statusText,headers})}return asset},async scheduled(event,env,ctx){ctx.waitUntil((async()=>{try{const v=await liveQuotes(env);await put(env,"quotes.json",v);try{await tlref(env,ctx)}catch(e){console.error("TLREF cron:",e?.message||e)}console.log("OYAK cron refresh",JSON.stringify({attempt:v.lastAttempt,lastSuccess:v.lastRefresh,status:v.sourceStatus,missing:v.missing,errors:v.errors}))}catch(e){console.error("OYAK cron refresh failed:",e?.message||e)}})())}};
