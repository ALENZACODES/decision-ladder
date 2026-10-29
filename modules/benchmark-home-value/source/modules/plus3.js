
/* ======================= Round 3: next-month nowcast, price against time to sell, cottage and waterfront,
   room-by-room measuring, neighbourhood momentum, official hazard maps, and broker branding on every report.
   All free; every card keeps working when a source is missing. ======================= */
(function(){
  const css=`.rooms textarea{width:100%;min-height:84px;font:13px var(--mono);padding:8px;border:1px solid var(--muted);border-radius:6px;background:var(--bg);color:var(--fg)}
  .linklist{display:grid;gap:6px}.linklist a{color:var(--accent);font-weight:600;text-decoration:underline;text-underline-offset:2px;overflow-wrap:anywhere}
  .opts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}.opts div{border:1px solid var(--line);border-radius:8px;padding:8px;text-align:center;display:grid;gap:2px}
  .opts div.best{border-color:var(--s3);background:color-mix(in srgb,var(--s3) 10%,transparent)}.opts b{font:600 14px var(--mono)}.opts small{font:500 11px var(--mono);color:var(--muted)}
  @container (max-width:520px){.opts{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .brand-line{font-size:13px;border-top:1px solid var(--line);padding-top:8px;margin-top:4px}`;
  const s=document.createElement("style");s.textContent=css;document.head.appendChild(s);
  const g=$("plus").querySelector(".pgrid");
  g.insertAdjacentHTML("beforeend",`
    <div class="pcard" id="pNow"></div>
    <div class="pcard" id="pMom"></div>
    <div class="pcard chart" id="pLiq"><div class="chart-top"><h3>Price against time to sell</h3><div class="tools"><button type="button" data-png="xl">PNG</button><button type="button" data-csv="xl">CSV</button></div></div>
      <div class="chart-sub" id="xlsub"></div><div class="opts" id="liqOpts"></div><div class="box" id="xl"></div><div class="mode" id="ml" hidden></div><div class="dl-msg"></div></div>
    <div class="pcard" id="pHaz"></div>
    <div class="pcard wide" id="pBrand"><h3>Put your name on every report</h3>
      <p class="hint" style="margin:0">For brokers, agents and advisors: your details print on the report and the equity digest, like a branded lender or broker tool. Saved in this browser only.</p>
      <div class="row3"><label for="brName">Name <input id="brName" autocomplete="name"></label><label for="brCo">Company <input id="brCo" autocomplete="organization"></label><label for="brLic">Licence no. <input id="brLic"></label></div>
      <div class="row3"><label for="brPhone">Phone <input id="brPhone" type="tel" autocomplete="tel"></label><label for="brEmail">Email <input id="brEmail" type="email" autocomplete="email"></label><label for="brWeb">Website <input id="brWeb" type="url"></label></div>
      <div class="hint" id="brSaved"></div></div>`);
  // cottage and waterfront questions, shown for cottages and rural homes
  const box=document.createElement("div");box.id="cottBox";box.className="sub";box.hidden=true;
  box.innerHTML=`<div class="subhead">Cottage and waterfront</div>
    <div class="row"><label for="cWater">Water <select id="cWater"><option value="none">No water nearby</option><option value="view">Water view</option><option value="shared">Shared or deeded access</option><option value="front">Private waterfront</option></select></label>
      <label for="cFront">Frontage (ft) <input id="cFront" type="number" min="0" max="5000" step="1" value="100"></label></div>
    <div class="row"><label for="cLake">Lake or river <select id="cLake"><option value="s">Small or shallow</option><option value="m" selected>Medium, good boating</option><option value="l">Large or big-lake</option></select></label>
      <label for="cAccess">Access <select id="cAccess"><option value="year">Year-round road</option><option value="seasonal">Seasonal road</option><option value="water">Water access only</option></select></label></div>
    <div class="row"><label for="cWinter">Winterized <select id="cWinter"><option value="1">Yes (insulated, heated, year-round water)</option><option value="0">No, three-season</option></select></label>
      <label for="cSun">Exposure <select id="cSun"><option value="0">Not sure</option><option value=".03">West or south (sunsets)</option><option value="-.02">North or east</option></select></label></div>
    <p class="hint" style="margin:0">Typical premiums from cottage-country sales patterns; local markets vary a lot. Each one shows in the adjustments.</p>`;
  $("condoBox").after(box);
  // room-by-room measuring (any phone measuring or LiDAR scanning app gives room sizes)
  const rm=document.createElement("details");rm.className="sub rooms";rm.id="roomBox";
  rm.innerHTML=`<summary class="subhead">Measure room by room <span class="hint">for an exact living area</span></summary>
    <p class="hint" style="margin:0">One room per line, in feet (12x14) or metres (3.6x4.2 m). A phone measuring or room-scanning app gives these in minutes. Count finished rooms, hallways and stairs; leave out the garage and unfinished basement.</p>
    <textarea id="roomList" placeholder="Living 16x14&#10;Kitchen 12x11&#10;Bedroom 12x11&#10;3.4x3.0 m"></textarea>
    <div class="btns"><button type="button" class="ghost" id="roomUse">Use this total</button><span class="hint" id="roomTot" aria-live="polite"></span></div>`;
  $("sqft").closest(".row").after(rm);
  Object.assign(FR_EXACT,{"Price against time to sell":"Prix selon le délai de vente","Put your name on every report":"Votre nom sur chaque rapport","Cottage and waterfront":"Chalet et bord de l’eau",
    "Measure room by room":"Mesurer pièce par pièce","Use this total":"Utiliser ce total","Next month, before the index is published":"Le mois prochain, avant la publication de l’indice",
    "Neighbourhood momentum":"Dynamisme du quartier","Flood, wildfire and climate":"Inondations, feux de forêt et climat"});
})();

