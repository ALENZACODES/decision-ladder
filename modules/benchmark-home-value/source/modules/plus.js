
/* ======================= More for every address: free versions of what paid valuation tools sell =======================
   Confidence score measured by the page's own backtest (RPS/Teranet/Redfin publish accuracy; this page measures it).
   Several valuations side by side (Realtor.com), value history (Zillow/Redfin), market rent and yield (RPS, RentCast,
   Zillow Rent Zestimate; CMHC rents), a 2-year outlook range (Gnowise, HouseCanary), condo building comparables
   (Condos.ca), a monthly equity and renewal digest (Homebot), saved homes tracked over time (Wahi), and two calculators
   that need no address (FHFA / BestRates purchase-price calculator; MPAC / BC Assessment value to today).
   Nothing here calls a paid service: every number comes from data already on the page. */
const PLUS={t:null,rep:{},boc:null,lastLbl:""};
const sgn=(x,d=1)=>(x>=0?"+":"−")+Math.abs(x*100).toFixed(d)+"%";
const IDXA=reg=>IDX[reg]||IDX.GTA, INOW=reg=>{const a=IDXA(reg);return a[a.length-1];};
const NOWM=MONTHS[MONTHS.length-1];
const addMonths=(d,k)=>{const x=new Date(d);x.setMonth(x.getMonth()+k);return x;};
const qtile=(a,p)=>{const s=[...a].sort((x,y)=>x-y),i=(s.length-1)*p,lo=Math.floor(i);return s[lo]+(s[Math.min(lo+1,s.length-1)]-s[lo])*(i-lo);};
const w10of=m=>1-Math.pow(2,-.1/m);   // share within 10% when errors fall off like the page's tests show (matches 67% at a 6.25% median)
function btGroup(){const m=st.muni,p=st.prov;if(p==="AB")return m==="Calgary"?"Calgary":m==="Edmonton"?"Edmonton":"Other Alberta";
  if(p==="BC")return m==="Vancouver"?"Vancouver":"Other BC";return "All";}
function pmtOf(P,ratePct,years){const r=ratePct/100/12,n=Math.max(1,years*12);return P>0?(r?P*r/(1-Math.pow(1+r,-n)):P/n):0;}
function balAfter(P,ratePct,years,k){const r=ratePct/100/12,pm=pmtOf(P,ratePct,years);return r?Math.max(0,P*Math.pow(1+r,k)-pm*(Math.pow(1+r,k)-1)/r):Math.max(0,P-pm*k);}
const PCT_TYPE=()=>({detached:"detached house",semi:"semi",town:"townhouse",condo:"condo",condotown:"condo townhouse",duplex:"duplex",multiplex:"plex",mobile:"mobile home"})[(window.EVID||{}).t]||"home";

/* --- how sure is this estimate? from the backtest, by the evidence this address has --- */
function confidence(){const E=window.EVID||{},condo=isCondo(st.sub),bt=typeof BT!=="undefined"&&BT.data,acc=DB.acc||{},dacc=DB.dacc||{};
  let m,w10=null,n=null,how;
  if(E.lvl==="own"&&!bt){m=condo?.152:.05;w10=condo?.35:.78;n=null;how="a home's own city assessment moved forward with this page's price index (built-in test results)";}
  else if(E.lvl==="own"&&bt){const g=bt.groups[btGroup()]||bt.groups.All,k=g.kind&&g.kind[condo?"condo":"house"]||g.methods.index;
    m=k.mdape;w10=k.w10;n=k.n;how=`a home's own city assessment moved forward with this page's price index (${condo?"condos":"houses"}${btGroup()==="All"?"":", "+btGroup()})`;}
  else if(E.lvl==="street"){m=(acc.by_level||{}).street||.095;n=acc.test_records;how="the typical assessment on the same street";}
  else if(E.lvl==="block"){m=(dacc.by_region||{})[cur().reg]||(sqftKnown?dacc.with_size_median_abs_pct_err:dacc.median_abs_pct_err)||.21;n=dacc.tested_on||dacc.records;how="the 2021 Census block and postal area, split by property type";}
  else if(E.lvl==="postal"){m=(acc.by_level||{}).postal||.22;n=acc.test_records;how="assessments across the postal area";}
  else{m=.25;how="the area benchmark alone (not testable against single homes)";}
  if(E.pp){const im=bt?bt.groups.All.methods.index.mdape:.0625;if(im<m){m=Math.sqrt(m*im);w10=null;how+=", blended with your purchase price moved forward with the index";}}
  if(w10==null)w10=w10of(m);
  return {m,w10,n,how,score:Math.max(5,Math.min(95,Math.round(w10*100))),b80:m*Math.log2(5)};}
function confWord(s){return s>=70?"High":s>=50?"Fair":s>=30?"Low":"Very low";}

/* --- every valuation the page can make for this address, in today's dollars --- */
function valuations(){const p=aiProp||{},E=window.EVID||{},t=E.t||st.sub,reg=cur().reg,prov=st.prov,out=[];
  const sq=sqftKnown?(+$("sqft").value||0):0;
  if(E.own){const [y,v]=E.own,vd=valDate(prov,y),then=idxAtPage(reg,prov,vd[0],vd[1]);
    out.push({k:"own",name:"This home's city assessment, moved to today",v:v*INOW(reg)/then,note:`${money(v)} on the ${y} roll (values as of ${monthName(vd)}) × the regional index since then`});}
  const s=p.street&&p.street[t];
  if(s){const r=s[2]&&sq?Math.min(3,Math.max(.4,sq/s[2]))**.5:1;out.push({k:"street",name:`Typical ${PCT_TYPE()} on this street`,v:s[0]*r,note:`${s[1]} assessments${s[2]?", typical "+s[2].toLocaleString("en-CA")+" sq ft":""}${r!==1?", sized to yours":""}`});}
  if(E.blkV)out.push({k:"block",name:"Neighbourhood model (Census block)",v:E.blkV,note:`2021 Census values for block ${esc(p.block&&p.block.da||"")} and the postal area, moved to today`});
  const pt=p.f&&p.f.t&&p.f.t[t];if(pt)out.push({k:"postal",name:`Typical ${PCT_TYPE()} in ${esc(p.fsa)}`,v:pt[0],note:`${pt[1]} assessments in the postal area`});
  const [bt0,f]=SUB[st.sub]||SUB.detached,ser=seriesFor(cur(),bt0);out.push({k:"bench",name:`${esc(st.muni)} benchmark, ${PCT_TYPE()}`,v:ser[ser.length-1]*f,note:"published regional benchmark level for this type"});
  const pp=+$("pp").value,pd=$("pd").value;
  if(pp>10000&&/^\d{4}-\d{2}$/.test(pd)){const [py,pm]=pd.split("-").map(Number),then=idxAtPage(reg,prov,py,pm-1),reno=(+$("reno").value||0)*.6;
    out.push({k:"paid",name:"What you paid, moved to today",v:pp*INOW(reg)/then+reno,note:`${money(pp)} in ${monthName([py,pm-1])}${reno?" plus 60% of renovations":""}`});}
  return out.filter(x=>Number.isFinite(x.v)&&x.v>5000);}
const monthName=([y,m])=>new Date(y,m,1).toLocaleDateString("en-CA",{month:"short",year:"numeric"});

