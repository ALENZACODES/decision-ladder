/* ---- Printable one-page report (Print / Save as PDF) and optional Google photos ----
   On your own site: set HVE_CONFIG.googleKey to a Google Maps Platform key (Street View Static + Maps Static APIs enabled)
   to show the Street View photo and a pinned map in the page and the report. Without a key, the report uses the
   OpenStreetMap pin (where map images are allowed) and printed photo links. */
window.HVE_CONFIG=window.HVE_CONFIG||{googleKey:""};
(function(){
  const css=`@media print{body{background:#fff!important;padding:0!important}.wrap>*:not(#report){display:none!important}#report{display:block!important}
    #report{color:#000;font-size:12px}#report h2{margin:0 0 4px}#report .rp-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px}
    #report .rp-photo{max-width:100%;border:1px solid #ccc}@page{margin:14mm}}
    #report{display:none;border:1px solid var(--line);border-radius:10px;padding:20px;background:var(--surface)}
    #report .rp-big{font:600 34px var(--display);color:var(--accent)}#report .rp-sec{border-top:1px solid var(--line);padding-top:10px;margin-top:10px}
    #report table{width:auto}#report .rp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 16px}
    #report .rp-photo{max-width:100%;border-radius:6px}#report .rp-map{height:220px;border-radius:6px;border:1px solid var(--line)}`;
  const st=document.createElement("style");st.textContent=css;document.head.appendChild(st);
  const rep=document.createElement("section");rep.id="report";rep.setAttribute("aria-label","Printable report");document.querySelector(".wrap").appendChild(rep);
  const box=document.querySelector('fieldset[data-step="3"] .row:last-of-type')||document.querySelector('fieldset[data-step="3"]');
  const b=document.createElement("button");b.type="button";b.className="cta";b.id="printBtn";b.textContent="Print / Save as PDF";
  const msg=document.createElement("div");msg.className="hint";msg.id="printMsg";msg.setAttribute("aria-live","polite");
  box.after(b,msg);
  b.addEventListener("click",async()=>{await buildReport();rep.style.display="block";rep.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
    const t0=Date.now();window.print();
    if(Date.now()-t0<60)msg.textContent="The report is shown below. If no print dialog opened, this preview blocks printing; Print / Save as PDF works when the page is on your own website.";});
})();

function gPhoto(ll,w,h){const k=HVE_CONFIG.googleKey;if(!k||!ll)return "";const [la,lo]=ll.split(",");
  return `https://maps.googleapis.com/maps/api/streetview?size=${w}x${h}&location=${la},${lo}&fov=80&key=${encodeURIComponent(k)}`;}
function gMap(ll,w,h){const k=HVE_CONFIG.googleKey;if(!k||!ll)return "";const [la,lo]=ll.split(",");
  return `https://maps.googleapis.com/maps/api/staticmap?center=${la},${lo}&zoom=17&size=${w}x${h}&markers=color:red%7C${la},${lo}&key=${encodeURIComponent(k)}`;}