/* ---------- room measuring ---------- */
function roomsTotal(){const t=$("roomList").value||"";let ft=0,n=0;
  for(const line of t.split(/\n+/)){const m=line.match(/(\d+(?:[.,]\d+)?)\s*(?:x|×|by|\*)\s*(\d+(?:[.,]\d+)?)\s*(m|metres?|meters?)?\b/i);if(!m)continue;
    const a=parseFloat(m[1].replace(",",".")),b=parseFloat(m[2].replace(",",".")),metric=!!m[3]||(a<8&&b<8&&/\d[.,]\d/.test(line));
    const area=a*b*(metric?10.7639:1);if(area>0&&area<5000){ft+=area;n++;}}
  return {ft:Math.round(ft),n};}
$("roomList").addEventListener("input",()=>{const r=roomsTotal();$("roomTot").textContent=r.n?`${r.n} room${r.n>1?"s":""}: ${r.ft.toLocaleString("en-CA")} sq ft (+8% for walls, halls and stairs = ${Math.round(r.ft*1.08).toLocaleString("en-CA")})`:"";});
$("roomUse").addEventListener("click",()=>{const r=roomsTotal();if(!r.n){$("roomTot").textContent="Add at least one room, like 12x14.";return;}
  $("sqft").value=Math.round(r.ft*1.08);sqftKnown=true;$("sqft").dispatchEvent(new Event("change"));$("roomTot").textContent=`Living area set to ${$("sqft").value} sq ft.`;});