/* assessment valuation dates by province (tax year -> [year, month 0-11]); editable in the calculator */
function valDate(prov,y){
  if(prov==="ON")return [2016,0];                                  // MPAC: every roll since 2017 still uses Jan 1, 2016
  if(prov==="BC"||prov==="AB"||prov==="YT")return [y-1,6];          // July 1 of the year before
  if(prov==="SK")return y>=2025?[2023,0]:y>=2021?[2019,0]:[2015,0]; // 4-year revaluations
  if(prov==="MB")return y>=2025?[2023,3]:y>=2023?[2021,3]:[2019,3]; // April 1, two years before each 2-year roll
  if(prov==="QC"){const r=2017+Math.floor((y-2017)/3)*3;return [r-2,6];}   // most 3-year rolls: July 1, 18 months before
  if(prov==="NB")return [y,0];
  return [y-1,0];}                                                   // NS, PE, NL, NT, NU: Jan 1 of the year before

/* ---------- layout ---------- */
(function(){
  const css=`.plus{margin-top:20px;container-type:inline-size}.plus>h2,.calc>h2{margin:2px 0 0;font:600 24px var(--display);color:var(--accent)}
  .pgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;grid-auto-flow:row dense}.pgrid .wide{grid-column:1/-1}
  @container (max-width:760px){.pgrid{grid-template-columns:minmax(0,1fr)}.pgrid .wide{grid-column:auto}}
  .pcard{border:1px solid var(--line);border-radius:8px;padding:14px;display:grid;gap:8px;align-content:start;min-width:0;background:var(--surface)}
  .pcard h3{margin:0;font:600 15px var(--body)}.pcard .num{font:600 30px var(--display);color:var(--accent);line-height:1.1;font-variant-numeric:tabular-nums}
  .meter{height:10px;border-radius:99px;background:var(--line);overflow:hidden}.meter i{display:block;height:100%;border-radius:99px;background:var(--s1)}
  .kv{display:grid;gap:0}.kv>div{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--line);font-size:13px}
  .kv>div>span:last-child{font:500 13px var(--mono);text-align:right;white-space:nowrap}.kv>div:last-child{border-bottom:0}
  .dots{position:relative;height:30px;margin:6px 6px 2px;border-bottom:1px solid var(--line)}.dots i{position:absolute;bottom:-5px;width:10px;height:10px;border-radius:50%;transform:translateX(-50%);background:var(--s3);border:2px solid var(--surface)}
  .dots i.me{width:14px;height:14px;bottom:-7px;background:var(--s1)}.dots .band{position:absolute;bottom:-3px;height:6px;border-radius:9px;background:color-mix(in srgb,var(--s1) 22%,transparent)}
  .vrow{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:4px 12px;align-items:baseline;padding:7px 0;border-bottom:1px solid var(--line);font-size:13px}
  .vrow b{font:600 14px var(--mono)}.vrow small{grid-column:1/-1;color:var(--muted);font-size:12px}.vrow .d{font:500 12px var(--mono);color:var(--muted)}
  .pcard .row{grid-template-columns:repeat(2,minmax(0,1fr))}.pcard .row3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
  @container (max-width:520px){.pcard .row3{grid-template-columns:minmax(0,1fr)}}
  .btns{display:flex;flex-wrap:wrap;gap:8px}.btns .ghost,.btns .cta{font-size:13px;padding:8px 12px}
  .flag{border-left:3px solid var(--s4);padding:6px 10px;font-size:13px;background:color-mix(in srgb,var(--s4) 10%,transparent);border-radius:0 6px 6px 0}
  .flag.good{border-color:var(--good);background:color-mix(in srgb,var(--good) 10%,transparent)}
  .units{max-height:280px;overflow:auto}.units tr.me td{font-weight:700;color:var(--accent)}
  .saved-list{display:grid;gap:8px}.sv{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 12px;align-items:center;border:1px solid var(--line);border-radius:8px;padding:10px 12px}
  .sv .l{font-weight:600;font-size:14px;overflow-wrap:anywhere}.sv .m{font:500 12px var(--mono);color:var(--muted)}.sv .act{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
  .sv .act button{font:500 12px var(--body);padding:5px 10px;border:1px solid var(--line);border-radius:999px;background:transparent;color:var(--fg);cursor:pointer}
  .sv svg{width:120px;height:28px;display:block}.dl-msg{font-size:12px;color:var(--muted);min-height:1em}
  #rConf{font-size:13px}#rConf b{font-family:var(--mono)}`;
  const s=document.createElement("style");s.textContent=css;document.head.appendChild(s);
  const chart=(id,title,sub,wide)=>`<div class="pcard chart${wide?" wide":""}"><div class="chart-top"><h3>${title}</h3><div class="tools"><button type="button" data-png="${id}">PNG</button><button type="button" data-csv="${id}">CSV</button></div></div>
    <div class="chart-sub" id="${id}sub">${sub}</div><div class="box" id="${id}"></div><div class="mode" id="m${id.slice(1)}" hidden></div><div class="dl-msg"></div></div>`;
  const plus=document.createElement("section");plus.className="panel plus";plus.id="plus";plus.hidden=true;plus.setAttribute("aria-labelledby","plusTitle");
  plus.innerHTML=`<div><div class="eyebrow">Your home, in depth</div><h2 id="plusTitle">Everything the paid tools show, free</h2>
    <p class="hint">Confidence, several valuations side by side, value history, rent, a 2-year range, your building, and a monthly equity check. All from public data already on this page.</p></div>
    <div class="pgrid">
      <div class="pcard" id="pConf"></div>
      <div class="pcard" id="pVals"></div>
      ${chart("xh","Value history","")}
      ${chart("xf","Where it could be in 2 years","")}
      <div class="pcard" id="pRent"></div>
      <div class="pcard" id="pBldg" hidden></div>
      <div class="pcard wide" id="pEq"><div class="chart-top"><h3>Monthly equity and renewal check</h3></div>
        <div class="row3">
          <label for="eqBal">Mortgage balance ($) <input id="eqBal" type="number" min="0" step="1" placeholder="e.g. 420000"></label>
          <label for="eqRate">Your rate (%) <input id="eqRate" type="number" min="0" max="20" step="0.01" value="4.79"></label>
          <label for="eqLeft">Years left to pay <input id="eqLeft" type="number" min="1" max="40" step="1" value="22"></label>
        </div>
        <div class="row3">
          <label for="eqRenew">Renewal date <input id="eqRenew" type="month" min="2026-01" max="2035-12"></label>
          <label for="eqMkt">Today's typical 5-yr rate (%) <input id="eqMkt" type="number" min="0" max="20" step="0.01"></label>
          <div class="hint" id="eqBoc" style="align-self:end"></div>
        </div>
        <div id="eqOut"></div>
        <div class="box" id="xe" style="position:relative;height:240px"></div><div class="mode" id="me" hidden></div>
        <div class="btns"><button type="button" class="cta" id="eqDigest">Download my equity digest (.html)</button><button type="button" class="ghost" id="eqIcs">Monthly reminder (.ics)</button><button type="button" class="ghost" data-csv="xe">Payoff table (.csv)</button></div>
        <div class="dl-msg"></div></div>
    </div>
    <div class="btns"><button type="button" class="cta" id="saveHome">Save this home and track it</button><button type="button" class="ghost" id="dlReport">Download full report (.html)</button></div><div class="dl-msg" id="plusMsg"></div>`;
  const saved=document.createElement("section");saved.className="panel plus";saved.id="saved";saved.hidden=true;saved.setAttribute("aria-labelledby","savedTitle");
  saved.innerHTML=`<div class="chart-top"><div><div class="eyebrow">Tracked homes</div><h2 id="savedTitle" style="margin:2px 0 0;font:600 22px var(--display);color:var(--accent)">My saved homes</h2></div>
    <div class="tools"><button type="button" id="svCsv">CSV</button><button type="button" id="svBackup">Backup</button><button type="button" id="svRestoreBtn">Restore</button><input type="file" id="svRestore" accept="application/json,.json" hidden></div></div>
    <p class="hint">Saved in this browser only. Each home's value follows the regional price index from the day you saved it; open a home to re-estimate it with the newest data.</p>
    <div class="saved-list" id="svList"></div><div class="dl-msg"></div>`;
  const calc=document.createElement("section");calc.className="panel plus calc";calc.id="calc";calc.setAttribute("aria-labelledby","calcTitle");
  const opts=M.map((m,i)=>[m,i]).sort((a,b)=>a[0].prov.localeCompare(b[0].prov)||a[0].name.localeCompare(b[0].name)).map(([m,i])=>`<option value="${i}">${esc(m.name)}, ${m.prov}</option>`).join("");
  const yrs=[];for(let y=2026;y>=2017;y--)yrs.push(`<option>${y}</option>`);
  calc.innerHTML=`<div><div class="eyebrow">No address needed</div><h2 id="calcTitle">Quick calculators</h2></div>
    <div class="pgrid">
      <div class="pcard"><h3>What's my home worth now? (from what I paid)</h3>
        <label for="ccMuni">Where <select id="ccMuni">${opts}</select></label>
        <div class="row"><label for="ccPrice">Price paid ($) <input id="ccPrice" type="number" min="10000" step="1" value="500000"></label>
          <label for="ccWhen">Month bought <input id="ccWhen" type="month" min="1990-01" max="2026-09" value="2019-06"></label></div>
        <div id="ccOut"></div></div>
      ${chart("xc","Your purchase, moved through the regional index","")}
      <div class="pcard wide"><h3>Turn an assessment into today's value</h3>
        <p class="hint" style="margin:0">Assessments are set as of an earlier valuation date. Ontario's MPAC values every roll since 2017 as of January 1, 2016; BC Assessment and Alberta cities use July 1 of the year before. Check the date on your notice and change it below if yours differs.</p>
        <div class="row3"><label for="caMuni">Where <select id="caMuni">${opts}</select></label>
          <label for="caVal">Assessed value ($) <input id="caVal" type="number" min="10000" step="1" value="650000"></label>
          <label for="caYear">Tax year on the notice <select id="caYear">${yrs.join("")}</select></label></div>
        <div class="row3"><label for="caDate">Valuation date <input id="caDate" type="month" min="2016-01" max="2026-09"></label><div></div><div></div></div>
        <div id="caOut"></div></div>
    </div>`;
  const bt=$("bt");bt.before(saved,plus,calc);
  const r=document.createElement("div");r.id="rConf";r.className="hint";$("rMeta").before(r);
  Object.assign(FR_EXACT,{"Everything the paid tools show, free":"Tout ce que montrent les outils payants, gratuitement","Your home, in depth":"Votre propriété en détail",
    "Value history":"Historique de la valeur","Where it could be in 2 years":"Où elle pourrait être dans 2 ans","Monthly equity and renewal check":"Bilan mensuel de l’avoir propre et du renouvellement",
    "Quick calculators":"Calculatrices rapides","No address needed":"Aucune adresse requise","My saved homes":"Mes propriétés enregistrées","Tracked homes":"Propriétés suivies",
    "Save this home and track it":"Enregistrer et suivre cette propriété","Download full report (.html)":"Télécharger le rapport complet (.html)",
    "Turn an assessment into today's value":"Convertir une évaluation en valeur d’aujourd’hui","What's my home worth now? (from what I paid)":"Combien vaut ma propriété? (d’après le prix payé)",
    "How sure is this estimate?":"Quel est le degré de certitude?","Every way to value it":"Toutes les façons de l’évaluer","Rent and yield":"Loyer et rendement","Your building":"Votre immeuble"});
})();

