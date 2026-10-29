"""Screenshots of the page with a picked address: desktop light/dark and phone, plus console errors."""
import os
import asyncio, sys
from playwright.async_api import async_playwright
Q = sys.argv[1] if len(sys.argv) > 1 else "24 Mountain Cir SE, Airdrie"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + os.sep; os.makedirs(OUT, exist_ok=True)
async def run(p, w, h, scheme, tag):
    b = await p.chromium.launch()
    pg = await b.new_page(viewport={"width": w, "height": h}, color_scheme=scheme)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "ERR_TUNNEL" not in m.text and "Failed to load resource" not in m.text else None)
    await pg.route("**/*", lambda r: r.abort() if not (r.request.url.startswith("http://localhost") or "cdnjs" in r.request.url or "fonts.g" in r.request.url) else r.continue_())
    await pg.goto("http://localhost:8765/index.html")
    await pg.wait_for_function("typeof BT!=='undefined' && BT.data && DB.munis")
    await pg.click("#addr"); await pg.keyboard.type(Q, delay=10); await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(6000)
    await pg.screenshot(path=OUT + f"shot_{tag}_top.png")
    el = pg.locator("#bt")
    await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(1500)
    await el.screenshot(path=OUT + f"shot_{tag}_bt.png")
    print(tag, "errors:", errs[:8])
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 1360, 1000, "light", "desk_light")
        if "all" in sys.argv:
            await run(p, 1360, 1000, "dark", "desk_dark")
            await run(p, 400, 860, "light", "phone")
asyncio.run(main())
