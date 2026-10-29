/* ---- Insights: what can be built on the lot, neighbourhood profile, zoning, commercial flag, Google Map ----
   All from free public sources: provincial/municipal housing law (2023-2025), municipal zoning in open data, CMHC rents
   (StatCan 34-10-0133), 2021 Census block profiles, StatCan address register building-use codes. */
(function(){
  const css=`.ins{display:grid;gap:10px}.ins h4{margin:0;font:600 14px var(--body);color:var(--accent)}
  .badge{display:inline-block;font:600 12px var(--body);padding:3px 10px;border-radius:999px;background:color-mix(in srgb,var(--accent-2) 14%,transparent);color:var(--accent-2)}
  .prof{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 14px;font-size:13px}
  @media (max-width:480px){.prof{grid-template-columns:minmax(0,1fr)}}
  .pbar{height:5px;border-radius:9px;background:var(--line);overflow:hidden;margin-top:3px}.pbar i{display:block;height:100%;background:var(--accent)}
  .build{border:1px solid var(--line);border-radius:10px;padding:12px;background:color-mix(in srgb,var(--good) 7%,var(--surface))}
  .build .num{font:600 26px var(--display);color:var(--good)}
  #gmap{width:100%;height:240px;border:0;border-radius:8px}`;
  const s=document.createElement("style");s.textContent=css;document.head.appendChild(s);
  const box=document.createElement("div");box.id="insights";box.className="ins";box.hidden=true;
  $("facts").after(box);
})();

const INS={rents:null,prof:{},profca:null,nonres:{},recent:null};
const dollars=v=>"$"+Math.round(v).toLocaleString("en-CA");   // exact, for rents and monthly costs
const fmtPct=v=>v==null?"—":Math.round(v)+"%";
/* units allowed on a typical residential lot (main home included), from provincial law and municipal by-laws */
const BUILD_RULES={
  ON:{n:3,why:"Ontario's More Homes Built Faster Act (2022) allows 3 units on most urban residential lots (main home + 2 additional units)."},
  BC:{n:4,why:"BC's small-scale multi-unit housing law (Bill 44, 2023) allows 3–4 units on most single-family lots in municipalities over 5,000 people, and up to 6 near frequent transit."},
  AB:{n:2,why:"Alberta municipalities generally allow a secondary or backyard suite."},
  QC:{n:2,why:"Québec's Bill 31 (2024) lets municipalities allow an accessory dwelling unit; many now do."},
  MB:{n:2,why:"Most Manitoba municipalities allow a secondary suite."},SK:{n:2,why:"Most Saskatchewan municipalities allow a secondary or garden suite."},
  NS:{n:2,why:"Most Nova Scotia municipalities allow a secondary or backyard suite."},NB:{n:2,why:"Most New Brunswick municipalities allow a secondary suite."},
  NL:{n:2,why:"Most municipalities allow a secondary suite."},PE:{n:2,why:"Most municipalities allow a secondary suite."},
  YT:{n:2,why:"Garden and secondary suites are generally allowed."},NT:{n:2,why:"Secondary suites are generally allowed."},NU:{n:2,why:"Secondary suites may be allowed; check with the municipality."}};
const CITY_RULES={ // municipalities that adopted more permissive by-laws (Housing Accelerator Fund agreements and city reforms)
  "ON|TORONTO":{n:4,why:"Toronto allows multiplexes of up to 4 units on residential lots city-wide (2023), and up to 6 in parts of Toronto and East York."},
  "ON|OTTAWA":{n:4,why:"Ottawa allows up to 4 units on residential lots under its Housing Accelerator commitments."},
  "ON|MISSISSAUGA":{n:4,why:"Mississauga permits up to 4 units on residential lots (2024)."},
  "ON|HAMILTON":{n:4,why:"Hamilton permits up to 4 units on residential lots."},"ON|LONDON":{n:4,why:"London permits up to 4 units on residential lots."},
  "ON|KITCHENER":{n:4,why:"Kitchener permits up to 4 units on residential lots."},
  "AB|CALGARY":{n:4,why:"Calgary's 2024 city-wide rezoning (R-CG) allows rowhouses and townhomes of about 4 homes, each with a secondary suite."},
  "AB|EDMONTON":{n:8,why:"Edmonton's 2024 zoning bylaw allows up to 8 units on most mid-block residential lots (RS zone)."},
  "MB|WINNIPEG":{n:4,why:"Winnipeg allows up to 4 units on residential lots under its Housing Accelerator agreement."},
  "SK|SASKATOON":{n:4,why:"Saskatoon allows up to 4 units on residential lots."},"SK|REGINA":{n:4,why:"Regina allows up to 4 units on residential lots."},
  "NS|HALIFAX":{n:4,why:"Halifax allows up to 4 units on residential lots across most of the municipality (2024)."},
  "NB|MONCTON":{n:4,why:"Moncton allows up to 4 units on residential lots."},"NB|FREDERICTON":{n:4,why:"Fredericton allows up to 4 units on residential lots."},
  "BC|VANCOUVER":{n:6,why:"Vancouver's multiplex zoning (2023) allows up to 6 units on most residential lots (8 for rental)."},
  "BC|VICTORIA":{n:6,why:"Victoria's missing-middle policy and Bill 44 allow up to 6 units on many residential lots."}};
