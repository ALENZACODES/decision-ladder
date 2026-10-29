
/* ======================= Round 5: building permits at this address (City of Toronto open data, live), so a renovation
   the city knows about can be added to the estimate; links for other cities. Falls back to a link when unreachable. ======================= */
const TOR_PERMITS="https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search";
const TOR_PERMITS_RES="6d0229af-bc54-46de-9c2b-26759b01dd05";
const PERMIT_LINKS={"Toronto":["City of Toronto building permits (open data)","https://open.toronto.ca/dataset/building-permits-active-permits/"],
  "Vancouver":["City of Vancouver issued building permits (open data)","https://opendata.vancouver.ca/explore/dataset/issued-building-permits/"]};
async function torontoPermits(it){const civic=String(it.civic||"").trim(),fsa=it.fsa;if(!civic||!fsa)return null;
  const word=(plain(it.sname||"").split(/\s+/).filter(w=>w&&!TYPEWORDS.has(w)&&!(w in DIRS))[0])||"";
  const u=`${TOR_PERMITS}?resource_id=${TOR_PERMITS_RES}&limit=100&filters=${encodeURIComponent(JSON.stringify({STREET_NUM:civic,POSTAL:fsa}))}`;
  let j=null;try{j=await (await fetchT(u,8000)).json();}catch(e){}
  if((!j||!j.success)&&ON_LOCAL)try{j=await (await fetchT(u.replace(TOR_PERMITS,"/proxy/ckan"),30000)).json();}catch(e){}
  if(!j||!j.success)throw new Error("bad");
  return (j.result.records||[]).filter(x=>!word||plain(x.STREET_NAME||"").includes(word.replace(/^SAINT$/,"ST"))||plain(x.STREET_NAME||"").includes(word));}
