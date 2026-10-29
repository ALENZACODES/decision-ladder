"""Add all residential property types (condo townhouse, stacked town, link, duplex, multiplex, mobile, rural) + condo fee."""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent

SEG = '''<div class="seg" id="type">
          <button type="button" data-v="detached" aria-pressed="true">Detached</button>
          <button type="button" data-v="semi" aria-pressed="false">Semi</button>
          <button type="button" data-v="town" aria-pressed="false">Townhouse</button>
          <button type="button" data-v="condo" aria-pressed="false">Condo apt</button>
        </div>'''
SELECT = '''<select id="ptype" aria-label="Property type">
          <optgroup label="Houses">
            <option value="detached">Detached house</option><option value="link">Link (detached above grade)</option>
            <option value="semi">Semi-detached</option><option value="town">Freehold townhouse</option>
            <option value="duplex">Duplex (2 units)</option><option value="multiplex">Triplex / fourplex</option>
            <option value="rural">Rural home / acreage</option><option value="cottage">Cottage / recreational</option>
            <option value="mobile">Mobile / manufactured home</option>
          </optgroup>
          <optgroup label="Condos">
            <option value="condo">Condo apartment</option><option value="loft">Condo loft</option>
            <option value="condotown">Condo townhouse</option><option value="stacked">Stacked townhouse</option>
            <option value="penthouse">Penthouse</option>
          </optgroup>
        </select>
        <div class="seg" id="type" hidden>
          <button type="button" data-v="detached" aria-pressed="true">Detached</button>
          <button type="button" data-v="semi" aria-pressed="false">Semi</button>
          <button type="button" data-v="town" aria-pressed="false">Townhouse</button>
          <button type="button" data-v="condo" aria-pressed="false">Condo apt</button>
        </div>
        <label for="cfee" id="cfeeWrap" hidden style="margin-top:10px">Monthly condo fee ($) <input id="cfee" type="number" min="0" step="10" value="650"></label>'''

JS = '''
/* Detailed residential types: each maps to a benchmark base type, a value factor and a typical size. */
const SUB={detached:["detached",1,2000],link:["detached",.9,1900],semi:["semi",1,1500],town:["town",1,1450],
  duplex:["detached",1.08,2400],multiplex:["detached",1.22,3200],rural:["detached",.92,2000],cottage:["detached",.82,1300],
  mobile:["detached",.32,1100],condo:["condo",1,800],loft:["condo",1.08,950],condotown:["town",.9,1300],
  stacked:["condo",1.15,1050],penthouse:["condo",1.6,1500]};
const SUBNAME={link:"Link",duplex:"Duplex",multiplex:"Triplex / fourplex",rural:"Rural / acreage",cottage:"Cottage",mobile:"Mobile home",
  loft:"Condo loft",condotown:"Condo townhouse",stacked:"Stacked townhouse",penthouse:"Penthouse"};
const isCondo=s=>["condo","loft","condotown","stacked","penthouse"].includes(s);
st.sub=st.sub&&SUB[st.sub]?st.sub:st.type;
function applySub(resetSize){const [base,,sq]=SUB[st.sub];st.type=base;setSeg("type",base);$("ptype").value=st.sub;
  $("cfeeWrap").hidden=!isCondo(st.sub);$("lot").disabled=isCondo(st.sub);if(resetSize)$("sqft").value=sq;}
$("ptype").addEventListener("change",()=>{st.sub=$("ptype").value;applySub(true);refresh();});
$("cfee").addEventListener("input",()=>{estimate();extras();});
const _estBase=estimate;
estimate=function(){
  const [base,f,sq0]=SUB[st.sub]||SUB.detached,sqIn=+$("sqft").value||sq0;
  // run the base-type model at the base type's typical-size scale, then apply the sub-type factor
  const keep=$("sqft").value;$("sqft").value=Math.round(sqIn*SQFT[base]/sq0);_estBase();$("sqft").value=keep;
  let k=f;
  if(isCondo(st.sub)){const fee=+$("cfee").value||0,per=fee/Math.max(300,sqIn);k*=Math.min(1.06,Math.max(.85,1-(per-.65)*.18));}
  if(st.sub==="mobile"||st.sub==="cottage"||st.sub==="rural"){/* wider uncertainty */const r=$("rRange").textContent.match(/\\$[\\d,]+/g);}
  if(k!==1){lastV=Math.round(lastV*k/5000)*5000;$("rVal").textContent="$"+lastV.toLocaleString("en-CA");
    $("rRange").textContent=$("rRange").textContent.replace(/\\$([\\d,]+)/g,(m,n)=>"$"+(Math.round(+n.replace(/,/g,"")*k/5000)*5000).toLocaleString("en-CA"));}
  if(SUBNAME[st.sub])$("rMeta").innerHTML=$("rMeta").innerHTML.replace(/ · (Detached|Semi|Townhouse|Condo apt) · /," · "+SUBNAME[st.sub]+" · ");
};
applySub(false);
'''


def patch(f):
    s = f.read_text(encoding="utf-8")
    if 'id="ptype"' in s:
        return print(f.name, "already patched")
    assert SEG in s, f.name
    s = s.replace(SEG, SELECT, 1)
    s = s.replace('<div style="font-size:13px;font-weight:600;margin-bottom:6px">Property type</div>',
                  '<label for="ptype" style="margin-bottom:6px">Property type</label>', 1)
    s = s.replace('function save(){try{localStorage.setItem("hve",JSON.stringify({prov:st.prov,muni:st.muni,type:st.type,span:st.span}))',
                  'function save(){try{localStorage.setItem("hve",JSON.stringify({prov:st.prov,muni:st.muni,type:st.type,sub:st.sub,span:st.span}))', 1)
    # The AI override for Edmonton suites should pick condo apartment
    s = s.replace('{st.type="condo";setSeg("type","condo");$("sqft").value=SQFT.condo;}', '{st.sub="condo";applySub(true);}', 1)
    # insert after the extras/go block (both files have go(1);)
    s = s.replace("\ngo(1);\n", "\ngo(1);\n" + JS, 1)
    f.write_text(s, encoding="utf-8"); print(f.name, "patched")


for f in [ROOT / "web" / "index.html", ROOT / "home-value-estimator.html"]:
    patch(f)
