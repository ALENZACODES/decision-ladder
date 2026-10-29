"""Canada Small Business Financing Program (CSBFP): eligibility, loan limits by asset class, maximum rates,
registration and administration fees, and the borrower's all-in cost of a CSBFP term loan."""
from __future__ import annotations

from . import cashflow as cf
from .params import CSBFP as P, assumptions, sources, val
from .unsecured import amortize, line_of_credit as _loc_cost

TERM_CLASSES = ("real_property", "equipment", "leasehold_improvements", "intangible_assets", "working_capital")


def eligibility(gross_annual_revenue: float, farming: bool = False, for_profit: bool = True,
                operates_in_canada: bool = True) -> dict:
    """Business-level eligibility screen against the verified program criteria."""
    reasons = []
    cap = val(P, "max_gross_revenue")
    if gross_annual_revenue < 0:
        raise ValueError("revenue must be >= 0")
    if gross_annual_revenue > cap:
        reasons.append(f"gross annual revenue ${gross_annual_revenue:,.0f} exceeds the ${cap:,.0f} cap")
    if farming and val(P, "farming_excluded"):
        reasons.append("farming businesses are not eligible")
    if not for_profit:
        reasons.append("the program finances for-profit small businesses")
    if not operates_in_canada:
        reasons.append("the business must operate in Canada")
    return {"eligible": not reasons, "reasons": reasons, "revenue_cap": cap,
            "revenue_headroom": round(cap - gross_annual_revenue, 2)}


def loan_limits(request: dict, existing_term_outstanding: float = 0.0, existing_loc_authorized: float = 0.0) -> dict:
    """Cap a requested CSBFP package by asset class, then by the term-loan and per-borrower limits.

    ``request`` maps any of :data:`TERM_CLASSES` plus ``line_of_credit`` to dollars. Existing CSBFP exposure of the
    borrower and related borrowers counts against the limits. Sub-limits are applied first (equipment and leasehold
    improvements together; intangibles and working capital together), then the term-loan limit, real property last
    in priority, so the most constrained uses are kept whole where possible.
    """
    bad = [k for k in request if k not in TERM_CLASSES + ("line_of_credit",)]
    if bad:
        raise ValueError(f"unknown CSBFP class(es): {bad}")
    if any(v < 0 for v in request.values()):
        raise ValueError("amounts must be >= 0")
    req = {k: float(request.get(k, 0)) for k in TERM_CLASSES}
    approved = dict(req)
    notes = []

    def cap_group(keys: tuple[str, ...], limit: float, label: str) -> None:
        total = sum(approved[k] for k in keys)
        if total > limit:
            scale = limit / total
            for k in keys:
                approved[k] *= scale
            notes.append(f"{label} limited to ${limit:,.0f} (requested ${total:,.0f}); reduced pro rata")

    cap_group(("equipment", "leasehold_improvements"), val(P, "max_equipment_and_leasehold"),
              "equipment + leasehold improvements")
    cap_group(("intangible_assets", "working_capital"), val(P, "max_intangibles_and_working_capital"),
              "intangible assets + working capital")
    term_room = max(0.0, min(val(P, "max_term_loans"), val(P, "max_per_borrower")) - existing_term_outstanding)
    other = sum(v for k, v in approved.items() if k != "real_property")
    if other > term_room:
        scale = term_room / other if other else 0.0
        for k in approved:
            approved[k] = approved[k] * scale if k != "real_property" else 0.0
        notes.append(f"term-loan room ${term_room:,.0f} after existing CSBFP term loans; non-property uses reduced")
    elif approved["real_property"] > term_room - other:
        approved["real_property"] = term_room - other
        notes.append(f"real property limited by remaining term-loan room ${term_room:,.0f}")
    term_total = sum(approved.values())
    loc_req = float(request.get("line_of_credit", 0))
    loc_room = max(0.0, min(val(P, "max_line_of_credit"),
                            val(P, "max_per_borrower") - existing_term_outstanding - term_total) - existing_loc_authorized)
    loc = min(loc_req, loc_room)
    if loc < loc_req:
        notes.append(f"line of credit limited to ${loc_room:,.0f}")
    return {"requested": {**req, "line_of_credit": loc_req},
            "eligible": {**{k: round(v, 2) for k, v in approved.items()}, "line_of_credit": round(loc, 2)},
            "term_loan_total": round(term_total, 2), "line_of_credit": round(loc, 2),
            "package_total": round(term_total + loc, 2),
            "shortfall": round(sum(req.values()) + loc_req - term_total - loc, 2), "notes": notes,
            "limits": {k: val(P, k) for k in ("max_per_borrower", "max_term_loans", "max_equipment_and_leasehold",
                                               "max_intangibles_and_working_capital", "max_line_of_credit")}}


def max_rate(kind: str, prime_pct: float | None = None, residential_rate_pct: float | None = None) -> float:
    """Maximum rate the lender may charge: 'floating' (prime + 3), 'fixed' (lender's single-family residential
    mortgage rate for the term + 3) or 'line_of_credit' (prime + 5)."""
    if kind == "floating":
        if prime_pct is None:
            raise ValueError("prime_pct needed for a floating-rate term loan")
        return prime_pct + val(P, "max_spread_floating_term")
    if kind == "fixed":
        if residential_rate_pct is None:
            raise ValueError("residential_rate_pct needed for a fixed-rate term loan")
        return residential_rate_pct + val(P, "max_spread_fixed_term")
    if kind == "line_of_credit":
        if prime_pct is None:
            raise ValueError("prime_pct needed for a line of credit")
        return prime_pct + val(P, "max_spread_line_of_credit")
    raise ValueError("kind must be floating, fixed or line_of_credit")


