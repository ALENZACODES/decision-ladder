/* ---- Full-address autocomplete from the packed National Address Register (data/addr/) ----
   packs.json: FSA -> pack id · idx_<L>.json: "CORE|DIR" -> [street, [FSA...]] · p<id>.json: FSA -> [[street, cityIdx, "LDU:civ u/civ;..."]] */
const ADDR={packs:null,idx:{},pack:{}};
async function addrPacks(){if(!ADDR.packs)ADDR.packs=getJSON("data/addr/packs.json").catch(()=>({}));return ADDR.packs;}
function addrIdx(L){if(!ADDR.idx[L])ADDR.idx[L]=getJSON("data/addr/idx_"+L+".json").catch(()=>({}));return ADDR.idx[L];}
function addrPack(id){if(!(id in ADDR.pack))ADDR.pack[id]=getJSON("data/addr/p"+id+".json").catch(()=>({}));return ADDR.pack[id];}
const provOf=f=>/^X0[ABC]/.test(f)?"NU":PROV_OF[f[0]];
const PROV_OF={A:"NL",B:"NS",C:"PE",E:"NB",G:"QC",H:"QC",J:"QC",K:"ON",L:"ON",M:"ON",N:"ON",P:"ON",R:"MB",S:"SK",T:"AB",V:"BC",X:"NT",Y:"YT"};

let TOWNF=null;
async function townFsas(town,pv){   // "PEFFERLAW" -> Set of postal areas where the register has that mailing town
  if(!TOWNF){TOWNF={};const TM=(typeof TOWN_MUNI!=="undefined"&&await TOWN_MUNI)||{};
    for(const k of Object.keys(TM.t||{})){const [f,t]=k.split("|"),n=plain(t).trim().replace(/\s+/g," ");(TOWNF[n]=TOWNF[n]||[]).push(f);}}
  return new Set((TOWNF[town]||[]).filter(f=>!pv||provOf(f)===pv));}
