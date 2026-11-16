const MIDAS="https://www.getmidas.com/canli-borsa/tum-hisseler";
const FX="https://www.doviz.com/";
const TLREF="https://www.borsaistanbul.com/endeksler/tlref";
const STOCKS=["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"];
const FXC=["USD","EUR","GBP"];
const H={"content-type":"application/json;charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"};

function num(v){let s=String(v??"").replace(/[^0-9,.-]/g,"").trim();if(!s)return null;if(s.includes(","))s=s.replace(/\./g,"").replace(",",".");let n=Number(s);return Number.isFinite(n)?n:null}
function text(h){return h.replace(/<script[\s\S]*?<\/script>/gi," ").replace(/<style[\s\S]*?<\/style>/gi," ").replace(/<[^>]+>/g," ").replace(/&nbsp;/gi," ").replace(/&amp;/gi,"&").replace(/\s+/g," ")}
function stock(h,s){
 const e=s.replace(/[.*+?^()|[\]\\]/g,"\\$&");
 let m=h.match(new RegExp("<tr[^>]*>[\\s\\S]{0,6000}?"+e+"[\\s\\S]{0,2500}?<td[^>]*>\\s*([0-9.,]+)\\s*<\\/td>","i"));
 if(m)return num(m[1]);
 m=text(h).match(new RegExp("(?:^|\\s)"+e+"\\s*(?:\\||\\s{2,})\\s*([0-9]+(?:[.,][0-9]+)?)","i"));
 return m?num(m[1]):null;
}
function fx(h,c){let m=text(h).match(new RegExp("(?:^|\\s)"+c+"\\s+[^|\\n]{0,80}?\\|?\\s*([0-9]+(?:[.,][0-9]+)?)","i"));return m?num(m[1]):null}
function tl(h){let a=[],seen=new Set(),m,r=/(\d{2}\.\d{2}\.\d{4})\s+(?:\|\s*)?([0-9]{2,3}[.,]\d{4})/g,t=text(h);while((m=r.exec(t))){let d=m[1].split(".").reverse().join("-");if(!seen.has(d)){seen.add(d);a.push({date:d,rate:num(m[2])/100})}}return a.sort((a,b)=>a.date.localeCompare(b.date))}
async function get(u){let r=await fetch(u,{headers:{"User-Agent":"Mozilla/5.0 (compatible; BakiyeWorker/1.0)","Accept":"text/html,application/xhtml+xml","Accept-Language":"tr-TR,tr;q=0.9"}});if(!r.ok)throw Error(u+" HTTP "+r.status);return r.text()}
async function read(env,k,path){let x=await env.BAKIYE_DATA.get(k);if(x)return JSON.parse(x);let r=await env.ASSETS.fetch(new Request("https://assets.local"+path));return r.ok?r.json():null}
async function put(env,k,v){await env.BAKIYE_DATA.put(k,JSON.stringify(v,null,2))}
async function quotes(env){
 let old=await read(env,"quotes.json","/data/quotes.json")||{quotes:{},fx:{}};
 let [mh,fh]=await Promise.all([get(MIDAS),get(FX)]),q={...old.quotes},f={...old.fx},missing=[];
 for(let s of STOCKS){let p=stock(mh,s);if(p!=null)q[s]=p;else missing.push(s)}
 for(let c of FXC){let p=fx(fh,c);if(p!=null)f[c+"TRY"]=p;else missing.push(c+"TRY")}
 let v={...old,source:"Midas Son fiyat (15 dk gecikmeli) + Döviz.com serbest piyasa",sourceUrl:MIDAS,fxSourceUrl:FX,asOf:new Date().toISOString().slice(0,10),lastRefresh:new Date().toISOString(),quotes:q,fx:f,missing};
 await put(env,"quotes.json",v);return v;
}
async function tlref(env){
 let old=await read(env,"tlref.json","/data/tlref.json")||{historical:[],stopaj:.175,startDate:"2025-08-24"};
 let fresh=tl(await get(TLREF));if(!fresh.length)throw Error("TLREF ayrıştırılamadı");
 let map=new Map((old.historical||[]).map(x=>[x.date,Number(x.rate)]));for(let x of fresh)map.set(x.date,x.rate);
 let historical=[...map].sort(([a],[b])=>a.localeCompare(b)).map(([date,rate])=>({date,rate})),last=historical.at(-1),stopaj=Number(old.stopaj??.175);
 let v={...old,source:"Borsa İstanbul TLREF",sourceUrl:TLREF,asOf:last.date,grossAnnualRate:last.rate,stopaj,netAnnualRate:last.rate*(1-stopaj),historical,updatedAt:new Date().toISOString(),method:"Günlük net TLREF fırsat maliyeti; brüt TLREF üzerinden %17,5 stopaj düşülür ve günlük bileşiklenir."};
 await put(env,"tlref.json",v);return v;
}
function out(v,s=200){return new Response(JSON.stringify(v),{status:s,headers:H})}
export default{
 async fetch(req,env){let u=new URL(req.url);
  if(u.pathname==="/api/quotes"){let v=await read(env,"quotes.json","/data/quotes.json");return v?out(v):out({error:"quotes_not_ready"},503)}
  if(u.pathname==="/api/tlref"){let v=await read(env,"tlref.json","/data/tlref.json");return v?out(v):out({error:"tlref_not_ready"},503)}
  if(u.pathname==="/api/health")return out({ok:true,service:"bakiye",time:new Date().toISOString()});
  return env.ASSETS.fetch(req);
 },
 async scheduled(e,env,ctx){if(e.cron==="30 15 * * *")ctx.waitUntil(tlref(env));else if(e.cron==="*/5 * * * *")ctx.waitUntil(quotes(env))}
};