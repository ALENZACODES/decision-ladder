import sys, asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto("http://localhost:8765/index.html")
        await pg.wait_for_function("typeof DB!=='undefined' && DB.munis")
        r = await pg.evaluate("""async q=>{const log=[];const orig=addressSearch;
          addressSearch=async function(a,mun,scope){log.push('call '+JSON.stringify({civic:a.civic,street:a.street,place:a.place,city:a.city&&a.city.name,any:a._anyTown,mun:mun&&mun.name,scope}));const r=await orig(a,mun,scope);log.push('  -> '+(r||[]).slice(0,2).map(o=>o.label+' '+o.sub+' s'+o.score).join(' || '));return r;};
          const a=parseAddr(q);const mun=a.city;await addressSearch(a,mun);addressSearch=orig;
          const t=DB.munis.find(x=>x.name==='Toronto');log.push('toronto fsa count '+t.fsa.length+' has M5H '+t.fsa.includes('M5H'));return log}""", sys.argv[1])
        print("\n".join(r)); await b.close()
asyncio.run(main())
