
/* ======================= Round 4: crime and safety (Statistics Canada + police open data), land transfer tax and
   closing costs, what's nearby (OpenStreetMap), cash-offer estimate, 3-year range, relocation map, share and embed
   links, official assessment lookups. Every live source has offline fallbacks. ======================= */
/* Statistics Canada, The Daily, July 22 2026 (Uniform Crime Reporting Survey): 2025 Crime Severity Index (Canada 2006 = 100) */
const CSI_CANADA=[75.0,-5];
const CSI_CMA={"St. John's":[79.2,-2],"Halifax":[68.6,-6],"Moncton":[105.6,11],"Saint John":[70.0,20],"Fredericton":[80.5,7],"Saguenay":[49.3,-13],"Québec":[55.0,-1],
  "Sherbrooke":[50.3,-7],"Trois-Rivières":[56.0,-10],"Drummondville":[72.3,4],"Montréal":[61.3,-5],"Gatineau":[60.6,-2],"Ottawa":[50.6,-6],"Kingston":[61.5,1],
  "Belleville–Quinte West":[63.1,-3],"Peterborough":[57.3,-6],"Toronto":[55.0,-7],"Hamilton":[54.8,-7],"St. Catharines–Niagara":[53.8,-9],"Kitchener–Cambridge–Waterloo":[66.8,-9],
  "Brantford":[72.1,8],"Guelph":[57.8,2],"London":[66.0,8],"Windsor":[55.4,-12],"Barrie":[46.9,-3],"Greater Sudbury":[64.9,-2],"Thunder Bay":[114.1,3],"Winnipeg":[113.4,-9],
  "Regina":[87.4,-12],"Saskatoon":[98.9,-7],"Lethbridge":[107.7,2],"Calgary":[61.7,-3],"Red Deer":[114.4,-3],"Edmonton":[95.6,-7],"Kelowna":[103.7,-4],"Kamloops":[126.2,-4],
  "Chilliwack":[134.3,-4],"Abbotsford–Mission":[95.5,-1],"Vancouver":[83.5,1],"Victoria":[74.6,5],"Nanaimo":[106.0,-1]};
const CSI_PROV={NL:[88.7,-4],PE:[68.4,-6],NS:[73.0,-3],NB:[90.4,6],QC:[61.6,-5],ON:[57.2,-6],MB:[130.0,-9],SK:[146.6,-5],AB:[90.6,-7],BC:[92.4,-2],YT:[195.4,-6],NT:[485.9,-8],NU:[461.2,10]};
const CMA_MEMBERS={"Toronto":"Toronto|Mississauga|Brampton|Markham|Vaughan|Richmond Hill|Oakville|Ajax|Pickering|Aurora|Newmarket|Milton|Halton Hills|Caledon|King|Whitchurch-Stouffville|East Gwillimbury|Georgina|Uxbridge|Bradford West Gwillimbury|New Tecumseth|Mono|Orangeville",
  "Hamilton":"Hamilton|Burlington|Grimsby","St. Catharines–Niagara":"St. Catharines|Niagara Falls|Welland|Fort Erie|Thorold|Port Colborne|Pelham|Lincoln|Niagara-on-the-Lake|Wainfleet",
  "Kitchener–Cambridge–Waterloo":"Kitchener|Cambridge|Waterloo|Woolwich|Wilmot|North Dumfries|Wellesley","Ottawa":"Ottawa|Russell|Clarence-Rockland",
  "Gatineau":"Gatineau|Cantley|Chelsea|L'Ange-Gardien|Val-des-Monts|Pontiac|La Pêche",
  "Montréal":"Montréal|Laval|Longueuil|Terrebonne|Repentigny|Brossard|Saint-Jérôme|Blainville|Mirabel|Mascouche|Châteauguay|Saint-Eustache|Boucherville|Vaudreuil-Dorion|Dollard-Des Ormeaux|Pointe-Claire|Saint-Constant|La Prairie|Sainte-Julie|Candiac|Varennes|Chambly|Boisbriand|Sainte-Thérèse|Rosemère|Deux-Montagnes|Côte-Saint-Luc|Mont-Royal|Westmount|Beaconsfield|Kirkland|Dorval|L'Assomption",
  "Québec":"Québec|Québec City|Lévis|L'Ancienne-Lorette|Saint-Augustin-de-Desmaures|Stoneham-et-Tewkesbury|Boischatel|Sainte-Brigitte-de-Laval|Lac-Beauport|Shannon",
  "Calgary":"Calgary|Airdrie|Chestermere|Cochrane|Rocky View County|Crossfield|Irricana|Beiseker",
  "Edmonton":"Edmonton|St. Albert|Strathcona County|Sherwood Park|Spruce Grove|Leduc|Fort Saskatchewan|Beaumont|Stony Plain|Parkland County|Sturgeon County|Leduc County|Devon|Morinville|Gibbons|Bon Accord|Bruderheim|Legal|Redwater",
  "Vancouver":"Vancouver|Surrey|Burnaby|Richmond|Coquitlam|Langley|Delta|North Vancouver|Maple Ridge|New Westminster|Port Coquitlam|West Vancouver|Port Moody|White Rock|Pitt Meadows|Bowen Island|Anmore|Belcarra|Lions Bay",
  "Victoria":"Victoria|Saanich|Langford|Oak Bay|Esquimalt|Colwood|Central Saanich|North Saanich|Sooke|View Royal|Sidney|Metchosin|Highlands",
  "Abbotsford–Mission":"Abbotsford|Mission","Kelowna":"Kelowna|West Kelowna|Lake Country|Peachland","Nanaimo":"Nanaimo|Lantzville",
  "Winnipeg":"Winnipeg|Springfield|East St. Paul|West St. Paul|Rosser|St. Clements|Headingley|Ritchot|Taché|Macdonald|St. François Xavier",
  "Regina":"Regina|White City|Pilot Butte","Saskatoon":"Saskatoon|Martensville|Warman|Corman Park","Halifax":"Halifax",
  "St. John's":"St. John's|Mount Pearl|Conception Bay South|Paradise|Torbay|Portugal Cove-St. Philip's","Moncton":"Moncton|Dieppe|Riverview",
  "Saint John":"Saint John|Rothesay|Quispamsis|Grand Bay-Westfield","Fredericton":"Fredericton","London":"London|St. Thomas|Strathroy-Caradoc|Middlesex Centre|Thames Centre|Central Elgin|Southwold",
  "Windsor":"Windsor|Tecumseh|LaSalle|Lakeshore|Amherstburg","Barrie":"Barrie|Innisfil|Springwater","Belleville–Quinte West":"Belleville|Quinte West",
  "Kingston":"Kingston","Peterborough":"Peterborough","Guelph":"Guelph","Brantford":"Brantford","Greater Sudbury":"Greater Sudbury","Thunder Bay":"Thunder Bay",
  "Saguenay":"Saguenay","Sherbrooke":"Sherbrooke","Trois-Rivières":"Trois-Rivières","Drummondville":"Drummondville","Lethbridge":"Lethbridge","Red Deer":"Red Deer",
  "Kamloops":"Kamloops","Chilliwack":"Chilliwack"};