/* ---------- cottage and waterfront ---------- */
function cottageFactor(){if(!["cottage","rural"].includes(st.sub))return [];const a=[];
  const w=$("cWater").value,lake={s:.25,m:.4,l:.6}[$("cLake").value]||.4,fr=Math.max(0,+$("cFront").value||0);
  if(w==="front"){a.push(["Private waterfront",lake]);if(fr>100)a.push([`Frontage ${fr} ft`,Math.min(.2,(fr-100)*.0015)]);else if(fr&&fr<75)a.push([`Narrow frontage (${fr} ft)`,-.06]);}
  else if(w==="shared")a.push(["Shared water access",.08]);else if(w==="view")a.push(["Water view",.05]);
  if($("cAccess").value==="seasonal")a.push(["Seasonal road",-.1]);if($("cAccess").value==="water")a.push(["Water access only",-.25]);
  if($("cWinter").value==="0")a.push(["Three-season (not winterized)",-.12]);
  const sun=+$("cSun").value||0;if(sun&&w!=="none")a.push([sun>0?"West or south exposure":"North or east exposure",sun]);
  return a;}
{const _estCott=estimate;estimate=function(){_estCott();try{
  $("cottBox").hidden=!["cottage","rural"].includes(st.sub);const a=cottageFactor();if(!a.length||!lastV)return;
  const base=lastV,k=a.reduce((p,x)=>p*(1+x[1]),1);lastV=r5k(base*k);$("rVal").textContent="$"+lastV.toLocaleString("en-CA");
  $("rRange").textContent=$("rRange").textContent.replace(/\$([\d,]+)/g,(m,n)=>"$"+r5k(+n.replace(/,/g,"")*k).toLocaleString("en-CA"));
  let run=base;$("adjBox").hidden=false;$("adjBox").insertAdjacentHTML("beforeend",a.map(([l,f])=>{const d=run*f;run+=d;return `<div><span>${esc(l)}</span><span class="${d>=0?"up":"down"}">${d>=0?"+":"−"}${money(Math.abs(d))}</span></div>`;}).join(""));}catch(e){}};}
["cWater","cFront","cLake","cAccess","cWinter","cSun"].forEach(id=>$(id).addEventListener("input",()=>{estimate();extras();}));
$("ptype").addEventListener("change",()=>{$("cottBox").hidden=!["cottage","rural"].includes(st.sub);});

/* ---------- next-month nowcast from the index's own momentum and season, tested walk-forward ---------- */
function nowcastModel(A){const f=(i)=>{const m3=Math.pow(A[i]/A[i-3],1/3),seas=(A[i-11]/A[i-12])/Math.pow(A[i-1]/A[i-13],1/12);   // last year's same-month move beyond its trend
    return A[i]*Math.pow(m3,.7)*Math.max(.98,Math.min(1.02,seas));};
  const err=[],naive=[];for(let i=24;i<A.length-1;i++){err.push(Math.abs(f(i)/A[i+1]-1));naive.push(Math.abs(A[i]/A[i+1]-1));}
  return {next:f(A.length-1),mdae:qtile(err,.5),naive:qtile(naive,.5),n:err.length};}
let RATES_FILE=null;
async function ratesLive(){   // Bank of Canada now (when reachable), else data/rates.json from the local updater, else the page's own series
  if(PLUS.boc&&PLUS.boc.policy)return {src:"Bank of Canada (live)",...PLUS.boc};
  if(!RATES_FILE)RATES_FILE=getJSON("data/rates.json").catch(()=>null);const f=await RATES_FILE;
  if(f&&f.policy)return {src:`Bank of Canada, saved ${f.d||""}`,...f};
  return {src:"this page's rate history",policy:null,posted:null,five:RATES[RATES.length-1]};}
