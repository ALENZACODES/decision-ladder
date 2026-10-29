import sys, asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith("http://localhost") else r.continue_())
        await pg.goto("http://localhost:8765/index.html")
        await pg.wait_for_function("typeof DB!=='undefined' && DB.munis")
        for q in sys.argv[1:]:
            r = await pg.evaluate("""async q=>{const log=[];const orig=addressSearch;
              addressSearch=async function(a,mun,scope){log.push('call '+JSON.stringify({civic:a.civic,unit:a.unit,street:a.street,place:a.place,city:a.city&&a.city.name,any:a._anyTown,mun:mun&&mun.name,nf:mun&&mun.fsa.length,scope}));const r=await orig(a,mun,scope);log.push('  -> '+(r||[]).slice(0,3).map(o=>o.label+' '+o.sub+' s'+o.score+(o.exact?' EXACT':'')).join(' || '));return r;};
              const r=await searchFor(q);addressSearch=orig;log.push('FINAL '+(r.items||[]).slice(0,3).map(o=>o.label+' '+o.sub+(o.exact?' EXACT':'')).join(' || '));return log}""", q)
            print("==", q); print("\n".join(r))
        await b.close()
asyncio.run(main())
