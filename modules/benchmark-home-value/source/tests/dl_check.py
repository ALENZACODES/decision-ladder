import os
import asyncio
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + os.sep; os.makedirs(OUT, exist_ok=True)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch();pg=await b.new_page(viewport={"width":1300,"height":900},accept_downloads=True)
        errs=[];pg.on("pageerror",lambda e:errs.append(str(e)))
        await pg.route("**/*",lambda r:r.abort() if not r.request.url.startswith("http://localhost") else r.continue_())
        await pg.goto("http://localhost:8765/index.html");await pg.wait_for_function("DB.munis&&typeof updatePlus==='function'")
        await pg.click("#addr");await pg.keyboard.type("24 Mountain Cir SE, Airdrie",delay=5);await pg.keyboard.press("Enter");await pg.wait_for_timeout(4000)
        await pg.fill("#eqBal","420000");await pg.fill("#eqRenew","2026-12");await pg.wait_for_timeout(300)
        for bid in ["dlReport","eqDigest","eqIcs","svCsv"]:
            if bid=="svCsv": await pg.click("#saveHome")
            async with pg.expect_download(timeout=15000) as d: await pg.click("#"+bid)
            dl=await d.value;path=OUT+dl.suggested_filename;await dl.save_as(path);print(bid,dl.suggested_filename,open(path,'rb').read()[:0] or len(open(path,'rb').read()))
        print(await pg.locator("#eqOut").inner_text())
        print("errors",errs);await b.close()
asyncio.run(main())
