
/* ======================= Layout: group the in-depth cards into sections ======================= */
(function(){const g=$("plus").querySelector(".pgrid");if(!g)return;
  const s=document.createElement("style");s.textContent=`#plus .pgrid{grid-auto-flow:row}.pgroup{grid-column:1/-1;margin:10px 0 -4px;padding-top:16px;border-top:1px solid var(--line);font:600 18px var(--body);color:var(--accent)}.pgroup:first-child{border-top:0;padding-top:0;margin-top:0}.pgroup small{display:block;font:400 13px var(--body);color:var(--muted);margin-top:2px}`;document.head.appendChild(s);
  const card=id=>{const e=$(id);return e?(e.classList.contains("pcard")?e:e.closest(".pcard")):null;};
  const groups=[["Value","How sure, every method, history and what's next",["pConf","pVals","xh","xf","pNow"]],
    ["Money","Rent, borrowing, equity and selling",["pRent","pLend","pEq","xs","pLiq"]],
    ["Neighbourhood","Safety, everyday places, momentum, permits, hazards, heating and your building",["pCrimeWrap","pNear","pMom","pPermit","pHaz","pEnergy","pBldg"]],
    ["Moving","Where your money goes further",["xr","pMoveMap","pTwin"]],
    ["Share","Put your name on it, or put it on your website",["pBrand","pShare"]]];
  const frag=document.createDocumentFragment(),used=new Set();
  for(const [t,sub,ids] of groups){const h=document.createElement("h3");h.className="pgroup";h.innerHTML=`${t}<small>${sub}</small>`;frag.appendChild(h);
    for(const id of ids){const c=card(id);if(c&&!used.has(c)){used.add(c);frag.appendChild(c);}}}
  [...g.children].forEach(c=>{if(!used.has(c)&&c.classList.contains("pcard"))frag.appendChild(c);});
  g.innerHTML="";g.appendChild(frag);
  Object.assign(FR_EXACT,{"Value":"Valeur","Money":"Argent","Neighbourhood":"Quartier","Moving":"Déménager","Share":"Partager"});
})();
/* declutter the drawn relocation map: label a city only if no labelled city sits right next to it */
{const _mm=drawMoveMap;drawMoveMap=function(){_mm();try{const svg=$("mvMap").querySelector("svg");if(!svg)return;const placed=[];
  [...svg.querySelectorAll("g")].map(g=>({g,c:g.querySelector("circle"),t:g.querySelector("text")})).sort((a,b)=>(a.t.textContent.length)-(b.t.textContent.length))
    .forEach(o=>{const x=+o.c.getAttribute("cx"),y=+o.c.getAttribute("cy");if(placed.some(p=>Math.abs(p[0]-x)<70&&Math.abs(p[1]-y)<14))o.t.remove();else placed.push([x,y]);});}catch(e){}};}