async function addressSearch(a,mun,scope){   // scope: undefined = municipality, 'prov', 'all'
  if((!a.street||a.street.length<2)&&a.fsa&&a.ldu){   // a full postal code alone: list the addresses at that code
    const packs=await addrPacks(),pid=packs&&packs[a.fsa];if(pid==null)return null;const pk=await addrPack(pid),out=[];
    for(const [street,ci,data] of pk[a.fsa]||[]){const city=(pk._c||[])[ci]||"";
      for(const seg of data.split(";")){const [lduTag,civs]=seg.split(":");const [ldu,da,ll]=lduTag.split("@");if(ldu!==a.ldu)continue;
        for(const t of civs.split(" ")){const [u,n]=t.includes("/")?t.split("/"):["",t];if(a.civic&&n!==a.civic)continue;
          out.push({sname:street,da:da||null,ll:ll||null,score:u?1:0,fsa:a.fsa,street:streetKey(street),civic:n,unit:u,postal:`${a.fsa} ${ldu}`,city,
            label:`${u?u+"-":""}${n} ${title(street)}`,sub:`${title(city)} ${provOf(a.fsa)||""} ${a.fsa} ${ldu}`});}}}
    return out.sort((x,y)=>x.score-y.score||(parseInt(x.civic)||0)-(parseInt(y.civic)||0)).slice(0,8);}
  if(!a.street||a.street.length<2)return null;
  const packs=await addrPacks();if(!packs||!Object.keys(packs).length)return null;   // address files not published: fall back
  const [want,wantDir]=streetKey(a.street).split("|");
  const munFsa=new Set(mun?mun.fsa:[]);
  const PL={NL:"A",NS:"B",PE:"C",NB:"E",QC:"GHJ",ON:"KLMNP",MB:"R",SK:"S",AB:"T",BC:"V",NT:"X",NU:"X",YT:"Y"};
  // a town was typed: search every postal area that town has (from the address register), in the typed province if one was given
  const wc0=a._anyTown?null:(a.place||(a.city?plain(a.city.name).trim().replace(/\s+/g," "):null)),TF=wc0?await townFsas(wc0,a.pv):null;
  let letters=a.fsa?[a.fsa[0]]:TF&&TF.size&&scope==="all"?[...new Set([...TF].map(f=>f[0]))]:scope==="all"?"ABCEGHJKLMNPRSTVXY".split(""):scope==="prov"?(PL[a.pv||st.prov]||"").split(""):[...new Set((mun?mun.fsa:[]).map(f=>f[0]))];
  if(a.pv&&!a.fsa&&scope)letters=letters.filter(L=>(PL[a.pv]||"").includes(L));
  if(scope)mun=null;
  if(!letters.length)return null;
  // 1. which postal areas have a street with this name
  const cands=[];
  for(const L of letters){const idx=await addrIdx(L);
    for(const [k,[disp,fs]] of Object.entries(idx)){const [core,dir]=k.split("|");
      if(!(core===want||core.startsWith(want)))continue;
      const score=(core===want?0:2)+(wantDir&&dir!==wantDir?1:0);
      for(const f of fs){if(a.fsa?f!==a.fsa:TF&&TF.size&&scope==="all"?!TF.has(f):(munFsa.size&&!munFsa.has(f)))continue;cands.push({score,k,f,rank:mun?mun.fsa.indexOf(f):0});}}}
  cands.sort((x,y)=>x.score-y.score||x.rank-y.rank);   // the municipality's main postal areas first
  // 2. load only the packs those postal areas live in; exact house numbers are collected across every candidate first
  const typed=plain(a.street).split(/\s+/);
  const wc=a._anyTown?null:(a.place||(a.city?plain(a.city.name).trim().replace(/\s+/g," "):null));
  const exact=[],near=[],cv=(a.civic||"").toUpperCase(),un=(a.unit||"").toUpperCase(),seen=new Set();
  for(const c of cands.slice(0,120)){const pid=packs[c.f];if(pid==null)continue;const pk=await addrPack(pid);const list=pk[c.f]||[];
    for(const [street,ci,data] of list){if(streetKey(street)!==c.k)continue;
      const city=(pk._c||[])[ci]||"";if(wc&&plain(city).trim().replace(/\s+/g," ")!==wc)continue;   // a town was typed: only that town
      for(const seg of data.split(";")){const [lduTag,civs]=seg.split(":");const [ldu,da,ll]=lduTag.split("@");
        for(const t of civs.split(" ")){const [u,n]=t.includes("/")?t.split("/"):["",t];
          if(cv&&!n.startsWith(cv))continue;if(un&&!(u&&u.startsWith(un)))continue;
          const isExact=!cv||n===cv;const bucket=isExact?exact:near;
          if(bucket.length>=(isExact?80:40))continue;
          const id=`${u}/${n}|${street}|${c.f}`;if(seen.has(id))continue;seen.add(id);
          bucket.push({sname:street,da:da||null,ll:ll||null,score:c.score+(u&&!un?0.5:0)+(typed.some(w=>TYPEWORDS.has(w))&&plain(street).split(/\s+/).some(w=>TYPEWORDS.has(w)&&!typed.includes(w))?0.3:0)+(mun&&plain(city)!==plain(mun.name)?1.5:0)-(a.place&&plain(city).trim().replace(/\s+/g," ")===a.place?2:0),fsa:c.f,street:c.k,civic:n,unit:u,postal:`${c.f} ${ldu}`,city,
            label:`${u?u+"-":""}${n} ${title(street)}`,sub:`${title(city)} ${provOf(c.f)||""} ${c.f} ${ldu}`});}}}
    if(exact.length>=40)break;}
  const out=exact.length?exact.concat(near):near;
  if(wc&&!out.length)return addressSearch({...a,place:null,city:null,_anyTown:1},mun,scope);   // nothing in that town: any town
  if(!cands.length&&!a.fsa&&scope!=="all")return addressSearch(a,mun,scope==="prov"?"all":"prov");   // not in this municipality: widen to province, then Canada
  // the name or house number only half-matches here: look wider and prefer an exact match elsewhere
  const exactHere=out.some(o=>o.street===`${want}|${wantDir||o.street.split("|")[1]}`&&(!cv||o.civic===cv)&&(!wantDir||o.street.endsWith("|"+wantDir)));
  const streetHere=cands.some(c=>c.score===0);              // the municipality has this exact street (name + direction)
  if(!exactHere&&!streetHere&&!a.fsa&&scope!=="all"){
    const wider=await addressSearch(a,mun,scope==="prov"?"all":"prov");
    if(wider&&wider.length&&wider[0].street.split("|")[0]===want&&(!cv||wider[0].civic===cv))return wider;}
  if(!out.length&&cv&&cands.length)return addressSearch({...a,civic:"",unit:""},mun,scope);   // number not on this street: list the street
  const ex=out.filter(o=>!cv||o.civic===cv).sort((x,y)=>x.score-y.score),rest=out.filter(o=>cv&&o.civic!==cv).sort((x,y)=>x.score-y.score||(parseInt(x.civic)||0)-(parseInt(y.civic)||0));
  return ex.concat(rest).slice(0,8);}

/* Speed: warm the address files before the first keystroke. On load (when the browser is idle) fetch the pack map and
   the street index for the province's postal letters; once typing starts, fetch the municipality's main packs too. */
const PROV_LETTERS={NL:"A",NS:"B",PE:"C",NB:"E",QC:"GHJ",ON:"KLMNP",MB:"R",SK:"S",AB:"T",BC:"V",NT:"X",NU:"X",YT:"Y"};
function idle(f){(window.requestIdleCallback||(c=>setTimeout(c,300)))(f);}
function warmProvince(){idle(async()=>{const packs=await addrPacks();
  const mun=(DB.munis||[]).find(x=>x.name===st.muni&&x.prov===st.prov);
  const letters=mun?[...new Set(mun.fsa.slice(0,3).map(f=>f[0]))]:(PROV_LETTERS[st.prov]||"").split("");
  for(const L of letters.slice(0,2))addrIdx(L);});}
let warmedMuni="";
function warmMunicipality(){const mun=(DB.munis||[]).find(x=>x.name===st.muni&&x.prov===st.prov);if(!mun||warmedMuni===mun.name)return;
  warmedMuni=mun.name;idle(async()=>{const packs=await addrPacks();const ids=[...new Set(mun.fsa.slice(0,6).map(f=>packs[f]).filter(x=>x!=null))];
    for(const id of ids.slice(0,3))addrPack(id);});}
$("addr").addEventListener("focus",()=>{warmProvince();warmMunicipality();});
$("addr").addEventListener("input",warmMunicipality,{once:true});
$("muni").addEventListener("change",()=>{warmedMuni="";warmProvince();});
$("prov").addEventListener("change",()=>{warmedMuni="";warmProvince();});
(function wait(){DB.munis?warmProvince():setTimeout(wait,250);})();   // after the page data has loaded