/* download helper that reports next to the button pressed */
let PLUS_BTN=null;document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("button");if(b)PLUS_BTN=b;},true);
function msgBox(){const c=PLUS_BTN&&PLUS_BTN.closest(".pcard");if(c&&c.querySelector(".dl-msg"))return c.querySelector(".dl-msg");const p=PLUS_BTN&&PLUS_BTN.closest(".panel");return p&&p.querySelector(":scope>.dl-msg");}
function plusMsg(t){const m=msgBox();if(m)m.textContent=t;else btMsg(t);}
async function plusSave(name,data){let dl=null;try{dl=await downloadsNS();}catch(e){}
  if(dl){try{await dl.save({filename:name,data});plusMsg("Saved "+name+".");return true;}
    catch(e){const c=e&&e.code;if(c==="declined"){plusMsg("Save cancelled.");return false;}if(c==="rate_limited"){plusMsg("A save is already waiting for your answer.");return false;}}}
  // fallback 2: an ordinary browser download link
  try{const blob=data instanceof Blob?data:new Blob([data],{type:/\.html$/.test(name)?"text/html":/\.csv$/.test(name)?"text/csv":/\.ics$/.test(name)?"text/calendar":"application/octet-stream"});
    const u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=name;a.textContent="Download "+name;
    const m=msgBox();
    if(m){m.textContent="";m.append("If it didn't download, ",a,".");}a.click();setTimeout(()=>URL.revokeObjectURL(u),120000);return true;}catch(e){}
  // fallback 3: show the text so it can be copied
  if(typeof data==="string"){const m=msgBox();
    if(m){m.innerHTML=`Saving isn't allowed here. Copy this and save it as <b>${esc(name)}</b>:<textarea rows="5" style="width:100%;font:12px var(--mono)" readonly></textarea>`;const ta=m.querySelector("textarea");ta.value=data;ta.select();return false;}}
  plusMsg("Saving files isn't available in this view.");return false;}

/* ---------- address cards ---------- */
function drawConf(){const c=confidence(),v=lastV,lo=r5k(v*(1-c.b80)),hi=r5k(v*(1+c.b80));PLUS.conf=c;
  $("rConf").innerHTML=`Confidence <b>${c.score}/100</b> · estimates built this way landed within 10% of the city's later assessment ${Math.round(c.w10*100)}% of the time in this page's tests`;
  $("pConf").innerHTML=`<h3>How sure is this estimate?</h3><div class="num">${c.score}<small style="font-size:16px;color:var(--muted)"> / 100 · ${confWord(c.score)}</small></div>
    <div class="meter" role="img" aria-label="Confidence ${c.score} out of 100"><i style="width:${c.score}%"></i></div>
    <div class="kv"><div><span>Within 10%, in tests</span><span>${Math.round(c.w10*100)}% of the time</span></div>
      <div><span>Typical miss (median)</span><span>±${(c.m*100).toFixed(1)}%</span></div>
      <div><span>8 in 10 land between</span><span>${money(lo)} – ${money(hi)}</span></div>
      ${c.n?`<div><span>Tests behind this</span><span>${Number(c.n).toLocaleString("en-CA")}</span></div>`:""}</div>
    <p class="hint" style="margin:0">Built from ${esc(c.how)}. Tests price each home from data known at the time and compare with what the city assessed later, the way RPS and Teranet describe their accuracy, but published here in full in the Backtest section below.</p>`;
  PLUS.rep.conf=`<div class="rp-sec"><b>Confidence</b><p>${c.score}/100 (${confWord(c.score)}). Estimates built from ${esc(c.how)} landed within 10% of the later city assessment ${Math.round(c.w10*100)}% of the time in this page's tests; median miss ±${(c.m*100).toFixed(1)}%. 8 in 10 land between ${money(lo)} and ${money(hi)}.</p></div>`;}