const CMA_OF={};for(const [c,l] of Object.entries(CMA_MEMBERS))for(const n of l.split("|"))CMA_OF[plain(n).replace(/\s+/g," ").trim()]=c;
const cmaFor=muni=>CMA_OF[plain(muni).replace(/\s+/g," ").trim()]||null;
/* each police service's own crime map or statistics (official pages) */
const POLICE_LINKS={"Toronto":["Toronto Police Public Safety Data Portal","https://data.torontopolice.on.ca/"],"Mississauga":["Peel Regional Police crime statistics and maps","https://www.peelpolice.ca/en/in-the-community/crime-statistics-and-maps.aspx"],
  "Brampton":["Peel Regional Police crime statistics and maps","https://www.peelpolice.ca/en/in-the-community/crime-statistics-and-maps.aspx"],"Ottawa":["Ottawa Police crime statistics","https://www.ottawapolice.ca/en/crime/Crime-Stats.aspx"],
  "Calgary":["Calgary Police statistical reports","https://www-prd.calgary.ca/cps/statistics/calgary-police-statistical-reports.html"],"Edmonton":["Edmonton Police neighbourhood crime map","https://www.edmontonpolice.ca/CrimeFiles/NeighbourhoodCrimeMapping"],
  "Vancouver":["Vancouver Police GeoDASH crime map","https://geodash.vpd.ca/"],"Winnipeg":["Winnipeg Police crime and calls-for-service maps","https://www.winnipeg.ca/police/crime-prevention/crime-calls-service-map"],
  "Halifax":["Halifax crime mapping","https://www.halifax.ca/safety-security/police/crime-mapping"],"Montréal":["Montréal police (SPVM) criminal acts open data","https://donneesquebec.ca/recherche/dataset/vmtl-actes-criminels"]};
const STATCAN_CRIME=["Statistics Canada: police-reported crime in Canada, 2025","https://www150.statcan.gc.ca/n1/pub/11-627-m/11-627-m2026025-eng.htm"];
/* Toronto Police neighbourhood crime rates (open data): live, then the copy saved by "Update live data", then the metro index */
const TPS_URL="https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/Neighbourhood_Crime_Rates_Open_Data/FeatureServer/0/query";
const TPS_CATS=[["ASSAULT","Assault"],["BREAKENTER","Break and enter"],["AUTOTHEFT","Auto theft"],["ROBBERY","Robbery"],["THEFTFROMMV","Theft from vehicle"],["THEFTOVER","Theft over $5,000"],["SHOOTING","Shootings"],["HOMICIDE","Homicides"]];
const TPS_YEARS=Array.from({length:12},(_,i)=>2014+i);
const ON_LOCAL=(()=>{try{return /^(localhost|127\.0\.0\.1)$/.test(location.hostname);}catch(e){return false;}})();   // the downloaded app's own server relays a few public data services
function fetchT(u,ms){const c=new AbortController(),t=setTimeout(()=>c.abort(),ms||7000);return fetch(u,{signal:c.signal}).finally(()=>clearTimeout(t));}
let TPS_ALL=null,TPS_LOCAL=null;
function tpsRow(a){const r={name:a.AREA_NAME,id:a.HOOD_ID,pop:a.POPULATION_2025,c:{},rt:{}};for(const [k] of TPS_CATS){r.c[k]=TPS_YEARS.map(y=>+a[`${k}_${y}`]||0);r.rt[k]=TPS_YEARS.map(y=>+a[`${k}_RATE_${y}`]||0);}return r;}
async function tpsAllLive(){if(TPS_ALL)return TPS_ALL;const f=["AREA_NAME","HOOD_ID","POPULATION_2025",...TPS_CATS.flatMap(([k])=>TPS_YEARS.flatMap(y=>[`${k}_${y}`,`${k}_RATE_${y}`]))].join(",");
  const qs=`where=1%3D1&outFields=*&returnGeometry=false&f=json`;let j=null;   // outFields=* keeps the address short (a long field list is refused)
  try{j=await (await fetchT(`${TPS_URL}?${qs}`,12000)).json();}catch(e){}
  if((!j||!j.features)&&ON_LOCAL)try{j=await (await fetchT(`/proxy/tps?${qs}`,25000)).json();}catch(e){}
  if(!j||!j.features||j.features.length<100)throw new Error("short");void f;
  return TPS_ALL=j.features.map(x=>tpsRow(x.attributes));}
