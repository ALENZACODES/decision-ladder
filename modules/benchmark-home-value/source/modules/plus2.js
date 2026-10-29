
/* ======================= More free tools: where your equity goes further, lendable value, sell now or wait,
   real return against renting, and heating cost. Every input has a fallback: page data first, then built-in
   tables, then plain defaults, so a missing file never blanks a card. ======================= */
/* built-in fallbacks (approximate, labelled on the page) */
const RENT_FB={ON:[1250,1650,2000,2350],BC:[1450,1750,2250,2700],AB:[1050,1350,1650,1850],SK:[850,1050,1300,1500],MB:[850,1100,1400,1650],
  QC:[750,950,1150,1400],NB:[750,950,1200,1350],NS:[1050,1300,1650,1900],PE:[900,1150,1450,1650],NL:[750,950,1150,1300],YT:[1200,1400,1750,2000],NT:[1500,1750,2100,2400],NU:[1700,2000,2400,2800]};
async function rentSafe(prov,muni){let r=null,src="CMHC Rental Market Survey";
  try{r=await rentsFor(prov,muni);}catch(e){}
  if(!r||!r.some(Boolean)){r=RENT_FB[prov]||RENT_FB.ON;src="built-in provincial averages (CMHC rent data didn't load)";}
  return {r,src};}
const CPI={1990:78.4,1991:82.8,1992:84,1993:85.6,1994:85.7,1995:87.6,1996:88.9,1997:90.4,1998:91.3,1999:92.9,2000:95.4,2001:97.8,2002:100,2003:102.8,2004:104.7,
  2005:107,2006:109.1,2007:111.5,2008:114.1,2009:114.4,2010:116.5,2011:119.9,2012:121.7,2013:122.8,2014:125.2,2015:126.6,2016:128.4,2017:130.4,2018:133.4,
  2019:136,2020:137,2021:141.6,2022:151.2,2023:157.1,2024:160.9,2025:164.2,2026:167.5};
const cpiAt=(y,m)=>{const a=CPI[Math.max(1990,Math.min(2026,y))],b=CPI[Math.max(1990,Math.min(2026,y+1))]||a;return a+(b-a)*(m/12);};
const RATE_PRE={1990:13,1991:11,1992:9.5,1993:8.5,1994:9,1995:8.5,1996:7.5,1997:7,1998:6.8,1999:7,2000:7.8,2001:6.8,2002:6.5,2003:5.8,2004:5.5,2005:5.2,
  2006:5.8,2007:6,2008:5.8,2009:4.5,2010:4.4,2011:4,2012:3.4,2013:3.3,2014:3.1,2015:2.8};
const rateAt=(y,m)=>{const i=mi(y,m);if(i>=0)return RATES[Math.min(i,RATES.length-1)]||4.2;return RATE_PRE[Math.max(1990,y)]||5;};
const idxSafe=(reg,prov,y,m)=>{try{const v=idxAtPage(reg,prov,y,m);if(Number.isFinite(v)&&v>0)return v;}catch(e){}
  const A=IDXA(reg),i=mi(y,m),g=({ON:.06,BC:.07,QC:.045})[prov]||.035;return i>=0?A[Math.min(i,A.length-1)]:A[0]/Math.pow(1+g,-i/12);};
const benchSafe=(m,type)=>{try{const s=seriesFor(m,type),v=s[s.length-1];if(Number.isFinite(v)&&v>0)return v;}catch(e){}return m.bench*((TYPE[m.reg]||{})[type]||1);};
/* heating: Environment Canada heating degree-day normals (base 18 °C), rounded */
const HDD_CITY={"St. John's":4800,"Mount Pearl":4800,"Corner Brook":4700,"Gander":5000,"Halifax":4000,"Truro":4400,"Cape Breton (Sydney)":4500,"Charlottetown":4500,"Summerside":4500,
  "Moncton":4600,"Dieppe":4600,"Fredericton":4700,"Saint John":4700,"Québec City":5100,"Lévis":5100,"Montréal":4500,"Laval":4500,"Longueuil":4500,"Gatineau":4500,"Sherbrooke":4900,
  "Saguenay":5700,"Rimouski":5200,"Trois-Rivières":4900,"Ottawa":4500,"Toronto":3500,"Mississauga":3800,"Hamilton":3800,"London":3900,"Windsor":3400,"Kitchener":4100,"Waterloo":4100,
  "Guelph":4200,"Barrie":4300,"Kingston":4000,"Greater Sudbury":5300,"Thunder Bay":5700,"Sault Ste. Marie":4900,"North Bay":5100,"Timmins":6000,"Kenora":5900,"Winnipeg":5700,
  "Brandon":5800,"Regina":5600,"Saskatoon":5800,"Prince Albert":6100,"Calgary":5100,"Edmonton":5100,"Red Deer":5500,"Lethbridge":4600,"Medicine Hat":4800,"Grande Prairie":5800,
  "Fort McMurray":6300,"Vancouver":2800,"Burnaby":2900,"Richmond":2800,"Surrey":2900,"Victoria":2900,"Saanich":2900,"Nanaimo":3000,"Kelowna":3600,"Kamloops":3500,
  "Prince George":4900,"Fort St. John":5800,"Whistler":4300,"Whitehorse":6800,"Yellowknife":8000,"Iqaluit":9900};
