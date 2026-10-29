/* ---- No-server mode: every lookup comes from pre-computed real data files in data/ ----
   munis.json   all 3,515 Canadian municipalities (StatCan National Address Register)
   fsa.json     every postal area: 2021 Census median moved to today + record medians by property type
   streets/XXX.json  street-level medians by type from municipal assessment records (Sep-2026 $)            */
let DB={munis:null,fsa:null,acc:null,streets:{}}, aiProp=null, acItems=[], acSel=-1, acT=null;
const acList=$("acList"), money=v=>"$"+(Math.round(v/1000)*1000).toLocaleString("en-CA"), r5k=v=>Math.round(v/5000)*5000;
const esc=t=>String(t).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const TYPEWORDS=new Set("ST STREET AVE AV AVENUE RD ROAD DR DRIVE CRES CR CRESCENT BLVD BOUL BOULEVARD BV PL PLACE CRT CT CO COURT TRAIL TR WAY WY CLOSE CL GATE GA LANE LN HTS HEIGHTS HT GREEN GR PARK PA PK TERR TERRACE TC CIR CIRCLE CI MANOR MR POINT PT RISE RI SQ SQUARE VIEW VW BAY BA RUE CH CHEMIN MONTEE MTEE RANG ALLEE COMMON CM LINK LI MEWS ME HILL HL PKY PARKWAY HWY HIGHWAY GDNS GARDENS GD ROW WALK WK LANDING LD CV COVE GROVE GV ESTATES ESTS BEND BN HEATH ISLAND VILLAGE RU BO RT RTE ROUTE MO RG CA CARRE CROIS CROISSANT IMP IMPASSE PROM PROMENADE TSSE TERRASSE AL CHE AU AUT AUTOROUTE SENTIER SENT COTE QUAI PARC CERCLE CE".split(" "));
const DIRS={N:"N",S:"S",E:"E",W:"W",NE:"NE",NW:"NW",SE:"SE",SW:"SW",NORTH:"N",SOUTH:"S",EAST:"E",WEST:"W",EST:"E",OUEST:"W",NORD:"N",SUD:"S",O:"W"};
const PART=new Set(["DE","LA","LE","DU","DES","L","D","THE"]);
const plain=s=>String(s||"").normalize("NFKD").replace(/\p{M}/gu,"").toUpperCase().replace(/\(.*?\)/g," ").replace(/[^A-Z0-9 ]/g," ");
function streetKey(street){const toks=plain(street).split(/\s+/).filter(Boolean);
  const allt=toks.filter(t=>!(t in DIRS)&&!PART.has(t));
  let core0=allt.filter(t=>!TYPEWORDS.has(t));if(!core0.length)core0=allt.slice(0,1);   // "VIEW ST" keeps VIEW
  const core=core0.map(t=>t.replace(/^(\d+)(ST|ND|RD|TH)$/,"$1"))
    .map(t=>["ST","STE","SAINTE"].includes(t)?"SAINT":({TWP:"TOWNSHIP",RGE:"RANGE",RR:"RANGE",MT:"MOUNT"}[t]||t));
  return core.join(" ")+"|"+toks.filter(t=>t in DIRS).map(t=>DIRS[t]).join("");}
