"""Pick addresses and screenshot the new in-depth panel, calculators and saved homes; report console errors."""
import os
import asyncio, sys
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + os.sep; os.makedirs(OUT, exist_ok=True)
ADDRS = sys.argv[1:] or ["24 Mountain Cir SE, Airdrie"]
async def run(p, w, h, scheme, tag, q, block_cdn=False):
    b = await p.chromium.launch()
    pg = await b.new_page(viewport={"width": w, "height": h}, color_scheme=scheme)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.type + ": " + m.text) if m.type in ("error", "warning") and "ERR_TUNNEL" not in m.text and "Failed to load resource" not in m.text else None)
    await pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith("http://localhost") or (block_cdn and "data/rents" in r.request.url) else r.continue_())
    await pg.goto("http://localhost:8765/index.html")
    await pg.wait_for_function("typeof BT!=='undefined' && DB.munis && typeof updatePlus==='function'")
    await pg.click("#addr"); await pg.keyboard.type(q, delay=5); await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(4000)
    if not await pg.evaluate("!!aiProp"):
        print(tag, "list:", (await pg.locator("#acList").inner_text())[:200].replace("\n"," | "))
        if await pg.locator("#acList li[data-i]").count(): await pg.locator("#acList li[data-i]").first.click(); await pg.wait_for_timeout(4000)
    info = await pg.evaluate("""()=>({addr:$('addr').value,v:lastV,ev:window.EVID,conf:$('rConf').textContent,plusHidden:$('plus').hidden,
      rent:$('pRent').innerText.slice(0,160),lend:$('pLend').innerText.slice(0,200),bldg:$('pBldg').hidden?null:$('pBldg').innerText.slice(0,200),
      modes:['mh','mf','me','mc','ms','mr','mq'].map(i=>i+':'+(health.renderer['x'+i.slice(1)]||'?'))})""")
    print(tag, info)
    if await pg.evaluate("!$('plus').hidden"): await pg.click("#saveHome"); await pg.wait_for_timeout(300)
    await pg.locator("#plus").screenshot(path=OUT + f"plus_{tag}.png")
    await pg.locator("#calc").screenshot(path=OUT + f"calc_{tag}.png")
    await pg.locator("#saved").screenshot(path=OUT + f"saved_{tag}.png")
    await pg.locator('fieldset[data-step="1"]').screenshot(path=OUT + f"step1_{tag}.png")
    print(tag, "errors:", errs[:10])
    await b.close()
async def main():
    async with async_playwright() as p:
        for i, q in enumerate(ADDRS):
            await run(p, 1360, 1000, "light", f"d{i}", q)
        if len(ADDRS) == 1:
            await run(p, 400, 860, "dark", "phone", ADDRS[0], block_cdn=True)
asyncio.run(main())
