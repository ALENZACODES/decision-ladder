"""Criminal interest rate check (Criminal Code s.347 and the Criminal Interest Rate Regulations, SOR/2024-114)."""
from __future__ import annotations

from datetime import date

from .params import CRIMINAL_RATE as P, assumptions, sources, val


def applicable_cap(credit_advanced: float, borrower_is_natural_person: bool = False,
                   business_purpose: bool = True, pawn: bool = False, on: str | None = None) -> dict:
    """Which criminal-rate ceiling applies to a credit agreement, as APR percent (``None`` = no ceiling)."""
    if credit_advanced <= 0:
        raise ValueError("credit advanced must be positive")
    if on and date.fromisoformat(on[:10]) < date.fromisoformat(val(P, "in_force")):
        raise ValueError("agreements before 2025-01-01 were subject to the former 60% effective annual rate; not modelled")
    commercial = not borrower_is_natural_person and business_purpose
    band = val(P, "commercial_mid_band")
    if commercial and credit_advanced > val(P, "commercial_exempt_above"):
        return {"cap_apr_pct": None, "regime": "commercial exemption: credit advanced over $500,000"}
    if commercial and band["above"] < credit_advanced <= band["up_to"]:
        return {"cap_apr_pct": band["cap_apr_pct"], "regime": "commercial band: $10,000 to $500,000 (48% APR)"}
    pb = val(P, "pawn_band")
    if pawn and credit_advanced < pb["below"]:
        return {"cap_apr_pct": pb["cap_apr_pct"], "regime": "pawn loan under $1,000 (48% APR)"}
    why = ("borrower is a natural person" if borrower_is_natural_person else
           "not for a business purpose" if not business_purpose else "credit advanced is $10,000 or less")
    return {"cap_apr_pct": val(P, "general_cap_apr_pct"), "regime": f"general criminal rate (35% APR): {why}"}


def check(apr_pct: float, credit_advanced: float, borrower_is_natural_person: bool = False,
          business_purpose: bool = True, pawn: bool = False, on: str | None = None) -> dict:
    """Compare an all-in APR (percent) with the applicable ceiling and say whether it is over."""
    cap = applicable_cap(credit_advanced, borrower_is_natural_person, business_purpose, pawn, on)
    c = cap["cap_apr_pct"]
    over = c is not None and apr_pct > c
    out = {"apr_pct": round(apr_pct, 4), "credit_advanced": round(credit_advanced, 2), **cap,
           "exceeds_criminal_rate": over,
           "headroom_pts": None if c is None else round(c - apr_pct, 4),
           "flag": ("EXCEEDS the criminal interest rate: do not arrange; refer for legal review" if over else
                    "within 5 points of the criminal rate: confirm every fee is in the APR" if c is not None
                    and apr_pct > c - 5 else None),
           "source": sources(P), "assumptions": assumptions("apr_method", "credit_advanced_net_of_fees")}
    return out