const title=s=>String(s).toLowerCase().replace(/(^|[\s\-'])(\p{L})/gu,(m,a,b)=>a+b.toUpperCase());
function niceStreet(k){const [core,dir]=k.split("|");return title(core)+(dir?" "+dir:"");}

const DAV={};let CSDT=null;
async function blockValue(code){if(!code)return null;const pr=code.slice(0,2);
  if(!DAV[pr])DAV[pr]=getJSON("data/da_"+pr+".json").catch(()=>({}));
  if(!CSDT)CSDT=getJSON("data/csd_types.json").catch(()=>({}));
  const v=(await DAV[pr])[code];return v?{da:code,v:v[0],mkey:v[1],types:(await CSDT)[v[1]]||null}:null;}
/* legal description + assessment history where cities publish them: data/detail/<prefix>.json (see build_details.py) */
const normNum=x=>{x=plain(x).replace(/[^0-9A-Z]/g,"");return x.replace(/^0+/,"")||(x?"0":"");};
let DETIDX=null;const DET={};
const STYPE={"ST":"ST","STREET":"ST","AVE":"AVE","AV":"AVE","AVENUE":"AVE","RD":"RD","ROAD":"RD","DR":"DR","DRIVE":"DR","CRES":"CRES","CR":"CRES","CRESCENT":"CRES","CROIS":"CRES","CROISSANT":"CRES","PL":"PL","PLACE":"PL","CT":"CT","CRT":"CT","CO":"CT","COURT":"CT","BAY":"BAY","BA":"BAY","CL":"CL","CLOSE":"CL","WAY":"WAY","WY":"WAY","GATE":"GATE","GA":"GATE","LANE":"LANE","LN":"LANE","TERR":"TERR","TERRACE":"TERR","TC":"TERR","CIR":"CIR","CIRCLE":"CIR","CI":"CIR","HTS":"HTS","HEIGHTS":"HTS","HT":"HTS","GREEN":"GR","GR":"GR","PARK":"PARK","PA":"PARK","PK":"PARK","MEWS":"MEWS","ME":"MEWS","BLVD":"BLVD","BOUL":"BLVD","BV":"BLVD","BOULEVARD":"BLVD","BO":"BLVD","GROVE":"GV","GV":"GV","RISE":"RISE","RI":"RISE","VIEW":"VIEW","VW":"VIEW","MANOR":"MR","MR":"MR","POINT":"PT","PT":"PT","SQ":"SQ","SQUARE":"SQ","COMMON":"CM","CM":"CM","LINK":"LINK","LI":"LINK","HILL":"HL","HL":"HL","LANDING":"LD","LD":"LD","COVE":"CV","CV":"CV","TRAIL":"TR","TR":"TR","HWY":"HWY","HIGHWAY":"HWY","RUE":"RUE","RU":"RUE","CH":"CH","CHEMIN":"CH","RTE":"RTE","RT":"RTE","ROUTE":"RTE","PKY":"PKY","PKWY":"PKY","PARKWAY":"PKY","ROW":"ROW","WALK":"WALK","WK":"WALK","ALLEE":"ALLEE","AL":"ALLEE"};
function stype(street){const toks=plain(street).split(/\s+/).filter(x=>x&&!(x in DIRS));let h="";for(const x of toks)if(STYPE[x])h=STYPE[x];return h;}
async function detailFor(it){if(!it||!it.fsa||!it.civic)return null;
  if(!DETIDX)DETIDX=getJSON("data/detail/index.json").catch(()=>({}));const idx=await DETIDX;
  const file=Object.keys(idx).find(k=>idx[k].includes(it.fsa));if(!file)return null;
  if(!DET[file])DET[file]=getJSON("data/detail/"+file+".json").catch(()=>({}));
  const d=((await DET[file])[it.fsa])||{},ty=stype(it.sname||""),k=`${normNum(it.unit||"")}|${normNum(it.civic||"")}|${it.street}|${ty}`;
  return d[k]||(it.unit?null:d[`|${normNum(it.civic||"")}|${it.street}|${ty}`])||null;}
async function nearbyFor(it){if(!it||!it.fsa||!it.street)return [];
  if(!DETIDX)return [];const idx=await DETIDX;const file=Object.keys(idx).find(k=>idx[k].includes(it.fsa));if(!file)return [];
  const d=((await DET[file])||{})[it.fsa]||{},me=parseInt(it.civic,10)||0,out=[],ty=stype(it.sname||"");
  for(const [k,v] of Object.entries(d)){const [u,c,core,dir,kt]=k.split("|");if(`${core}|${dir}`!==it.street||u||(kt||"")!==ty)continue;
    const n=parseInt(c,10);if(!n||n===me)continue;const h=decodeHistory(v[1]);if(!h.length)continue;
    const last=h[h.length-1],first=h[0];out.push({civic:c,dist:Math.abs(n-me),val:last[1],year:last[0],chg:first[0]<last[0]?Math.round((last[1]/first[1]-1)*100):null,since:first[0]});}
  // drop office towers and other whole-building records: far above or below the street's typical value
  const vs=out.map(o=>o.val).sort((a,b)=>a-b),med=vs[Math.floor(vs.length/2)]||0;
  const ok=vs.length>=3?out.filter(o=>o.val<=med*3&&o.val>=med/3):out.filter(o=>o.val<5e6);
  return ok.sort((a,b)=>a.dist-b.dist).slice(0,6).sort((a,b)=>(parseInt(a.civic)||0)-(parseInt(b.civic)||0));}
function decodeHistory(s){if(!s)return [];const [head,vals]=s.split(":"),[yy,step]=head.split("/").map(Number);
  return vals.split(",").map((v,i)=>v?[2000+yy+i*step,parseInt(v,36)*1000]:null).filter(Boolean);}
/* Map and satellite on the page (OpenStreetMap + Esri World Imagery: free, no key; nothing opens another site) */
let mapLayer="map";
const TOWN_MUNI=getJSON("data/town_muni.json").catch(()=>({})),DA_MUNI=getJSON("data/da_muni.json").catch(()=>({}));
function photoLinks(it){const box=$("photoLinks");if(!it){box.hidden=true;return;}
  const [la,lo]=(it.ll||"").split(",");if(!la){box.hidden=true;return;}
  box.innerHTML=`<div class="seg view-tabs" role="group" aria-label="View">${[["map","Map"],["sat","Satellite"]].map(([k,n])=>`<button type="button" data-v="${k}" aria-pressed="${mapLayer===k}">${n}</button>`).join("")}</div>`;
  box.querySelectorAll("[data-v]").forEach(b=>b.onclick=()=>{mapLayer=b.dataset.v;box.querySelectorAll("[data-v]").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));setLayer();});
  box.hidden=false;tryMap(+la,+lo);}
let mapReady=null,lmap=null,lpin=null;
let baseOSM=null,baseSat=null,satLabels=null;
function setLayer(){if(!lmap)return;const sat=mapLayer==="sat";
  [baseOSM,baseSat,satLabels].forEach(l=>l&&lmap.hasLayer(l)&&lmap.removeLayer(l));
  if(sat){baseSat.addTo(lmap);satLabels.addTo(lmap);lmap.setZoom(Math.max(lmap.getZoom(),18));}else baseOSM.addTo(lmap);}
function tryMap(la,lo){ // probe one tile first; where the host refuses outside images the map stays hidden and a note explains
  if(mapReady===false){mapBlocked();return;}
  const show=()=>{$("map").hidden=false;if(!lmap){lmap=L.map("map",{scrollWheelZoom:false});
      baseOSM=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:"© OpenStreetMap"});
      baseSat=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{maxZoom:19,attribution:"Imagery © Esri, Maxar, Earthstar Geographics"});
      satLabels=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",{maxZoom:19});}
    setLayer();lmap.setView([la,lo],mapLayer==="sat"?18:17);if(lpin)lpin.setLatLng([la,lo]);else lpin=L.circleMarker([la,lo],{radius:9,color:css("--accent-2"),fillOpacity:1,className:"hve-pin"}).addTo(lmap);setTimeout(()=>lmap.invalidateSize(),60);};
  if(mapReady===true){show();return;}
  const img=new Image();img.onload=()=>{const css=document.createElement("link");css.rel="stylesheet";css.href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";document.head.appendChild(css);
    const sc=document.createElement("script");sc.src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";sc.onload=()=>{mapReady=true;show();};sc.onerror=()=>{mapReady=false;mapBlocked();};document.head.appendChild(sc);};
  img.onerror=()=>{mapReady=false;mapBlocked();};img.src="https://tile.openstreetmap.org/0/0/0.png";}
