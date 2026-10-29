"""Builds the image prompt pack (docs/image-prompts/) for ChatGPT image generation.

Every prompt is self-contained (ChatGPT does not remember the style between chats), names its output file and
where the image is used. Run: python scripts/image_prompts.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "image-prompts"

STYLE = ("Style: refined editorial illustration for a Canadian fintech product, deep ink-navy (#0d1726 to #23354f) "
         "background, one bright accent of electric lime green (#76b900) used sparingly, warm amber (#e07a2f) as a "
         "secondary highlight, soft volumetric light, subtle paper grain, clean geometric shapes, calm and trustworthy. "
         "Strict rules: NO text, letters, numbers or words anywhere in the image; NO logos, brand marks or flags; "
         "NO real people or recognizable faces; NO university crests; not cartoonish, not stock-photo cheesy.")
STYLE_LIGHT = ("Style: clean editorial illustration on a warm off-white (#f3f5f8) background, ink-navy (#0d1726) "
               "line work and shapes, one small accent of lime green (#76b900), soft shadows, generous empty space. "
               "Strict rules: NO text, letters, numbers or words; NO logos or brand marks; NO real people.")
ICON = ("Icon style: single flat-but-dimensional icon, centered, on a pure transparent or plain #0d1726 square "
        "background, ink-navy and white shapes with one lime green (#76b900) accent, rounded geometry, consistent 3px "
        "stroke feel, no text, no letters, no logos. Square 1024x1024, the icon fills about 60% of the frame.")
PHOTO = ("Style: realistic architectural photograph, overcast soft daylight, Southern Ontario, natural colours, "
         "shot at eye level with a 35mm lens, no people, no visible house numbers, street signs, licence plates or "
         "brand names, no text anywhere.")

SIZES = {"wide": "1792x1024 (landscape 16:9)", "banner": "1792x1024, will be cropped to 1280x400 (keep the subject "
         "in the middle third, leave the left 40% calm for overlaid title text)", "square": "1024x1024",
         "tall": "1024x1792 (portrait 9:16)", "card": "1792x1024, will be cropped to 1200x630"}

P: list[dict] = []


def add(group: str, file: str, use: str, size: str, subject: str, style: str = STYLE) -> None:
    P.append({"id": f"{group[0]}{sum(1 for p in P if p['group'] == group) + 1:02d}", "group": group, "file": file,
              "use": use, "size": SIZES[size], "prompt": f"{subject} {style} Size: {SIZES[size]}."})


# ---------------------------------------------------------------- A. Brand and hero
G = "A-hero"
add(G, "hero/readme-banner.png", "Top of README and Devpost cover", "banner",
    "A tall ladder of seventeen glowing rungs rising from a quiet suburban Canadian street at dusk into a night sky; "
    "each rung is a thin bar of light, the lower rungs warm amber and the upper rungs lime green; small translucent "
    "document cards, a house outline and a key float beside the ladder.")
add(G, "hero/os-home.png", "Mortgage OS home tab header", "banner",
    "An isometric control room seen from above: a long desk with twenty-one small glowing app tiles arranged along a "
    "curved path from a house key at the left to a set of signed papers at the right, thin light trails linking them.")
add(G, "hero/journey-path.png", "'One client, start to finish' section", "wide",
    "A winding path through a miniature Ontario neighbourhood seen in isometric view, marked by ten softly glowing "
    "waypoints: a mailbox, a calculator, a folder, a magnifying glass, a house, a key, a calendar, a rising line chart, "
    "an office tower, a shield; the path ends at a front door with warm light.")
add(G, "hero/devpost-thumbnail.png", "Devpost project thumbnail and gallery image 1", "card",
    "A single elegant ladder made of light leaning against a stylized Canadian house silhouette, the house built from "
    "stacked translucent financial documents, lime green glow at the top rung, deep navy night background.")
add(G, "hero/youtube-thumbnail.png", "YouTube video thumbnail (title text added afterwards)", "card",
    "Dramatic close-up of a glowing ladder rung in the foreground with a blurred house and floating charts behind it, "
    "strong lime green rim light, high contrast, the right half calm and dark for overlaid title text.")
add(G, "hero/social-og.png", "Open Graph / link preview image", "card",
    "Minimal composition: a small house outline drawn in a single lime green line sits on the top rung of a "
    "minimalist ladder, everything else deep navy with faint grid lines like a blueprint.")
add(G, "hero/three-tier-models.png", "'Nano / Super / Ultra' explainer", "wide",
    "Three abstract glowing processor-like crystals of increasing size from left to right (small, medium, large), "
    "connected by beams of light to a single mortgage document in the centre; the small one is quick and bright, "
    "the large one deep and slow-glowing.")
add(G, "hero/crosscheck.png", "'Cross-checks: my apps check each other' section", "wide",
    "Three separate calculators on a dark desk, each projecting a beam of light that meets at one exact point above "
    "them, forming a small bright star where they agree; one faint beam slightly off target in amber.")
add(G, "hero/provenance.png", "Provenance verifier explainer", "wide",
    "A magnifying glass held over a paragraph of abstract unreadable lines, with thin lime green threads running "
    "from specific spots in the paragraph down to small glowing calculator tiles below, showing every figure is traced "
    "to its source.")
add(G, "hero/tavily-research.png", "Research / Tavily section", "wide",
    "A lantern of light moving across a dark library of official-looking binders and government-style folders "
    "(no text, no crests), picking out two pages that glow; a thin line connects them to a rate chart.")
add(G, "hero/serverless.png", "Nebius Serverless deploy section", "wide",
    "A row of small glowing containers floating above clouds at night, one of them opening to release a stream of "
    "tiny documents and envelopes toward houses far below; clean, technical, no logos.")
add(G, "hero/renewal-book.png", "Renewal Book job section", "wide",
    "A tall stack of mortgage files on a desk, a beam of light scanning down the stack and lifting out three files "
    "that glow amber, a calendar page and an alarm clock nearby.")

# ---------------------------------------------------------------- B. Lifecycle stages (art + icons)
STAGES = [
    ("lead", "Lead & first conversation", "an open email envelope with a speech bubble and a small house rising out of it"),
    ("prequal", "Affordability & pre-qualification", "a balance scale weighing a stack of coins against a small house"),
    ("documents", "Documents & intake", "a neat fan of documents being sorted into labelled folders by thin beams of light"),
    ("underwriting", "Pre-underwriting & qualification", "a magnifying glass over a document with a checkmark shield"),
    ("property", "Property value & house prices", "a house on a pedestal with a rising line chart behind it"),
    ("closing", "Cash to close & closing", "a key on a ring resting on signed papers next to a small pile of coins"),
    ("servicing", "Servicing, renewal & refinance", "a circular arrow wrapped around a house with a calendar page"),
    ("market", "Market, rates & research", "three overlapping rate lines on a chart with a compass"),
    ("commercial", "Commercial & private credit", "a mid-rise apartment building with a briefcase and a bar chart"),
    ("compliance", "Compliance & client messages", "a shield with a document and a speech bubble"),
]
for key, name, motif in STAGES:
    add("B-stages", f"stages/{key}.png", f"Stage header art: {name}", "wide",
        f"Wide atmospheric illustration for the mortgage lifecycle stage '{name}': {motif}, set in a quiet scene with "
        "plenty of dark negative space.")
for key, name, motif in STAGES:
    add("C-stage-icons", f"icons/stage-{key}.png", f"Stage chip icon: {name}", "square", f"Icon of {motif}.", ICON)

# ---------------------------------------------------------------- D. Module cover cards (the author's 21 modules)
MODULES = [
    ("mortgageloanops", "MortgageLoanOps", "a loan file moving along a small conveyor through a stress-test gauge"),
    ("canadian-mortgage-suite", "Canadian Mortgage Calculator Suite", "fourteen small calculator tiles arranged in a neat grid like a toolbox"),
    ("cash-to-close", "Cash to Close", "a house key beside neatly stacked envelopes of cash and a closing-day calendar"),
    ("mortgage-decision-lab", "Mortgage Decision Lab", "laboratory glassware filled with glowing liquid shaped like small houses and coins"),
    ("pre-underwriting-copilot", "Loan File Pre-Underwriting Check", "a clipboard checklist with some items glowing green and one amber"),
    ("private-credit-screener", "Private Credit Deal Screener", "a commercial building inside a radar-like scanning circle with a grade badge shape (no letters)"),
    ("renewal-check", "Renewal Check", "a renewal letter envelope with a small payment gauge needle"),
    ("renewal-shock-radar", "Renewal Shock Radar", "a radar screen with a few blips shaped like houses, one pulsing amber"),
    ("canada-rate-cycle-dashboard", "Canada's Rate Cycle 2015-2026", "a smooth wave-like rate curve rising and falling over a decade, drawn as a glowing ribbon"),
    ("doc-quest", "Doc Quest", "a treasure map path leading between documents, the next three steps glowing"),
    ("benchmark-home-value", "Benchmark Home Value", "a street of houses with a soft heat-map glow over the roofs"),
    ("canada-home-value", "Canada Home Value", "a map-like grid of neighbourhoods with small glowing house pins"),
    ("canada-housing-affordability-index-1980-2026", "Canada Housing Affordability Index 1980-2026", "a very long timeline ribbon with a house rising further and further out of reach"),
    ("renewal-radar", "Renewal Radar", "a broker's desk with a wall of upcoming maturity calendars and a sweeping radar beam"),
    ("canada-policy-rate-bond-yield-mortgage-rate", "Who Sets Canada's 5 Year Mortgage Rate?", "three stacked ribbons (policy rate, bond yield, mortgage rate) with gaps between them"),
    ("canada-real-interest-rates-cpi-vs-policy-rate", "Real Interest Rates in Canada Since 2009", "two lines crossing, one for prices and one for rates, over a shopping basket"),
    ("canada-renewal-shock-2020-2021-five-year-fixed", "Canada's Renewal Wave", "a large ocean wave made of small houses about to break on a shoreline"),
    ("kaggle-boc-notebooks", "Bank of Canada notebooks", "open notebooks with charts spilling out as floating lines"),
    ("quiet-charges", "Quiet Charges", "a bank statement with a few recurring lines softly glowing like tiny lanterns"),
    ("shoebox", "Shoebox", "an open shoebox full of receipts being sorted into labelled trays by beams of light"),
    ("renewal-check-pitch", "RenewalCheck pitch deck", "a sequence of ten floating presentation slides in a gentle arc"),
]
for key, name, motif in MODULES:
    add("D-modules", f"modules/{key}.png", f"Module card cover in the OS: {name}", "card",
        f"Cover illustration for the app '{name}': {motif}.")

# ---------------------------------------------------------------- E. Desks (written for the hackathon)
DESKS = [
    ("commercial", "Commercial Lending Desk", "a 24-unit mid-rise apartment building with a construction crane and a bridge arching to a second building"),
    ("business", "Business Lending Desk", "a small storefront with an invoice turning into coins and an equipment crate"),
    ("income", "Income & Rental Qualification Desk", "a pay stub, a rental duplex and a self-employed laptop balanced on a scale"),
    ("servicing", "Servicing Desk", "a long amortization curve descending to zero with payment markers along it like stepping stones"),
    ("disclosure", "Disclosure & Compliance Desk", "a disclosure document under a desk lamp with a shield and a calendar marked 21 days ahead (no numbers visible)"),
]
for key, name, motif in DESKS:
    add("E-desks", f"desks/{key}-cover.png", f"Header image of /static/desks/{key}.html", "banner",
        f"Header illustration for the '{name}': {motif}.")
    add("E-desks", f"desks/{key}-icon.png", f"Desk link icon: {name}", "square", f"Icon of {motif}.", ICON)

# ---------------------------------------------------------------- F. The 17 ladder rungs (icons)
RUNGS = [
    ("intake", "an envelope opening into a form"), ("screening", "a person silhouette outline behind a shield, faceless"),
    ("documents", "a stack of three documents with a paperclip"), ("affordability", "a balance scale with a house and coins"),
    ("readiness", "a traffic light with the green light on"), ("insurance", "an umbrella over a house"),
    ("qualification", "a pressure gauge with the needle in the green zone"), ("crosscheck", "three arrows meeting at one point"),
    ("lender", "a building with columns (generic, no crest) and a handshake outline"), ("property", "a house with a price tag shape (no numbers)"),
    ("closing", "a key turning in a lock"), ("market", "a line chart with a compass needle"),
    ("exit_cost", "a door with an exit arrow and a coin"), ("renewal_outlook", "a calendar with a looping arrow"),
    ("commercial", "an apartment building"), ("compliance", "a shield with a checkmark"), ("decision", "a gavel resting on a document"),
]
for key, motif in RUNGS:
    add("F-rungs", f"icons/rung-{key}.png", f"Ladder rung icon: {key}", "square", f"Icon of {motif}.", ICON)

# ---------------------------------------------------------------- G. Sample files (fictional clients and properties)
PROPS = [
    ("oakville-semi", "Priya's file", "a two-storey semi-detached brick house on a leafy Oakville street in autumn, maple trees"),
    ("brampton-town", "Daniel's file", "a newer three-storey freehold townhouse row in a Brampton subdivision"),
    ("markham-house", "Wei's renewal", "a detached two-storey family home in a Markham suburb, tidy front lawn"),
    ("toronto-refi", "Marco's refinance", "a semi-detached Victorian house on a Toronto street with a porch"),
    ("hamilton-24-unit", "Hamilton commercial bridge loan", "a 1960s 24-unit mid-rise brick apartment building in Hamilton with balconies"),
]
for key, who, scene in PROPS:
    add("G-samples", f"samples/{key}.png", f"Property photo on the sample-file card: {who}", "card", f"Photograph of {scene}.", PHOTO)
PERSONAS = [
    ("priya", "a first-time buyer couple in their thirties looking at a laptop at a kitchen table, seen from behind"),
    ("daniel", "a young buyer holding a set of keys, hands and keys only in focus"),
    ("wei", "an older homeowner reading a letter at a dining table, shot from over the shoulder, face not visible"),
    ("marco", "a homeowner on a front porch holding a coffee, cropped at the shoulders, face not visible"),
    ("harbourview", "a property manager walking past an apartment building entrance, back to camera"),
]
for key, scene in PERSONAS:
    add("G-samples", f"samples/persona-{key}.png", f"Persona image on the sample-file card ({key}, fictional)", "square",
        f"Warm editorial illustration (not a photo) of {scene}; faces hidden or out of frame.", STYLE_LIGHT)
DOCS = [("pay-stub", "a pay stub"), ("t4", "a tax slip"), ("renewal-letter", "a bank renewal offer letter"),
        ("bank-statement", "a bank statement with columns of lines"), ("purchase-agreement", "a purchase agreement with a signature line"),
        ("discharge-statement", "a mortgage payout statement")]
for key, what in DOCS:
    add("G-samples", f"docs/{key}.png", f"Thumbnail for an uploaded document type: {what}", "square",
        f"Overhead view of {what} lying on a desk; every line of text replaced by soft abstract grey bars so nothing is "
        "readable; a pen beside it.", STYLE_LIGHT)

# ---------------------------------------------------------------- H. Video (3 minutes)
SCENES = [
    ("title", "Opening title card (title text added in editing)", "the glowing ladder from the banner, slow push-in composition, dark top third for text"),
    ("problem", "Scene: a broker juggling apps", "a desk overflowing with twenty browser windows drawn as floating translucent panels, tangled light threads between them"),
    ("one-system", "Scene: one system", "the same floating panels snapping into one tidy curved row along a ladder of light"),
    ("nemotron", "Scene: three Nemotron tiers", "three crystals small, medium, large lighting up one after another along a beam"),
    ("crosscheck-bug", "Scene: the cross-check found a bug", "two calculator beams that miss each other by a hair, a small amber spark at the gap"),
    ("commercial", "Scene: commercial bridge loan", "a mid-rise apartment at night with a translucent bridge of light to a second building"),
    ("renewal", "Scene: renewal wave", "a wave of small houses rising toward a calendar"),
    ("disclosure", "Scene: disclosure and compliance", "a document sliding under a desk lamp with a shield glowing beside it"),
    ("serverless", "Scene: batch job on Nebius Serverless", "small containers lifting off and processing a long row of files"),
    ("end-card", "End card (links added in editing)", "the ladder from the banner seen from far away, calm, lots of dark space"),
]
for key, use, scene in SCENES:
    add("H-video", f"video/{key}.png", use, "wide", f"Cinematic still for a product video: {scene}.")
for i, mood in enumerate(["slow amber to lime green light sweep", "thin lime line drawing itself across black",
                          "grid of tiny squares lighting up left to right", "soft particles forming a house outline",
                          "rings of light expanding from the centre", "a ladder rung sliding into place"], 1):
    add("H-video", f"video/transition-{i}.png", "Transition background", "wide", f"Abstract transition frame: {mood}.")

# ---------------------------------------------------------------- I. App states
STATES = [("empty-ladder", "an empty ladder waiting in soft light, a single folder at its foot"),
          ("empty-book", "an empty filing tray with one envelope about to land in it"),
          ("loading", "a small ladder whose rungs light up one by one"),
          ("offline", "a ladder under a glass dome, calm, like a demo model"),
          ("error", "a ladder with one rung missing, a small spare rung resting nearby"),
          ("no-results", "a magnifying glass over an empty desk"),
          ("success", "a front door opening with warm light spilling out"),
          ("restructure", "a ladder being rearranged by small hands of light, rungs repositioned")]
for key, scene in STATES:
    add("I-states", f"states/{key}.png", f"App {key.replace('-', ' ')} state", "square", f"Small spot illustration of {scene}.", STYLE_LIGHT)

# ---------------------------------------------------------------- J. Devpost gallery and social
GALLERY = [("gallery-architecture", "an exploded isometric view of a building with five floors, each floor a different layer of an app stack, light flowing upward"),
           ("gallery-modules", "twenty-one small glowing tiles arranged on a ladder like books on shelves"),
           ("gallery-desks", "five desks in a row in a dark office, each lit by its own lamp, each with a different small object"),
           ("gallery-data", "a river of Bank of Canada style data lines flowing into a small house-shaped reservoir (no text)"),
           ("gallery-trust", "a scale of justice balanced with a calculator on one side and a document on the other"),
           ("linkedin-post", "the glowing ladder leaning on a house made of documents, square crop friendly"),
           ("x-post", "a single ladder rung glowing lime green in darkness, minimal")]
for key, scene in GALLERY:
    add("J-gallery", f"gallery/{key}.png", f"Devpost gallery / social image: {key}", "card", f"Illustration of {scene}.")


def write() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prompts.json").write_text(json.dumps(P, indent=1), encoding="utf-8")
    with (OUT / "prompts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "group", "file", "size", "use", "prompt"])
        w.writeheader()
        w.writerows(P)
    lines = ["# Image prompt pack for Decision Ladder", "",
             f"{len(P)} prompts. Paste one prompt per ChatGPT message. Save each image with the exact file name under "
             "`docs/images/` (for example `docs/images/hero/readme-banner.png`) and send them back; I wire them into the "
             "app, README, video and Devpost.", "",
             "Rules baked into every prompt: no text in the image (titles are added afterwards so they are spelled right), "
             "no logos (use the official NVIDIA / Nebius / Tavily marks from their press kits instead), no real people. "
             "Real app screenshots must stay real screenshots: never generate a fake UI or fake numbers.", "",
             "To reach 300-500 images: generate 3 variations of every A, D, E and H prompt and pick the best one.", ""]
    group = None
    for p in P:
        if p["group"] != group:
            group = p["group"]
            lines += ["", f"## {group}", ""]
        lines += [f"### {p['id']} · `{p['file']}`", f"*Use:* {p['use']}", "", "```", p["prompt"], "```", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    write()
    print(len(P), "prompts ->", OUT)