function inRing(x,y,ring){let ins=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const [xi,yi]=ring[i],[xj,yj]=ring[j];if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi))ins=!ins;}return ins;}
async function torontoHood(la,lo){
  try{const pq=`geometry=${lo},${la}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=HOOD_ID&returnGeometry=false&f=json`;let j=null;
    try{j=await (await fetchT(`${TPS_URL}?${pq}`,10000)).json();}catch(e){}
    if((!j||!j.features)&&ON_LOCAL)j=await (await fetchT(`/proxy/tps?${pq}`,25000)).json();
    const id=j.features&&j.features[0]&&j.features[0].attributes.HOOD_ID;if(id!=null){const all=await tpsAllLive();const me=all.find(x=>x.id===id);if(me)return {me,all,src:"Toronto Police open data (live)"};}}catch(e){}
  try{if(!TPS_LOCAL)TPS_LOCAL=getJSON("data/crime_toronto.json").catch(()=>null);const L=await TPS_LOCAL;
    if(L&&L.rows&&L.geo){for(const row of L.rows){const g=L.geo[row.id];if(g&&g.some(ring=>inRing(+lo,+la,ring)))return {me:row,all:L.rows,src:`Toronto Police open data (saved ${L.d||""})`};}}}catch(e){}
  return null;}