function mapBlocked(){const box=$("photoLinks");if(!box||box.querySelector(".map-note"))return;
  box.querySelector(".view-tabs")?.remove();
  box.insertAdjacentHTML("beforeend",`<p class="hint map-note">The map and satellite view load when this page runs on its own website. This preview host blocks outside map images.</p>`);}
async function getJSON(u){const r=await fetch(u);if(!r.ok)throw new Error(u+" "+r.status);return r.json();}
async function loadData(){try{[DB.munis,DB.fsa,DB.acc]=await Promise.all([getJSON("data/munis.json"),getJSON("data/fsa.json"),getJSON("data/accuracy.json")]);DB.dacc=await getJSON("data/da_accuracy.json").catch(()=>null);
  fillMuni();$("addrHint").textContent="Type your street address, or a postal code. Pick your municipality first if you don't know the postal code.";}
  catch(e){$("addrHint").textContent="The local data didn't load. Estimates will use the regional benchmarks only.";}}
async function streetsFor(f){if(f in DB.streets)return DB.streets[f];
  if(!DB.fsa||!DB.fsa[f]||!DB.fsa[f].s){DB.streets[f]={};return DB.streets[f];}   // no records in this postal area
  const L=f[0];DB.letter=DB.letter||{};
  if(!DB.letter[L])DB.letter[L]=getJSON("data/streets_"+L+".json").catch(()=>({}));   // one bundle per postal-code letter
  DB.streets[f]=(await DB.letter[L])[f]||{};return DB.streets[f];}

/* every municipality in the province, not just the built-in list */
const _fillMuni=fillMuni;
fillMuni=function(){if(!DB.munis){_fillMuni();return;}
  const list=DB.munis.filter(m=>m.prov===st.prov);
  if(!list.some(m=>m.name===st.muni))st.muni=(list[0]||{}).name;
  $("muni").innerHTML=list.map(m=>`<option${m.name===st.muni?" selected":""}>${esc(m.name)}</option>`).join("");
  ensureBench(st.muni,st.prov);};
function ensureBench(name,prov){ // give the chart model a benchmark for any municipality
  if(M.some(x=>x.name===name&&x.prov===prov))return;const mm=(DB.munis||[]).find(x=>x.name===name&&x.prov===prov);if(!mm)return;
  const f=mm.fsa.map(c=>DB.fsa[c]).find(Boolean);if(!f||!f.c)return;M.push({name,prov,reg:f.r,bench:f.c,fsa:mm.fsa});}

