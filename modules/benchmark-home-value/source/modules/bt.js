
/* ======================= Charts: one look for every chart on the page =======================
   Thin 2px lines with a 10% wash for a lone series, a ringed end-dot, hairline grid, a crosshair on
   hover, legends with line keys, bars capped at 24px with rounded data ends. Colors come from tokens. */
const RM=()=>matchMedia("(prefers-reduced-motion: reduce)").matches;
const ink=()=>({fg:css("--fg"),muted:css("--muted"),line:css("--line"),surface:css("--surface"),mono:css("--mono")||"monospace"});
function tipOpts(fmtFn,extra){const k=ink();return Object.assign({backgroundColor:k.surface,borderColor:k.line,borderWidth:1,titleColor:k.fg,bodyColor:k.fg,
  padding:10,boxPadding:4,usePointStyle:true,titleFont:{family:k.mono,weight:"600",size:12},bodyFont:{family:k.mono,size:12},
  callbacks:fmtFn?{label:t=>` ${t.dataset.label}: ${fmtFn(t.parsed.y)}`}:{}},extra||{});}
function legendOpts(show){const k=ink();return{display:show,position:"top",align:"start",
  labels:{color:k.muted,usePointStyle:true,pointStyle:"line",boxWidth:18,boxHeight:2,padding:12,font:{family:k.mono,size:12}}};}
function axisOpts(fmt,extra){const k=ink();return Object.assign({ticks:{color:k.muted,font:{family:k.mono,size:11},callback:fmt,maxTicksLimit:6},
  grid:{color:k.line,drawTicks:false},border:{display:false}},extra||{});}
const xhair={id:"xhair",afterDatasetsDraw(c){const a=c.tooltip&&c.tooltip.getActiveElements&&c.tooltip.getActiveElements();
  if(!a||!a.length||c.config.type!=="line")return;const x=a[0].element.x,{top,bottom}=c.chartArea,g=c.ctx;
  g.save();g.strokeStyle=css("--muted");g.globalAlpha=.45;g.lineWidth=1;g.beginPath();g.moveTo(x,top);g.lineTo(x,bottom);g.stroke();g.restore();}};
const endDot={id:"enddot",afterDatasetsDraw(c){if(c.config.type!=="line")return;const g=c.ctx;
  c.data.datasets.forEach((d,i)=>{const m=c.getDatasetMeta(i);if(m.hidden||!m.data.length||d.noEnd||(d.type&&d.type!=="line"))return;const p=m.data[m.data.length-1];
    if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y))return;
    g.save();g.beginPath();g.arc(p.x,p.y,4,0,Math.PI*2);g.fillStyle=d.borderColor;g.strokeStyle=css("--surface");g.lineWidth=2;g.fill();g.stroke();g.restore();});}};
const SPECS={};
chartjs=function(c,spec){const k=ink(),bar=spec.kind==="bar",one=spec.sets.length===1;
  return new Chart(c,{type:spec.kind,
    data:{labels:spec.labels,datasets:spec.sets.map(s=>bar
      ?{label:s.label,data:s.data,backgroundColor:s.data.map(v=>v>=0?css("--s1"):css("--s2")),borderRadius:3,borderSkipped:"start",maxBarThickness:24,categoryPercentage:.92,barPercentage:.92}
      :{label:s.label,data:s.data,borderColor:s.color,backgroundColor:s.color+"1a",fill:one?"start":false,borderWidth:2,pointRadius:0,pointHoverRadius:5,
        pointHoverBorderWidth:2,pointHoverBorderColor:k.surface,pointHoverBackgroundColor:s.color,tension:.3,borderCapStyle:"round",borderJoinStyle:"round"})},
    options:{responsive:true,maintainAspectRatio:false,animation:RM()?false:{duration:450},interaction:{mode:"index",intersect:false},layout:{padding:{top:2,right:10}},
      plugins:{legend:legendOpts(!one),tooltip:tipOpts(spec.fmt)},
      scales:{x:axisOpts(undefined,{ticks:{color:k.muted,font:{family:k.mono,size:11},maxTicksLimit:6,maxRotation:0,autoSkip:true},grid:{display:false}}),
        y:axisOpts(spec.fmt)}},
    plugins:bar?[]:[xhair,endDot]});};
{const _rnd=render;render=function(id,spec){SPECS[id]=spec;return _rnd(id,spec);};}

/* ======================= Saving: PNG, CSV and one zip of everything ======================= */
const downloadsNS=()=>Promise.resolve(null);   // files are saved as ordinary browser downloads
const btMsg=t=>{const m=$("btMsg");if(m)m.textContent=t;};
async function saveFile(name,data){const dl=await downloadsNS();
  if(!dl){try{const blob=data instanceof Blob?data:new Blob([data],{type:/\.csv$/.test(name)?"text/csv":/\.png$/.test(name)?"image/png":"application/octet-stream"});const u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),120000);btMsg("Downloaded "+name+".");return true;}catch(e){btMsg("Couldn't save "+name+".");return false;}}
  try{await dl.save({filename:name,data});btMsg("Saved "+name+".");return true;}
  catch(e){const c=e&&e.code;btMsg(c==="declined"?"Save cancelled.":c==="rate_limited"?"A save is already waiting for your answer.":"Couldn't save "+name+".");return false;}}
