"""Round-4 checks: crime (Toronto Police live feed mocked, then blocked), OpenStreetMap nearby (mocked, then blocked), closing costs, share."""
import os
import asyncio, json, random, sys
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + os.sep; os.makedirs(OUT, exist_ok=True)
CATS=["ASSAULT","BREAKENTER","AUTOTHEFT","ROBBERY","THEFTFROMMV","THEFTOVER","SHOOTING","HOMICIDE"]
def row(i):
    a={"AREA_NAME":f"Hood {i}","HOOD_ID":i,"POPULATION_2025":20000+i*50}
    if i==174: a["AREA_NAME"]="South Eglinton-Davisville"
    for k in CATS:
        for y in range(2014,2026):
            c=random.randint(0,120 if k=="ASSAULT" else 40); a[f"{k}_{y}"]=c; a[f"{k}_RATE_{y}"]=c/a["POPULATION_2025"]*1e5
    return {"attributes":a}
ALL={"features":[row(i) for i in range(1,159)]+[row(174)]}
OSM={"elements":[{"type":"node","lat":43.6525,"lon":-79.3835,"tags":{"shop":"supermarket","name":"Test Grocer"}},{"type":"node","lat":43.6531,"lon":-79.3841,"tags":{"highway":"bus_stop"}},
  {"type":"way","center":{"lat":43.654,"lon":-79.382},"tags":{"leisure":"park","name":"Nathan Phillips Square"}},{"type":"node","lat":43.6522,"lon":-79.384,"tags":{"amenity":"cafe"}},{"type":"node","lat":43.651,"lon":-79.380,"tags":{"amenity":"pharmacy"}}]}
async def run(p,q,mock,tag):
    b=await p.chromium.launch();pg=await b.new_page(viewport={"width":1360,"height":1000})
    errs=[];pg.on("pageerror",lambda e:errs.append(str(e)))
    async def route(r):
        u=r.request.url
        if mock and "Neighbourhood_Crime_Rates" in u:
            body={"features":[{"attributes":{"HOOD_ID":174}}]} if "geometry=" in u else ALL
            return await r.fulfill(status=200,content_type="application/json",body=json.dumps(body))
        if mock and "overpass" in u: return await r.fulfill(status=200,content_type="application/json",body=json.dumps(OSM))
        if not u.startswith("http://localhost"): return await r.abort()
        await r.continue_()
    await pg.route("**/*",route)
    await pg.goto("http://localhost:8765/index.html");await pg.wait_for_function("DB.munis&&typeof drawCrime==='function'")
    await pg.evaluate("try{localStorage.clear()}catch(e){}")
    await pg.click("#addr");await pg.keyboard.type(q,delay=5);await pg.keyboard.press("Enter");await pg.wait_for_timeout(7000)
    if not await pg.evaluate("!!aiProp"):
        if await pg.locator("#acList li[data-i]").count(): await pg.locator("#acList li[data-i]").first.click(); await pg.wait_for_timeout(6000)
    print(tag,await pg.evaluate("$('addr').value"))
    for id in ["pCrime","pNear"]: print(" ",id,"::",(await pg.locator("#"+id).inner_text())[:600].replace("\n"," | "))
    print("  crimeChart hidden:",await pg.evaluate("$('pCrimeChart').hidden"),"| xf has 3y:",await pg.evaluate("$('xfsub').textContent.includes('In 3 years')"),"| cash offer:",await pg.evaluate("$('xlsub').textContent.includes('cash buyer')"))
    print("  share:",(await pg.locator("#pShare").inner_text())[:160].replace("\n"," | "))
    await pg.select_option("#lcProv","ON");await pg.fill("#lcPrice","1000000");await pg.select_option("#lcCity","toronto");await pg.check("#lcFirst");await pg.wait_for_timeout(200)
    print("  close:",(await pg.locator("#lcOut").inner_text())[:500].replace("\n"," | "))
    await pg.locator("#plus").screenshot(path=OUT+f"plus4_{tag}.png")
    print("  errors:",errs[:6]);await b.close()
async def main():
    async with async_playwright() as p:
        await run(p,"100 Queen St W, Toronto",True,"tor_mock")
        await run(p,"100 Queen St W, Toronto",False,"tor_blocked")
        await run(p,"24 Mountain Cir SE, Airdrie",False,"airdrie")
asyncio.run(main())