function parseAddr(text){
  const raw=String(text).toUpperCase();
  const pc=raw.match(/\b([ABCEGHJKLMNPRSTVXY]\d[A-Z])\s?(\d[A-Z]\d)?\b/);
  let rest=raw.replace(/\b[ABCEGHJKLMNPRSTVXY]\d[A-Z]\s?(\d[A-Z]\d)?\b/,"");
  // a city is only read after a comma: "12 Main St, Gatineau"
  let city=null,place=null;const parts=rest.split(",");
  const pv=(raw.match(/\b(AB|BC|SK|MB|ON|QC|NB|NS|PE|NL|YT|NT|NU)\b\.?\s*(?:[ABCEGHJKLMNPRSTVXY]\d[A-Z]\s?\d[A-Z]\d)?\s*$/)||[])[1]||null;
  if(parts.length>1){const tail=plain(parts.slice(1).join(" ")).replace(/\b(AB|BC|SK|MB|ON|QC|NB|NS|PE|NL|YT|NT|NU)\b/g,"").trim();
    if(tail)city=(DB.munis||[]).filter(x=>(!pv||x.prov===pv)&&(plain(x.name)===tail||tail.startsWith(plain(x.name)))).sort((a,b)=>b.n-a.n)[0]||null;if(tail&&!city)place=tail.replace(/\s+/g," ");rest=parts[0];}
  else{   // no comma: "100 Queen St W Toronto ON" — a trailing municipality name after a street type or direction
    const w=rest.replace(/\b(AB|BC|SK|MB|ON|QC|NB|NS|PE|NL|YT|NT|NU)\.?\s*$/,"").trim().split(/\s+/),sq=s=>plain(s).trim().replace(/\s+/g," ");
    for(let n=Math.min(3,w.length-3);n>=1&&!city;n--){const name=sq(w.slice(-n).join(" ")),before=sq(w[w.length-n-1]);
      if(!(TYPEWORDS.has(before)||/^(N|S|E|W|NE|NW|SE|SW|EST|OUEST)$/.test(before)))continue;
      const mm=(DB.munis||[]).filter(x=>(!pv||x.prov===pv)&&sq(x.name)===name).sort((a,b)=>b.n-a.n)[0];
      if(mm){city=mm;rest=w.slice(0,-n).join(" ");}}}
  rest=rest.replace(/\b(APT|UNIT|SUITE)\b\.?\s*(\w+)/,(m,w,u)=>" #"+u+" ");
  let unit="";const hash=rest.match(/#\s*(\w+)/);if(hash){unit=hash[1];rest=rest.replace(hash[0]," ");}
  const m=rest.trim().match(/^(?:(\w+)\s*-\s*)?(\d+[A-Z]?)\s+(.*)$/);
  if(m&&m[1])unit=m[1];
  let street=(m?m[3]:rest).trim();
  // "12141 Jasper Ave 1607": a trailing number after a street type is the unit (not "Township Road 510")
  const tail=street.match(/^(.*\b(ST|STREET|AVE|AV|AVENUE|DR|DRIVE|BLVD|BOUL|CRES|CRT|CT|PL|PLACE|WAY|LANE|LN|TERR|SQ|GATE|CLOSE|RUE|CIR)\b\.?(?:\s+(?:N|S|E|W|NE|NW|SE|SW|EST|OUEST))?)\s+#?(\d+[A-Z]?)$/);
  if(tail&&!unit){street=tail[1];unit=tail[3];}
  return {unit,civic:m?m[2]:"",street,fsa:pc?pc[1]:null,ldu:pc&&pc[2]||null,city,place,pv};}

function acShow(items,msg){acItems=items;acSel=-1;
  acList.innerHTML=msg?`<li class="msg" role="option" aria-disabled="true">${esc(msg)}</li>`:items.map((it,i)=>`<li role="option" id="ac${i}" data-i="${i}">${esc(it.label)}<br><small>${esc(it.sub)}</small></li>`).join("");
  acList.hidden=!(items.length||msg);$("addr").setAttribute("aria-expanded",String(!acList.hidden));}

async function suggest(){const q=$("addr").value.trim();$("addrClear").hidden=!q;if(q.length<3||!DB.fsa){acShow([]);return;}
  const a=parseAddr(q);if(a.city){st.prov=a.city.prov;$("prov").value=a.city.prov;st.muni=a.city.name;fillMuni();}
  const mun=DB.munis.find(x=>x.name===st.muni&&x.prov===st.prov);
  const fsas=a.fsa?[a.fsa]:(mun?mun.fsa:[]);
  let full=null;
  if(a.place&&a.street){   // "10 Sunrise Dr, Eskasoni": a community that is not a municipality; search Canada for the street in that place
    const r=await addressSearch(a,null,"all"),hit=(r||[]).filter(o=>plain(o.city).trim().replace(/\s+/g," ")===a.place);if(hit.length)full=hit;}
  if(!(full&&full.length))full=await addressSearch(a,mun);          // full address list when the address files are available
  if(a.city&&a.street){const want=plain(a.city.name).trim().replace(/\s+/g," "),inTown=o=>plain(o.city).trim().replace(/\s+/g," ")===want;
    if(!(full&&full.some(inTown))){const r=await addressSearch({...a,city:null,place:want},null,"all"),hit=(r||[]).filter(inTown);if(hit.length)full=hit;}}
  if(a.street&&!a.city){   // "9291 Morning Glory Rd Pefferlaw ON": drop a trailing town/hamlet name and search all of Canada
    const sq=s=>plain(s).trim().replace(/\s+/g," "),w=a.street.replace(/\b(AB|BC|SK|MB|ON|QC|NB|NS|PE|NL|YT|NT|NU)\.?$/,"").trim().split(/\s+/);
    const found=full&&full.length;
    // a result already in the town typed at the end: keep it
    if(!(found&&w.length>2&&sq(w.slice(-3).join(" ")).includes(sq(full[0].city))))
    for(let n=1;n<=Math.min(4,w.length-1);n++){const place=sq(w.slice(-n).join(" ")),before=sq(w[w.length-n-1]);
      if(found&&!(TYPEWORDS.has(before)||/^(N|S|E|W|NE|NW|SE|SW|EST|OUEST)$/.test(before)))continue;   // only a word after the street type can be a town
      const r=await addressSearch({...a,street:w.slice(0,-n).join(" "),place},null,"all");
      if(r&&r.length){const hit=r.filter(o=>sq(o.city)===place);if(hit.length){full=hit;break;}if(!found){full=r;break;}}}}
  if(full&&full.length){acShow(full);return;}
  if(!a.street||a.street.length<2){
    const own=a.fsa&&((mun&&mun.fsa.includes(a.fsa))?mun:(DB.munis||[]).filter(x=>x.prov===provOf(a.fsa)&&x.fsa.includes(a.fsa)).sort((p,q)=>q.n-p.n)[0]);
    if(a.fsa&&DB.fsa[a.fsa])acShow([{fsa:a.fsa,label:`Postal area ${a.fsa}`,sub:`${own?own.name+", ":""}value from the postal area`,street:null}]);else acShow([]);return;}
  const [want,wantDir]=streetKey(a.street).split("|");const items=[];
  const files=await Promise.all(fsas.map(f=>streetsFor(f).then(s=>[f,s])));
  for(const [f,s] of files){if(!s)continue;
    for(const k of Object.keys(s)){const [core,dir]=k.split("|");
      if(!(core.startsWith(want)||core.includes(" "+want)))continue;
      const rg=s[k]._r,cv=parseInt(a.civic,10);
      const score=(core===want?0:2)+(wantDir&&dir!==wantDir?1:0)+(rg&&cv?(cv>=rg[0]&&cv<=rg[1]?0:4):0);
      items.push({score,fsa:f,street:k,civic:a.civic,unit:a.unit,
        label:`${a.unit?a.unit+"-":""}${a.civic?a.civic+" ":""}${core===want?title(a.street):niceStreet(k)}`,
        sub:`${mun?mun.name:""} ${f} · ${Object.entries(s[k]).filter(([t])=>t!=="_r").reduce((n,[,x])=>n+x[1],0)} homes on record`});}}
  items.sort((x,y)=>x.score-y.score);items.splice(8);
  if(!items.length&&(a.fsa||(mun&&a.city))){/* never fall back to a postal area left over from an earlier search */const f=a.fsa||fsas[0];items.push({fsa:f,street:null,civic:a.civic,unit:a.unit,label:q,sub:`No records for this street. We'll use postal area ${f||""}.`});}
  acShow(items,items.length?null:"Pick your municipality below or add the postal code, then type the street again.");}
$("addr").addEventListener("input",()=>{clearTimeout(acT);acT=setTimeout(suggest,90);});
$("addr").addEventListener("keydown",e=>{if(acList.hidden||!acItems.length)return;
  if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();acSel=(acSel+(e.key==="ArrowDown"?1:-1)+acItems.length)%acItems.length;
    [...acList.children].forEach((li,i)=>li.setAttribute("aria-selected",String(i===acSel)));}
  else if(e.key==="Enter"){e.preventDefault();pick(acItems[Math.max(0,acSel)]);} else if(e.key==="Escape")acShow([]);});
acList.addEventListener("mousedown",e=>{const li=e.target.closest("li[data-i]");if(li){e.preventDefault();pick(acItems[+li.dataset.i]);}});
$("addr").addEventListener("blur",()=>setTimeout(()=>acShow([]),120));
$("addrClear").addEventListener("click",()=>{$("instant").hidden=true;$("photoLinks").hidden=true;$("map").hidden=true;$("addr").value="";$("addrClear").hidden=true;aiProp=null;$("facts").hidden=true;acShow([]);refresh();$("addr").focus();});
$("muni").addEventListener("change",()=>ensureBench(st.muni,st.prov));

async function pick(it){if(!it)return;acShow([]);sqftKnown=false;parkSet=false;
  if(it.postal){$("addr").value=`${it.label}, ${it.sub}`;
    // the municipality: from this address's Census block (exact), else its postal code / mailing town in the register
    const TM=(await TOWN_MUNI)||{},DM=(await DA_MUNI)||{},tm=(it.da&&DM.d&&DM.d[it.da]!=null&&DM.n[DM.d[it.da]])||(TM.p||{})[String(it.postal||"").replace(/\s/g,"")]||(TM.t||TM)[`${it.fsa}|${String(it.city||"").toUpperCase()}`];
    const mm=(tm&&(DB.munis||[]).find(x=>x.name===tm&&x.prov===provOf(it.fsa)))
      ||(DB.munis||[]).filter(x=>x.prov===(provOf(it.fsa)||st.prov)&&x.fsa.includes(it.fsa)&&plain(x.name)===plain(it.city))[0]
      ||(DB.munis||[]).filter(x=>x.prov===(provOf(it.fsa)||st.prov)&&x.fsa.includes(it.fsa)).sort((a,b)=>b.n-a.n)[0];
    if(mm){st.prov=mm.prov;$("prov").value=mm.prov;st.muni=mm.name;fillMuni();}}
  if(!it.postal&&it.fsa){   // postal-area pick: move to the municipality that owns this postal area, not the last one used
    const cur=(DB.munis||[]).find(x=>x.name===st.muni&&x.prov===st.prov);
    if(!cur||!cur.fsa.includes(it.fsa)){const mm=(DB.munis||[]).filter(x=>x.prov===provOf(it.fsa)&&x.fsa.includes(it.fsa)).sort((a,b)=>b.n-a.n)[0];
      if(mm){st.prov=mm.prov;$("prov").value=mm.prov;st.muni=mm.name;fillMuni();}}}
  if(it.postal);else if(it.street)$("addr").value=`${it.label}, ${st.muni} ${it.fsa}`;
  const f=DB.fsa[it.fsa]||null, s=it.street?((await streetsFor(it.fsa))||{})[it.street]:null;
  ensureBench(st.muni,st.prov);
  photoLinks(it);
  const det=await detailFor(it),near=await nearbyFor(it),legal=det&&det[0]?det[0].replace(/(^|[ ,])Pl /g,"$1Plan ").replace(/ Blk /g," Block "):null;
  aiProp={detail:det,near,pick:it,history:det?decodeHistory(det[1]):[],legal,fsa:it.fsa,f,street:s,streetName:it.street?niceStreet(it.street):null,unit:it.unit,block:await blockValue(it.da)};
  if(it.unit&&!isCondo(st.sub)){st.sub="condo";applySub(true);}
  else if(!it.unit&&!s&&isCondo(st.sub)){st.sub="detached";applySub(true);}   // no unit: drop a leftover condo choice
  else if(s&&!it.unit){const top=Object.entries(s).filter(([t])=>t!=="_r").sort((a,b)=>b[1][1]-a[1][1])[0];if(top&&SUB[top[0]]&&top[0]!==st.sub){st.sub=top[0];applySub(true);}}
  $("condoBox").hidden=!isCondo(st.sub);drawRepairs();
  if(it.unit){const n=parseInt(it.unit,10);if(n>=100)$("floor").value=Math.floor(n/100);}
  const rows=[["Municipality",st.muni],["Postal area",it.fsa||"—"]];
  if(legal)rows.push(["Legal description",legal]);
  const hist=aiProp&&aiProp.history||[];
  if(hist.length>=2){const a=hist[0],b=hist[hist.length-1],ch=Math.round((b[1]/a[1]-1)*100);
    rows.push([`Assessed ${a[0]} → ${b[0]}`,`${money(a[1])} → ${money(b[1])} (${ch>=0?"+":""}${ch}%)`]);}
  if(s){for(const [t,v] of Object.entries(s).filter(([t])=>t!=="_r").sort((a,b)=>b[1][1]-a[1][1]).slice(0,3))
    rows.push([`${SUBNAME[t]||({detached:"Detached",semi:"Semi",town:"Townhouse",condo:"Condo"})[t]||t} on this street`,`${money(v[0])} typical · ${v[1]} on record`]);
    const any=Object.entries(s).filter(([t])=>t!=="_r").map(e=>e[1])[0];if(any&&any[3])rows.push(["Typical year built",any[3]]);}
  if(aiProp.block)rows.push(["Neighbourhood median (block "+aiProp.block.da+", today)",money(aiProp.block.v)]);
  if(f&&f.c)rows.push(["Postal area median (Census, today)",money(f.c)]);
  const nb=$("nearby");if(nb){nb.hidden=!near.length;nb.innerHTML=near.length?`<div class="subhead">Homes near you on this street</div>`+near.map(n=>`<div><span>${esc(n.civic)} ${esc(title(it.sname||niceStreet(it.street)))}</span><span>${money(n.val)} <small class="hint">(${n.year}${n.chg!=null?`, ${n.chg>=0?"+":""}${n.chg}% since ${n.since}`:""})</small></span></div>`).join(""):"";}
  $("facts").innerHTML=rows.map(([k,v])=>`<div><span>${esc(k)}</span><br><b>${esc(v)}</b></div>`).join("");$("facts").hidden=false;
  $("addrHint").textContent=s?"Found records for this street. Answer a few questions to sharpen the estimate.":"Answer a few questions to sharpen the estimate.";
  refresh();
  // instant estimate right after the address, before any questions
  renderInstant();}
/* condos in pricier markets: ask about parking and a locker right in the instant estimate, and fold the answer straight in */
let parkSet=false,sqftKnown=false;$("sqft").addEventListener("input",e=>{if(e.isTrusted)sqftKnown=true;});$("sqft").addEventListener("change",e=>{if(e.isTrusted)sqftKnown=true;});
$("park").addEventListener("change",e=>{if(e.isTrusted)parkSet=true;});
const PRICEY=new Set(["Toronto","Vancouver","Burnaby","Richmond","North Vancouver","West Vancouver","Coquitlam","Surrey","Victoria","Mississauga","Oakville","Markham","Richmond Hill","Vaughan","Brampton","Burlington","Ottawa","Montréal","Calgary"]);
function renderInstant(){if(!aiProp)return;const v=+($("rVal").textContent.replace(/[^\d]/g,""))||0;
  const ask=isCondo(st.sub)&&(v>=450000||PRICEY.has(st.muni));
  const seg=(id,opts)=>`<div class="seg" role="group" data-f="${id}">${opts.map(([val,t])=>`<button type="button" data-val="${val}" aria-pressed="${$(id).value===val}">${t}</button>`).join("")}</div>`;
  $("instant").hidden=false;
  $("instant").innerHTML=`<div class="eyebrow">Instant estimate</div><div class="big" style="font-size:30px">${$("rVal").textContent}</div><div class="range">${$("rRange").textContent}</div>`
    +(ask?`<div class="ask-cp"><div class="subhead">Does it come with parking?</div>${seg("park",[["0","None"],["1","1 space"],["2","2 spaces"]])}<div class="subhead">A storage locker?</div>${seg("locker",[["0","No"],["0.01","Yes"]])}</div>`:"")
    +`<div class="hint">${({street:"From real assessments on your street.",block:"From your neighbourhood's Census values and local assessment ratios.",postal:"From assessments in your postal area."})[(aiProp.street?"street":aiProp.block?"block":"postal")]} Tell us about your home to sharpen it.</div>`;
  $("instant").querySelectorAll(".ask-cp [data-val]").forEach(btn=>btn.onclick=()=>{const el=$(btn.parentNode.dataset.f);el.value=btn.dataset.val;if(el.id==="park")parkSet=true;
    el.dispatchEvent(new Event("change",{bubbles:true}));el.dispatchEvent(new Event("input",{bubbles:true}));refresh();renderInstant();});}

/* Repairs a buyer would price in (2026 CAD typical cost) */
const REPAIRS=[["roof","Roof replacement",16000,"house"],["hvac","Furnace or A/C",9000,"house"],["windows","Windows",25000,"house"],
  ["foundation","Foundation or water leaks",30000,"house"],["electrical","Old wiring or panel",15000,"all"],["plumbing","Old plumbing",12000,"all"],
  ["mould","Water damage or mould",20000,"all"],["kitchen","Dated kitchen",30000,"all"],["bath","Dated bathroom(s)",15000,"all"],
  ["flooring","Worn flooring",10000,"all"],["paint","Needs painting",6000,"all"],["exterior","Siding, deck or driveway",14000,"house"]];
function drawRepairs(){const condo=isCondo(st.sub);const was=new Set([...document.querySelectorAll("#repList input:checked")].map(x=>x.value));
  $("repList").innerHTML=REPAIRS.filter(r=>r[3]==="all"||!condo).map(([k,l,c])=>`<label><input type="checkbox" id="rep_${k}" value="${k}"${was.has(k)?" checked":""}> ${l} <span class="hint">~${money(c)}</span></label>`).join("");}
drawRepairs();
$("repList").addEventListener("change",()=>{estimate();extras();});
["floor","view","locker","amen","sa","reserve"].forEach(id=>$(id).addEventListener("input",()=>{estimate();extras();}));
$("ptype").addEventListener("change",()=>{$("condoBox").hidden=!isCondo(st.sub);drawRepairs();});
$("condoBox").hidden=!isCondo(st.sub);

const _estimate=estimate;
estimate=function(){_estimate();
  const adj=[],condo=isCondo(st.sub),sq=sqftKnown?(+$("sqft").value||0):0;let v=lastV,band=null,note="";   // the form default is not this home's size
  const p=aiProp, t=st.sub in {detached:1,semi:1,town:1,condo:1,condotown:1,duplex:1,multiplex:1,mobile:1}?st.sub:SUB[st.sub][0];
  const acc=DB.acc||{by_level:{street:.1,postal:.23}};
  const DEF={detached:1.15,semi:.92,town:.8,condotown:.8,condo:.65,duplex:1.4,multiplex:1.4,mobile:.4};
  const bt=t==="condotown"?"town":t==="duplex"?"multiplex":t;
  // homes without records: geometric mean of the neighbourhood block and postal-area values, split by local type ratio (tested 18-21% median error)
  const base0=p&&p.block?(p.f&&p.f.c?Math.sqrt(p.block.v*p.f.c):p.block.v):null;
  const B={detached:[.8,1.8],semi:[.6,1.4],town:[.5,1.3],condo:[.3,1.2],mobile:[.15,.9],multiplex:[.8,3]}[bt]||[.3,3];
  const rt=Math.min(B[1],Math.max(B[0],(p&&p.block&&p.block.types&&p.block.types[bt])||DEF[t]||1));
  const blk=base0?{v:base0*rt,n:null,sf:null,lvl:"block"}:null;
  const rural=p&&p.fsa&&p.fsa[1]==="0";
  const local=p&&p.street&&p.street[t]&&!rural?{v:p.street[t][0],n:p.street[t][1],sf:p.street[t][2],lvl:"street"}
             :blk?blk
             :p&&p.f&&p.f.t&&p.f.t[t]?{v:p.f.t[t][0],n:p.f.t[t][1],sf:p.f.t[t][2],lvl:"postal"}:null;
  // this home's own assessment (2025-26 roll) is the strongest anchor where cities publish it
  const hh=p&&p.history||[];let own=hh.length&&hh[hh.length-1][0]>=2025?hh[hh.length-1]:null;
  // a whole building's record (e.g. commercial or rental block at the same address) is not a single home: don't anchor on it
  if(own&&local&&(own[1]>local.v*3||own[1]<local.v*.35))own=null;
  if(own&&local){const sq0=(SUB[st.sub]||SUB.detached)[2];
    const r=local.sf&&sq?Math.min(3,Math.max(.4,sq/local.sf))**.5:1;
    v=.75*own[1]+.25*local.v*r;const pp=+$("pp").value&&$("pd").value;if(pp)v=(v*2+lastV)/3;
    const c=+$("cond").value;if(c!==1){adj.push(["Condition",v*(c-1)]);v*=c;}band=.09;
    note=`<b>From this home's own assessment:</b> assessed at ${money(own[1])} on the ${own[0]} roll, combined with ${local.lvl==="street"?"the street's":"the neighbourhood's"} typical value of ${money(local.v)}${pp?" and your purchase price indexed to today":""}. Assessments usually land within 5–10% of market value.`;}
  else if(local){const sq0=(SUB[st.sub]||SUB.detached)[2];
    const r=local.sf&&sq?Math.min(3,Math.max(.4,sq/local.sf))**.5:(local.lvl==="block"&&sq?Math.min(3,Math.max(.4,sq/sq0))**.4:1);v=local.v*r;
    const pp=+$("pp").value&&$("pd").value;if(pp)v=(v+lastV)/2;
    const c=+$("cond").value;if(c!==1){adj.push(["Condition",v*(c-1)]);v*=c;}
    const lvlErr=local.lvl==="block"?((DB.dacc&&(sq?DB.dacc.with_size_median_abs_pct_err:DB.dacc.median_abs_pct_err))||.2):acc.by_level[local.lvl];
    band=Math.min(.3,lvlErr*1.5);
    note=`<b>${local.lvl==="block"?"From public Census and assessment data":"From real assessment records"}:</b> typical ${({detached:"detached house",semi:"semi",town:"townhouse",condo:"condo",condotown:"condo townhouse",duplex:"duplex",multiplex:"plex",mobile:"mobile home"})[t]||t} ${local.lvl==="street"?"on "+esc(p.streetName):local.lvl==="block"?"in this neighbourhood (Census block "+esc(p.block.da)+")":"in postal area "+esc(p.fsa)} is ${money(local.v)} today${local.lvl==="block"?" (2021 Census values for your block and postal area, moved to today and split by property type using local assessment ratios)":" ("+local.n+" assessments"+(local.sf?", typical "+local.sf.toLocaleString("en-CA")+" sq ft":"")+")"}${r!==1?`, adjusted for your ${sq.toLocaleString("en-CA")} sq ft`:""}${pp?", averaged with your purchase price indexed to today":""}. Typical error at this level: ${(lvlErr*100).toFixed(0)}%.`;}
  else if(p&&p.f&&p.f.c){const m=cur(),ratio=Math.min(2.5,Math.max(.4,p.f.c/m.bench));v=lastV*ratio;band=.25;
    note=`<b>Postal area ${esc(p.fsa)}:</b> 2021 Census median home value ${money(p.f.c21)}, moved to today with the regional price index (×${p.f.x}) = ${money(p.f.c)}. Your home's details are applied on top.`;}
  if(condo){const fl=Math.max(1,+$("floor").value||1),fp=st.sub==="penthouse"?0:Math.min(.12,Math.max(-.03,(fl-4)*.006));
    let k=0;for(const [x,label] of [[fp,"Floor "+fl],[+$("view").value,"View"],[+$("locker").value,"Locker"],[+$("amen").value,"Amenities"],[+$("reserve").value,"Reserve fund"]])if(x){adj.push([label,v*x]);k+=x;}
    if(parkSet){const pk=(+$("park").value-1)*Math.min(.09,Math.max(.03,.03+(v-300000)/400000*.05));   // vs a typical one-space unit; worth more in pricier markets
      if(pk){adj.push([+$("park").value?"Parking ("+$("park").value+")":"No parking",v*pk]);k+=pk;}}
    v*=1+k;const sa=+$("sa").value||0;if(sa){adj.push(["Special assessment",-sa]);v-=sa;}}
  let rep=0;document.querySelectorAll("#repList input:checked").forEach(x=>{rep+=REPAIRS.find(r=>r[0]===x.value)[2];});
  if(rep){adj.push(["Repairs needed",-rep]);v-=rep;}
  $("repSum").textContent=rep?`(${money(rep)} deducted)`:"";
  v=Math.max(10000,v);lastV=r5k(v);
  $("rVal").textContent="$"+lastV.toLocaleString("en-CA");
  const rb=document.querySelector("#rbar .rbar-fill");if(rb&&band){const w=Math.min(90,band*2*100*1.6);rb.style.left=(50-w/2)+"%";rb.style.right=(50-w/2)+"%";}
  if(band)$("rRange").textContent=`Range $${r5k(lastV*(1-band)).toLocaleString("en-CA")} – $${r5k(lastV*(1+band)).toLocaleString("en-CA")}`;
  $("aiBox").hidden=!note;$("aiBox").innerHTML=note;
  $("adjBox").hidden=!adj.length;$("adjBox").innerHTML=adj.map(([k,d])=>`<div><span>${esc(k)}</span><span class="${d>=0?"up":"down"}">${d>=0?"+":"−"}${money(Math.abs(d))}</span></div>`).join("");};
loadData().then(refresh);
refresh();

/* "Live" tag: today's date, plus the date the daily updater last checked every source (data/updated.json) */
let LIVE=null;
function renderLive(){const el=$("liveTag");if(!el||!LIVE)return;const fr=(document.documentElement.lang||"").startsWith("fr");
  const f=d=>new Date(d+"T12:00:00").toLocaleDateString(fr?"fr-CA":"en-CA",{year:"numeric",month:"short",day:"numeric"});
  const today=new Date().toISOString().slice(0,10);
  el.textContent=(fr?"En direct · ":"Live · ")+f(today)+(LIVE.date!==today?(fr?" · données vérifiées le ":" · data checked ")+f(LIVE.date):"");el.hidden=false;}
getJSON("data/updated.json?"+Date.now()).then(d=>{LIVE=d;renderLive();}).catch(()=>{});
document.addEventListener("click",e=>{if(e.target.closest&&e.target.closest("#langBtn"))setTimeout(renderLive,50);});