const csvCell=v=>{const s=v==null?"":String(v);return /[",\n]/.test(s)?`"${s.replace(/"/g,'""')}"`:s;};
const toCSV=rows=>rows.map(r=>r.map(csvCell).join(",")).join("\n")+"\n";
const slug=s=>String(s).toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,60);
const today=()=>new Date().toISOString().slice(0,10);
function chartTitle(id){const el=$(id),h=el&&el.closest(".chart")&&el.closest(".chart").querySelector("h3");return h?h.textContent.trim():id;}
function chartObj(id){return BT.ch[id]||charts[id]||null;}
function pngOf(ch,title,sub){const src=ch.canvas,sc=src.width/(src.clientWidth||src.width)||1,pad=Math.round(52*sc),W=src.width,H=src.height+pad+Math.round(18*sc);
  const cv=document.createElement("canvas");cv.width=W;cv.height=H;const g=cv.getContext("2d");
  g.fillStyle=css("--surface");g.fillRect(0,0,W,H);g.fillStyle=css("--fg");g.font=`600 ${Math.round(15*sc)}px ${css("--body")}`;g.fillText(title,Math.round(4*sc),Math.round(20*sc));
  g.fillStyle=css("--muted");g.font=`400 ${Math.round(11*sc)}px ${css("--mono")}`;g.fillText(sub||"",Math.round(4*sc),Math.round(40*sc));
  g.drawImage(src,0,pad);g.font=`400 ${Math.round(10*sc)}px ${css("--mono")}`;g.fillText("Benchmark Home Value · "+today(),Math.round(4*sc),H-Math.round(5*sc));
  return new Promise(r=>cv.toBlob(r,"image/png"));}
function csvRowsFor(id){if(BT.csv[id])return BT.csv[id]();const s=SPECS[id];if(!s)return null;
  return [["Month",...s.sets.map(x=>x.label)],...s.labels.map((l,i)=>[l,...s.sets.map(x=>x.data[i]==null||!Number.isFinite(+x.data[i])?"":Math.round(x.data[i]*100)/100)])];}
document.addEventListener("click",async e=>{const b=e.target.closest&&e.target.closest("[data-png],[data-csv]");if(!b)return;
  if(b.dataset.png){const ch=chartObj(b.dataset.png);if(!ch){btMsg("That chart hasn't drawn yet.");return;}
    const t=chartTitle(b.dataset.png);await saveFile(slug(t)+".png",await pngOf(ch,t,BT.sub[b.dataset.png]||($("mName")&&$("mName").textContent)||""));}
  else{const rows=csvRowsFor(b.dataset.csv);if(!rows){btMsg("Nothing to save yet.");return;}
    await saveFile(slug(b.dataset.csv==="fsa"?"backtest-postal-areas":chartTitle(b.dataset.csv))+".csv",toCSV(rows));}});
function loadScript(src){return new Promise((ok,no)=>{const s=document.createElement("script");s.src=src;s.onload=ok;s.onerror=no;document.head.appendChild(s);});}
$("btSaveAll")&&$("btSaveAll").addEventListener("click",async()=>{btMsg("Packing every chart and table…");
  try{if(!window.JSZip)await loadScript("https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js").catch(()=>loadScript("vendor/jszip.min.js"));}catch(e){btMsg("Couldn't load the zip tool. Use the PNG and CSV buttons on each chart.");return;}
  const z=new JSZip(),ids=["c1","c2","c3","c4","b1","b2","b3","b4","b7","b5","b6","bm"];let n=0;
  for(const id of ids){const ch=chartObj(id);if(!ch)continue;const t=chartTitle(id),f=String(++n).padStart(2,"0")+"-"+slug(t);
    z.file(f+".png",await pngOf(ch,t,BT.sub[id]||""));const rows=csvRowsFor(id);if(rows)z.file(f+".csv",toCSV(rows));}
  const fr=csvRowsFor("fsa");if(fr)z.file("postal-areas.csv",toCSV(fr));
  if(BT.data)z.file("backtest.json",JSON.stringify(BT.data,null,1));
  if(BT.mineRows)z.file("this-address.csv",toCSV(BT.mineRows));
  z.file("README.txt",["Benchmark Home Value — backtest export, "+today(),"",
    "Charts are PNG; each has a CSV of the numbers behind it.","backtest.json holds every figure on the page's Backtest panel.",
    $("btNotes")?$("btNotes").textContent:""].join("\n"));
  await saveFile("home-value-backtest-"+today()+".zip",await z.generateAsync({type:"blob"}));});
// PNG / CSV buttons on the four market charts
document.querySelectorAll(".market-panel .chart").forEach(c=>{const h=c.querySelector("h3"),box=c.querySelector(".box");if(!h||!box)return;
  const top=document.createElement("div");top.className="chart-top";h.before(top);top.appendChild(h);
  top.insertAdjacentHTML("beforeend",`<div class="tools"><button type="button" data-png="${box.id}">PNG</button><button type="button" data-csv="${box.id}">CSV</button></div>`);});

/* ======================= Backtest panel ======================= */
const BT={data:null,city:"All",ch:{},csv:{},sub:{},mineRows:null};
const pct=(v,d=1)=>v==null||!Number.isFinite(v)?"—":(v*100).toFixed(d)+"%";
const spct=(v,d=1)=>v==null||!Number.isFinite(v)?"—":(v>=0?"+":"−")+Math.abs(v*100).toFixed(d)+"%";
const big=n=>n>=1e6?(n/1e6).toFixed(n>=1e7?1:2).replace(/\.0+$/,"")+"M":n>=1e4?Math.round(n/1e3)+"K":n.toLocaleString("en-CA");
const PROVN={NL:"Newfoundland & Labrador",NS:"Nova Scotia",PE:"Prince Edward Island",NB:"New Brunswick",QC:"Québec",ON:"Ontario",MB:"Manitoba",SK:"Saskatchewan",AB:"Alberta",BC:"British Columbia",YT:"Yukon",NT:"Northwest Territories",NU:"Nunavut"};
function btChart(id,cfg,sub){const box=$(id);if(!box)return;if(BT.ch[id]){try{BT.ch[id].destroy();}catch(e){}BT.ch[id]=null;}box.innerHTML="";BT.sub[id]=sub||"";
  if(!window.Chart){const rows=csvRowsFor(id);box.style.height="auto";box.innerHTML=rows?`<div class="tbl"><table><thead><tr>${rows[0].map(h=>`<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.slice(1).map(r=>`<tr>${r.map(c=>`<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`:"";return;}
  const c=document.createElement("canvas");c.setAttribute("role","img");c.setAttribute("aria-label",chartTitle(id));box.appendChild(c);
  cfg.options=Object.assign({responsive:true,maintainAspectRatio:false,animation:RM()?false:{duration:450},layout:{padding:{top:2,right:10}}},cfg.options||{});
  BT.ch[id]=new Chart(c,cfg);}
const barDS=(label,data,color,extra)=>Object.assign({label,data,backgroundColor:color,hoverBackgroundColor:color,borderRadius:4,borderSkipped:"start",maxBarThickness:24,
  categoryPercentage:.72,barPercentage:.9,pointStyle:"rectRounded"},extra||{});
function G(){const d=BT.data;return d&&(d.groups[BT.city]||d.groups.All);}

function btTiles(){const d=BT.data,g=G(),m=g.methods,L=d.lookup,homes=BT.city==="All"?d.tested_homes:(d.homes_by_city[BT.city]||0);
  const t=(k,v,dd)=>`<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${dd}</div></div>`;
  $("btTiles").innerHTML=
    t("Median error, this page's index",pct(m.index.mdape),`<b>${pct(m.flat.mdape)}</b> if values never changed · <b>${pct(m.local.mdape)}</b> with the postal area's own trend`)+
    t("Within 10% of the assessment",pct(m.index.w10,0),`within 5%: <b>${pct(m.index.w5,0)}</b> · within 20%: <b>${pct(m.index.w20,0)}</b>`)+
    t(BT.city==="All"?"Homes tested":"Homes tested here",homes.toLocaleString("en-CA"),`<b>${big(m.index.n)}</b> predictions from ${d.records.toLocaleString("en-CA")} assessment records`)+
    (L?t("Address lookups that land on the right home",pct(L.correct/L.n,1),`<b>${L.wrong.toLocaleString("en-CA")}</b> wrong homes in ${L.n.toLocaleString("en-CA")} streets${L.before?` · before this fix: <b>${pct(L.before.wrong/L.before.n,1)}</b> went to a different home`:""}`):"");}

function btCharts(){const d=BT.data,g=G(),k=ink(),S=[css("--s1"),css("--s2"),css("--s3"),css("--s4")],city=BT.city==="All"?"all areas":BT.city;
  // b1: error distribution
  const H=g.hist,labs=H.index.bins.map((_,i)=>-50+i*2.5);
  BT.csv.b1=()=>[["Error (%)","This page's index","No change","Postal-area trend"],...labs.map((x,i)=>[x,+(H.index.bins[i]*100).toFixed(3),+(H.flat.bins[i]*100).toFixed(3),+(H.local.bins[i]*100).toFixed(3)])];
  btChart("b1",{type:"bar",data:{labels:labs.map(x=>(x>0?"+":"")+x+"%"),datasets:[
      barDS("This page's index",H.index.bins.map(v=>v*100),S[0],{categoryPercentage:1,barPercentage:.9,borderRadius:2,order:2}),
      {type:"line",label:"Postal-area trend",data:H.local.bins.map(v=>v*100),borderColor:S[2],backgroundColor:S[2],borderWidth:2,pointRadius:0,tension:.35,order:1,noEnd:true},
      {type:"line",label:"No change",data:H.flat.bins.map(v=>v*100),borderColor:S[3],backgroundColor:S[3],borderWidth:2,pointRadius:0,tension:.35,order:0,noEnd:true}]},
    options:{interaction:{mode:"index",intersect:false},plugins:{legend:legendOpts(true),tooltip:tipOpts(v=>v.toFixed(1)+"% of predictions",{callbacks:{title:t=>"Error "+t[0].label,label:t=>` ${t.dataset.label}: ${t.parsed.y.toFixed(1)}% of predictions`}})},
      scales:{x:axisOpts(undefined,{grid:{display:false},ticks:{color:k.muted,font:{family:k.mono,size:11},maxRotation:0,autoSkip:false,callback:(v,i)=>i%4===0?(labs[i]>0?"+":"")+labs[i]+"%":""}}),
        y:axisOpts(v=>v+"%")}}},`${city} · share of predictions by error`);
  // b2: error by horizon
  const hz=Object.entries(g.horizon);
  BT.csv.b2=()=>[["Years ahead","This page's index","Postal-area trend","No change","Predictions"],...hz.map(([h,v])=>[h,v.index.mdape,v.local&&v.local.mdape,v.flat.mdape,v.index.n])];
  btChart("b2",{type:"bar",data:{labels:hz.map(([h])=>h+" years"),datasets:[
      barDS("This page's index",hz.map(([,v])=>v.index.mdape*100),S[0]),barDS("Postal-area trend",hz.map(([,v])=>(v.local?v.local.mdape:NaN)*100),S[2]),
      barDS("No change",hz.map(([,v])=>v.flat.mdape*100),S[3])]},
    options:{interaction:{mode:"index",intersect:false},plugins:{legend:legendOpts(true),tooltip:tipOpts(v=>v.toFixed(1)+"% median error")},
      scales:{x:axisOpts(undefined,{grid:{display:false}}),y:axisOpts(v=>v+"%",{beginAtZero:true})}}},`${city} · median absolute error`);
  // b3: index vs actual
  const cal=d.calib.filter(r=>BT.city==="All"||r.city===BT.city),many=BT.city==="All";
  $("b3").classList.toggle("tall",many);
  BT.csv.b3=()=>[["Area","From roll","To roll","Assessed change (median)","Index change","Homes"],...cal.map(r=>[r.city,r.from,r.to,r.actual,r.index,r.n])];
  btChart("b3",{type:"bar",data:{labels:cal.map(r=>(many?r.city+"  ":"")+r.from+"→"+String(r.to).slice(2)),datasets:[
      barDS("Assessed values (median home)",cal.map(r=>r.actual*100),S[2],{borderSkipped:false,borderRadius:3}),barDS("This page's index",cal.map(r=>r.index*100),S[0],{borderSkipped:false,borderRadius:3})]},
    options:{indexAxis:many?"y":"x",interaction:{mode:"index",intersect:false},plugins:{legend:legendOpts(true),
        tooltip:tipOpts(null,{callbacks:{label:t=>` ${t.dataset.label}: ${spct((many?t.parsed.x:t.parsed.y)/100)}`,
          afterBody:t=>{const r=cal[t[0].dataIndex];return `Gap: ${spct(r.index-r.actual)} · ${r.n.toLocaleString("en-CA")} homes`;}}})},
      scales:many?{y:axisOpts(undefined,{grid:{display:false},ticks:{color:k.muted,font:{family:k.mono,size:11},autoSkip:false}}),x:axisOpts(v=>(v>0?"+":"")+v+"%")}
        :{x:axisOpts(undefined,{grid:{display:false}}),y:axisOpts(v=>(v>0?"+":"")+v+"%")}}},`${city} · valuation dates July 1 of the year before each roll`);
  // b4: predicted vs assessed
  const ci=d.cities.indexOf(BT.city),pts=d.scatter.filter(r=>BT.city==="All"||r[0]===ci).map(r=>({x:r[2]*1000,y:r[1]*1000}));
  const lo=Math.max(50000,Math.min(...pts.map(p=>Math.min(p.x,p.y)))),hi=Math.max(...pts.map(p=>Math.max(p.x,p.y)));
  BT.csv.b4=()=>[["Area","Assessed ($)","Predicted ($)","Condo"],...d.scatter.filter(r=>BT.city==="All"||r[0]===ci).map(r=>[d.cities[r[0]],r[2]*1000,r[1]*1000,r[3]?"yes":"no"])];
  btChart("b4",{type:"scatter",data:{datasets:[
      {label:"Prediction",data:pts,backgroundColor:S[0]+"59",borderColor:S[0]+"59",pointRadius:2.5,pointHoverRadius:5,pointHoverBorderColor:k.surface,pointHoverBorderWidth:2},
      {type:"line",label:"Exactly right",data:[{x:lo,y:lo},{x:hi,y:hi}],borderColor:k.muted,borderWidth:1,pointRadius:0,noEnd:true}]},
    options:{plugins:{legend:legendOpts(true),tooltip:tipOpts(null,{callbacks:{label:t=>t.datasetIndex?"":` assessed ${money(t.parsed.x)} · predicted ${money(t.parsed.y)} (${spct(t.parsed.y/t.parsed.x-1)})`}})},
      scales:{x:axisOpts(v=>fmt$(v),{type:"logarithmic",min:lo,max:hi,title:{display:true,text:"Assessed",color:k.muted,font:{family:k.mono,size:11}},grid:{color:k.line},ticks:{color:k.muted,font:{family:k.mono,size:11},maxTicksLimit:5,callback:v=>fmt$(v)}}),
        y:axisOpts(v=>fmt$(v),{type:"logarithmic",min:lo,max:hi,title:{display:true,text:"Predicted",color:k.muted,font:{family:k.mono,size:11}},ticks:{color:k.muted,font:{family:k.mono,size:11},maxTicksLimit:5,callback:v=>fmt$(v)}})}}},
    `${city} · ${pts.length.toLocaleString("en-CA")} sampled predictions`);
  // b7: houses vs condos
  BT.csv.b7=()=>[["Kind","This page's index (median error)","Street median of neighbours (median error)","Predictions","Homes in street test"],
    ["Houses",g.kind.house&&g.kind.house.mdape,g.xs.house&&g.xs.house.mdape,g.kind.house&&g.kind.house.n,g.xs.house&&g.xs.house.n],
    ["Condos",g.kind.condo&&g.kind.condo.mdape,g.xs.condo&&g.xs.condo.mdape,g.kind.condo&&g.kind.condo.n,g.xs.condo&&g.xs.condo.n]];
  btChart("b7",{type:"bar",data:{labels:["Houses","Condos"],datasets:[
      barDS("This page's index",[g.kind.house,g.kind.condo].map(s=>s?s.mdape*100:NaN),S[0]),
      barDS("Street median of neighbours",[g.xs.house,g.xs.condo].map(s=>s?s.mdape*100:NaN),S[2])]},
    options:{interaction:{mode:"index",intersect:false},plugins:{legend:legendOpts(true),tooltip:tipOpts(v=>v.toFixed(1)+"% median error")},
      scales:{x:axisOpts(undefined,{grid:{display:false}}),y:axisOpts(v=>v+"%",{beginAtZero:true})}}},`${city} · median absolute error`);}

function btCoverage(){const d=BT.data;if(!d.coverage)return;const C=d.coverage,k=ink();
  const T=[["own","Its own assessment record","--q5"],["street","Assessments on its street","--q4"],["block","Its Census block's values","--q3"],["postal","Its postal area's values","--q2"],["region","Regional benchmark only","--q1"]];
  const provs=Object.entries(C.by_prov).map(([p,v])=>[p,v,Object.values(v).reduce((a,b)=>a+b,0)]).sort((a,b)=>b[2]-a[2]);
  $("b5leg").innerHTML=T.map(([key,l,tok])=>`<span><i style="background:var(${tok})"></i>${l} · ${pct(C.tiers[key]/C.addresses,1)}</span>`).join("");
  $("b5sub").textContent=`All ${C.addresses.toLocaleString("en-CA")} addresses in the National Address Register, by the best evidence the page has for each.`;
  BT.csv.b5=()=>[["Province","Addresses",...T.map(t=>t[1])],...provs.map(([p,v,n])=>[PROVN[p]||p,n,...T.map(t=>v[t[0]]||0)])];
  btChart("b5",{type:"bar",data:{labels:provs.map(([p,,n])=>`${p}  ${big(n)}`),datasets:T.map(([key,l,tok])=>({label:l,data:provs.map(([,v,n])=>(v[key]||0)/n*100),
      backgroundColor:css(tok),borderColor:css("--surface"),borderWidth:{right:2},borderSkipped:false,maxBarThickness:22,categoryPercentage:.8,barPercentage:.95}))},
    options:{indexAxis:"y",interaction:{mode:"index",intersect:false},plugins:{legend:{display:false},
        tooltip:tipOpts(null,{callbacks:{title:t=>PROVN[provs[t[0].dataIndex][0]],label:t=>{const [, v,n]=provs[t.dataIndex],key=T[t.datasetIndex][0];
          return ` ${t.dataset.label}: ${(v[key]||0).toLocaleString("en-CA")} (${t.parsed.x.toFixed(1)}%)`;}}})},
      scales:{x:axisOpts(v=>v+"%",{stacked:true,max:100}),y:axisOpts(undefined,{stacked:true,grid:{display:false},ticks:{color:k.muted,font:{family:k.mono,size:11},autoSkip:false}})}}},
    `${C.addresses.toLocaleString("en-CA")} addresses · share by evidence`);}

function btLookup(){const L=BT.data.lookup;if(!L)return;const k=ink(),S=[css("--s1"),css("--s2"),css("--s3"),css("--s4")];
  const provs=Object.entries(L.by_prov).sort((a,b)=>b[1].n-a[1].n);
  const T=[["correct","Lands on the right home",S[0]],["ask_listed","Asks you to pick; right home is listed",S[2]],["ask_missing","Asks you to pick; not listed",S[3]],["wrong","Lands on a different home",S[1]]];
  $("b6sub").textContent=`One address from each of ${L.n.toLocaleString("en-CA")} streets in Canada, typed as "number street, town", then Enter. `+
    (L.before?`Before this fix, the same test on ${L.before.n.toLocaleString("en-CA")} of them sent ${pct(L.before.wrong/L.before.n,1)} to a different home.`:"");
  BT.csv.b6=()=>[["Province","Streets tested",...T.map(t=>t[1])],...provs.map(([p,v])=>[PROVN[p]||p,v.n,...T.map(t=>v[t[0]]||0)])];
  btChart("b6",{type:"bar",data:{labels:provs.map(([p,v])=>`${p}  ${big(v.n)}`),datasets:T.map(([key,l,c])=>({label:l,data:provs.map(([,v])=>(v[key]||0)/v.n*100),
      backgroundColor:c,borderColor:css("--surface"),borderWidth:{right:2},borderSkipped:false,maxBarThickness:22,categoryPercentage:.8,barPercentage:.95,pointStyle:"rectRounded"}))},
    options:{indexAxis:"y",interaction:{mode:"index",intersect:false},plugins:{legend:Object.assign(legendOpts(true),{labels:Object.assign(legendOpts(true).labels,{pointStyle:"rectRounded",boxWidth:10,boxHeight:10})}),
        tooltip:tipOpts(null,{callbacks:{title:t=>PROVN[provs[t[0].dataIndex][0]],label:t=>{const v=provs[t.dataIndex][1],key=T[t.datasetIndex][0];return ` ${t.dataset.label}: ${(v[key]||0).toLocaleString("en-CA")} (${t.parsed.x.toFixed(2)}%)`;}}})},
      scales:{x:axisOpts(v=>v+"%",{stacked:true,max:100}),y:axisOpts(undefined,{stacked:true,grid:{display:false},ticks:{color:k.muted,font:{family:k.mono,size:11},autoSkip:false}})}}},
    `${L.n.toLocaleString("en-CA")} streets · what Enter does`);}

const FSAS={k:3,d:1};
function btFsa(){const d=BT.data,rows=d.fsa.filter(r=>BT.city==="All"||r[1]===BT.city);
  const H=[["Postal area",0],["Area",1],["Predictions",2],["Median error",3],["Bias",4],["Within 10%",5]];
  rows.sort((a,b)=>{const x=a[FSAS.k],y=b[FSAS.k];return (typeof x==="string"?x.localeCompare(y):x-y)*FSAS.d;});
  const t=$("btFsa");t.tHead.innerHTML="<tr>"+H.map(([h,i])=>`<th data-i="${i}">${h}${FSAS.k===i?(FSAS.d>0?" ▲":" ▼"):""}</th>`).join("")+"</tr>";
  t.tBodies[0].innerHTML=rows.map(r=>`<tr><td>${r[0]}</td><td>${esc(r[1])}</td><td>${r[2].toLocaleString("en-CA")}</td><td>${pct(r[3])}</td><td>${spct(r[4])}</td><td>${pct(r[5],0)}</td></tr>`).join("");
  BT.csv.fsa=()=>[["Postal area","Area","Predictions","Median abs error","Median error (bias)","Within 10%"],...rows.map(r=>r.slice())];}
$("btFsa")&&$("btFsa").addEventListener("click",e=>{const th=e.target.closest("th");if(!th)return;const i=+th.dataset.i;FSAS.d=FSAS.k===i?-FSAS.d:(i<2?1:-1);FSAS.k=i;btFsa();});

function btNotes(){const d=BT.data;$("btNotes").textContent=
  `How this was tested: ${d.records.toLocaleString("en-CA")} assessment records published by Calgary, Edmonton, Vancouver, other Alberta and BC municipalities and Winnipeg; `+
  `${d.tested_homes.toLocaleString("en-CA")} homes had at least two assessments (Winnipeg publishes none). From each earlier assessment the page's own regional index predicted every later one; `+
  `an assessment roll reflects market value on July 1 of the year before. Office towers, parking stalls and records far from their street's typical value were left out. `+
  `"Postal area's own trend" uses the median change of all assessed homes in the same postal area over the same years: it shows how much a local index would add, and is hindsight, so it is a benchmark rather than something the page can use for the future. `+
  `Assessments are not sale prices; cities aim to land within about 5–10% of market value. Results generated ${d.generated}.`;}

function btCityButtons(){const d=BT.data,cs=["All",...d.cities.filter(c=>d.groups[c])];
  $("btCity").innerHTML=cs.map(c=>`<button type="button" data-v="${esc(c)}" aria-pressed="${c===BT.city}">${c==="All"?"All areas":esc(c)}</button>`).join("");}
$("btCity")&&$("btCity").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;BT.city=b.dataset.v;
  [...$("btCity").children].forEach(x=>x.setAttribute("aria-pressed",String(x===b)));try{localStorage.setItem("hve-btcity",BT.city);}catch(e){}drawBT(true);});
function drawBT(cityOnly){if(!BT.data)return;btTiles();btCharts();btFsa();if(!cityOnly){btCoverage();btLookup();btNotes();}}
function btLiveTag(){const el=$("btLive");if(!el||!BT.data)return;el.textContent=`Live · results ${BT.data.generated}`+(LIVE&&LIVE.date?` · data checked ${LIVE.date}`:"");}
getJSON("data/backtest.json?"+Date.now()).then(d=>{BT.data=d;try{const c=localStorage.getItem("hve-btcity");if(c&&d.groups[c])BT.city=c;}catch(e){}
    btCityButtons();drawBT();btLiveTag();renderBacktest(aiProp);})
  .catch(()=>{$("btTiles").innerHTML=`<p class="hint">The backtest results didn't load. Reload the page to try again.</p>`;});
getJSON("data/updated.json?"+Date.now()).then(d=>{if(!LIVE)LIVE=d;btLiveTag();}).catch(()=>{});
// redraw in the viewer's theme
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change",()=>{drawBT();renderBacktest(aiProp);});
new MutationObserver(()=>{drawBT();renderBacktest(aiProp);}).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});

/* ======================= This address, backtested live ======================= */
const G_PRE={ON:.06,BC:.07,QC:.045};
function idxAtPage(reg,prov,y,m){const idx=IDX[reg]||IDX.GTA,i=mi(y,m),g=G_PRE[prov]||.035;return i>=0?idx[Math.min(i,idx.length-1)]:idx[0]/Math.pow(1+g,-i/12);}
const rollIdx=(reg,prov,y)=>idxAtPage(reg,prov,y-1,6);          // a roll year values homes as of July 1 the year before
const medOf=a=>{if(!a.length)return NaN;const s=a.slice().sort((x,y)=>x-y),k=s.length>>1;return s.length%2?s[k]:(s[k-1]+s[k])/2;};
async function fsaRecords(fsa){if(!DETIDX)DETIDX=getJSON("data/detail/index.json").catch(()=>({}));const idx=await DETIDX;
  const file=Object.keys(idx).find(k=>idx[k].includes(fsa));if(!file)return null;
  if(!DET[file])DET[file]=getJSON("data/detail/"+file+".json").catch(()=>({}));return ((await DET[file])||{})[fsa]||null;}
function localGrowth(recs,y0,y1){const r=[];for(const v of Object.values(recs||{})){const h=decodeHistory(v[1]);const a=h.find(x=>x[0]===y0),b=h.find(x=>x[0]===y1);
  if(a&&b&&a[1]>20000&&b[1]>20000)r.push(b[1]/a[1]);}return r.length>=20?medOf(r):NaN;}
function addrOfKey(k){const [u,c,core,dir,ty]=k.split("|");return `${u?u+"-":""}${c} ${title(core)}${ty?" "+title(ty):""}${dir?" "+dir:""}`;}
let mineSeq=0;
async function renderBacktest(p){const box=$("btMine");if(!box)return;const my=++mineSeq;
  if(BT.ch.bm){try{BT.ch.bm.destroy();}catch(e){}BT.ch.bm=null;}
  if(!p||!p.pick){box.hidden=true;BT.mineRows=null;return;}
  const it=p.pick,fsa=p.fsa,h=p.history||[],reg=(DB.fsa&&DB.fsa[fsa]&&DB.fsa[fsa].r)||cur().reg,prov=provOf(fsa)||st.prov,where=esc(it.label||$("addr").value);
  if(h.length<2){   // no history here: say what the estimate rests on and how that kind of estimate tested
    const acc=DB.acc||{},dacc=DB.dacc||{},lvl=p.street?"street":p.block?"block":"postal";
    const e=lvl==="street"?(acc.by_level&&acc.by_level.street):lvl==="block"?(dacc.with_size_median_abs_pct_err||dacc.median_abs_pct_err):(acc.by_level&&acc.by_level.postal);
    const n=lvl==="block"?dacc.tested_on:acc.test_records,ev={street:"assessments of homes on this street",block:"its Census block's home values",postal:"its postal area's home values"}[lvl];
    const row=BT.data&&BT.data.fsa.find(r=>r[0]===fsa);
    box.hidden=false;BT.mineRows=null;
    box.innerHTML=`<div class="eyebrow">This address, backtested</div><h3>${where}</h3>
      <p class="hint">${h.length===1?`One assessment is on record here (${h[0][0]} roll, ${money(h[0][1])}), so there's no earlier value to test from. `:"No assessment history is published for this address, so it can't be tested home by home. "}
      Its estimate rests on ${ev}. Estimates built that way were off by a median of <b>${pct(e)}</b> when checked against ${n?n.toLocaleString("en-CA"):"thousands of"} homes that do have records.${row?` In postal area ${fsa}, the page's index was off by a median of <b>${pct(row[3])}</b> across ${row[2].toLocaleString("en-CA")} predictions.`:""}</p>`;
    return;}
  const recs=await fsaRecords(fsa);if(my!==mineSeq)return;
  const last=h[h.length-1],k=ink(),S=[css("--s1"),css("--s2"),css("--s3"),css("--s4")];
  const rows=h.slice(0,-1).map(([y,v])=>{const pi=v*rollIdx(reg,prov,last[0])/rollIdx(reg,prov,y),lg=localGrowth(recs,y,last[0]);
    return {y,v,pi,ei:pi/last[1]-1,pl:Number.isFinite(lg)?v*lg:NaN,el:Number.isFinite(lg)?v*lg/last[1]-1:NaN};});
  const first=rows[0],nowI=IDX[reg][IDX[reg].length-1],path=h.map(([y])=>first.v*rollIdx(reg,prov,y)/rollIdx(reg,prov,first.y));
  const labels=[...h.map(([y])=>y+" roll"),"Today"],todayIdx=last[1]*nowI/rollIdx(reg,prov,last[0]);
  BT.mineRows=[["Address","Postal area","Start roll","Start value","Predicted for "+last[0]+" (page index)","Predicted (postal-area trend)","Assessed "+last[0],"Error (index)","Error (postal-area trend)"],
    ...rows.map(r=>[it.label,fsa,r.y,r.v,Math.round(r.pi),Number.isFinite(r.pl)?Math.round(r.pl):"",last[1],+(r.ei*100).toFixed(2),Number.isFinite(r.el)?+(r.el*100).toFixed(2):""])];
  BT.csv.bm=()=>BT.mineRows;
  box.hidden=false;
  box.innerHTML=`<div class="chart-top"><div><div class="eyebrow">This address, backtested</div><h3>${where}</h3></div>
      <div class="tools"><button type="button" data-png="bm">PNG</button><button type="button" data-csv="bm">CSV</button><button type="button" id="btFsaCsv">Every address in ${esc(fsa)} (.csv)</button></div></div>
    <p class="hint">From its ${first.y} assessment of <b>${money(first.v)}</b>, this page's index would have predicted <b>${money(first.pi)}</b> for the ${last[0]} roll. The city assessed <b>${money(last[1])}</b>: off by <span class="err-pill">${spct(first.ei)}</span>.${Number.isFinite(first.el)?` Postal area ${esc(fsa)}'s own trend would have said ${money(first.pl)} (${spct(first.el)}).`:""} Moved to today with the same index, the ${last[0]} assessment is about <b>${money(todayIdx)}</b>; the estimate above is <b>${$("rVal").textContent}</b>.</p>
    <div class="grid2"><div class="box" id="bm"></div>
      <div class="tbl"><table><thead><tr><th>From</th><th>Value then</th><th>Predicted ${last[0]}</th><th>Error</th></tr></thead><tbody>
        ${rows.map(r=>`<tr><td>${r.y} roll</td><td>${money(r.v)}</td><td>${money(r.pi)}</td><td>${spct(r.ei)}</td></tr>`).join("")}
        <tr><td>${last[0]} roll</td><td colspan="2">Assessed</td><td>${money(last[1])}</td></tr></tbody></table></div></div>`;
  btChart("bm",{type:"line",data:{labels,datasets:[
      {label:"City assessment",data:[...h.map(x=>x[1]),null],borderColor:S[2],backgroundColor:S[2],borderWidth:2,pointRadius:4,pointHoverRadius:6,pointBorderColor:k.surface,pointBorderWidth:2,tension:.25,noEnd:true},
      {label:"Page index from "+first.y,data:[...path,first.v*nowI/rollIdx(reg,prov,first.y)],borderColor:S[0],backgroundColor:S[0]+"1a",fill:false,borderWidth:2,borderDash:[5,4],pointRadius:0,pointHoverRadius:5,tension:.25},
      {label:"Estimate today",data:[...h.map(()=>null),lastV||null],borderColor:S[1],backgroundColor:S[1],pointRadius:6,pointHoverRadius:7,pointBorderColor:k.surface,pointBorderWidth:2,showLine:false,noEnd:true}]},
    options:{interaction:{mode:"index",intersect:false},plugins:{legend:legendOpts(true),tooltip:tipOpts(v=>money(v))},
      scales:{x:axisOpts(undefined,{grid:{display:false}}),y:axisOpts(v=>fmt$(v))}},plugins:[xhair]},`${it.label} · ${it.sub||""}`);
  $("btFsaCsv").onclick=async()=>{btMsg("Backtesting every address in "+fsa+"…");const out=[["Address","Unit","Zoning","Rolls","First roll","First value","Last roll","Assessed","Predicted (page index)","Error (page index) %"]];
    for(const [key,v] of Object.entries(recs||{})){const hh=decodeHistory(v[1]);if(hh.length<2){out.push([addrOfKey(key),key.split("|")[0],v[2]||"",hh.map(x=>x[0]+":"+x[1]).join(" "),"","","","","",""]);continue;}
      const a=hh[0],b=hh[hh.length-1],pr=a[1]*rollIdx(reg,prov,b[0])/rollIdx(reg,prov,a[0]);
      out.push([addrOfKey(key),key.split("|")[0],v[2]||"",hh.map(x=>x[0]+":"+x[1]).join(" "),a[0],a[1],b[0],b[1],Math.round(pr),+((pr/b[1]-1)*100).toFixed(2)]);}
    await saveFile(`backtest-${fsa}-every-address.csv`,toCSV(out));};}
{const _pk=pick;pick=async function(it){const r=await _pk(it);renderBacktest(aiProp);return r;};}