async function drawNowcast(){const el=$("pNow"),reg=cur().reg,A=IDXA(reg),v=lastV;if(!v)return;const m=nowcastModel(A),now=A[A.length-1],g=m.next/now-1,R=await ratesLive();
  const r3=RATES[RATES.length-1]-RATES[RATES.length-4];
  el.innerHTML=`<h3>Next month, before the index is published</h3><div class="num">${money(v*(1+g))}<small style="font-size:16px;color:var(--muted)"> ${label(addMonths(NOWM,1))}</small></div>
    <div class="kv"><div><span>Expected move</span><span class="${g>=0?"up":"down"}">${sgn(g,2)}</span></div>
      <div><span>Typical miss, tested month by month</span><span>±${(m.mdae*100).toFixed(2)}% (vs ±${(m.naive*100).toFixed(2)}% assuming no change)</span></div>
      <div><span>Mortgage rates, last 3 months</span><span>${r3<=0?"down":"up"} ${Math.abs(r3).toFixed(2)} pts</span></div>
      ${R.policy?`<div><span>Bank of Canada policy rate</span><span>${R.policy}%</span></div>`:""}</div>
    <p class="hint" style="margin:0">From the ${REGION_NAME[reg]} index's recent momentum and its usual seasonal pattern, re-tested on ${m.n} past months. Rates from ${esc(R.src)}. Run "Update live data" in the downloaded app to refresh rates on your computer.</p>`;
  PLUS.rep.now=`<div class="rp-sec"><b>Next month</b><p>${money(v*(1+g))} expected for ${label(addMonths(NOWM,1))} (${sgn(g,2)}); typical miss ±${(m.mdae*100).toFixed(2)}%.</p></div>`;}

/* ---------- price against time to sell (stated model; no listing data needed) ---------- */
function drawLiquidity(){const v=lastV;if(!v)return;const reg=cur().reg,A=IDXA(reg),n=A.length,tr=Math.pow(A[n-1]/A[n-4],1/3)-1,condo=isCondo(st.sub);
  const base=(tr>.003?20:tr<-.003?45:30)+(condo?10:0)+(["rural","cottage"].includes(st.sub)?30:0),temp=tr>.003?"rising":tr<-.003?"softening":"balanced";
  const S=eqState(),fee=(+$("slFee").value||4)/100,carry=(S.bal*(S.rate||4.5)/100/12)+v*.009/12+(condo?(+$("cfee").value||0)+v*.004/12:v*.01/12)+(condo?40:150);
  const pts=[-5,-4,-3,-2,-1,0,1,2,3,4,5].map(p=>{const days=Math.max(5,Math.round(base*Math.exp(.13*p))),price=v*(1+p/100),sell=price*(1-Math.min(.6,Math.max(0,p)*.12)/10),
    net=sell-sell*fee-2000-carry*days/30.4;return {p,days,price,net};});
  const best=pts.reduce((a,b)=>b.net>a.net?b:a),show=[-4,-2,0,2,4].map(p=>pts.find(x=>x.p===p));
  $("liqOpts").innerHTML=show.map(x=>`<div class="${x===best||(x.p===best.p)?"best":""}"><small>${x.p>0?"+":""}${x.p}% list</small><b>${money(x.price)}</b><small>~${x.days} days</small><small>net ${money(x.net)}</small></div>`).join("");
  $("xlsub").innerHTML=`A ${temp} market here, so a home priced at value typically takes about <b>${base} days</b>. Each 1% above value adds roughly 13% to the wait (and homes listed high often sell under list); each 1% below shortens it. Net is after ${Math.round(fee*100)}% commission, $2,000 legal and ${dollars(carry)}/mo carrying costs. Best net here: <b>${best.p>0?"+":""}${best.p}%</b>. A stated model, not listing data.`;
  render("xl",{kind:"line",labels:pts.map(x=>(x.p>0?"+":"")+x.p+"%"),fmt:v=>Math.round(v)+" days",sets:[{label:"Expected days to sell",data:pts.map(x=>x.days),color:css("--s1")}]});
  PLUS.rep.liq=`<div class="rp-sec"><b>Price against time to sell</b><p>${show.map(x=>`${x.p>0?"+":""}${x.p}%: ${money(x.price)}, ~${x.days} days, net ${money(x.net)}`).join("; ")}.</p></div>`;}