async function drawCrime(){PLUS.rep.crimeHood="";const el=$("pCrime"),p=aiProp||{},it=p.pick||{},muni=st.muni,prov=st.prov,cma=cmaFor(muni),C=cma&&CSI_CMA[cma],P=CSI_PROV[prov];
  const rows=Object.entries(CSI_CMA).sort((a,b)=>a[1][0]-b[1][0]),rank=cma?rows.findIndex(r=>r[0]===cma)+1:null;
  const lvl=C?{name:`${cma} metro area`,v:C[0],ch:C[1]}:P?{name:`${PROV[prov]} (province-wide)`,v:P[0],ch:P[1]}:{name:"Canada",v:CSI_CANADA[0],ch:CSI_CANADA[1]};
  const vsCa=lvl.v/CSI_CANADA[0]-1,link=POLICE_LINKS[muni]||(cma&&POLICE_LINKS[cma]);
  let hoodHTML="",chartSets=null;$("pCrimeChart").hidden=true;
  const [la,lo]=(it.ll||"").split(",");
  if(muni==="Toronto"&&la){const H=await torontoHood(la,lo);
    if(H){const yi=TPS_YEARS.length-1,tot=row=>TPS_CATS.reduce((s,[k])=>s+row.c[k][yi],0),pop=H.all.reduce((s,r)=>s+(r.pop||0),0);
      const cityRate=k=>H.all.reduce((s,r)=>s+r.c[k][yi],0)/pop*1e5,meRate=k=>H.me.rt[k][yi];
      const per=row=>row.pop?tot(row)/row.pop:0,meP=per(H.me),safer=Math.round(H.all.filter(r=>per(r)>meP).length/H.all.length*100);
      hoodHTML=`<div class="flag ${safer>=50?"good":""}"><b>${esc(H.me.name)}</b>: safer than ${safer}% of Toronto's ${H.all.length} neighbourhoods by major crime per person in 2025.</div>
        <div class="tbl"><table><thead><tr><th style="text-align:left">Per 100,000 people, 2025</th><th>Here</th><th>Toronto</th></tr></thead><tbody>${TPS_CATS.map(([k,l])=>{const a=meRate(k),b=cityRate(k);return `<tr><td style="text-align:left">${l}</td><td class="${a<=b?"up":"down"}">${a.toFixed(0)}</td><td>${b.toFixed(0)}</td></tr>`;}).join("")}</tbody></table></div>`;
      const trend=row=>TPS_YEARS.map((y,i)=>TPS_CATS.reduce((s,[k])=>s+row.c[k][i],0)),cityT=TPS_YEARS.map((y,i)=>H.all.reduce((s,r)=>s+TPS_CATS.reduce((q,[k])=>q+r.c[k][i],0),0)/pop*1e5);
      chartSets={labels:TPS_YEARS.map(String),sets:[{label:H.me.name,data:trend(H.me).map(v=>Math.round(v/(H.me.pop||1)*1e5)),color:css("--s2")},{label:"All of Toronto",data:cityT.map(Math.round),color:css("--s1")}]};
      const busy=H.me.pop&&TPS_CATS.filter(([k])=>meRate(k)>cityRate(k)*2.5).length>=3;
      if(busy)hoodHTML+=`<div class="flag">Busy downtown, entertainment and shopping areas draw far more visitors than residents, so crime per resident runs high here. Compare streets within the area, and the metro index above, before drawing conclusions.</div>`;
      PLUS.rep.crimeHood=`${esc(H.me.name)}: safer than ${safer}% of Toronto neighbourhoods (Toronto Police open data, 2025)${busy?"; a busy area with many visitors, so per-resident rates run high":""}.`;
      hoodHTML+=`<p class="hint" style="margin:0">Source: ${esc(H.src)}. Counts per year use 2025 population for the trend.</p>`;}
    else hoodHTML=`<p class="hint" style="margin:0">Toronto Police neighbourhood data couldn't be reached from this page; the metro index below is used instead.${link?"":""}</p>`;}
  el.innerHTML=`<h3>Crime and safety</h3><div class="num">${lvl.v.toFixed(1)}<small style="font-size:16px;color:var(--muted)"> Crime Severity Index</small></div>
    <div class="kv"><div><span>${esc(lvl.name)}</span><span class="${vsCa<=0?"up":"down"}">${vsCa<=0?Math.round(-vsCa*100)+"% below":Math.round(vsCa*100)+"% above"} Canada (${CSI_CANADA[0].toFixed(1)})</span></div>
      <div><span>Change from 2024</span><span class="${lvl.ch<=0?"up":"down"}">${lvl.ch>0?"+":""}${lvl.ch}%</span></div>
      ${rank?`<div><span>Rank among ${rows.length} metro areas</span><span>#${rank} lowest</span></div>`:""}
      ${C&&P?`<div><span>${esc(PROV[prov])} overall</span><span>${P[0]}</span></div>`:""}</div>
    ${hoodHTML}
    <div class="linklist">${[link,STATCAN_CRIME].filter(Boolean).map(([t,u])=>`<a href="${u}" target="_blank" rel="noopener">${esc(t)} ↗</a>`).join("")}</div>
    <p class="hint" style="margin:0">Crime Severity Index from Statistics Canada (2025, released July 2026): it weights each crime by how serious it is; Canada in 2006 = 100. ${C?"Metro areas include their suburbs.":"This municipality isn't its own metro area, so the province-wide figure is shown."}</p>`;
  if(chartSets){$("pCrimeChart").hidden=false;render("xk",{kind:"line",labels:chartSets.labels,fmt:v=>Math.round(v).toLocaleString("en-CA"),sets:chartSets.sets});}
  PLUS.rep.crime=`<div class="rp-sec"><b>Crime and safety</b><p>Crime Severity Index ${lvl.v.toFixed(1)} for ${esc(lvl.name)} (Canada ${CSI_CANADA[0].toFixed(1)}), ${lvl.ch>0?"+":""}${lvl.ch}% from 2024.${rank?` #${rank} lowest of ${rows.length} metro areas.`:""} ${PLUS.rep.crimeHood&&muni==="Toronto"?PLUS.rep.crimeHood:""}</p></div>`;}

/* ---------- what's nearby: OpenStreetMap (two public servers), cached; a link if neither answers ---------- */
const OSM_SERVERS=["https://overpass.openstreetmap.fr/api/interpreter","https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter","https://overpass.private.coffee/api/interpreter"];
function osmQuery(la,lo){return `[out:json][timeout:20];(nwr(around:1000,${la},${lo})[shop~"^(supermarket|grocery|greengrocer|convenience)$"];nwr(around:1200,${la},${lo})[amenity~"^(school|kindergarten)$"];node(around:600,${la},${lo})[highway=bus_stop];nwr(around:1200,${la},${lo})[railway~"^(station|tram_stop|subway_entrance)$"];nwr(around:800,${la},${lo})[leisure~"^(park|playground)$"];nwr(around:800,${la},${lo})[amenity~"^(cafe|restaurant|pub|bar)$"];nwr(around:1500,${la},${lo})[amenity~"^(pharmacy|clinic|doctors|hospital)$"];);out center tags 400;`;}
const OSM_CATS=[["grocery","Groceries",1000,t=>/^(supermarket|grocery|greengrocer|convenience)$/.test(t.shop||""),22],["transit","Transit stop",600,t=>t.highway==="bus_stop"||/^(station|tram_stop|subway_entrance)$/.test(t.railway||""),22],
  ["school","School",1200,t=>/^(school|kindergarten)$/.test(t.amenity||""),16],["park","Park or playground",800,t=>/^(park|playground)$/.test(t.leisure||""),16],
  ["food","Cafés and restaurants",800,t=>/^(cafe|restaurant|pub|bar)$/.test(t.amenity||""),12],["health","Pharmacy or clinic",1500,t=>/^(pharmacy|clinic|doctors|hospital)$/.test(t.amenity||""),12]];
async function osmNearby(la,lo){const key=`hve-osm-${(+la).toFixed(3)},${(+lo).toFixed(3)}`;
  try{const c=JSON.parse(localStorage.getItem(key)||"null");if(c&&Date.now()-c.t<30*864e5)return {...c.d,src:"OpenStreetMap (saved on this device)"};}catch(e){}
  const urls=[OSM_SERVERS[0],...(ON_LOCAL?["/proxy/overpass"]:[]),...OSM_SERVERS.slice(1)];   // fastest server first, then the app relay (which tries them all), then the rest
  for(const s of urls){try{const r=await fetchT(s+"?data="+encodeURIComponent(osmQuery(la,lo)),s.startsWith("/")?60000:12000);if(!r.ok)continue;const j=await r.json();if(!j||!Array.isArray(j.elements))continue;
      const d=summarizeOSM(j.elements,+la,+lo);try{localStorage.setItem(key,JSON.stringify({t:Date.now(),d}));}catch(e){}return {...d,src:"OpenStreetMap (live)"};}catch(e){}}
  return null;}
function summarizeOSM(els,la,lo){const km=(a,b)=>{const r=Math.PI/180,x=(b-lo)*r*Math.cos(la*r),y=(a-la)*r;return 6371000*Math.hypot(x,y);};const out={};
  for(const [k] of OSM_CATS)out[k]={n:0,near:null,name:""};
  for(const e of els){const t=e.tags||{},a=e.lat??(e.center&&e.center.lat),b=e.lon??(e.center&&e.center.lon);if(a==null)continue;const d=km(a,b);
    for(const [k,,,test] of OSM_CATS)if(test(t)){const o=out[k];o.n++;if(o.near==null||d<o.near){o.near=Math.round(d);o.name=t.name||"";}}}
  return {cats:out};}
async function drawNearby(){const el=$("pNear"),ll=((aiProp||{}).pick||{}).ll||"",[la,lo]=ll.split(",");
  if(!la){el.innerHTML=`<h3>What's nearby</h3><p class="hint">No map point for this address.</p>`;return;}
  el.innerHTML=`<h3>What's nearby</h3><p class="hint">Looking up OpenStreetMap…</p>`;const my=PLUS.nearSeq=(PLUS.nearSeq||0)+1;
  const d=await osmNearby(la,lo);if(my!==PLUS.nearSeq)return;
  const osm=`https://www.openstreetmap.org/?mlat=${la}&mlon=${lo}#map=16/${la}/${lo}`;
  if(!d){el.innerHTML=`<h3>What's nearby</h3><p class="hint">The free OpenStreetMap servers couldn't be reached from this page (some previews block outside requests; the downloaded app can reach them).</p><div class="linklist"><a href="${osm}" target="_blank" rel="noopener">Open this spot on OpenStreetMap ↗</a></div>`;PLUS.rep.near="";return;}
  let sc=0;const rows=OSM_CATS.map(([k,l,rad,,w])=>{const o=d.cats[k];const got=o.n>0;sc+=got?(k==="food"?Math.min(1,o.n/8)*w:w*(o.near<=rad/2?1:.7)):0;
    return `<div><span>${l}</span><span>${got?`${o.n} · nearest ${o.near<1000?o.near+" m":(o.near/1000).toFixed(1)+" km"}${o.name?" ("+esc(o.name).slice(0,28)+")":""}`:"none within "+(rad<1000?rad+" m":rad/1000+" km")}</span></div>`;}).join("");
  sc=Math.round(sc);const word=sc>=80?"Walk to almost everything":sc>=60?"Very walkable":sc>=40?"Some errands on foot":"Car-dependent";
  el.innerHTML=`<h3>What's nearby</h3><div class="num">${sc}<small style="font-size:16px;color:var(--muted)"> / 100 · ${word}</small></div><div class="meter"><i style="width:${sc}%;background:var(--s3)"></i></div>
    <div class="kv">${rows}</div><p class="hint" style="margin:0">Everyday places within walking distance, from ${esc(d.src)}. A free stand-in for paid walkability scores.</p>
    <div class="linklist"><a href="${osm}" target="_blank" rel="noopener">See them on OpenStreetMap ↗</a></div>`;
  PLUS.rep.near=`<div class="rp-sec"><b>What's nearby</b><p>Everyday-walk score ${sc}/100 (${word}), from OpenStreetMap.</p></div>`;}

