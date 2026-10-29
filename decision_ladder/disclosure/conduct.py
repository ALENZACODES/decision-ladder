"""Suitability and conflict-of-interest checklist for a borrower file.

Ontario: O. Reg. 188/08 (Mortgage Brokerages: Standards of Practice) as cited by FSRA, read with FSRA guidance
MB0054INT. Alberta: RECA Real Estate Act Rules for mortgage brokerages. Each rule names the file fields it reads;
a rule whose trigger is absent is reported as not applicable rather than passed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .cost_of_borrowing import delivery_timing
from .sources import cite, envelope

KYC_FIELDS = ("employment", "income", "property", "financial_knowledge", "objectives", "risk_tolerance",
              "housing_plan", "vulnerability", "credit_history")
COI_EXEMPT_LENDERS = ("brokerage", "financial_institution")


@dataclass(frozen=True)
class Rule:
    id: str
    jurisdiction: str
    source: str
    section: str
    requirement: str
    fields: tuple[str, ...]
    when: Callable[[dict], bool] = lambda f: True

    def evaluate(self, f: dict) -> dict:
        out = {"id": self.id, "requirement": self.requirement, "citation": f"{self.source} {self.section}"}
        if not self.when(f):
            return {**out, "status": "n/a", "missing": []}
        missing = [k for k in self.fields if not f.get(k)]
        return {**out, "status": "met" if not missing else "missing", "missing": missing}


def _yes(key: str) -> Callable[[dict], bool]:
    return lambda f: bool(f.get(key))


RULES: list[Rule] = [
    Rule("ON-SUIT", "ON", "ON_188_08", "s. 24(1)", "Reasonable steps to ensure the mortgage presented is suitable; "
         "assessment documented so a third party could re-perform it (MB0054INT Outcome 6)",
         ("suitability_documented",)),
    Rule("ON-REC", "ON", "FSRA_MB0054INT", "Outcome 4", "Rationale for the recommendation recorded and client's "
         "written acknowledgement of the options", ("recommendation_rationale", "client_ack_options")),
    Rule("ON-RISK", "ON", "ON_188_08", "s. 25", "Material risks disclosed in writing and acknowledged in writing",
         ("material_risks_disclosed", "material_risks_acknowledged")),
    Rule("ON-COI", "ON", "ON_188_08", "s. 27(1)-(2)", "Conflicts of interest disclosed in writing and acknowledged "
         "in writing by the client", ("conflicts_disclosed_in_writing", "conflicts_acknowledged"),
         lambda f: bool(f.get("conflicts")) and f.get("lender_type") not in COI_EXEMPT_LENDERS),
    Rule("ON-REL", "ON", "ON_188_08", "s. 26", "Relationships between the parties, and any conflict they create, "
         "disclosed", ("relationships_disclosed",), _yes("relationships")),
    Rule("ON-ROLE", "ON", "ON_188_08", "ss. 18-19", "Disclosed whether the brokerage acts for the borrower, the "
         "lender or both, and the number of lenders used in the last fiscal year",
         ("role_disclosed", "lenders_count_disclosed")),
    Rule("ON-FEES", "ON", "ON_188_08", "ss. 21-22", "Fees, remuneration and incentives received or paid disclosed",
         ("fees_disclosed",)),
    Rule("ON-INC", "ON", "FSRA_MB0054INT", "Outcome 3", "Incentives disclosed early with written acknowledgement",
         ("incentives_disclosed", "incentives_acknowledged"), _yes("incentives")),
    Rule("ON-ID", "ON", "ON_188_08", "ss. 10-11", "Reasonable steps taken to verify the identity of each party",
         ("identity_verified",)),
    Rule("ON-COB", "ON", "ON_191_08", "s. 8", "Cost of borrowing disclosure statement delivered",
         ("cost_of_borrowing_disclosed",)),
    Rule("ON-ADV", "ON", "ON_188_08", "s. 37", "No advance fee or deposit required or accepted where the principal "
         "is $400,000 or less", ("no_advance_fee",),
         lambda f: f.get("principal") is not None and float(f["principal"]) <= 400000),
    Rule("ON-REV", "ON", "ON_188_08", "FSRA disclosure page", "Reverse mortgage: lawyer's written statement of "
         "independent legal advice before arranging", ("ila_certificate",), _yes("reverse_mortgage")),
    Rule("AB-COMP", "AB", "RECA_RULES", "s. 41(c)", "How the licensee will be paid disclosed at the earliest "
         "practical opportunity", ("compensation_disclosed",)),
    Rule("AB-COI", "AB", "RECA_RULES", "s. 41(f)", "Any conflict of interest disclosed at the earliest practical "
         "opportunity", ("conflicts_disclosed_in_writing",), _yes("conflicts")),
    Rule("AB-AGR", "AB", "RECA_RULES", "s. 43", "Written service agreement stating remuneration, signed, copy "
         "delivered on signing", ("service_agreement_signed", "service_agreement_copy_delivered")),
    Rule("AB-REF", "AB", "RECA_RULES", "s. 45", "Referral fee or benefit disclosed in writing, copy retained",
         ("referral_fee_disclosed",), _yes("referral_fee")),
    Rule("AB-DISC", "AB", "RECA_RULES", "s. 65(c)", "Written disclosure of the service relationship, lender "
         "relationships, range of lenders, compensation, other lender benefits and any extra borrower fees",
         ("relationship_disclosure_delivered",)),
    Rule("AB-VER", "AB", "RECA_RULES", "s. 72", "Written disclosure of the steps taken to verify information, "
         "including identity, with supporting documents on file",
         ("verification_steps_disclosed", "verification_docs_on_file")),
    Rule("AB-COMMIT", "AB", "RECA_RULES", "s. 74(1)(a)", "Disclosure statement provided before the borrower agrees "
         "to the mortgage commitment", ("disclosure_before_commitment",)),
    Rule("AB-OWN", "AB", "RECA_RULES", "s. 75", "Licensee dealing on own behalf: written disclosure of any direct or "
         "indirect interest", ("licensee_interest_disclosed",), _yes("licensee_interest")),
]


def rules_table(jurisdiction: str | None = None) -> list[dict]:
    return [{"id": r.id, "jurisdiction": r.jurisdiction, "requirement": r.requirement,
             "citation": f"{r.source} {r.section}", "fields": list(r.fields)}
            for r in RULES if jurisdiction in (None, r.jurisdiction)]


def evaluate(file: dict, jurisdiction: str = "ON") -> dict:
    """Evaluate a borrower file against the jurisdiction's rules; returns every rule's status and what is missing."""
    j = jurisdiction.upper()
    if j not in ("ON", "AB"):
        raise ValueError("jurisdiction must be ON or AB")
    results = [r.evaluate(file) for r in RULES if r.jurisdiction == j]
    if j == "ON":
        kyc = file.get("kyc") or {}
        gaps = [k for k in KYC_FIELDS if not kyc.get(k)]
        results.insert(1, {"id": "ON-KYC", "citation": "FSRA_MB0054INT Outcome 1",
                           "requirement": "Borrower information collected for the suitability assessment",
                           "status": "met" if not gaps else "missing", "missing": [f"kyc.{g}" for g in gaps]})
        if file.get("disclosure_date") and (file.get("signing_date") or file.get("payment_date")):
            t = delivery_timing(file["disclosure_date"], file.get("signing_date"), file.get("payment_date"),
                                waiver_date=file.get("waiver_date"))
            results.append({"id": "ON-TIME", "citation": "ON_188_08 s. 35",
                            "requirement": "Disclosures at least two business days before signing or payment, unless "
                                           "waived in writing", "status": "met" if t["ok"] else "missing",
                            "missing": [] if t["ok"] else ["disclosure_date"], "detail": t["finding"]})
    elif file.get("borrower_fee_charged"):
        ok = bool(file.get("funding_confirmation_accepted") and file.get("initial_disclosure_date")
                  and file.get("fee_date"))
        detail = "fee charged before funding confirmation accepted or without initial disclosure"
        if ok:
            t = delivery_timing(file["initial_disclosure_date"], payment_date=file["fee_date"],
                                waiver_date=file.get("waiver_date"), jurisdiction="AB",
                                extra_holidays=file.get("holidays"))
            ok, detail = t["ok"], t["finding"]
        results.append({"id": "AB-FEE", "citation": "RECA_RULES s. 71(1)",
                        "requirement": "No borrower fee until funding confirmation accepted and initial disclosure "
                                       "delivered two business days earlier (unless waived)",
                        "status": "met" if ok else "missing", "missing": [] if ok else ["borrower fee timing"],
                        "detail": detail})
    missing = [{"id": r["id"], "citation": r["citation"], "missing": r["missing"]} for r in results
               if r["status"] == "missing"]
    out = {"jurisdiction": j, "results": results, "missing": missing,
           "summary": {s: sum(r["status"] == s for r in results) for s in ("met", "missing", "n/a")},
           "complete": not missing}
    if j == "AB":
        out["assumptions"] = ["Alberta business days: weekends and any holidays passed in 'holidays' only"]
    cites = [cite(c.split(" ", 1)[0], c.split(" ", 1)[1]) for c in {r["citation"] for r in results}]
    return envelope(out, "disclosure.conduct", sorted(cites, key=lambda c: (c["source"], c["section"])))