const HDD_REG={GTA:3700,OTT:4500,SWO:3900,EON:4300,NON:5500,CGY:5100,EDM:5200,ABO:5400,VAN:2900,BCO:3700,PRA:5700,MTL:4500,QCO:5000,ATL:4400,TER:7500};
const FUEL={BC:["gas",15,11.5],AB:["gas",13,17],SK:["gas",12,18],MB:["gas",12,10],ON:["gas",14,13],QC:["elec",0,7.8],NB:["elec",0,14],NL:["elec",0,14],
  NS:["oil",1.6,18],PE:["oil",1.55,17],YT:["oil",1.75,19],NT:["oil",1.9,35],NU:["oil",1.7,40]};   // [main fuel, gas $/GJ or oil $/L, electricity ¢/kWh]

/* ---------- layout ---------- */
(function(){
  const chart=(id,title,sub,wide,extra)=>`<div class="pcard chart${wide?" wide":""}"><div class="chart-top"><h3>${title}</h3><div class="tools"><button type="button" data-png="${id}">PNG</button><button type="button" data-csv="${id}">CSV</button></div></div>
    ${extra||""}<div class="chart-sub" id="${id}sub">${sub}</div><div class="box" id="${id}"></div><div class="mode" id="m${id.slice(1)}" hidden></div><div class="dl-msg"></div></div>`;
  const g=$("plus").querySelector(".pgrid");
  g.insertAdjacentHTML("beforeend",`
    <div class="pcard" id="pLend"></div>
    ${chart("xs","Sell now or wait?","",false,`<div class="row"><label for="slPrice">List below market (%) <input id="slPrice" type="number" min="0" max="20" step="0.5" value="0"></label><label for="slFee">Agent commission (%) <input id="slFee" type="number" min="0" max="8" step="0.1" value="4"></label></div>`)}
    ${chart("xr","Where your money goes further","",true,`<div class="row"><label for="mvEq">Cash to move with ($) <input id="mvEq" type="number" min="0" step="1000"></label><label for="mvType">Home to buy <select id="mvType"><option value="detached">Detached house</option><option value="semi">Semi-detached</option><option value="town">Townhouse</option><option value="condo">Condo apartment</option></select></label></div>`)}
    <div class="pcard" id="pEnergy"><h3>Heating cost and green upgrades</h3>
      <div class="row"><label for="enAge">Built <select id="enAge"><option value="1.45">Before 1960</option><option value="1.25">1960–1979</option><option value="1" selected>1980–1999</option><option value=".85">2000–2011</option><option value=".7">2012 or later</option></select></label>
      <label for="enFuel">Heated by <select id="enFuel"><option value="gas">Natural gas</option><option value="elec">Electric baseboard</option><option value="oil">Heating oil</option><option value="hp">Heat pump</option></select></label></div>
      <div id="enOut"></div></div>
    <div class="pcard wide" id="pTwin"></div>`);
  const c=$("calc").querySelector(".pgrid");
  const opts=$("ccMuni").innerHTML;
  c.insertAdjacentHTML("beforeend",`<div class="pcard"><h3>Did owning actually pay? (after inflation, against renting)</h3>
      <label for="rrMuni">Where <select id="rrMuni">${opts}</select></label>
      <div class="row"><label for="rrPrice">Price paid ($) <input id="rrPrice" type="number" min="10000" step="1" value="500000"></label><label for="rrWhen">Month bought <input id="rrWhen" type="month" min="1990-01" max="2026-09" value="2016-06"></label></div>
      <div class="row3"><label for="rrDown">Down payment (%) <input id="rrDown" type="number" min="5" max="100" step="1" value="20"></label><label for="rrBeds">Bedrooms <select id="rrBeds"><option value="1">1</option><option value="2">2</option><option value="3" selected>3+</option></select></label><label for="rrFund">Index fund return (%/yr) <input id="rrFund" type="number" min="0" max="15" step="0.5" value="6"></label></div>
      <div class="btns"><button type="button" class="ghost" id="rrMine">Use my home's answers</button></div>
      <div id="rrOut"></div></div>
    ${chart("xq","Owner against renter who invested the difference","")}`);
  $("rrMuni").value=String(M.indexOf(cur()));
  Object.assign(FR_EXACT,{"Sell now or wait?":"Vendre maintenant ou attendre?","Where your money goes further":"Où votre argent va plus loin","Heating cost and green upgrades":"Coût de chauffage et rénovations écoénergétiques",
    "Did owning actually pay? (after inflation, against renting)":"Être propriétaire a-t-il vraiment rapporté? (après inflation, comparé à la location)","What a lender will finance":"Ce qu’un prêteur financera"});
})();