function drawVals(){const vs=valuations(),v=lastV;if(!vs.length){$("pVals").hidden=true;return;}$("pVals").hidden=false;
  const b=PLUS.conf?PLUS.conf.b80:.1,all=[...vs.map(x=>x.v),v,v*(1-b),v*(1+b)],lo=Math.min(...all)*.97,hi=Math.max(...all)*1.03,X=x=>Math.max(0,Math.min(100,(x-lo)/(hi-lo)*100)).toFixed(1)+"%";
  const med=qtile(vs.map(x=>x.v),.5),spread=vs.length>1?Math.max(...vs.map(x=>Math.abs(x.v/med-1))):null;
  $("pVals").innerHTML=`<h3>Every way to value it</h3><p class="hint" style="margin:0">Each method on its own, in today's dollars. The large dot is this page's estimate${PLUS.conf?"; the band is its 8-in-10 range":""}.</p>
    <div class="dots" aria-hidden="true"><span class="band" style="left:${X(v*(1-b))};right:calc(100% - ${X(v*(1+b))})"></span>${vs.map(x=>`<i style="left:${X(x.v)}" title="${esc(x.name)}: ${money(x.v)}"></i>`).join("")}<i class="me" style="left:${X(v)}" title="Estimate ${money(v)}"></i></div>
    <div>${vs.map(x=>`<div class="vrow"><span>${x.name}</span><b>${money(x.v)}</b><span class="d">${sgn(x.v/v-1,0)}</span><small>${x.note}</small></div>`).join("")}
    <div class="vrow"><span><b style="font-family:var(--body)">This page's estimate</b></span><b>${money(v)}</b><span class="d">blend</span></div></div>
    ${spread!=null?`<div class="flag${spread<.1?" good":""}">${spread<.1?`These ${vs.length} methods agree within ±${Math.round(spread*100)}%.`:`The methods differ by up to ±${Math.round(spread*100)}%. The ones built on this home's own records or its street are the most reliable here.`}</div>`:""}`;
  PLUS.rep.vals=`<div class="rp-sec"><b>Every way to value it</b><table>${vs.map(x=>`<tr><td style="text-align:left">${x.name}</td><td>${money(x.v)}</td><td>${sgn(x.v/v-1,0)}</td></tr>`).join("")}<tr><td style="text-align:left"><b>Estimate</b></td><td><b>${money(v)}</b></td><td></td></tr></table></div>`;}
function drawHistory(){const reg=cur().reg,A=IDXA(reg),now=A[A.length-1],v=lastV,p=aiProp||{},prov=st.prov;
  const est=A.map(x=>Math.round(v*x/now)),pts=new Array(A.length).fill(null),buy=new Array(A.length).fill(null);
  for(const [y,val] of (p.history||[])){const d=valDate(prov,y),i=mi(d[0],d[1]);if(i>=0&&i<A.length)pts[i]=val;}
  const pp=+$("pp").value,pd=$("pd").value;if(pp>10000&&/^\d{4}-\d{2}$/.test(pd)){const [py,pm]=pd.split("-").map(Number),i=mi(py,pm-1);if(i>=0&&i<A.length)buy[i]=pp;}
  const sets=[{label:"This home through the "+REGION_NAME[reg]+" index",data:est,color:css("--s1")}];
  if(pts.some(x=>x))sets.push({label:"City assessments (at valuation date)",data:pts,color:css("--s2"),points:true});
  if(buy.some(x=>x))sets.push({label:"What you paid",data:buy,color:css("--s4"),points:true});
  $("xhsub").textContent=`Today's estimate run backwards through the regional price index, monthly from Jan 2016${pts.some(x=>x)?", with this home's own assessments where the city publishes them":""}. Peak ${money(Math.max(...est))} (${label(MONTHS[est.indexOf(Math.max(...est))])}).`;
  render("xh",{kind:"line",labels:MONTHS.map(label),fmt:fmt$,sets});
  const y5=est[est.length-61];PLUS.rep.hist=`<div class="rp-sec"><b>Value history</b><p>Through the ${REGION_NAME[reg]} index: ${money(est[0])} in Jan 2016, peak ${money(Math.max(...est))} (${label(MONTHS[est.indexOf(Math.max(...est))])}), ${money(v)} today${y5?`; ${sgn(v/y5-1)} over 5 years`:""}.</p></div>`;}
function outlook(reg){const A=IDXA(reg),n=A.length,r24=[],r12=[];for(let i=0;i+24<n;i++)r24.push(A[i+24]/A[i]);for(let i=0;i+12<n;i++)r12.push(A[i+12]/A[i]);
  return {lo:qtile(r24,.1),mid:qtile(r24,.5),hi:qtile(r24,.9),lo1:qtile(r12,.1),mid1:qtile(r12,.5),hi1:qtile(r12,.9),trend:A[n-1]/A[n-13],cagr:Math.pow(A[n-1]/A[0],12/(n-1))-1};}
function drawOutlook(){const reg=cur().reg,A=IDXA(reg),n=A.length,now=A[n-1],v=lastV,o=outlook(reg),past=36,fut=24;PLUS.out=o;
  const labels=[...MONTHS.slice(n-past-1).map(label),...Array.from({length:fut},(_,k)=>label(addMonths(NOWM,k+1)))];
  const hist=[...A.slice(n-past-1).map(x=>Math.round(v*x/now)),...new Array(fut).fill(null)];
  const path=R=>[...new Array(past).fill(null),...Array.from({length:fut+1},(_,k)=>Math.round(v*Math.pow(R,k/24)))];
  const trend2=o.trend*o.trend;
  render("xf",{kind:"line",labels,fmt:fmt$,sets:[{label:"Past 3 years",data:hist,color:css("--s1")},{label:"Typical 2 years",data:path(o.mid),color:css("--s3")},
    {label:"Strong (top 10%)",data:path(o.hi),color:css("--s4"),dash:[6,4]},{label:"Weak (bottom 10%)",data:path(o.lo),color:css("--s2"),dash:[6,4]},{label:"Last 12 months repeated",data:path(trend2),color:css("--muted"),dash:[2,4]}]});
  $("xfsub").innerHTML=`Not a prediction: the range of what ${REGION_NAME[reg]} prices did over every 2-year stretch since 2016. In 2 years: <b>${money(v*o.lo)}</b> weak, <b>${money(v*o.mid)}</b> typical, <b>${money(v*o.hi)}</b> strong. The last 12 months were ${sgn(o.trend-1)}.`;
  PLUS.rep.out=`<div class="rp-sec"><b>2-year range</b><p>Based on every 2-year stretch of the ${REGION_NAME[reg]} index since 2016 (not a forecast): weak ${money(v*o.lo)}, typical ${money(v*o.mid)}, strong ${money(v*o.hi)}. In 1 year: ${money(v*o.lo1)} – ${money(v*o.hi1)}.</p></div>`;}
