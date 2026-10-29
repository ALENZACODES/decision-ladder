import os
import asyncio
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + os.sep; os.makedirs(OUT, exist_ok=True)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch();pg=await b.new_page(viewport={"width":1360,"height":1000},accept_downloads=True)
        errs=[];pg.on("pageerror",lambda e:errs.append(str(e)));pg.on("console",lambda m:errs.append(m.text) if m.type=="error" and "Failed to load" not in m.text and "TUNNEL" not in m.text else None)
        await pg.route("**/*",lambda r:r.abort() if not r.request.url.startswith("http://localhost") else r.continue_())
        await pg.goto("http://localhost:8765/index.html");await pg.wait_for_function("DB.munis&&typeof updatePlus==='function'")
        await pg.click("#addr");await pg.keyboard.type("24 Mountain Cir SE, Airdrie",delay=5);await pg.keyboard.press("Enter");await pg.wait_for_timeout(5000)
        for id in ["pNow","pMom","pLiq","pHaz"]: print(id,"::",(await pg.locator("#"+id).inner_text())[:420].replace("\n"," | "))
        await pg.fill("#brName","Jane Broker");await pg.locator("#brName").dispatch_event("change");await pg.fill("#brCo","Example Mortgages");await pg.locator("#brCo").dispatch_event("change")
        async with pg.expect_download() as d: await pg.click("#dlReport")
        dl=await d.value;t=open(await dl.path(),encoding="utf8").read();print("report has brand:", "Prepared by Jane Broker" in t, "nowcast:", "Next month" in t, len(t))
        # cottage
        v0=await pg.evaluate("lastV");await pg.evaluate("go(2)");await pg.select_option("#ptype","cottage");await pg.wait_for_timeout(300)
        v1=await pg.evaluate("lastV");await pg.select_option("#cWater","front");await pg.select_option("#cAccess","seasonal");await pg.wait_for_timeout(300)
        print("cottage",v0,v1,await pg.evaluate("lastV"),(await pg.locator("#adjBox").inner_text()).replace("\n"," | "))
        await pg.click("#roomBox summary");await pg.fill("#roomList","Living 16x14\nKitchen 12x11\n3.4x3.0 m");await pg.click("#roomUse");print("rooms",await pg.locator("#roomTot").inner_text(),await pg.evaluate("$('sqft').value"))
        await pg.locator("#plus").screenshot(path=OUT+"plus3.png");await pg.locator('fieldset[data-step="2"]').screenshot(path=OUT+"step2.png")
        print("errors",errs[:8]);await b.close()
asyncio.run(main())