/* ---------- cash offer and 3-year range, added to the existing cards ---------- */
{const _liq=drawLiquidity;drawLiquidity=function(){_liq();try{const v=lastV;if(!v)return;let rep=0;document.querySelectorAll("#repList input:checked").forEach(x=>{rep+=REPAIRS.find(r=>r[0]===x.value)[2];});
  const offer=v*.92-rep*.5,S=eqState(),carry=(S.bal*(S.rate||4.5)/100/12);
  $("xlsub").insertAdjacentHTML("beforeend",`<div class="flag" style="margin-top:8px"><b>Sell to a cash buyer instead:</b> about ${money(offer)} as-is in roughly 2–3 weeks, with no commission or showings. Instant-offer companies typically charge 5–8% plus a risk discount; get several offers and compare with the listing route above.</div>`);
  PLUS.rep.liq=(PLUS.rep.liq||"").replace("</p></div>",` Cash buyer as-is: about ${money(offer)}.</p></div>`);}catch(e){}};}
{const _out=drawOutlook;drawOutlook=function(){_out();try{const A=IDXA(cur().reg),r36=[];for(let i=0;i+36<A.length;i++)r36.push(A[i+36]/A[i]);const v=lastV;
  $("xfsub").insertAdjacentHTML("beforeend",` <b>In 3 years:</b> ${money(v*qtile(r36,.1))} – ${money(v*qtile(r36,.9))} (typical ${money(v*qtile(r36,.5))}).`);}catch(e){}};}