async function drawRent(){const el=$("pRent"),{r:rent,src:rsrc}=await rentSafe(st.prov,st.muni),v=lastV,condo=isCondo(st.sub);
  const bIn=+$("beds").value||2,beds=Math.max(0,Math.min(3,$("beds").dataset.touched||!condo?bIn:(sqftKnown&&+$("sqft").value<650?1:Math.min(bIn,2)))),pick=rent?(rent[beds]||rent[Math.max(1,beds-1)]||rent.find(Boolean)):null;
  if(!pick||!v){el.innerHTML=`<h3>Rent and yield</h3><p class="hint">No CMHC rent survey covers ${esc(st.muni)}.</p>`;PLUS.rep.rent="";return;}
  // CMHC's survey averages every occupied unit, including long-time tenants; units re-let today ask more, so show both
  const isHouse=!condo&&st.sub!=="semi"&&st.sub!=="town",mk=isHouse?1.25:1.12,lo=pick,hi=Math.round(pick*mk*1.1/25)*25,mid=Math.round(pick*mk/25)*25;
  const rate=+$("rate").value||4.2,mort=pmtOf(v*.8,rate,25),tax=v*.009/12,fee=condo?(+$("cfee").value||0):0,upkeep=condo?v*.004/12:v*.01/12,ins=(condo?40:150);
  const noi=mid*12*.96-(tax+fee+upkeep+ins)*12,cash=mid*.96-mort-tax-fee-upkeep-ins;
  el.innerHTML=`<h3>Rent and yield</h3><div class="num">${dollars(mid)}<small style="font-size:16px;color:var(--muted)"> /mo</small></div>
    <p class="hint" style="margin:0">Likely range ${dollars(lo)} – ${dollars(hi)} for a ${beds===0?"studio":beds===3?"3-bedroom-or-larger":beds+"-bedroom"} ${condo?"condo":isHouse?"house":"home"} in ${esc(st.muni)}.</p>
    <div class="kv"><div><span>CMHC average, all occupied units</span><span>${dollars(pick)}/mo</span></div>
      <div><span>Gross yield</span><span>${(mid*12/v*100).toFixed(1)}%</span></div>
      <div><span>Cap rate (after 4% vacancy, tax, upkeep${condo?", fees":""})</span><span>${(noi/v*100).toFixed(1)}%</span></div>
      <div><span>Cash flow with 20% down at ${rate.toFixed(2)}%</span><span class="${cash>=0?"up":"down"}">${cash>=0?"+":"−"}${dollars(Math.abs(cash))}/mo</span></div>
      <div><span>Price-to-rent</span><span>${(v/(mid*12)).toFixed(1)} years</span></div></div>
    <p class="hint" style="margin:0">Source: ${esc(rsrc)}. New tenancies usually rent above the survey average, so the middle figure adds ${Math.round((mk-1)*100)}%. Tax ~0.9% of value a year, upkeep ${condo?"0.4":"1"}%${condo?", your condo fee":""} and insurance are assumed.</p>`;
  PLUS.rep.rent=`<div class="rp-sec"><b>Rent and yield</b><p>Likely rent ${dollars(mid)}/mo (${dollars(lo)} – ${dollars(hi)}); CMHC average ${dollars(pick)}/mo. Gross yield ${(mid*12/v*100).toFixed(1)}%, cap rate ${(noi/v*100).toFixed(1)}%, cash flow with 20% down ${cash>=0?"+":"−"}${dollars(Math.abs(cash))}/mo.</p></div>`;}
async function drawBuilding(){const el=$("pBldg"),it=aiProp&&aiProp.pick;el.hidden=true;PLUS.rep.bldg="";PLUS.units=null;
  if(!it||!it.fsa||!it.civic||!it.street)return;
  if(!DETIDX)DETIDX=getJSON("data/detail/index.json").catch(()=>({}));const idx=await DETIDX,file=Object.keys(idx).find(k=>idx[k].includes(it.fsa));if(!file)return;
  if(!DET[file])DET[file]=getJSON("data/detail/"+file+".json").catch(()=>({}));
  const d=((await DET[file])||{})[it.fsa]||{},c=normNum(it.civic),ty=stype(it.sname||""),me=normNum(it.unit||""),rows=[];
  for(const [k,v] of Object.entries(d)){const [u,cv,core,dir,kt]=k.split("|");if(!u||cv!==c||`${core}|${dir}`!==it.street||(kt||"")!==ty)continue;
    const h=decodeHistory(v[1]);if(!h.length)continue;const a=h[0],b=h[h.length-1];rows.push({u,v:b[1],y:b[0],ch:a[0]<b[0]?b[1]/a[1]-1:null,since:a[0],me:u===me});}
  if(rows.length<2)return;
  rows.sort((a,b)=>(parseInt(a.u,10)||0)-(parseInt(b.u,10)||0)||a.u.localeCompare(b.u));
  const vals=rows.map(r=>r.v),med=qtile(vals,.5),mine=rows.find(r=>r.me),rank=mine?Math.round(vals.filter(x=>x<mine.v).length/(vals.length-1||1)*100):null;
  const chs=rows.map(r=>r.ch).filter(x=>x!=null),chMed=chs.length?qtile(chs,.5):null,y=rows[0].y;PLUS.units=rows;
  el.hidden=false;el.innerHTML=`<div class="chart-top"><h3>Your building: ${rows.length} units on record</h3><div class="tools"><button type="button" id="bldgCsv">CSV</button></div></div>
    <div class="kv"><div><span>Median unit, ${y} roll</span><span>${money(med)}</span></div><div><span>Range</span><span>${money(Math.min(...vals))} – ${money(Math.max(...vals))}</span></div>
      ${mine?`<div><span>Your unit</span><span>${money(mine.v)} · above ${rank}% of units</span></div>`:""}
      ${chMed!=null?`<div><span>Typical change since ${rows[0].since}</span><span>${sgn(chMed)}</span></div>`:""}</div>
    <div class="tbl units"><table><thead><tr><th style="text-align:left">Unit</th><th>Assessed</th><th>vs median</th><th>Change</th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.me?"me":""}"><td style="text-align:left">${esc(r.u)}</td><td>${money(r.v)}</td><td>${sgn(r.v/med-1,0)}</td><td>${r.ch!=null?sgn(r.ch,0):"—"}</td></tr>`).join("")}</tbody></table></div>
    <p class="hint" style="margin:0">Every unit at this address in the city's open assessment roll, the free version of a condo-building comparables page.</p><div class="dl-msg"></div>`;
  $("bldgCsv").onclick=()=>plusSave(slug("building-"+$("addr").value)+".csv",toCSV([["Unit","Assessed","Roll year","Change since first roll","First roll"],...rows.map(r=>[r.u,r.v,r.y,r.ch!=null?Math.round(r.ch*1000)/10+"%":"",r.since])]));
  PLUS.rep.bldg=`<div class="rp-sec"><b>Your building</b><p>${rows.length} units on record; median ${money(med)}${mine?`; this unit ${money(mine.v)}, above ${rank}% of units`:""}.</p></div>`;}

/* ---------- equity, payoff and renewal (Homebot-style digest, no sign-up) ---------- */
function eqState(){const bal=+$("eqBal").value||+$("bal").value||0,rate=+$("eqRate").value||0,left=+$("eqLeft").value||25,mkt=+$("eqMkt").value||+$("rate").value||4.2,renew=$("eqRenew").value;
  return {bal,rate,left,mkt,renew};}