/* ---------- neighbourhood momentum (Census growth, new homes, street assessments vs the region) ---------- */
async function drawMomentum(){const el=$("pMom"),p=aiProp||{},it=p.pick||{};const parts=[];
  try{const prof=await profileFor(it.da),ca=await INS.profca;
    if(prof&&ca&&ca.pct){const F=["pop","growth","age","inc","own","sfd","apt","old","new","ocost","rcost","bach","unemp","transit","lowinc"],rank=f=>{const P=ca.pct[f],x=prof[F.indexOf(f)];if(!P||x==null)return null;let k=0;while(k<P.length&&P[k]<=x)k++;return Math.max(0,Math.min(100,(k-1)*5));};
      const gr=rank("growth"),nw=rank("new"),ag=rank("age"),ba=rank("bach");
      if(gr!=null)parts.push(["Population growth 2016–21",gr]);if(nw!=null)parts.push(["Share of newer homes",nw]);
      if(ag!=null)parts.push(["Younger residents",100-ag]);if(ba!=null)parts.push(["University-educated residents",ba]);}}catch(e){}
  const near=(p.near||[]).filter(x=>x.chg!=null);
  if(near.length>=3){const ch=qtile(near.map(x=>x.chg/100),.5),y0=Math.min(...near.map(x=>x.since)),y1=Math.max(...near.map(x=>x.year)),reg=cur().reg,
      ix=idxSafe(reg,st.prov,y1-1,6)/idxSafe(reg,st.prov,y0-1,6)-1,score=Math.max(0,Math.min(100,50+(ch-ix)*250));
    parts.push([`Street assessments ${sgn(ch,0)} vs region ${sgn(ix,0)} since ${y0}`,Math.round(score)]);}
  if(!parts.length){el.innerHTML=`<h3>Neighbourhood momentum</h3><p class="hint">Not enough Census or assessment detail for this address.</p>`;PLUS.rep.mom="";return;}
  const sc=Math.round(parts.reduce((a,b)=>a+b[1],0)/parts.length),word=sc>=65?"Strong":sc>=50?"Building":sc>=35?"Steady":"Quiet";
  el.innerHTML=`<h3>Neighbourhood momentum</h3><div class="num">${sc}<small style="font-size:16px;color:var(--muted)"> / 100 · ${word}</small></div>
    <div class="meter"><i style="width:${sc}%;background:var(--s3)"></i></div>
    <div class="kv">${parts.map(([k,v])=>`<div><span>${esc(k)}</span><span>${v} / 100</span></div>`).join("")}</div>
    <p class="hint" style="margin:0">Each signal is ranked against every Canadian neighbourhood (50 is the middle). Street assessments rising faster than the region often lead prices. Census 2021 and city assessment rolls.</p>`;
  PLUS.rep.mom=`<div class="rp-sec"><b>Neighbourhood momentum</b><p>${sc}/100 (${word}): ${parts.map(([k,v])=>`${k} ${v}`).join("; ")}.</p></div>`;}

/* ---------- official hazard maps (free government viewers) ---------- */
const FLOOD_PROV={ON:["Ontario flood hazard mapping","https://ontario.ca/page/flood-hazard-identification-and-mapping"]};
function drawHazard(){const el=$("pHaz"),ll=((aiProp||{}).pick||{}).ll||"",[la,lo]=ll.split(","),prov=st.prov,hdd=HDD_CITY[st.muni]||HDD_REG[cur().reg]||4500;
  const L=[["Canada's flood maps, by province and city (geo.ca)","https://geo.ca/flood-mapping"],FLOOD_PROV[prov],["Wildfire risk and current fires (Canadian Wildland Fire Information System)","https://cwfis.cfs.nrcan.gc.ca/interactive-map"],["Climate projections for this area (ClimateData.ca)","https://climatedata.ca/"]].filter(Boolean);
  const flags=[];if(["BC","AB"].includes(prov))flags.push("Wildfire season risk is highest in BC and Alberta; check the fire map and your insurer's wildfire rules.");
  if(["NS","NB","PE","NL"].includes(prov)||(prov==="BC"&&cur().reg==="VAN"))flags.push("Coastal and river flooding: ask the city whether this lot is in a mapped floodplain before you buy or renovate.");
  if(["MB","SK"].includes(prov))flags.push("Spring river flooding: check the provincial flood map and overland water coverage on your policy.");
  if(prov==="QC"||prov==="ON")flags.push("Overland flood coverage is optional on many policies; check yours if the lot is near water.");
  el.innerHTML=`<h3>Flood, wildfire and climate</h3>${la?`<p class="hint" style="margin:0">Coordinates for the map viewers: <b style="font-family:var(--mono)">${esc(la)}, ${esc(lo)}</b></p>`:""}
    <div class="linklist">${L.map(([t,u])=>`<a href="${u}" target="_blank" rel="noopener">${esc(t)} ↗</a>`).join("")}</div>
    ${flags.map(f=>`<div class="flag">${esc(f)}</div>`).join("")}
    <p class="hint" style="margin:0">Heating need here: ${hdd.toLocaleString("en-CA")} degree-days a year. Climate projections show most of Canada warming, which lowers heating costs but raises flood, heat and wildfire exposure. Insurance cost and availability can move value; the official maps above are free.</p>`;}