/* ---------- relocation map: Leaflet when map tiles load here, otherwise a drawn map of city dots ---------- */
const CITY_LL={"Toronto":[43.653,-79.383],"Vancouver":[49.283,-123.121],"Montréal":[45.502,-73.567],"Calgary":[51.045,-114.072],"Edmonton":[53.546,-113.494],"Ottawa":[45.421,-75.697],
  "Winnipeg":[49.895,-97.138],"Québec City":[46.813,-71.208],"Hamilton":[43.256,-79.869],"Kitchener":[43.452,-80.493],"London":[42.984,-81.245],"Halifax":[44.649,-63.575],
  "Victoria":[48.428,-123.366],"Saskatoon":[52.133,-106.67],"Regina":[50.445,-104.619],"St. John's":[47.561,-52.712],"Moncton":[46.088,-64.778],"Trois-Rivières":[46.343,-72.543],
  "Fredericton":[45.964,-66.643],"Charlottetown":[46.238,-63.131],"Kelowna":[49.888,-119.496],"Windsor":[42.315,-83.036],"Sherbrooke":[45.404,-71.893],"Thunder Bay":[48.381,-89.247],
  "Lethbridge":[49.694,-112.833],"Saint John":[45.273,-66.063],"Whitehorse":[60.721,-135.057],"Brandon":[49.848,-99.95]};