function zoningMeaning(z){if(!z)return null;const u=z.toUpperCase();
  if(/^(C|CC|CB|CR|CS|CD-|DC|M[A-Z]?\b|I|IL|IG|IH|IB)/.test(u)&&!/^CD-1/.test(u))return "commercial, mixed-use or industrial zone";
  if(/R-CG|RCG|RS\b|^RT|^RM|^RF[3-5]|^RA|M-C|M-G|RH|R2|R3|R4|RIL|RSL/.test(u))return "residential zone that allows more than one home";
  if(/^R|^RF[12]|^R1|^RS[1-9]|^R-C1|^R-1/.test(u))return "low-density residential zone";
  if(/^A|^AG|^RR|^RU/.test(u))return "agricultural or rural zone";
  return null;}
async function rentsFor(prov,muni){if(!INS.rents)INS.rents=getJSON("data/rents.json").catch(()=>({}));const r=await INS.rents;
  return r[`${prov}|${plain(muni)}`]||r[`${prov}|${plain(muni).split(" ")[0]}`]||r[`${prov}|*`]||null;}
async function profileFor(da){if(!da)return null;const pr=da.slice(0,2);
  if(!INS.prof[pr])INS.prof[pr]=getJSON("data/prof_"+pr+".json").catch(()=>({}));
  if(!INS.profca)INS.profca=getJSON("data/prof_ca.json").catch(()=>null);
  return (await INS.prof[pr])[da]||null;}
async function isNonRes(it){if(!it||!it.fsa)return false;const L=it.fsa[0];
  if(!INS.nonres[L])INS.nonres[L]=getJSON("data/nonres/"+L+".json").catch(()=>({}));
  const d=((await INS.nonres[L])[it.fsa])||{},list=(d[it.street]||"").split(" ");
  return list.includes(it.unit?`${it.unit}/${it.civic}`:it.civic);}

const SCH={};
async function schoolsNear(prov,ll){if(!ll)return [];const [la,lo]=ll.split(",").map(Number);
  if(!(prov in SCH))SCH[prov]=getJSON("data/schools_"+prov+".json").catch(()=>[]);const all=await SCH[prov];
  const km=(a,b)=>{const r=Math.PI/180,x=(b[1]-lo)*r*Math.cos(la*r),y=(b[0]-la)*r;return 6371*Math.hypot(x,y);};
  const d=all.map(s=>Object.assign([...s],{d:km(0,[s[1],s[2]])})).filter(s=>s.d<15).sort((a,b)=>a.d-b.d);
  return [...d.filter(s=>s[3]!=="S").slice(0,3),...d.filter(s=>s[3]!=="E").slice(0,2)].filter((s,i,a)=>a.indexOf(s)===i).sort((a,b)=>a.d-b.d);}
