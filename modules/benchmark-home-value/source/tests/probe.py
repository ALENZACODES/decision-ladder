"""Call the page's own address search for one query and print the steps."""
import sys, asyncio, json
from playwright.async_api import async_playwright

async def main():
    qs = sys.argv[1:]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        pg.on("console", lambda m: print("console:", m.text))
        await pg.goto("http://localhost:8765/index.html")
        await pg.wait_for_function("typeof DB!=='undefined' && DB.munis")
        for q in qs:
            r = await pg.evaluate("""async q=>{const a=parseAddr(q);
              const mun=a.city||DB.munis.find(x=>x.name===st.muni&&x.prov===st.prov);
              const res=await addressSearch(a,mun);
              return {parsed:{...a,city:a.city&&a.city.name},key:streetKey(a.street),res:(res||[]).map(o=>o.label+' | '+o.sub+' | score '+o.score)}}""", q)
            print(json.dumps({"q": q, **r}, indent=1))
        await b.close()

asyncio.run(main())
