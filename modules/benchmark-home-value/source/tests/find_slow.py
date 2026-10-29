import os
APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the app folder
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUTDIR, exist_ok=True)
import sys, asyncio, json, time
from playwright.async_api import async_playwright
S=json.load(open(OUTDIR+'/sample_all.json'))
a,b=int(sys.argv[1]),int(sys.argv[2])
async def main():
    async with async_playwright() as p:
        br=await p.chromium.launch();pg=await br.new_page()
        await pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith("http://localhost") else r.continue_())
        await pg.goto("http://localhost:8765/index.html");await pg.wait_for_function("typeof DB!=='undefined' && DB.munis && DB.fsa")
        for i in range(a,b):
            q=S[i][0];t=time.time()
            try:
                await asyncio.wait_for(pg.evaluate("q=>searchFor(q).then(r=>r.items.length)",q),timeout=8)
            except asyncio.TimeoutError:
                print("SLOW",i,q,flush=True);break
            dt=time.time()-t
            if dt>1: print("slowish",i,round(dt,2),q,flush=True)
        print("checked to",i)
        await br.close()
asyncio.run(main())