/* ---------- lendable value: what a lender will finance, not just market value ---------- */
async function drawLend(){const v=lastV,el=$("pLend");if(!v)return;const sub=st.sub,condo=isCondo(sub),sq=sqftKnown?(+$("sqft").value||0):0,bal=+$("eqBal").value||+$("bal").value||0;
  let nonres=false;try{nonres=await isNonRes(aiProp&&aiProp.pick);}catch(e){}
  let lo=1,hi=1;const flags=[];
  if(sub==="rural"){lo=.85;flags.push("Acreage: most lenders value the house plus about 5–10 acres; extra land and outbuildings often count for little or nothing.");}
  if(sub==="cottage"){lo=.8;flags.push("Cottage: year-round road access, a winterized home and potable water decide whether it's financed like a home (Type A) or with 20–50% down (Type B).");}
  if(sub==="mobile"){lo=.6;hi=.9;flags.push("Mobile home: on leased land it's usually financed as a chattel loan (shorter term, higher rate); on owned land with a permanent foundation, as a home.");}
  if(condo&&sq&&sq<500){lo=Math.min(lo,.9);flags.push(`Small condo (${sq} sq ft): many lenders limit units under about 500 sq ft to 65–80% of value or decline them.`);}
  if(condo&&!sq)flags.push("Condos under about 500 sq ft get stricter lending; add your size in step 2 to check.");
  if(sub==="multiplex")flags.push("2–4 units: rental income can count toward qualifying; owner-occupied buildings can still be insured with a smaller down payment.");
  if(nonres)flags.push("Statistics Canada lists this address as non-residential: expect commercial lending terms.");
  if(v>=1500000)flags.push("At $1.5M or more, mortgage insurance isn't available, so buyers need at least 20% down.");
  const lv=[v*lo,v*hi],L=lv[0],ins=v<1500000,down=ins?.05*Math.min(v,500000)+.1*Math.max(0,v-500000):v*.2,buyMtg=v-down,
    prem=ins&&down/v<.2?(down/v<.1?.04:down/v<.15?.031:.028)*buyMtg:0,refi=Math.max(0,L*.8-bal),heloc=Math.max(0,Math.min(L*.65,L*.8-bal));
  const mkt=+$("eqMkt").value||+$("rate").value||4.2,qual=Math.max(mkt+2,5.25),tax=v*.009/12,heat=100,
    incBuy=(pmtOf(buyMtg+prem,qual,25)+tax+heat)*12/.39,incRefi=bal||refi?(pmtOf(bal+refi,qual,25)+tax+heat)*12/.39:0;
  el.innerHTML=`<h3>What a lender will finance</h3><div class="num">${lo===hi?money(L):money(lv[0])+" – "+money(lv[1])}</div>
    <p class="hint" style="margin:0">Lending value: what a lender is likely to use, which can be below market value for some homes.</p>
    <div class="kv"><div><span>Largest mortgage to buy it, owner-occupied</span><span>${money(buyMtg)} (${money(down)} down)</span></div>
      ${prem?`<div><span>Mortgage insurance premium added</span><span>${money(prem)}</span></div>`:""}
      <div><span>Income needed for that (stress test ${qual.toFixed(2)}%)</span><span>${money(incBuy)}/yr</span></div>
      <div><span>Refinance cash available (80%)</span><span>${money(refi)}</span></div>
      <div><span>Home-equity line (65% limit)</span><span>${money(heloc)}</span></div>
      ${incRefi?`<div><span>Income to qualify for that refinance</span><span>${money(incRefi)}/yr</span></div>`:""}</div>
    ${flags.map(f=>`<div class="flag">${f}</div>`).join("")||`<div class="flag good">A standard home: lenders should value it at full market value.</div>`}
    <p class="hint" style="margin:0">General Canadian rules for 2026: insured purchases under $1.5M need 5% down on the first $500K and 10% above; refinances to 80%; lines of credit to 65%; qualifying at the higher of your rate + 2% or 5.25%, with housing costs at 39% of income. Lenders differ.</p>`;
  PLUS.rep.lend=`<div class="rp-sec"><b>What a lender will finance</b><p>Lending value ${lo===hi?money(L):money(lv[0])+" – "+money(lv[1])}. Largest purchase mortgage ${money(buyMtg)}; refinance cash ${money(refi)}; home-equity line ${money(heloc)}.${flags.length?" "+flags.join(" "):""}</p></div>`;}

