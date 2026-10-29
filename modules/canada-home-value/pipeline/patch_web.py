import pathlib
p = pathlib.Path(__file__).resolve().parent.parent / "web" / "index.html"
s = p.read_text(encoding="utf-8")
def rep(a, b):
    global s
    assert a in s, a[:60]; s = s.replace(a, b, 1)

rep('</style>', '''.ac{position:relative}
.ac ul{position:absolute;z-index:5;left:0;right:0;top:100%;margin:4px 0 0;padding:4px;list-style:none;background:var(--surface);border:1px solid var(--line);border-radius:6px;max-height:320px;overflow:auto;box-shadow:0 10px 30px rgba(0,0,0,.12)}
.ac li{padding:8px 10px;border-radius:4px;cursor:pointer;font-size:14px}
.ac li[aria-selected="true"],.ac li:hover{background:color-mix(in srgb,var(--accent) 12%,transparent)}
.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 12px;font-size:13px}
.facts span{color:var(--muted)}
</style></head><body>''')
rep('<input id="addr" placeholder="e.g. 4571 Dunedin Cres, Mississauga ON L5L 3X3">',
    '<span class="ac"><input id="addr" role="combobox" aria-autocomplete="list" aria-controls="acList" aria-expanded="false" placeholder="Start typing, e.g. 15 Deermeade"><ul id="acList" role="listbox" hidden></ul></span>')
rep('<div class="hint" id="addrHint">We match the city or postal-code area (FSA) in what you type.</div>',
    '<div class="hint" id="addrHint">Type a few words of your address and pick it from the list.</div>\n      <div class="facts" id="facts" hidden></div>')
rep('<div id="rMeta" class="hint"></div>', '<div id="rMeta" class="hint"></div>\n        <div id="aiBox" class="hint" hidden></div>')
rep('refresh();\n</script>', '''refresh();
/* ---- Live address autocomplete + AI valuation from the local API ---- */
let acT, acItems=[], acSel=-1, aiProp=null;
const acList=$("acList");
function acShow(items){acItems=items;acSel=-1;acList.innerHTML=items.map((it,i)=>`<li role="option" id="ac${i}" data-i="${i}">${it.label.replace(/</g,"&lt;")}</li>`).join("");
  acList.hidden=!items.length;$("addr").setAttribute("aria-expanded",String(!!items.length));}
$("addr").addEventListener("input",()=>{clearTimeout(acT);const q=$("addr").value.trim();if(q.length<3){acShow([]);return;}
  acT=setTimeout(async()=>{try{const r=await fetch("/api/suggest?q="+encodeURIComponent(q));if(r.ok)acShow(await r.json());}catch(e){}},150);});
$("addr").addEventListener("keydown",e=>{if(acList.hidden)return;
  if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();acSel=(acSel+(e.key==="ArrowDown"?1:-1)+acItems.length)%acItems.length;
    [...acList.children].forEach((li,i)=>li.setAttribute("aria-selected",String(i===acSel)));}
  else if(e.key==="Enter"&&acSel>=0){e.preventDefault();pick(acItems[acSel]);} else if(e.key==="Escape")acShow([]);});
acList.addEventListener("mousedown",e=>{const li=e.target.closest("li");if(li){e.preventDefault();pick(acItems[+li.dataset.i]);}});
$("addr").addEventListener("blur",()=>setTimeout(()=>acShow([]),100));
async function pick(it){$("addr").value=it.label;acShow([]);
  if(PROV[it.prov]){st.prov=it.prov;$("prov").value=it.prov;}
  const near=M.filter(m=>m.prov===it.prov).find(m=>it.city&&(m.name.toUpperCase()===it.city.toUpperCase()||it.city.toUpperCase().includes(m.name.toUpperCase())));
  const pc=it.label.match(/[A-Z]\\d[A-Z] ?\\d[A-Z]\\d/);const byPc=pc?matchAddress(pc[0]):null;
  st.muni=(near||byPc?.m||M.find(m=>m.prov===it.prov)||M[0]).name;fillMuni();
  $("addrHint").textContent="Looking up this property…";aiProp=null;
  try{const r=await fetch("/api/property/"+it.id);aiProp=r.ok?await r.json():null;}catch(e){}
  const f=aiProp&&aiProp.facts||{},rows=[];
  if(aiProp){rows.push(["Municipality",aiProp.municipality||aiProp.city],["Postal code",aiProp.postal||"—"]);
    if(f.hood)rows.push(["Neighbourhood",f.hood]);if(f.year)rows.push(["Year built",Math.round(f.year)]);
    if(f.lot_sf)rows.push(["Lot size",Math.round(f.lot_sf).toLocaleString("en-CA")+" sq ft"]);
    if(f.garage!=null)rows.push(["Garage",f.garage?"Yes":"No"]);
    if(f.assessed_value)rows.push(["2026 assessment","$"+Math.round(f.assessed_value).toLocaleString("en-CA")]);
    if(f.ptype&&/SUITE|^CO/.test(f.ptype)){st.type="condo";setSeg("type","condo");$("sqft").value=SQFT.condo;}}
  $("facts").innerHTML=rows.map(([k,v])=>`<div><span>${k}</span><br><b>${v}</b></div>`).join("");$("facts").hidden=!rows.length;
  $("addrHint").textContent=aiProp&&aiProp.ai?"Found it. We filled in what public records show about this home.":"Found the address. Detailed records aren't available here yet, so we'll use area data and your answers.";
  refresh();}
const _estimate=estimate;
estimate=function(){_estimate();const a=aiProp&&aiProp.ai;$("aiBox").hidden=!a;if(!a)return;
  const pp=+$("pp").value&&$("pd").value;let v=a.estimate;
  if(pp){v=(lastV+a.estimate)/2;}
  lastV=Math.round(v/5000)*5000;
  $("rVal").textContent="$"+lastV.toLocaleString("en-CA");
  $("rRange").textContent="Range $"+Math.round(a.low/5000*5000).toLocaleString("en-CA")+" – $"+Math.round(a.high).toLocaleString("en-CA");
  $("aiBox").innerHTML=`<b>AI estimate:</b> ${a.method}${pp?", averaged with your purchase price indexed to today":""}. Model alone: $${a.model_value.toLocaleString("en-CA")}. Assessment adjusted to today: $${a.assessment_today.toLocaleString("en-CA")}. Typical model error in this city: ${(a.model_median_error*100).toFixed(1)}%.`;};
</script></body></html>''')
p.write_text(s, encoding="utf-8"); print("patched")