async function insights(it){const box=$("insights");if(!it||!it.postal){box.hidden=true;return;}
  const prov=provOf(it.fsa)||st.prov,muni=st.muni,det=aiProp.detail||null,zone=det&&det[2]||null,zmean=zoningMeaning(zone);
  const nonres=await isNonRes(it),condo=isCondo(st.sub)||!!it.unit;
  const [rent,prof]=await Promise.all([rentsFor(prov,muni),profileFor(it.da)]);
  const parts=[];let buildPart="";
  if(nonres||(zmean&&/commercial|industrial/.test(zmean)))parts.push(`<div><span class="badge">${nonres?"Non-residential or commercial building":"Commercial / mixed-use zoning"}</span>
    <p class="hint">${nonres?"Statistics Canada's address register marks this address as non-residential. ":""}Residential value models fit it less well; a commercial appraisal or income approach is more reliable.</p></div>`);
  if(zone)parts.push(`<div><h4>Zoning: ${esc(zone)}</h4><p class="hint">${zmean?esc(zmean[0].toUpperCase()+zmean.slice(1))+". ":""}From the city's open property data. Check the full by-law before building.</p></div>`);
  // what can be built
  if(!condo&&!nonres){const rule=CITY_RULES[`${prov}|${plain(muni)}`]||BUILD_RULES[prov]||BUILD_RULES.ON;
    let n=rule.n;if(zmean&&/more than one home/.test(zmean))n=Math.max(n,3);if(zmean&&/agricultural/.test(zmean))n=2;
    const add=Math.max(1,n-1),r1=rent&&rent[1]||1200,r2=rent&&rent[2]||1500;
    const unitRent=add<=2?r1:r2,gross=add*unitRent*12,net=gross*.7,valueAdd=net/.05;
    const cost=add===1?[120000,180000]:[add*250000,add*350000],lo=Math.max(0,valueAdd-cost[1]),hi=Math.max(0,valueAdd-cost[0]);
    buildPart=(`<div class="build"><h4>What can I build here?</h4>
      <div class="num">Up to ${n} home${n>1?"s":""} on this lot</div>
      <p class="hint">${typeof LANG!=="undefined"&&LANG==="fr"?`Selon la loi provinciale et les règlements municipaux récents, jusqu’à ${n} logements sont permis sur ce type de terrain résidentiel.`:esc(rule.why)}</p>
      <div class="adj"><div><span>Added units</span><span>${add}</span></div>
      <div><span>Typical rent per unit (CMHC ${rent?"2025":"estimate"})</span><span>${dollars(unitRent)}/mo</span></div>
      <div><span>Potential rent income</span><span>${money(gross)}/yr</span></div>
      <div><span>Value of that income (5% cap rate, 30% costs)</span><span>${money(valueAdd)}</span></div>
      <div><span>Typical build cost</span><span>${money(cost[0])} – ${money(cost[1])}</span></div>
      <div><span>Possible equity created</span><span>${money(lo)} – ${money(hi)}</span></div></div>
      <p class="hint">Financing: Canada's Secondary Suite Refinance Program (2025) allows refinancing up to 90% of the finished value with a 30-year amortization to add a suite; multiplexes of 5+ units can use CMHC MLI Select. Estimates only; confirm zoning, servicing, permits and costs.</p></div>`);}
  // neighbourhood profile
  const ca=await INS.profca;
  if(prof&&prof.length){const v=prof,F=["pop","growth","age","inc","own","sfd","apt","old","new","ocost","rcost","bach","unemp","transit","lowinc"],i=k=>F.indexOf(k);
    const rk=F.map((f,j)=>{const P=ca&&ca.pct&&ca.pct[f];if(!P||v[j]==null)return null;let n=0;while(n<P.length&&P[n]<=v[j])n++;return Math.max(0,Math.min(100,(n-1)*5));});
    const row=(label,val,rank)=>`<div><span class="hint">${label}</span><br><b>${val}</b>${rank!=null?`<div class="pbar" title="Higher than ${rank}% of Canadian neighbourhoods"><i style="width:${rank}%"></i></div>`:""}</div>`;
    parts.push(`<div><h4>Your neighbourhood (2021 Census block ${esc(it.da)})</h4><div class="prof">
      ${row("Median household income",v[i("inc")]!=null?money(v[i("inc")]):"—",rk[i("inc")])}
      ${row("Homeowners",fmtPct(v[i("own")]),rk[i("own")])}
      ${row("Population growth 2016–21",v[i("growth")]!=null?(v[i("growth")]>0?"+":"")+v[i("growth")]+"%":"—",rk[i("growth")])}
      ${row("Median age",v[i("age")]??"—",rk[i("age")])}
      ${row("University degree",fmtPct(v[i("bach")]),rk[i("bach")])}
      ${row("Commute by transit",fmtPct(v[i("transit")]),rk[i("transit")])}
      ${row("Detached houses",fmtPct(v[i("sfd")]),rk[i("sfd")])}
      ${row("Homes built before 1961",fmtPct(v[i("old")]),rk[i("old")])}
      ${row("Owner monthly costs",v[i("ocost")]!=null?dollars(v[i("ocost")]):"—",rk[i("ocost")])}
      ${row("Renter monthly costs",v[i("rcost")]!=null?dollars(v[i("rcost")]):"—",rk[i("rcost")])}</div>
      <p class="hint">Bars show how this block compares with all Canadian neighbourhoods.</p></div>`);}
  // newer than the Census: municipal population (StatCan July 1 estimates) and the local job market (Labour Force Survey)
  if(!INS.recent)INS.recent=getJSON("data/recent.json").catch(()=>null);const rec=await INS.recent;const rm=rec&&rec.muni&&rec.muni[`${muni}|${prov}`];
  if(rm){const jb=rec.jobs[rm[3]]||rec.jobs[prov],gr=((rm[1]/rm[0]-1)*100).toFixed(1),mo=jb?new Date(jb[0]+"-15").toLocaleDateString("en-CA",{month:"long",year:"numeric"}):"";
    parts.push(`<div><h4>${esc(muni)} today</h4><div class="prof">
      <div><span class="hint">Population ${rm[2]}</span><br><b>${rm[1].toLocaleString("en-CA")}</b></div>
      <div><span class="hint">Growth since 2021</span><br><b>${gr>0?"+":""}${gr}%</b></div>
      ${jb?`<div><span class="hint">Unemployment, ${esc(mo)} (${esc(rec.jobs[rm[3]]?rm[3]+" area":prov)})</span><br><b>${jb[1]}%</b>${jb[2]!=null?` <small class="hint">${jb[1]<=jb[2]?"down":"up"} from ${jb[2]}% a year earlier</small>`:""}</div>`:""}</div>
      <p class="hint">Statistics Canada population estimates (July 1, ${rm[2]}) and Labour Force Survey (3-month average). Updated automatically as new releases come out.</p></div>`);}
  // schools: the closest elementary and secondary schools, with Ontario EQAO placement by year
  const sch=await schoolsNear(prov,it.ll);
  if(sch.length)parts.push(`<div><h4>Nearby schools</h4><div class="schools">${sch.map(x=>{const h=Object.entries(x[7]||{}),last=h[h.length-1];
      return `<div class="sch"><div><b>${esc(x[0])}</b> <small class="hint">${x[3]==="E"?"Elementary":x[3]==="S"?"Secondary":"K–12"}${x[6]?" · "+esc(x[6]):""} · ${esc(x[4])} · ${x.d<1?Math.round(x.d*1000)+" m":x.d.toFixed(1)+" km"}</small></div>
        ${last?`<div class="hint">Better than <b>${last[1][1]}%</b> of Ontario ${x[3]==="S"?"secondary":"elementary"} schools in ${last[0]} (${last[1][0]}% of students at the provincial standard)</div>
        <div class="rank-trend">${h.map(([y,[sc,rk]])=>`<span title="${y}: ${sc}% at standard"><i style="height:${Math.max(4,rk*.36)}px"></i><small>${y.slice(2)}</small></span>`).join("")}</div>`:""}</div>`;}).join("")}</div>
    <p class="hint">Closest schools by distance; your assigned school depends on the board's boundary, so confirm with ${sch[0][5]?esc(sch[0][5]):"the school board"}. ${prov==="ON"?"Placement from Ontario's EQAO results (data.ontario.ca), refreshed each school year; bars show the yearly rank, 2019–21 skipped while testing paused.":"School list from Statistics Canada's Open Database of Educational Facilities."}</p></div>`);
  if(buildPart)parts.push(buildPart);
  box.innerHTML=parts.join("");box.hidden=!parts.length;
  // free street-level photos from Mapillary (free token, no credit card) when HVE_CONFIG.mapillaryToken is set
  const [la,lo]=(it.ll||"").split(","),tok=(window.HVE_CONFIG||{}).mapillaryToken;
  if(tok&&la){try{const u=`https://graph.mapillary.com/images?access_token=${encodeURIComponent(tok)}&fields=id,thumb_1024_url,captured_at&lng=${lo}&lat=${la}&radius=60&limit=3`;
    const r=await fetch(u);const j=await r.json();const imgs=(j.data||[]).filter(x=>x.thumb_1024_url);
    if(imgs.length){box.insertAdjacentHTML("afterbegin",`<div><h4>Street photos near this address</h4><div style="display:grid;grid-template-columns:repeat(${Math.min(3,imgs.length)},1fr);gap:6px">${imgs.map(x=>`<a href="https://www.mapillary.com/app/?pKey=${x.id}" target="_blank" rel="noopener"><img src="${x.thumb_1024_url}" alt="Street photo near this address" style="width:100%;border-radius:6px"></a>`).join("")}</div><p class="hint">Photos: Mapillary contributors (CC BY-SA)${imgs[0].captured_at?", taken "+new Date(imgs[0].captured_at).getFullYear():""}.</p></div>`);box.hidden=false;}}catch(e){}}}
const _pickIns=pick;
pick=async function(it){await _pickIns(it);try{await insights(it);}catch(e){}};