async function buildReport(){
  const p=aiProp||{},it=p.pick||{},rep=$("report"),e=s=>esc(s||"");
  const facts=[...$("facts").querySelectorAll("div")].map(d=>[d.querySelector("span")?.textContent,d.querySelector("b")?.textContent]).filter(x=>x[0]);
  const adj=[...$("adjBox").querySelectorAll("div")].map(d=>[...d.children].map(c=>c.textContent));
  const hist=p.history||[];
  const ll=it.ll||"",[la,lo]=ll.split(","),q=encodeURIComponent($("addr").value);
  const photo=gPhoto(ll,640,320),gm=gMap(ll,640,260);
  rep.innerHTML=`<div class="eyebrow">Home value report · ${new Date().toLocaleDateString(LANG==="fr"?"fr-CA":"en-CA",{year:"numeric",month:"long",day:"numeric"})}</div>
  <h2 style="font-family:var(--brand);color:var(--accent-2)">${e($("addr").value)||e(st.muni)}</h2>
  <div class="rp-big">${e($("rVal").textContent)}</div><div class="range">${e($("rRange").textContent)}</div>
  ${photo?`<div class="rp-sec"><img class="rp-photo" src="${photo}" alt="Street View photo near this address"></div>`:""}
  <div class="rp-sec"><b>How we got this number</b><p>${$("aiBox").innerHTML||""}</p>
    ${adj.length?`<table>${adj.map(([k,v])=>`<tr><td>${e(k)}</td><td style="text-align:right">${e(v)}</td></tr>`).join("")}</table>`:""}</div>
  <div class="rp-sec"><b>Property</b><div class="rp-grid">${facts.map(([k,v])=>`<div><span class="hint">${e(k)}</span><br>${e(v)}</div>`).join("")}
    <div><span class="hint">Type</span><br>${e($("ptype").selectedOptions[0]?.textContent)}</div><div><span class="hint">Living area</span><br>${e($("sqft").value)} sq ft</div></div></div>
  ${(p.near||[]).length?`<div class="rp-sec"><b>Homes near you on this street</b><table>${p.near.map(n=>`<tr><td>${e(n.civic)}</td><td style="text-align:right">${money(n.val)} (${n.year})</td></tr>`).join("")}</table></div>`:""}
  ${hist.length?`<div class="rp-sec"><b>Assessment history</b><div style="height:170px"><canvas id="rpHist"></canvas></div>
    <table>${hist.map(([y,v])=>`<tr><td>${y}</td><td style="text-align:right">${money(v)}</td></tr>`).join("")}</table></div>`:""}
  <div class="rp-sec"><b>Location</b>${gm?`<br><img class="rp-photo" src="${gm}" alt="Map with a pin at this address">`:`<div class="rp-map" id="rpMap"></div>`}
    <p class="hint">${la?`Coordinates ${la}, ${lo} · `:""}Street View: https://www.google.com/maps/search/?api=1&amp;query=${q}</p></div>
  <div class="rp-sec"><b>Equity and borrowing</b><div class="rp-grid"><div><span class="hint">Estimated equity</span><br>${e($("eqVal").textContent)}</div>
    ${[...$("borrow").querySelectorAll("div")].map(d=>`<div><span class="hint">${e(d.children[0]?.textContent)}</span><br>${e(d.children[1]?.textContent)}</div>`).join("")}</div></div>
  <p class="notice">Indicative only. Values come from public municipal assessment records, the 2021 Census and published regional benchmarks, not from sold listings. Not an appraisal and not suitable for lending decisions. Sources: Statistics Canada (National Address Register, 2021 Census, Canadian Housing Statistics Program), municipal open data, MAMH Québec, published MLS® HPI benchmarks.</p>`;
  if(document.fonts)await document.fonts.ready;
  if(hist.length&&window.Chart){new Chart($("rpHist"),{type:"line",data:{labels:hist.map(h=>h[0]),datasets:[{data:hist.map(h=>h[1]),borderColor:css("--print-primary"),backgroundColor:css("--print-primary"),pointRadius:2,tension:.2}]},
    options:{animation:false,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:css("--print-muted"),font:{family:css("--mono"),size:12}},grid:{color:css("--print-line")}},y:{ticks:{color:css("--print-muted"),font:{family:css("--mono"),size:12},callback:v=>fmt$(v)},grid:{color:css("--print-line")}}}}});}
  if(!gm&&la&&typeof mapReady!=="undefined"&&mapReady&&window.L){const m=L.map("rpMap",{zoomControl:false,attributionControl:true});
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:"© OpenStreetMap"}).addTo(m);m.setView([+la,+lo],17);
    L.circleMarker([+la,+lo],{radius:9,color:css("--print-accent"),fillOpacity:1,className:"hve-pin"}).addTo(m);await new Promise(r=>setTimeout(r,600));}
  else if(!gm){const el=$("rpMap");if(el)el.outerHTML=`<p class="hint">Map pin: ${la?la+", "+lo:"—"}</p>`;}
}