def term_loan(amount: float, annual_rate_pct: float, years: float, rate_kind: str = "floating",
              prime_pct: float | None = None, residential_rate_pct: float | None = None,
              finance_registration_fee: bool = True, other_fees: float = 0.0) -> dict:
    """Borrower's cost of a CSBFP term loan (monthly payments): payment, registration fee, all-in APR, the program
    rate ceiling, and the administration fee the lender remits on end-of-month balances."""
    if amount <= 0 or years <= 0:
        raise ValueError("amount and years must be positive")
    if years > val(P, "max_term_years"):
        raise ValueError(f"CSBFP term loans run at most {val(P, 'max_term_years')} years")
    ceiling = max_rate(rate_kind, prime_pct, residential_rate_pct)
    reg_fee = amount * val(P, "registration_fee_pct") / 100
    loan = amount + (reg_fee if finance_registration_fee else 0.0)
    n = round(years * 12)
    rows = amortize(loan, annual_rate_pct / 1200, n)
    net = amount - other_fees - (0.0 if finance_registration_fee else reg_fee)
    rates = cf.rate_summary(cf.irr([net] + [-r["payment"] for r in rows]), 12)
    admin = sum(r["balance"] for r in rows) * val(P, "admin_fee_annual_pct") / 1200   # 1.25%/12 of each month-end balance
    total_paid = sum(r["payment"] for r in rows)
    return {"program": "CSBFP term loan", "amount": amount, "registration_fee": round(reg_fee, 2),
            "registration_fee_financed": finance_registration_fee, "loan_balance_at_funding": round(loan, 2),
            "monthly_payment": round(rows[0]["payment"], 2), "payments": n,
            "total_interest": round(sum(r["interest"] for r in rows), 2), "total_paid": round(total_paid, 2),
            "contract_rate_pct": annual_rate_pct, "rate_kind": rate_kind, "max_rate_pct": round(ceiling, 4),
            "within_max_rate": annual_rate_pct <= ceiling + 1e-9,
            "apr_pct": rates["apr_pct"], "ear_pct": rates["ear_pct"],
            "lender_admin_fee_total": round(admin, 2),
            "engine": "business.csbfp.term_loan", "source": sources(P),
            "assumptions": assumptions("csbfp_rate_compounding", "csbfp_admin_fee_borne_by", "apr_method")}


def line_of_credit(authorized: float, average_drawn: float, annual_rate_pct: float, prime_pct: float,
                   years: float = 5.0, standby_fee_pct: float = 0.0) -> dict:
    """CSBFP line of credit: program limit and maximum rate (prime + 5), the 2% registration fee on the authorized
    amount spread over the registration period (max 5 years), and the annual cost on the average drawn balance."""
    cap, max_years = val(P, "max_line_of_credit"), val(P, "max_loc_term_years")
    if authorized > cap:
        raise ValueError(f"CSBFP lines of credit are limited to ${cap:,.0f}")
    if not 0 < years <= max_years:
        raise ValueError(f"a CSBFP line of credit is registered for at most {max_years} years")
    reg_fee = authorized * val(P, "registration_fee_pct") / 100
    out = _loc_cost(authorized, average_drawn, annual_rate_pct, standby_fee_pct, setup_fee=reg_fee, expected_years=years)
    ceiling = max_rate("line_of_credit", prime_pct)
    out.update({"product": "CSBFP line of credit", "registration_fee": round(reg_fee, 2), "max_rate_pct": round(ceiling, 4),
                "within_max_rate": annual_rate_pct <= ceiling + 1e-9,
                "lender_admin_fee_annual": round(average_drawn * val(P, "admin_fee_annual_pct") / 100, 2),
                "engine": "business.csbfp.line_of_credit", "source": sources(P),
                "assumptions": {**out["assumptions"], **assumptions("csbfp_admin_fee_borne_by")}})
    return out


def assess(gross_annual_revenue: float, request: dict, farming: bool = False,
           existing_term_outstanding: float = 0.0, existing_loc_authorized: float = 0.0) -> dict:
    """One-call CSBFP screen: eligibility plus the eligible package and its registration fees."""
    elig = eligibility(gross_annual_revenue, farming)
    lim = loan_limits(request, existing_term_outstanding, existing_loc_authorized)
    reg = val(P, "registration_fee_pct") / 100
    return {"eligibility": elig, "package": lim if elig["eligible"] else None,
            "registration_fees": None if not elig["eligible"] else {
                "term_loans": round(lim["term_loan_total"] * reg, 2),
                "line_of_credit": round(lim["line_of_credit"] * reg, 2)},
            "max_terms_years": {"term_loans": val(P, "max_term_years"), "line_of_credit": val(P, "max_loc_term_years")},
            "engine": "business.csbfp.assess", "source": sources(P)}
