"""Citation registry for the Disclosure & Compliance Desk.

Every rule the desk applies points at one entry here. ``verified`` says what the text was actually checked
against on ``checked``; where the official consolidation could not be read directly (ontario.ca e-Laws renders
in the browser only) the entry names the copy that was read instead. Anything not verified is labelled an
assumption in the engine that uses it.
"""
from __future__ import annotations

CHECKED = "2026-10-29"
NOT_LEGAL_ADVICE = ("Not legal advice. This is a deterministic checklist built from the cited provisions as read on "
                    f"{CHECKED}; confirm against the current official text and with your principal broker or counsel.")

SOURCES: dict[str, dict] = {
    "ON_191_08": {
        "title": "O. Reg. 191/08, Cost of Borrowing and Disclosure to Borrowers (Mortgage Brokerages, Lenders and "
                 "Administrators Act, 2006)",
        "url": "https://www.ontario.ca/laws/regulation/080191",
        "verified": "ss. 2, 3(1), 5, 7, 8(1) items 1-6 against the vLex consolidation from 2022-03-01 "
                    "(https://ca.vlex.com/vid/cost-of-borrowing-and-904974201); ss. 1, 3(2), 4, 6, 8, 9, 14 against the "
                    "2008 text (https://expert.filogix.com/expert/WebHelp/Expert_EN/MBLAA/MBLAA.pdf), later amendments "
                    "to those sections not confirmed",
    },
    "ON_188_08": {
        "title": "O. Reg. 188/08, Mortgage Brokerages: Standards of Practice",
        "url": "https://www.fsrao.ca/industry/mortgage-brokering/compliance-and-other-resources/"
               "mortgage-brokerage-disclosure-requirements",
        "verified": "section numbers as cited by FSRA's disclosure-requirements page; s. 27 conflicts from FSRA "
                    "guidance MB0054INT (https://www.fsrao.ca/media/25786/download)",
    },
    "FSRA_MB0054INT": {
        "title": "FSRA Interpretation Guidance MB0054INT, Mortgage Product Suitability Assessment (effective 2024-06-19)",
        "url": "https://www.fsrao.ca/industry/mortgage-brokering/regulatory-framework/guidance-mortgage-brokering/"
               "mortgage-product-suitability-assessment",
        "verified": "outcomes 1, 3, 4 and 6 read",
    },
    "RECA_RULES": {
        "title": "Real Estate Act Rules (Alberta), RECA (stated current as of 2023-07-17)",
        "url": "https://www.reca.ca/rules/",
        "verified": "ss. 41, 43, 45, 65, 71, 72, 74, 75 read",
    },
    "INTEREST_ACT": {
        "title": "Interest Act, R.S.C. 1985, c. I-15 (current to 2026-09-30)",
        "url": "https://laws-lois.justice.gc.ca/eng/acts/I-15/FullText.html",
        "verified": "ss. 6 to 10 read",
    },
    "FCPF_REGS": {
        "title": "Financial Consumer Protection Framework Regulations, SOR/2021-181 (Bank Act; current to 2026-09-30)",
        "url": "https://laws-lois.justice.gc.ca/eng/regulations/SOR-2021-181/page-3.html",
        "verified": "ss. 45, 47, 48 read",
    },
    "INTERPRETATION_ACT": {
        "title": "Interpretation Act, R.S.C. 1985, c. I-21, s. 27",
        "url": "https://laws-lois.justice.gc.ca/eng/acts/I-21/section-27.html",
        "verified": "s. 27(1)-(2) read",
    },
    "ON_LEGISLATION_ACT": {
        "title": "Legislation Act, 2006 (Ontario), ss. 88-89",
        "url": "https://www.ontario.ca/laws/statute/06l21",
        "verified": "secondary sources only: holiday list per https://foiassist.ca/2026/06/29/how-are-holidays-defined-"
                    "under-fippa-and-mfippa-when-counting-business-days/ ; s. 89(3) 'at least' counting per "
                    "https://tips.slaw.ca/2019/practice/unclear-days-computing-time-in-statutes-and-regulations/",
    },
    "FINTRAC_METHODS": {
        "title": "FINTRAC, Methods to verify the identity of persons and entities",
        "url": "https://fintrac-canafe.canada.ca/guidance-directives/client-clientele/Guide11/11-eng",
        "verified": "photo ID, credit file, dual-process and reliance sections read",
    },
    "FINTRAC_MORTGAGE": {
        "title": "FINTRAC, When to verify identity: mortgage administrators, brokers and lenders (modified 2024-10-11)",
        "url": "https://fintrac-canafe.canada.ca/guidance-directives/client-clientele/client/mort-eng",
        "verified": "triggers, exceptions, information-record contents, beneficial-owner definition read",
    },
    "PCMLTFA_MORTGAGE_2024": {
        "title": "PCMLTFA amendments for the mortgage sector, in force 2024-10-11 (Fasken bulletin, secondary)",
        "url": "https://www.fasken.com/en/knowledge/2024/10/new-antimoney-laundering-requirements",
        "verified": "5-year retention, PEP/HIO, third-party, compliance-program elements read from the bulletin",
    },
}


def cite(key: str, section: str = "") -> dict:
    s = SOURCES[key]
    return {"source": key, "section": section, "title": s["title"], "url": s["url"], "checked": CHECKED,
            "verified": s["verified"]}


def envelope(result: dict, engine: str, cites: list[dict]) -> dict:
    """Attach the engine name, de-duplicated citations and the not-legal-advice note to a result."""
    seen, uniq = set(), []
    for c in cites:
        k = (c["source"], c["section"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    result["engine"] = engine
    result["citations"] = uniq
    result["note"] = NOT_LEGAL_ADVICE
    return result