function drawEquity(){const v=lastV,S=eqState(),o=PLUS.out||outlook(cur().reg),out=$("eqOut");if(!v)return;
  const pm=pmtOf(S.bal,S.rate,S.left),eq=v-S.bal,ltv=S.bal/v,b12=balAfter(S.bal,S.rate,S.left,12),flags=[];
  if(S.renew){const [ry,rm]=S.renew.split("-").map(Number),days=Math.round((new Date(ry,rm-1,1)-new Date())/864e5),k=Math.max(0,Math.round(days/30.4)),
      atR=balAfter(S.bal,S.rate,S.left,k),yrsLeft=Math.max(1,S.left-k/12),nowP=pmtOf(atR,S.rate,yrsLeft),newP=pmtOf(atR,S.mkt,yrsLeft),diff=newP-nowP;
    if(days<0)flags.push(["","Your renewal date has passed. Check what rate you renewed at."]);
    else flags.push([diff<=0?"good":"",`Renewal in ${days} days (${monthName([ry,rm-1])}). At today's ${S.mkt.toFixed(2)}% your payment would be ${dollars(newP)}/mo, ${diff<=0?dollars(-diff)+" less":dollars(diff)+" more"} than now${days<=120?". Lenders let you hold a rate up to 120 days ahead, so you can lock one now.":"."}`]);}
  if(S.bal&&S.rate>S.mkt+.5)flags.push(["good",`Your rate is ${(S.rate-S.mkt).toFixed(2)} points above today's typical rate. Ask your lender about a blend-and-extend or the cost of breaking early.`]);
  if(S.bal&&ltv<.8)flags.push(["good",`You owe ${Math.round(ltv*100)}% of the value, so a refinance or home-equity line could free up to ${money(v*.8-S.bal)} (80% limit).`]);
  out.innerHTML=`<div class="kv"><div><span>Estimated value</span><span>${money(v)}</span></div><div><span>Equity today</span><span>${S.bal?money(eq)+" ("+Math.round(eq/v*100)+"%)":"add your balance"}</span></div>
    ${S.bal?`<div><span>Payment at ${S.rate.toFixed(2)}%, ${S.left} years left</span><span>${dollars(pm)}/mo</span></div>
    <div><span>Principal you'll pay off in 12 months</span><span>${money(S.bal-b12)}</span></div>
    <div><span>Equity in 12 months (typical year / weak / strong)</span><span>${money(v*o.mid1-b12)} / ${money(v*o.lo1-b12)} / ${money(v*o.hi1-b12)}</span></div>`:""}</div>
    ${flags.map(([c,t])=>`<div class="flag ${c}">${t}</div>`).join("")}`;
  const yrs=Math.min(30,Math.max(10,Math.ceil(S.left))),labels=[],val=[],bal=[],eqs=[];
  for(let y=0;y<=yrs;y++){labels.push(String(NOWM.getFullYear()+y));const vv=v*Math.pow(1+o.cagr,y),bb=balAfter(S.bal,S.rate,S.left,y*12);val.push(Math.round(vv));bal.push(Math.round(bb));eqs.push(Math.round(vv-bb));}
  render("xe",{kind:"line",labels,fmt:fmt$,sets:[{label:`Value at ${(o.cagr*100).toFixed(1)}%/yr (this region since 2016)`,data:val,color:css("--s1")},{label:"Mortgage balance",data:bal,color:css("--s2")},{label:"Equity",data:eqs,color:css("--s3")}]});
  PLUS.eq={S,pm,eq,b12,flags,labels,val,bal,eqs,o};}
let BOC_TRIED=false;
async function bankOfCanada(){if(BOC_TRIED)return;BOC_TRIED=true;   // free Bank of Canada Valet API; where the page can't reach it, the field keeps the page's rate
  try{const ctl=new AbortController();setTimeout(()=>ctl.abort(),5000);
    const r=await fetch("https://www.bankofcanada.ca/valet/observations/V80691335,V39079/json?recent=1",{signal:ctl.signal});const j=await r.json(),o=j.observations&&j.observations[0];
    if(o){PLUS.boc={posted:+(o.V80691335&&o.V80691335.v),policy:+(o.V39079&&o.V39079.v),d:o.d};
      $("eqBoc").textContent=`Bank of Canada, ${o.d}: policy rate ${PLUS.boc.policy}%, posted 5-year ${PLUS.boc.posted}% (most borrowers get well below posted).`;}}catch(e){}}

/* ---------- saved homes (this browser), tracked through the index ---------- */
const SV_KEY="hve-homes";
let SV_MEM=null;
function svLoad(){if(SV_MEM)return SV_MEM.map(x=>({...x}));try{const a=JSON.parse(localStorage.getItem(SV_KEY)||"[]");return Array.isArray(a)?a:[];}catch(e){return [];}}
function svStore(a){try{localStorage.setItem(SV_KEY,JSON.stringify(a));if(JSON.parse(localStorage.getItem(SV_KEY)).length===a.length){SV_MEM=null;return true;}}catch(e){}
  SV_MEM=a.map(x=>({...x}));return false;}