async function drawPermits(){PLUS.permitAdd=0;const el=$("pPermit"),it=(aiProp||{}).pick||{},muni=st.muni,link=PERMIT_LINKS[muni];el.hidden=false;
  if(muni!=="Toronto"){el.innerHTML=`<h3>Permits at this address</h3><p class="hint" style="margin:0">Building permits show renovations, additions and new suites that raise value. ${link?"This city publishes them as open data:":"Ask the city's building department, or check its open-data site, for permits at this address."}</p>${link?`<div class="linklist"><a href="${link[1]}" target="_blank" rel="noopener">${esc(link[0])} ↗</a></div>`:""}`;PLUS.rep.permit="";return;}
  el.innerHTML=`<h3>Permits at this address</h3><p class="hint">Checking City of Toronto permits…</p>`;const my=PLUS.permSeq=(PLUS.permSeq||0)+1;
  let recs=null;try{recs=await torontoPermits(it);}catch(e){recs=null;}if(my!==PLUS.permSeq)return;
  if(recs==null){el.innerHTML=`<h3>Permits at this address</h3><p class="hint" style="margin:0">The City of Toronto permit data couldn't be reached from this page (the downloaded app can reach it).</p><div class="linklist"><a href="${PERMIT_LINKS.Toronto[1]}" target="_blank" rel="noopener">${esc(PERMIT_LINKS.Toronto[0])} ↗</a></div>`;return;}
  const cost=x=>{const n=parseFloat(String(x.EST_CONST_COST||"").replace(/[^\d.]/g,""));return Number.isFinite(n)&&n>0?n:0;};
  const isNew=x=>/new building|new house|new sfd|new dwelling/i.test(`${x.WORK} ${x.PERMIT_TYPE}`);
  const builds=recs.filter(isNew),newYear=builds.length?String(builds.map(x=>x.ISSUED_DATE||x.APPLICATION_DATE||"").sort().pop()).slice(0,4):"";
  const reno=recs.filter(x=>!isNew(x)&&/addition|alteration|renovat|suite|basement|deck|garage|interior|second unit|laneway|garden suite/i.test(`${x.WORK} ${x.DESCRIPTION} ${x.PERMIT_TYPE}`)&&cost(x)>0);
  const total=reno.reduce((s,x)=>s+cost(x),0);
  recs.sort((a,b)=>String(b.ISSUED_DATE||b.APPLICATION_DATE||"").localeCompare(String(a.ISSUED_DATE||a.APPLICATION_DATE||"")));
  el.innerHTML=`<h3>Permits at this address</h3>${recs.length?`<div class="kv">${recs.slice(0,8).map(x=>`<div><span>${esc((x.ISSUED_DATE||x.APPLICATION_DATE||"").slice(0,10))} · ${esc(x.WORK||x.PERMIT_TYPE||"Permit")}${x.STATUS?` · ${esc(x.STATUS)}`:""}</span><span>${cost(x)?dollars(cost(x)):"—"}</span></div>`).join("")}</div>
    ${builds.length?`<div class="flag good">A new building permit was issued here${newYear?` in ${esc(newYear)}`:""}: this may be a newly built home, which neighbourhood-level figures treat like an older one. <button type="button" class="ghost" id="permitNew" style="padding:4px 10px;font-size:13px;min-height:32px">Treat it as a new home</button></div>`:""}
    ${total?`<div class="flag good">The city lists about ${dollars(total)} of renovation work here. <button type="button" class="ghost" id="permitUse" style="padding:4px 10px;font-size:13px;min-height:32px">Add it to my estimate</button></div>`:""}`:`<p class="hint" style="margin:0">No active permits at this address in the City of Toronto's open data.</p>`}
    <p class="hint" style="margin:0">City of Toronto active building permits (open data, live). Renovation value is counted at 60% of its cost, the same as the renovation answer in step 2.</p><div class="dl-msg"></div>`;
  if(builds.length)$("permitNew").onclick=()=>{PLUS_BTN=$("permitNew");$("cond").value="1.1";$("cond").dispatchEvent(new Event("change"));estimate();extras();plusMsg("Condition set to new / fully renovated. Change it in step 2 if that's not right.");};
  if(total)$("permitUse").onclick=()=>{PLUS_BTN=$("permitUse");
    if(+$("pp").value&&$("pd").value){$("reno").value=Math.round(total);PLUS.permitAdd=0;}else PLUS.permitAdd=total*.6;   // with a purchase price, it joins the renovation answer; otherwise it's added directly
    estimate();extras();plusMsg(`Added ${dollars(total)} of permitted work (counted at 60%).`);};
  PLUS.rep.permit=recs.length?`<div class="rp-sec"><b>Permits at this address</b><p>${recs.length} City of Toronto permit${recs.length>1?"s":""} on record${builds.length?`, including a new building permit${newYear?` (${esc(newYear)})`:""}`:""}${total?`, about ${dollars(total)} of renovation work`:""}.</p></div>`:"";}
{const _estPermit=estimate;estimate=function(){_estPermit();try{const a=PLUS.permitAdd||0;if(!a||!lastV||(+$("pp").value&&$("pd").value))return;
  lastV=r5k(lastV+a);$("rVal").textContent="$"+lastV.toLocaleString("en-CA");$("rRange").textContent=$("rRange").textContent.replace(/\$([\d,]+)/g,(m,n)=>"$"+r5k(+n.replace(/,/g,"")+a).toLocaleString("en-CA"));
  $("adjBox").hidden=false;$("adjBox").insertAdjacentHTML("beforeend",`<div><span>Permitted renovations (city records)</span><span class="up">+${money(a)}</span></div>`);}catch(e){}};}
$("addr").addEventListener("input",()=>{PLUS.permitAdd=0;});
(function(){$("pNear").insertAdjacentHTML("afterend",`<div class="pcard" id="pPermit" hidden></div>`);Object.assign(FR_EXACT,{"Permits at this address":"Permis à cette adresse"});})();
const _updPlus5=updatePlus;updatePlus=function(){_updPlus5();if(!aiProp||!lastV)return;const lbl=$("addr").value.trim();if(lbl!==PLUS.permLbl){PLUS.permLbl=lbl;drawPermits().catch(()=>{});}};
const _repPlus5=buildReport;buildReport=async function(){await _repPlus5();const rep=$("report"),n=rep.querySelector(".brand-line")||rep.querySelector(".notice");
  if(PLUS.rep.permit)(n?n.insertAdjacentHTML("beforebegin",PLUS.rep.permit):rep.insertAdjacentHTML("beforeend",PLUS.rep.permit));};