/* ---------- sell now or wait: net proceeds by month, from carrying costs and the recent trend ---------- */
function drawSell(){const v=lastV;if(!v)return;const reg=cur().reg,A=IDXA(reg),n=A.length,drift=Math.pow(A[n-1]/A[n-4],1/3)-1,yr=Math.pow(A[n-1]/A[n-13],1/12)-1;
  const S=eqState(),fee=(+$("slFee").value||0)/100,cut=(+$("slPrice").value||0)/100,condo=isCondo(st.sub);
  const carry=(S.bal*(S.rate||4.5)/100/12)+v*.009/12+(condo?(+$("cfee").value||0)+v*.004/12:v*.01/12)+(condo?40:150);
  const labels=[],net=[],rows=[];
  for(let k=0;k<=6;k++){const price=v*(1-cut)*Math.pow(1+drift,k),costs=price*fee+2000+carry*k,nn=price-costs-S.bal;labels.push(k?k+" mo":"Now");net.push(Math.round(nn));rows.push([k,price,carry*k,nn]);}
  render("xs",{kind:"bar",labels,fmt:fmt$,sets:[{label:"Cash after selling",data:net}]});
  const best=rows.reduce((a,b)=>b[3]>a[3]?b:a);
  $("xssub").innerHTML=`Cash in hand after commission, $2,000 legal fees${S.bal?", paying off the mortgage":""} and ${dollars(carry)}/mo carrying costs while it's for sale. Prices here moved ${sgn(drift)} a month over the last 3 months (${sgn(Math.pow(1+yr,12)-1)} over the year)${cut?`; listed ${(cut*100).toFixed(1)}% under value to sell faster`:""}. ${best[0]===0?"Selling sooner nets more right now.":`Waiting about ${best[0]} months nets the most, if the trend holds.`}`;
  PLUS.rep.sell=`<div class="rp-sec"><b>Sell now or wait</b><p>Net after selling now ${money(rows[0][3])}; in 3 months ${money(rows[3][3])}; in 6 months ${money(rows[6][3])} (carrying ${dollars(carry)}/mo, trend ${sgn(drift)}/mo).</p></div>`;}

/* ---------- equity relocation and "your home's twin" in other cities ---------- */
const TWIN_CITIES=["Toronto","Vancouver","Montréal","Calgary","Edmonton","Ottawa","Winnipeg","Québec City","Hamilton","Kitchener","London","Halifax","Victoria","Saskatoon",
  "Regina","St. John's","Moncton","Trois-Rivières","Fredericton","Charlottetown","Kelowna","Windsor","Sherbrooke","Thunder Bay","Lethbridge","Saint John","Whitehorse","Brandon"];