function svTracked(h){const reg=h.reg in IDX?h.reg:"GTA";return h.v*INOW(reg)/(h.i||INOW(reg));}
function spark(pts){if(pts.length<2)return "";const vs=pts.map(p=>p[1]),lo=Math.min(...vs),hi=Math.max(...vs)||1,W=120,H=28;
  const d=pts.map((p,i)=>`${i?"L":"M"}${(i/(pts.length-1)*(W-4)+2).toFixed(1)},${(H-3-(hi===lo?.5:(p[1]-lo)/(hi-lo))*(H-6)).toFixed(1)}`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true"><path d="${d}" fill="none" stroke="${css("--s1")}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;}
function drawSaved(){const a=svLoad(),box=$("saved");box.hidden=!a.length;if(!a.length)return;
  $("svList").innerHTML=a.map((h,i)=>{const t=svTracked(h),ch=t/h.v-1,pts=[...(h.snaps||[]),[today(),t]];
    return `<div class="sv"><div><div class="l">${esc(h.label)}</div><div class="m">Saved ${esc(h.d)} at ${money(h.v)} · now ${money(t)} <span class="${ch>=0?"up":"down"}">${sgn(ch)}</span>${h.bal?` · equity ${money(t-h.bal)}`:""}</div></div>
      <div class="act">${spark(pts)}<button type="button" data-sv-open="${i}">Open</button><button type="button" data-sv-del="${i}" aria-label="Remove ${esc(h.label)}">Remove</button></div></div>`;}).join("");}
function svUpsert(){if(!aiProp||!lastV)return null;const a=svLoad(),lbl=$("addr").value.trim(),reg=cur().reg,d=today();
  let h=a.find(x=>x.label===lbl);
  if(!h){h={label:lbl,prov:st.prov,muni:st.muni,reg,sub:st.sub,v:lastV,i:INOW(reg),d,snaps:[[d,lastV]]};a.unshift(h);}
  else{h.v=lastV;h.i=INOW(reg);h.sub=st.sub;h.snaps=(h.snaps||[]).filter(s=>s[0]!==d);h.snaps.push([d,lastV]);h.snaps=h.snaps.slice(-120);}
  const b=+$("eqBal").value||+$("bal").value;if(b)h.bal=b;svStore(a);return h;}
function svTouch(){const a=svLoad(),lbl=$("addr").value.trim(),h=a.find(x=>x.label===lbl);if(h&&lastV){svUpsert();drawSaved();}}
$("saveHome").addEventListener("click",()=>{const h=svUpsert();if(!h){plusMsg("Pick an address first.");return;}
  plusMsg(SV_MEM?`Saved for this visit only: this browser blocks storage. Use Backup in "My saved homes" to keep a copy.`:`Saved. ${h.label} is now tracked in "My saved homes" (this browser).`);drawSaved();});
$("svList").addEventListener("click",async e=>{const o=e.target.closest("[data-sv-open]"),d=e.target.closest("[data-sv-del]");
  if(d){const a=svLoad();a.splice(+d.dataset.svDel,1);svStore(a);drawSaved();return;}
  if(o){const h=svLoad()[+o.dataset.svOpen];if(!h)return;$("addr").value=h.label;$("addr").dispatchEvent(new Event("input",{bubbles:true}));
    if(h.bal)$("eqBal").value=h.bal;go(1);$("f").scrollIntoView({behavior:RM()?"auto":"smooth",block:"start"});
    if(await resolveTyped()){refresh();}}});
$("svCsv").addEventListener("click",()=>{const a=svLoad();if(!a.length)return;
  plusSave("my-saved-homes-"+today()+".csv",toCSV([["Address","Municipality","Province","Saved on","Value when saved","Tracked value today","Change","Mortgage balance"],...a.map(h=>[h.label,h.muni,h.prov,h.d,Math.round(h.v),Math.round(svTracked(h)),(Math.round((svTracked(h)/h.v-1)*1000)/10)+"%",h.bal||""])]));});
$("svBackup").addEventListener("click",()=>plusSave("my-saved-homes-"+today()+".json",JSON.stringify(svLoad(),null,1)));
$("svRestoreBtn").addEventListener("click",()=>$("svRestore").click());
$("svRestore").addEventListener("change",async e=>{const f=e.target.files[0];if(!f)return;try{const a=JSON.parse(await f.text());if(!Array.isArray(a))throw 0;
  const cur0=svLoad(),seen=new Set(cur0.map(h=>h.label)),add=a.filter(h=>h&&h.label&&Number.isFinite(+h.v)&&!seen.has(h.label)).map(h=>({label:String(h.label),prov:String(h.prov||""),muni:String(h.muni||""),reg:String(h.reg||"GTA"),sub:String(h.sub||"detached"),v:+h.v,i:+h.i||0,d:String(h.d||today()),snaps:Array.isArray(h.snaps)?h.snaps.filter(s=>Array.isArray(s)&&Number.isFinite(+s[1])).map(s=>[String(s[0]),+s[1]]):[],bal:+h.bal||0}));
  svStore([...cur0,...add]);drawSaved();PLUS_BTN=$("svRestoreBtn");plusMsg(`Restored ${add.length} home${add.length===1?"":"s"}.`);}catch(err){PLUS_BTN=$("svRestoreBtn");plusMsg("That file isn't a saved-homes backup.");}e.target.value="";});
drawSaved();

/* ---------- equity digest and reminder downloads ---------- */
let docShell=(title,body)=>`<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title>
<style>:root{--fg:#0b1a33;--muted:#56627a;--line:#d6dce8;--accent:#011f5b;--bg:#fff}@media (prefers-color-scheme:dark){:root{--fg:#e8edf7;--muted:#9aa8c2;--line:#26324d;--accent:#82afd3;--bg:#0b1324}}
body{font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--fg);background:var(--bg);max-width:760px;margin:0 auto;padding:24px 16px}h1,h2{color:var(--accent);line-height:1.2}h1{font-size:26px}
table{border-collapse:collapse;width:100%;margin:6px 0}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right;font-variant-numeric:tabular-nums}td:first-child,th:first-child{text-align:left}
.big,.rp-big{font-size:34px;font-weight:700;color:var(--accent)}.range{color:var(--muted)}.hint,.notice{color:var(--muted);font-size:13px}.rp-sec{border-top:1px solid var(--line);padding-top:10px;margin-top:12px}.rp-sec>b{display:block;margin-bottom:4px}
.rp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 16px}img{max-width:100%;border-radius:6px}.eyebrow{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
@media print{body{color:#000;background:#fff}}</style></head><body>${body}</body></html>`;
$("eqDigest").addEventListener("click",()=>{if(!PLUS.eq){plusMsg("Pick an address first.");return;}const E=PLUS.eq,S=E.S,adr=$("addr").value||st.muni,d=new Date().toLocaleDateString("en-CA",{year:"numeric",month:"long",day:"numeric"});
  const body=`<div class="eyebrow">Home equity digest · ${d}</div><h1>${esc(adr)}</h1><div class="big">${money(lastV)}</div><p class="hint">Estimated value (${esc($("rRange").textContent)}). ${PLUS.conf?`Confidence ${PLUS.conf.score}/100.`:""}</p>
  <div class="rp-sec"><b>Your equity</b><table><tr><td>Mortgage balance</td><td>${S.bal?money(S.bal):"—"}</td></tr><tr><td>Equity today</td><td>${S.bal?money(E.eq):"—"}</td></tr>
  ${S.bal?`<tr><td>Payment at ${S.rate.toFixed(2)}%</td><td>${dollars(E.pm)}/mo</td></tr><tr><td>Principal paid off over the next 12 months</td><td>${money(S.bal-E.b12)}</td></tr>
  <tr><td>Equity in 12 months (typical / weak / strong year)</td><td>${money(lastV*E.o.mid1-E.b12)} / ${money(lastV*E.o.lo1-E.b12)} / ${money(lastV*E.o.hi1-E.b12)}</td></tr>`:""}</table></div>
  ${E.flags.length?`<div class="rp-sec"><b>Worth a look</b><ul>${E.flags.map(f=>`<li>${f[1]}</li>`).join("")}</ul></div>`:""}
  <div class="rp-sec"><b>Value, balance and equity by year</b><table><tr><th>Year</th><th>Value</th><th>Balance</th><th>Equity</th></tr>${E.labels.map((y,i)=>`<tr><td>${y}</td><td>${money(E.val[i])}</td><td>${money(E.bal[i])}</td><td>${money(E.eqs[i])}</td></tr>`).join("")}</table>
  <p class="hint">Value grows at ${(E.o.cagr*100).toFixed(1)}% a year, the ${REGION_NAME[cur().reg]} average since 2016. Not a forecast.</p></div>
  ${PLUS.rep.rent||""}${PLUS.rep.out||""}
  <p class="notice">Indicative only; not an appraisal or financial advice. From public assessment records, the 2021 Census, CMHC rents and published regional benchmarks. Open Benchmark Home Value again next month for a fresh digest.</p>`;
  plusSave("equity-digest-"+slug(adr)+"-"+today()+".html",docShell("Home equity digest — "+adr,body));});
$("eqIcs").addEventListener("click",()=>{const adr=$("addr").value||st.muni,n=new Date(),dt=x=>x.toISOString().replace(/[-:]/g,"").slice(0,15)+"Z",
  start=new Date(n.getFullYear(),n.getMonth()+1,1,9,0,0),day=start.toISOString().slice(0,10).replace(/-/g,""),uid="hve-"+slug(adr)+"-"+Date.now()+"@benchmark-home-value";
  const ics=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Benchmark Home Value//EN","BEGIN:VEVENT","UID:"+uid,"DTSTAMP:"+dt(n),"DTSTART;VALUE=DATE:"+day,"RRULE:FREQ=MONTHLY",
    "SUMMARY:Check my home value and equity","DESCRIPTION:Open Benchmark Home Value and pick "+adr.replace(/[,;\\]/g," ")+" for this month's value\\, equity and renewal check.","END:VEVENT","END:VCALENDAR"].join("\r\n")+"\r\n";
  plusSave("home-value-reminder.ics",ics);});

/* ---------- report: extend the printable report and offer it as a file ---------- */
const _buildReport=buildReport;
buildReport=async function(){await _buildReport();const rep=$("report"),n=rep.querySelector(".notice");
  const extra=["conf","vals","hist","out","rent","bldg"].map(k=>PLUS.rep[k]||"").join("");if(n)n.insertAdjacentHTML("beforebegin",extra);else rep.insertAdjacentHTML("beforeend",extra);};
