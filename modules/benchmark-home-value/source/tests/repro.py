"""Reproduce the 'typed address lands on another address' bug in a real browser."""
import sys, asyncio, json
from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/index.html"
CASES = [
    # (what the user types, how they finish: 'enter' | 'click' | 'wait-enter')
    ("123 Main St, Toronto", "enter"),
    ("123 Main St, Toronto", "click"),
    ("4756 Drummond Dr, Vancouver", "enter"),
    ("4756 Drummond Dr, Vancouver", "wait-enter"),
    ("24 Mountain Cir SE, Airdrie", "enter"),
    ("12141 Jasper Ave, Edmonton", "enter"),
    ("1 Yonge St, Toronto", "enter"),
    ("10 Riverview Dr SE", "enter"),
    ("55 Bloor St W, Toronto", "wait-enter"),
    ("200 Bay St, Toronto", "wait-click"),
]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(URL)
        await pg.wait_for_function("typeof DB!=='undefined' && DB.munis")
        for q, how in CASES:
            await pg.evaluate("go(1)")
            await pg.fill("#addr", "")
            await pg.click("#addr")
            await pg.keyboard.type(q, delay=35)   # a quick typist
            if how.startswith("wait"):
                await pg.wait_for_timeout(2500)
            before = await pg.evaluate("[...document.querySelectorAll('#acList li')].map(l=>l.innerText.replace(/\\n/g,' | '))")
            if how.endswith("enter"):
                await pg.keyboard.press("Enter")
            else:
                li = pg.locator("#acList li[data-i]").first
                if await li.count():
                    await li.dispatch_event("mousedown")
            await pg.wait_for_timeout(7000)
            got = await pg.evaluate("[document.getElementById('addr').value, st.muni, (aiProp&&aiProp.pick)?aiProp.pick.label+' '+aiProp.pick.sub:null, document.querySelector('fieldset[data-step=\"3\"]').hidden?'still on step 1/2':'jumped to result']")
            print(json.dumps({"typed": q, "how": how, "list_at_finish": before[:3], "field_after": got}))
        print("page errors:", errs)
        await b.close()

asyncio.run(main())