function drawMove(){const v=lastV;if(!v)return;const here=cur(),S=eqState(),type=$("mvType").value||st.type;
  if(!$("mvEq").dataset.touched)$("mvEq").value=Math.max(0,Math.round((v*.95-S.bal-2000)/1000)*1000);
  const cash=+$("mvEq").value||0,f=(SUB[st.sub]||SUB.detached)[1],hereB=benchSafe(here,st.type)*f||v;
  const all=M.map(m=>({m,cost:benchSafe(m,type),twin:v*benchSafe(m,st.type)/(benchSafe(here,st.type)||1)})).filter(x=>Number.isFinite(x.cost)&&x.cost>0);
  const ok=all.filter(x=>x.cost<=cash).sort((a,b)=>b.cost-a.cost),pick=TWIN_CITIES.map(n=>all.find(x=>x.m.name===n)).filter(Boolean).filter(x=>x.m!==here);
  pick.sort((a,b)=>(cash-b.cost)-(cash-a.cost));
  const tn={detached:"detached house",semi:"semi",town:"townhouse",condo:"condo"}[type];
  render("xr",{kind:"bar",labels:pick.map(x=>x.m.name),fmt:fmt$,sets:[{label:`Cash left after buying a typical ${tn} outright`,data:pick.map(x=>Math.round(cash-x.cost))}]});
  $("xrsub").innerHTML=`With ${money(cash)}${$("mvEq").dataset.touched?"":" (your estimate less 5% selling costs"+(S.bal?" and your mortgage":"")+")"}, you could buy a typical ${tn} <b>mortgage-free in ${ok.length} of ${all.length}</b> municipalities on this page. Bars below zero still need a mortgage.`;
  const top=ok.slice(0,12);
  $("pTwin").innerHTML=`<div class="chart-top"><h3>Your home's twin in other cities</h3><div class="tools"><button type="button" id="twCsv">CSV</button></div></div>
    <p class="hint" style="margin:0">What a home like yours (same type, same place in its local market) is worth elsewhere, from each city's benchmark. ${ok.length?`Most expensive places you could buy a ${tn} with no mortgage: ${top.map(x=>`<b>${esc(x.m.name)}</b> (${money(x.cost)})`).join(", ")}.`:"No municipality on this page is affordable mortgage-free with that cash; lower the type or raise the cash."}</p>
    <div class="tbl units"><table><thead><tr><th style="text-align:left">City</th><th>Your home there</th><th>vs here</th><th>Typical ${tn}</th><th>Cash left</th></tr></thead>
    <tbody>${[...pick].sort((a,b)=>b.twin-a.twin).map(x=>`<tr><td style="text-align:left">${esc(x.m.name)}, ${x.m.prov}</td><td>${money(x.twin)}</td><td>${sgn(x.twin/v-1,0)}</td><td>${money(x.cost)}</td><td class="${cash>=x.cost?"up":"down"}">${cash>=x.cost?"":"−"}${money(Math.abs(cash-x.cost))}</td></tr>`).join("")}</tbody></table></div><div class="dl-msg"></div>`;
  $("twCsv").onclick=()=>plusSave("home-twins-"+today()+".csv",toCSV([["Municipality","Province","Your home there","Typical "+tn,"Cash left with "+Math.round(cash)],...all.sort((a,b)=>b.twin-a.twin).map(x=>[x.m.name,x.m.prov,Math.round(x.twin),Math.round(x.cost),Math.round(cash-x.cost)])]));
  PLUS.rep.move=`<div class="rp-sec"><b>Where your money goes further</b><p>With ${money(cash)} you could buy a typical ${tn} mortgage-free in ${ok.length} of ${all.length} municipalities${top.length?", including "+top.slice(0,6).map(x=>esc(x.m.name)).join(", "):""}.</p></div>`;}

