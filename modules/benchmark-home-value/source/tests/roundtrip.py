"""Address round-trip backtest: type every sampled address the way a person would and check
which home the page lands on. Runs the page's own search code in a real browser.

usage: roundtrip.py <new|old> <start> <count> [out.jsonl]
"""
import os
APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the app folder
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUTDIR, exist_ok=True)
import sys, asyncio, json, time
from playwright.async_api import async_playwright

which, start, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
outp = sys.argv[4] if len(sys.argv) > 4 else f"{OUTDIR}/rt_{which}_{start}.jsonl"
URL = {"new": "http://localhost:8765/index.html", "old": "http://localhost:8766/index.html"}[which]
sample = json.load(open(OUTDIR + "/sample_all.json"))[start:start + count]

JS_NEW = """async batch=>{const out=[];
  for(const [q,fsa,street,n,u] of batch){
    let r;try{r=await searchFor(q);}catch(e){out.push({e:String(e)});continue;}
    const items=(r&&r.items)||[],ex=items.filter(i=>i.exact);
    const auto=ex.length===1||(ex.length>1&&ex[0].score<ex[1].score)?ex[0]:null;
    const same=o=>!!o&&o.fsa===fsa&&o.street===streetKey(street)&&o.civic===n&&(o.unit||"")===u;
    out.push({top:same(items[0])?1:items[0]?0:-1,auto:auto?(same(auto)?1:0):-1,inList:items.some(same)?1:0,
      got:items[0]?items[0].label+" | "+items[0].sub:null,autoGot:auto?auto.label+" | "+auto.sub:null});}
  return out;}"""
JS_OLD = """async batch=>{const out=[];
  for(const [q,fsa,street,n,u] of batch){
    document.getElementById("addr").value=q;
    try{await suggest();}catch(e){out.push({e:String(e)});continue;}
    const items=acItems||[];
    const same=o=>!!o&&o.fsa===fsa&&o.street===streetKey(street)&&o.civic===n&&(o.unit||"")===u;
    out.push({top:same(items[0])?1:items[0]?0:-1,auto:items[0]?(same(items[0])?1:0):-1,inList:items.some(same)?1:0,
      got:items[0]?items[0].label+" | "+(items[0].sub||""):null,autoGot:items[0]?items[0].label+" | "+(items[0].sub||""):null});}
  return out;}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.route("**/*", lambda route: route.abort() if not route.request.url.startswith("http://localhost") else route.continue_())
        await pg.goto(URL)
        await pg.wait_for_function("typeof DB!=='undefined' && DB.munis && DB.fsa")
        t0 = time.time(); B = 250
        with open(outp, "w") as fo:
            for i in range(0, len(sample), B):
                batch = sample[i:i + B]
                res = await pg.evaluate(JS_NEW if which == "new" else JS_OLD, batch)
                for s, r in zip(batch, res):
                    fo.write(json.dumps({"q": s[0], "fsa": s[1], **r}) + "\n")
                if i % 5000 == 0:
                    print(which, start + i, f"{time.time() - t0:.0f}s", flush=True)
        print("done", which, start, count, f"{time.time() - t0:.0f}s")
        await b.close()

asyncio.run(main())