$("dlReport").addEventListener("click",async()=>{if(!aiProp){plusMsg("Pick an address first.");return;}plusMsg("Building the report…");
  await buildReport();const rep=$("report").cloneNode(true);
  rep.querySelectorAll("canvas").forEach((c,i)=>{const src=$("report").querySelectorAll("canvas")[i];let u="";try{u=src.toDataURL("image/png");}catch(e){}
    if(u&&u.length>2000){const im=document.createElement("img");im.src=u;im.alt="Assessment history chart";c.parentNode.removeAttribute("style");c.replaceWith(im);}
    else{const par=c.parentNode;c.remove();if(par&&par.getAttribute("style")&&!par.children.length)par.remove();}});
  rep.querySelectorAll(".leaflet-container,#rpMap").forEach(x=>x.remove());
  // add the value-history chart picture when it has drawn
  const ch=charts.xh;if(ch){try{const u=ch.canvas.toDataURL("image/png");rep.insertAdjacentHTML("beforeend",`<div class="rp-sec"><b>Value history</b><img src="${u}" alt="Value history chart"></div>`);}catch(e){}}
  const adr=$("addr").value||st.muni;await plusSave("home-value-report-"+slug(adr)+"-"+today()+".html",docShell("Home value report — "+adr,rep.innerHTML));});

/* ---------- calculators (no address) ---------- */
function calcPaid(){const m=M[+$("ccMuni").value]||cur(),price=+$("ccPrice").value||0,w=$("ccWhen").value,out=$("ccOut");
  if(!(price>0)||!/^\d{4}-\d{2}$/.test(w)){out.innerHTML=`<p class="hint">Enter a price and month.</p>`;return;}
  const [y,mo]=w.split("-").map(Number),A=IDXA(m.reg),now=A[A.length-1],then=idxAtPage(m.reg,m.prov,y,mo-1),val=price*now/then,yrs=Math.max(1/12,(NOWM-new Date(y,mo-1,1))/31557600000);
  const g=G_PRE[m.prov]||.035,early=mi(y,mo-1)<0;
  out.innerHTML=`<div class="num">${money(val)}</div><div class="kv"><div><span>Change since ${monthName([y,mo-1])}</span><span class="${val>=price?"up":"down"}">${val>=price?"+":"−"}${money(Math.abs(val-price))} (${sgn(val/price-1)})</span></div>
    <div><span>Per year</span><span>${sgn(Math.pow(val/price,1/yrs)-1)}</span></div><div><span>Index used</span><span>${REGION_NAME[m.reg]}</span></div></div>
    <p class="hint" style="margin:0">Value today = price × (index now ÷ index when bought), the same method as the US government's FHFA calculator.${early?` Before 2016 the index is extended back at ${(g*100).toFixed(1)}% a year, so older purchases are rougher.`:""} It assumes your home moved with the region; renovations, condition and street can push it either way.</p>`;
  const i0=Math.max(0,mi(y,mo-1)),lab=MONTHS.slice(i0).map(label),path=A.slice(i0).map(x=>Math.round(price*x/then));
  $("xcsub").textContent=`${money(price)} in ${monthName([y,mo-1])}, ${esc(m.name)} (${REGION_NAME[m.reg]}). Monthly to ${label(NOWM)}.`;
  render("xc",{kind:"line",labels:lab,fmt:fmt$,sets:[{label:"Your home through the index",data:path,color:css("--s1")}]});}
function calcAssess(fromYear){const m=M[+$("caMuni").value]||cur(),val=+$("caVal").value||0,y=+$("caYear").value,out=$("caOut");
  if(fromYear||!$("caDate").value){const d=valDate(m.prov,y);$("caDate").value=`${d[0]}-${String(d[1]+1).padStart(2,"0")}`;}
  const [dy,dm]=$("caDate").value.split("-").map(Number);if(!(val>0)||!dy){out.innerHTML="";return;}
  const now=INOW(m.reg),then=idxAtPage(m.reg,m.prov,dy,dm-1),v=val*now/then;
  const lag=m.prov==="ON"?"Ontario has not reassessed since 2016, so the gap is large; use the result as a rough anchor.":"";
  out.innerHTML=`<div class="num">${money(v)}</div><div class="kv"><div><span>Assessed value, as of ${monthName([dy,dm-1])}</span><span>${money(val)}</span></div>
    <div><span>Regional index since then</span><span>${sgn(now/then-1)}</span></div><div><span>Likely market range today (±10%)</span><span>${money(v*.9)} – ${money(v*1.1)}</span></div></div>
    <p class="hint" style="margin:0">Assessments usually land within 5–10% of market value on their valuation date. ${lag} In this page's backtest, the index alone moved assessments within 10% of the next roll ${typeof BT!=="undefined"&&BT.data?Math.round(BT.data.groups.All.methods.index.w10*100):67}% of the time.</p>`;}
(function(){const ci=String(M.indexOf(cur()));$("ccMuni").value=ci;$("caMuni").value=ci;
  ["ccMuni","ccPrice","ccWhen"].forEach(id=>$(id).addEventListener("input",calcPaid));
  $("caYear").addEventListener("input",()=>calcAssess(true));$("caMuni").addEventListener("input",()=>calcAssess(true));
  ["caVal","caDate"].forEach(id=>$(id).addEventListener("input",()=>calcAssess(false)));
  calcAssess(true);try{calcPaid();}catch(e){}})();

/* ---------- wiring: redraw after every estimate ---------- */
function updatePlus(){const box=$("plus");if(!aiProp||!lastV){box.hidden=true;$("rConf").textContent="";return;}
  box.hidden=false;if(!$("eqMkt").value)$("eqMkt").value=$("rate").value||"4.20";
  if(!$("eqBal").value&&$("bal").value)$("eqBal").value=$("bal").value;
  for(const f of [drawConf,drawVals,drawHistory,drawOutlook,drawEquity])try{f();}catch(e){console.warn(f.name,e);}
  drawRent().catch(()=>{});const lbl=$("addr").value.trim();if(lbl!==PLUS.lastLbl){PLUS.lastLbl=lbl;drawBuilding().catch(()=>{});svTouch();}
  if(!$("eqMkt").value)$("eqMkt").value=(RATES&&RATES.length?RATES[RATES.length-1]:4.2).toFixed(2);
  bankOfCanada();}
function schedulePlus(){clearTimeout(PLUS.t);PLUS.t=setTimeout(updatePlus,120);}
$("beds").addEventListener("change",e=>{if(e.isTrusted)$("beds").dataset.touched="1";});
const _estPlus=estimate;estimate=function(){_estPlus();schedulePlus();};
const _instPlus=renderInstant;renderInstant=function(){_instPlus();if(aiProp&&$("instant")&&!$("instant").hidden){try{const c=confidence();
  $("instant").insertAdjacentHTML("beforeend",`<div class="hint">Confidence <b style="font-family:var(--mono)">${c.score}/100</b> (${confWord(c.score)}) · <a href="#plus">rent, history, 2-year range and more ↓</a></div>`);}catch(e){}}};
["eqBal","eqRate","eqLeft","eqRenew","eqMkt"].forEach(id=>$(id).addEventListener("input",()=>{try{drawEquity();}catch(e){}}));
$("eqBal").addEventListener("change",()=>{if($("eqBal").value){$("bal").value=$("eqBal").value;extras();}});
$("bal").addEventListener("input",()=>{$("eqBal").value=$("bal").value;});
$("addr").addEventListener("input",()=>{if(!aiProp){$("plus").hidden=true;$("rConf").textContent="";}});
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change",schedulePlus);
new MutationObserver(()=>{schedulePlus();try{calcPaid();}catch(e){}}).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
addEventListener("resize",()=>{clearTimeout(PLUS.rz);PLUS.rz=setTimeout(()=>{schedulePlus();try{calcPaid();}catch(e){}},250);});