/* ---------- heating cost (degree-days x size x age) and what a heat pump or insulation would change ---------- */
function drawEnergy(){const v=lastV,el=$("enOut");if(!v)return;const m=cur(),prov=m.prov,F=FUEL[prov]||FUEL.ON,hdd=HDD_CITY[m.name]||HDD_REG[m.reg]||4500;
  const p=aiProp||{},s=p.street||{},yb=Object.entries(s).filter(([t])=>t!=="_r").map(e=>e[1][3]).find(Boolean);
  if(yb&&!$("enAge").dataset.touched)$("enAge").value=yb<1960?"1.45":yb<1980?"1.25":yb<2000?"1":yb<2012?".85":".7";
  if(!$("enFuel").dataset.touched)$("enFuel").value=F[0];
  const sq=+$("sqft").value||(SUB[st.sub]||SUB.detached)[2],tf={detached:1,semi:.85,town:.75,condo:.5,mobile:1.3}[st.sub]||(isCondo(st.sub)?.5:1);
  const need=sq*hdd*.0027*(+$("enAge").value||1)*tf,el$=F[2]/100,cop=hdd<3500?3:hdd<5000?2.6:hdd<6500?2.2:1.8;
  const costOf=fu=>fu==="gas"?need/.95/277.8*(F[0]==="gas"?F[1]:14):fu==="oil"?need/.85/10.75*(F[0]==="oil"?F[1]:1.65):fu==="hp"?need/cop*el$:need*el$;
  const fuel=$("enFuel").value,now=costOf(fuel),hp=costOf("hp"),ins=now*.8,save=now-hp,cap=x=>Math.max(0,x)*8;
  el.innerHTML=`<div class="num">${dollars(now/12)}<small style="font-size:16px;color:var(--muted)"> /mo heating</small></div>
    <div class="kv"><div><span>Per year</span><span>${dollars(now)}</span></div><div><span>Heating degree-days, ${esc(HDD_CITY[m.name]?m.name:REGION_NAME[m.reg])}</span><span>${hdd.toLocaleString("en-CA")}</span></div>
      ${fuel!=="hp"?`<div><span>With a cold-climate heat pump</span><span class="${save>0?"up":"down"}">${dollars(hp)}/yr (${save>0?"saves "+dollars(save):"costs "+dollars(-save)+" more"})</span></div>`:""}
      <div><span>With insulation and air sealing (−20%)</span><span>${dollars(ins)}/yr (saves ${dollars(now-ins)})</span></div>
      <div><span>Value effect if buyers credit 8 years of savings</span><span>heat pump ${money(cap(save))} · insulation ${money(cap(now-ins))}</span></div></div>
    <p class="hint" style="margin:0">From Environment Canada heating degree-day normals, your size, age and type, and typical ${prov} prices (${F[0]==="gas"?"gas $"+F[1]+"/GJ":F[0]==="oil"?"oil $"+F[1]+"/L":"electricity"}, electricity ${F[2]}¢/kWh). Heat pump efficiency ${cop}× for this climate. Approximate; your bills are the best guide.${isCondo(st.sub)?" In many condo buildings heat is paid through the condo fee.":""}</p>`;
  PLUS.rep.energy=`<div class="rp-sec"><b>Heating</b><p>About ${dollars(now)}/yr (${dollars(now/12)}/mo). A heat pump: ${dollars(hp)}/yr; insulation and air sealing: ${dollars(ins)}/yr.</p></div>`;}