/* ---------- broker branding on reports and digests ---------- */
const BR_IDS=["brName","brCo","brLic","brPhone","brEmail","brWeb"];let BR_MEM=null;
function brLoad(){if(BR_MEM)return BR_MEM;try{return JSON.parse(localStorage.getItem("hve-brand")||"{}")||{};}catch(e){return {};}}
function brSave(){const b={};BR_IDS.forEach(id=>b[id]=$(id).value.trim());try{localStorage.setItem("hve-brand",JSON.stringify(b));BR_MEM=null;$("brSaved").textContent="Saved in this browser.";}catch(e){BR_MEM=b;$("brSaved").textContent="Saved for this visit (this browser blocks storage).";}}
function brHTML(){const b=brLoad();if(!b.brName&&!b.brCo)return "";const safeUrl=u=>/^https?:\/\//i.test(u||"")?u:"";
  return `<div class="rp-sec brand-line"><b>Prepared by ${esc(b.brName||"")}</b>${b.brCo?` · ${esc(b.brCo)}`:""}${b.brLic?` · Licence ${esc(b.brLic)}`:""}<br>${[b.brPhone&&esc(b.brPhone),b.brEmail&&`<a href="mailto:${esc(b.brEmail)}">${esc(b.brEmail)}</a>`,safeUrl(b.brWeb)&&`<a href="${esc(safeUrl(b.brWeb))}">${esc(b.brWeb)}</a>`].filter(Boolean).join(" · ")}</div>`;}
{const b=brLoad();BR_IDS.forEach(id=>{if(b[id])$(id).value=b[id];$(id).addEventListener("change",brSave);});}

/* ---------- wiring ---------- */
const _updPlus3=updatePlus;updatePlus=function(){_updPlus3();if(!aiProp||!lastV)return;
  for(const f of [drawLiquidity,drawHazard])try{f();}catch(e){console.warn(f.name,e);}
  drawNowcast().catch(()=>{});const lbl=$("addr").value.trim();if(lbl!==PLUS.momLbl){PLUS.momLbl=lbl;drawMomentum().catch(()=>{});}};
["slFee","eqBal","eqRate"].forEach(id=>$(id).addEventListener("input",()=>{try{drawLiquidity();}catch(e){}}));
const _repPlus3=buildReport;buildReport=async function(){await _repPlus3();const rep=$("report"),n=rep.querySelector(".notice");
  const extra=["now","liq","mom"].map(k=>PLUS.rep[k]||"").join("")+brHTML();if(n)n.insertAdjacentHTML("beforebegin",extra);else rep.insertAdjacentHTML("beforeend",extra);};
// branding on the equity digest too: wrap the shell used for both downloads
{const _shell=docShell;docShell=(title,body)=>_shell(title,/Prepared by/.test(body)?body:body.replace(/<p class="notice">/,brHTML()+`<p class="notice">`));}