let moveMap=null;
function drawMoveMap(){const box=$("mvMap");if(!box||!lastV)return;const cash=+$("mvEq").value||0,type=$("mvType").value||st.type;
  const pts=Object.entries(CITY_LL).map(([n,ll])=>{const m=M.find(x=>x.name===n);return m?{n,ll,cost:benchSafe(m,type)}:null;}).filter(Boolean);
  const good=css("--good"),bad=css("--bad");
  if(window.L&&typeof mapReady!=="undefined"&&mapReady===true){try{box.innerHTML="";box.style.height="320px";if(moveMap){moveMap.remove();moveMap=null;}
      moveMap=L.map(box,{scrollWheelZoom:false,attributionControl:true});L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:12,attribution:"© OpenStreetMap"}).addTo(moveMap);
      moveMap.fitBounds([[42,-128],[61,-52]]);for(const p of pts){const ok=cash>=p.cost;L.circleMarker(p.ll,{radius:7,color:ok?good:bad,fillOpacity:.85}).bindTooltip(`${p.n}: ${money(p.cost)} · ${ok?"cash left "+money(cash-p.cost):"short "+money(p.cost-cash)}`).addTo(moveMap);}
      return;}catch(e){}}
  // drawn map: longitude/latitude projected, no outside images needed
  const W=760,H=340,x=lo=>((lo+136)/(136-50))*(W-40)+20,y=la=>H-20-((la-41.5)/(62-41.5))*(H-40);
  box.style.height="auto";box.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of Canadian cities showing where this cash buys a home outright" style="width:100%;height:auto;display:block">
    <rect x="0" y="0" width="${W}" height="${H}" rx="8" fill="${css("--bg")}"/>
    ${pts.map(p=>{const ok=cash>=p.cost,cx=x(p.ll[1]).toFixed(1),cy=y(p.ll[0]).toFixed(1);return `<g><title>${esc(p.n)}: ${money(p.cost)}</title><circle cx="${cx}" cy="${cy}" r="6" fill="${ok?good:bad}" stroke="${css("--surface")}" stroke-width="2"/><text x="${+cx+8}" y="${+cy+4}" font-size="11" font-family="${css("--mono")}" fill="${css("--muted")}">${esc(p.n)}</text></g>`;}).join("")}
  </svg><p class="hint" style="margin:4px 0 0"><span style="color:${good}">●</span> buy outright with ${money(cash)} · <span style="color:${bad}">●</span> still needs a mortgage</p>`;}
{const _mv=drawMove;drawMove=function(){_mv();try{drawMoveMap();}catch(e){}};}

/* ---------- land transfer tax and closing costs (WOWA-style, 2026 rules, approximate) ---------- */
function brackets(v,B){let t=0,lo=0;for(const [hi,r] of B){if(v>lo)t+=(Math.min(v,hi)-lo)*r;lo=hi;}return t;}
const ON_B=[[55000,.005],[250000,.01],[400000,.015],[2000000,.02],[Infinity,.025]];
const TOR_B=[[55000,.005],[250000,.01],[400000,.015],[2000000,.02],[3000000,.025],[4000000,.035],[5000000,.045],[10000000,.055],[20000000,.065],[Infinity,.075]];
function ltt(prov,price,first,city){const out=[];
  if(prov==="ON"){let p=brackets(price,ON_B);const reb=first?Math.min(4000,p):0;out.push(["Ontario land transfer tax",p],...(reb?[["First-time buyer rebate (Ontario)",-reb]]:[]));
    if(city==="toronto"){const m=brackets(price,TOR_B),mr=first?Math.min(4475,m):0;out.push(["Toronto municipal land transfer tax",m],...(mr?[["First-time buyer rebate (Toronto)",-mr]]:[]));}}
  else if(prov==="BC"){const p=brackets(price,[[200000,.01],[2000000,.02],[3000000,.03],[Infinity,.05]]);let ex=0;
    if(first&&price<=860000){const full=brackets(Math.min(price,500000),[[200000,.01],[500000,.02]]);ex=price<=835000?full:full*(860000-price)/25000;}
    out.push(["BC property transfer tax",p],...(ex?[["First-time buyer exemption",-ex]]:[]));}
  else if(prov==="MB")out.push(["Manitoba land transfer tax",brackets(price,[[30000,0],[90000,.005],[150000,.01],[200000,.015],[Infinity,.02]])]);
  else if(prov==="QC"){const B=[[61500,.005],[307800,.01],[Infinity,.015]],MTL=[[61500,.005],[307800,.01],[552300,.015],[1104700,.02],[2136500,.025],[3113000,.035],[Infinity,.04]];
    out.push([city==="montreal"?"Welcome tax (Montréal rates)":"Welcome tax (droits de mutation)",brackets(price,city==="montreal"?MTL:B)]);}
  else if(prov==="NB")out.push(["New Brunswick real property transfer tax (1%)",price*.01]);
  else if(prov==="NS")out.push(["Deed transfer tax (1.5% in Halifax; 0.5–1.5% elsewhere)",price*.015]);
  else if(prov==="PE")out.push(["PEI real property transfer tax (1%)",first?0:price*.01],...(first?[["First-time buyer exemption","note"]]:[]));
  else if(prov==="AB")out.push(["Alberta land title transfer fee",50+Math.ceil(price/5000)*5]);
  else if(prov==="SK")out.push(["Saskatchewan land title fee (about 0.3%)",price>6300?(price-6300)*.003+25:25]);
  else if(prov==="NL")out.push(["Newfoundland and Labrador deed registration",100+Math.max(0,price-500)*.004]);
  else out.push(["Land title registration (small fixed fees)",500]);
  return out.filter(x=>x[1]!=="note");}
function calcClose(){const prov=$("lcProv").value,price=+$("lcPrice").value||0,first=$("lcFirst").checked,city=$("lcCity").value,dnPct=Math.max(5,+$("lcDown").value||20)/100,out=$("lcOut");
  if(!(price>0)){out.innerHTML="";return;}
  const minDown=price<1500000?.05*Math.min(price,500000)+.1*Math.max(0,price-500000):price*.2,down=Math.max(price*dnPct,minDown),loan=price-down,ltv=loan/price;
  const premRate=ltv<=.8?0:ltv<=.85?.028:ltv<=.9?.031:.04,prem=loan*premRate+(first&&premRate?loan*0.002*0:0),pstRate={ON:.08,QC:.09,SK:.06}[prov]||0,pst=prem*pstRate;
  const L=ltt(prov,price,first,city),taxes=L.reduce((s,x)=>s+x[1],0),legal=prov==="AB"?1500:2000,other=[["Legal fees and disbursements",legal],["Title insurance",350],["Home inspection",550],["Adjustments (prepaid tax, utilities)",price*.0015]];
  if(pst)other.push([`Provincial sales tax on mortgage insurance (${pstRate*100}%)`,pst]);
  const cash=down+taxes+other.reduce((s,x)=>s+x[1],0),rate=+$("eqMkt").value||+$("rate").value||4.2,pm=pmtOf(loan+prem,rate,first?30:25);
  out.innerHTML=`<div class="num">${money(cash)}<small style="font-size:16px;color:var(--muted)"> cash to close</small></div>
    <div class="kv"><div><span>Down payment (${(down/price*100).toFixed(1)}%)</span><span>${money(down)}</span></div>
      ${L.map(([k,v])=>`<div><span>${esc(k)}</span><span class="${v<0?"up":""}">${v<0?"−":""}${dollars(Math.abs(v))}</span></div>`).join("")}
      ${other.map(([k,v])=>`<div><span>${esc(k)}</span><span>${dollars(v)}</span></div>`).join("")}
      ${prem?`<div><span>Mortgage insurance premium (${(premRate*100).toFixed(2)}%, added to the loan)</span><span>${dollars(prem)}</span></div>`:""}
      <div><span>Mortgage payment at ${rate.toFixed(2)}%, ${first?30:25} years</span><span>${dollars(pm)}/mo</span></div></div>
    <p class="hint" style="margin:0">2026 rules, approximate: insured mortgages need 5% down on the first $500,000 and 10% above, up to $1.5M; first-time buyers can choose 30-year insured amortization. Taxes vary by municipality; your lawyer confirms the exact figures.</p>`;}

/* ---------- share and embed (broker widget), and ?address= links ---------- */
function pageBase(){try{return location.origin&&location.origin!=="null"?location.origin+location.pathname:"";}catch(e){return "";}}
function drawShare(){const el=$("pShare"),adr=$("addr").value.trim(),base=pageBase(),link=base&&adr?`${base}?address=${encodeURIComponent(adr)}`:"";
  const embed=base?`<iframe src="${base}${adr?`?address=${encodeURIComponent(adr)}`:""}" title="Home value estimate" style="width:100%;height:1400px;border:0" loading="lazy"></iframe>`:"";
  el.innerHTML=`<h3>Share it or put it on your website</h3><p class="hint" style="margin:0">A link that opens straight to this home's estimate, and code to embed the whole tool on a broker or agent website, like a home-value widget. Links work wherever the app is hosted (your own site or the downloaded app); a private preview link may not pass the address along.</p>
    ${link?`<label>Link to this estimate <input readonly value="${esc(link)}" onclick="this.select()"></label>`:""}
    ${embed?`<label>Embed code <textarea readonly rows="3" style="width:100%;font:12px var(--mono);padding:8px;border:1px solid var(--muted);border-radius:6px;background:var(--bg);color:var(--fg)" onclick="this.select()">${esc(embed)}</textarea></label>`:`<p class="hint">Host the downloaded app's folder on any website to get an embed code.</p>`}
    <div class="btns"><button type="button" class="ghost" id="shareCopy">Copy link</button></div><div class="dl-msg"></div>`;
  $("shareCopy").onclick=async()=>{PLUS_BTN=$("shareCopy");if(!link){plusMsg("No link available in this view.");return;}try{await navigator.clipboard.writeText(link);plusMsg("Link copied.");}catch(e){plusMsg("Select the link above and copy it.");}};}
(function autoAddress(){let q=null;try{const u=new URLSearchParams(location.search);q=u.get("address")||u.get("a");}catch(e){}
  if(!q)return;const t0=Date.now();(function wait(){if(DB.munis&&DB.fsa&&typeof resolveTyped==="function"){$("addr").value=q.slice(0,200);resolveTyped().then(ok=>{if(ok)refresh();});}else if(Date.now()-t0<20000)setTimeout(wait,250);})();})();

/* ---------- layout ---------- */
(function(){
  const g=$("plus").querySelector(".pgrid");
  g.insertAdjacentHTML("beforeend",`
    <div class="pcard" id="pCrimeWrap"><div id="pCrime"></div><div class="chart" id="pCrimeChart" hidden><div class="chart-top"><h3>Major crime per 100,000 people</h3><div class="tools"><button type="button" data-png="xk">PNG</button><button type="button" data-csv="xk">CSV</button></div></div><div class="box" id="xk"></div><div class="mode" id="mk" hidden></div><div class="dl-msg"></div></div></div>
    <div class="pcard" id="pNear"></div>
    <div class="pcard wide" id="pMoveMap"><h3>Map: where your cash buys a home outright</h3><div id="mvMap"></div></div>
    <div class="pcard wide" id="pShare"></div>`);
  const c=$("calc").querySelector(".pgrid"),pv=Object.entries(PROV).map(([k,v])=>`<option value="${k}">${v}</option>`).join("");
  c.insertAdjacentHTML("beforeend",`<div class="pcard wide"><h3>Land transfer tax and closing costs</h3>
    <div class="row3"><label for="lcProv">Province <select id="lcProv">${pv}</select></label><label for="lcPrice">Purchase price ($) <input id="lcPrice" type="number" min="10000" step="1000" value="800000"></label><label for="lcDown">Down payment (%) <input id="lcDown" type="number" min="5" max="100" step="1" value="10"></label></div>
    <div class="row3"><label for="lcCity">City <select id="lcCity"><option value="">Elsewhere</option><option value="toronto">Toronto (adds municipal tax)</option><option value="montreal">Montréal (higher tiers)</option></select></label>
      <label style="display:flex;gap:8px;align-items:center;align-self:end"><input id="lcFirst" type="checkbox" style="width:auto;min-height:auto"> First-time buyer</label><div></div></div>
    <div id="lcOut"></div></div>`);
  $("lcProv").value=st.prov in PROV?st.prov:"ON";
  ["lcProv","lcPrice","lcDown","lcCity","lcFirst"].forEach(id=>$(id).addEventListener("input",calcClose));calcClose();
  // official assessment lookups next to the assessment calculator
  const ca=$("caOut");if(ca)ca.insertAdjacentHTML("afterend",`<div class="linklist" style="margin-top:4px"><a href="https://www.mpac.ca/" target="_blank" rel="noopener">Ontario: MPAC ↗</a><a href="https://www.bcassessment.ca/" target="_blank" rel="noopener">British Columbia: BC Assessment ↗</a><a href="https://www.pvsc.ca/" target="_blank" rel="noopener">Nova Scotia: PVSC ↗</a></div>`);
  Object.assign(FR_EXACT,{"Crime and safety":"Criminalité et sécurité","What's nearby":"À proximité","Land transfer tax and closing costs":"Droits de mutation et frais de clôture",
    "Share it or put it on your website":"Partager ou intégrer à votre site","Map: where your cash buys a home outright":"Carte : où votre argent achète une propriété sans hypothèque"});
})();

/* ---------- wiring ---------- */
const _updPlus4=updatePlus;updatePlus=function(){_updPlus4();if(!aiProp||!lastV)return;
  try{drawShare();}catch(e){}
  const lbl=$("addr").value.trim();if(lbl!==PLUS.crimeLbl){PLUS.crimeLbl=lbl;drawCrime().catch(e=>console.warn("crime",e));drawNearby().catch(()=>{});}};
$("mvEq").addEventListener("input",()=>{try{drawMoveMap();}catch(e){}});$("mvType").addEventListener("input",()=>{try{drawMoveMap();}catch(e){}});
const _repPlus4=buildReport;buildReport=async function(){await _repPlus4();const rep=$("report"),n=rep.querySelector(".notice"),b=rep.querySelector(".brand-line");
  const extra=["crime","near"].map(k=>PLUS.rep[k]||"").join("");(b||n)?(b||n).insertAdjacentHTML("beforebegin",extra):rep.insertAdjacentHTML("beforeend",extra);};