/* ---------- real return: owning against renting and investing the difference, after inflation ---------- */
async function calcReal(){const m=M[+$("rrMuni").value]||cur(),P=+$("rrPrice").value||0,w=$("rrWhen").value,out=$("rrOut");
  if(!(P>0)||!/^\d{4}-\d{2}$/.test(w)){out.innerHTML=`<p class="hint">Enter a price and month.</p>`;return;}
  const [y,mo]=w.split("-").map(Number),dn=Math.min(1,Math.max(.05,(+$("rrDown").value||20)/100)),fund=(+$("rrFund").value||0)/100,beds=+$("rrBeds").value||3;
  const {r:rents,src}=await rentSafe(m.prov,m.name),rentNow=(rents[beds]||rents.find(Boolean)||1500)*1.12;
  const reg=m.reg,i0=mi(y,mo-1),n=MONTHS.length-1,then=idxSafe(reg,m.prov,y,mo-1),cpiNow=cpiAt(NOWM.getFullYear(),NOWM.getMonth()),cpi0=cpiAt(y,mo-1);
  let bal=P*(1-dn),rate=rateAt(y,mo-1),left=300,pmt=pmtOf(bal,rate,25),port=P*dn+P*.015,interest=0,carry=0,rentPaid=0;const lab=[],own=[],ren=[];
  for(let i=i0,k=0;i<=n;i++,k++){const yy=2016+Math.floor(i/12),mm=((i%12)+12)%12;
    if(k&&k%60===0&&left>0){rate=rateAt(yy,mm);pmt=pmtOf(bal,rate,left/12);}
    const val=P*idxSafe(reg,m.prov,yy,mm)/then,int=bal*rate/100/12,prin=Math.min(bal,left>0?pmt-int:0);bal-=prin;left--;interest+=int;
    const c=(left>=0?pmt:0)+val*.019/12+100,rent=rentNow*cpiAt(yy,mm)/cpiNow;carry+=val*.019/12+100;rentPaid+=rent;
    port=port*(1+fund/12)+(c-rent);
    if(i>=0&&(k%3===0||i===n)){lab.push(label(MONTHS[i]));own.push(Math.round(val-bal-val*.05));ren.push(Math.round(port));}}
  const valNow=P*INOW(reg)/then,ownNet=valNow-bal-valNow*.05,real=(valNow/P)/(cpiNow/cpi0)-1,diff=ownNet-port,yrs=(n-i0)/12;
  out.innerHTML=`<div class="num">${diff>=0?"Owning":"Renting"} ahead by ${money(Math.abs(diff))}</div>
    <div class="kv"><div><span>Home value now</span><span>${money(valNow)} (${sgn(valNow/P-1)})</span></div><div><span>After inflation</span><span>${sgn(real)}</span></div>
      <div><span>Mortgage interest paid</span><span>${money(interest)}</span></div><div><span>Tax, upkeep, insurance</span><span>${money(carry)}</span></div>
      <div><span>Owner's wealth if sold now (−5%)</span><span>${money(ownNet)}</span></div><div><span>Renter's index fund at ${(fund*100).toFixed(1)}%</span><span>${money(port)}</span></div>
      <div><span>Rent paid by the renter</span><span>${money(rentPaid)}</span></div></div>
    <p class="hint" style="margin:0">Over ${yrs.toFixed(1)} years. The renter invests the same down payment and closing costs, then invests (or draws) the monthly difference between owning costs and rent. Rent today ${dollars(rentNow)}/mo from ${src}, plus 12% for a new lease, run back with CPI. Mortgage rates are typical 5-year rates, renewed every 5 years${i0<0?"; before 2016 the price index is extended at a steady rate":""}. Ownership costs: 0.9% tax, 1% upkeep, $100/mo insurance.</p>`;
  $("xqsub").textContent=`${money(P)} in ${monthName([y,mo-1])}, ${m.name}: net worth if each sold out or cashed out at that date.`;
  render("xq",{kind:"line",labels:lab,fmt:fmt$,sets:[{label:"Owner (home equity after selling costs)",data:own,color:css("--s1")},{label:"Renter (index fund)",data:ren,color:css("--s2")}]});}
$("rrMine").addEventListener("click",()=>{if(+$("pp").value&&$("pd").value){$("rrPrice").value=$("pp").value;$("rrWhen").value=$("pd").value;}
  $("rrMuni").value=String(M.indexOf(cur()));$("rrBeds").value=String(Math.min(3,Math.max(1,+$("beds").value||3)));calcReal();
  PLUS_BTN=$("rrMine");if(!(+$("pp").value&&$("pd").value))plusMsg("Add what you paid and when in step 2 to use your own purchase.");});
["rrMuni","rrPrice","rrWhen","rrDown","rrBeds","rrFund"].forEach(id=>$(id).addEventListener("input",()=>calcReal().catch(()=>{})));
calcReal().catch(()=>{});

/* ---------- wiring ---------- */
$("mvEq").addEventListener("input",()=>{$("mvEq").dataset.touched="1";try{drawMove();}catch(e){}});
$("mvType").addEventListener("input",()=>{try{drawMove();}catch(e){}});
["enAge","enFuel"].forEach(id=>$(id).addEventListener("input",()=>{$(id).dataset.touched="1";try{drawEnergy();}catch(e){}}));
["slPrice","slFee"].forEach(id=>$(id).addEventListener("input",()=>{try{drawSell();}catch(e){}}));
["eqBal","eqRate"].forEach(id=>$(id).addEventListener("input",()=>{try{drawSell();drawMove();drawLend();}catch(e){}}));
const _updPlus2=updatePlus;updatePlus=function(){_updPlus2();if(!aiProp||!lastV)return;
  if(!$("mvType").dataset.set){$("mvType").value=st.type;}
  for(const f of [drawSell,drawMove,drawEnergy])try{f();}catch(e){console.warn(f.name,e);}
  drawLend().catch(()=>{});};
const _repPlus2=buildReport;buildReport=async function(){await _repPlus2();const rep=$("report"),n=rep.querySelector(".notice");
  const extra=["lend","sell","move","energy"].map(k=>PLUS.rep[k]||"").join("");if(n)n.insertAdjacentHTML("beforebegin",extra);else rep.insertAdjacentHTML("beforeend",extra);};
$("mvType").addEventListener("change",()=>{$("mvType").dataset.set="1";});
