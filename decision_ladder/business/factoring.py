"""Invoice factoring: advance, discount fee (flat, per period or tiered), reserve release, recourse versus
non-recourse, and the effective annualized cost from the actual timing of the cash."""
from __future__ import annotations

import math

from . import cashflow as cf
from . import usury
from .params import assumptions


def _rate_check(apr_pct: float, credit: float, recourse: bool) -> dict:
    """Criminal-rate comparison, qualified by how the arrangement is likely characterized."""
    out = usury.check(apr_pct, credit)
    if recourse:
        out["characterization"] = "recourse: may be treated as credit secured by the receivable, so s.347 may apply"
    else:
        out["characterization"] = "non-recourse: normally a true sale of the receivable; s.347 generally not engaged"
        if out["exceeds_criminal_rate"]:
            out["flag"] = "APR above the criminal rate for comparison only; confirm true-sale terms with counsel"
    return out


def discount_fee_pct(days: float, fee_type: str, fee_pct: float = 0.0, period_days: int = 30,
                     tiers: list[dict] | None = None, prorate: bool = False) -> float:
    """Discount fee, percent of the fee basis, for an invoice outstanding ``days`` days.

    * ``flat``: ``fee_pct`` once, whatever the days.
    * ``per_period``: ``fee_pct`` for each ``period_days`` (each started period, or pro rata with ``prorate``).
    * ``tiered``: ``tiers`` = [{"up_to_days": 30, "fee_pct": 2.0}, {"up_to_days": 60, "fee_pct": 3.5}, ...] giving the
      cumulative fee by days outstanding; past the last tier ``fee_pct`` is added per ``period_days`` started.
    """
    if days < 0:
        raise ValueError("days must be >= 0")
    if fee_type == "flat":
        return fee_pct
    if fee_type == "per_period":
        periods = days / period_days if prorate else max(1, math.ceil(days / period_days - 1e-9))
        return fee_pct * periods
    if fee_type == "tiered":
        if not tiers:
            raise ValueError("tiered fees need tiers")
        ts = sorted(tiers, key=lambda t: t["up_to_days"])
        if any(b["fee_pct"] < a["fee_pct"] for a, b in zip(ts, ts[1:])):
            raise ValueError("tier fees must not fall as days increase")
        for t in ts:
            if days <= t["up_to_days"]:
                return float(t["fee_pct"])
        if not fee_pct:
            raise ValueError(f"invoice outstanding {days} days, past the last tier ({ts[-1]['up_to_days']} days); "
                             "give fee_pct for each extra period")
        extra = math.ceil((days - ts[-1]["up_to_days"]) / period_days - 1e-9)
        return float(ts[-1]["fee_pct"]) + fee_pct * extra
    raise ValueError("fee_type must be flat, per_period or tiered")


def factor_invoice(face: float, advance_rate_pct: float, days_to_collect: float, fee_type: str = "per_period",
                   fee_pct: float = 0.0, period_days: int = 30, tiers: list[dict] | None = None, prorate: bool = False,
                   fee_basis: str = "face", recourse: bool = True, recourse_days: int | None = 90,
                   non_recourse_premium_pct: float = 0.0, upfront_fees: float = 0.0) -> dict:
    """One invoice. Under recourse, if the customer has not paid by ``recourse_days`` the client repurchases the
    invoice then (repays the advance plus fees to that day). Non-recourse adds ``non_recourse_premium_pct`` of face
    and the factor bears the customer's non-payment."""
    if face <= 0 or not 0 < advance_rate_pct <= 100 or days_to_collect <= 0:
        raise ValueError("need face > 0, 0 < advance rate <= 100 and days to collect > 0")
    if fee_basis not in ("face", "advance"):
        raise ValueError("fee_basis must be face or advance")
    advance = face * advance_rate_pct / 100
    repurchased = recourse and recourse_days is not None and days_to_collect > recourse_days
    settle_day = float(recourse_days) if repurchased else float(days_to_collect)
    pct = discount_fee_pct(settle_day, fee_type, fee_pct, period_days, tiers, prorate)
    if not recourse:
        pct += non_recourse_premium_pct
    fee = (face if fee_basis == "face" else advance) * pct / 100
    if fee + advance > face and not repurchased:
        raise ValueError("fees exceed the reserve: the factor would claw back more than the invoice")
    net = advance - upfront_fees
    if net <= 0:
        raise ValueError("upfront fees exceed the advance")
    flows = [(0.0, net), (settle_day, -(advance + fee))]
    ear = cf.xirr(flows)
    total_cost = fee + upfront_fees
    out = {"face": face, "advance": round(advance, 2), "advance_rate_pct": advance_rate_pct,
           "reserve": round(face - advance, 2), "discount_fee_pct": round(pct, 4), "discount_fee": round(fee, 2),
           "upfront_fees": upfront_fees, "total_cost": round(total_cost, 2),
           "cost_pct_of_face": round(total_cost / face * 100, 4),
           "days_outstanding": settle_day, "recourse": recourse, "repurchased_under_recourse": repurchased,
           "reserve_release": None if repurchased else round(face - advance - fee, 2),
           "reserve_release_day": None if repurchased else settle_day,
           "repurchase_payment": round(advance + fee, 2) if repurchased else None,
           "ear_pct": round(ear * 100, 4), "apr_pct": round(cf.apr_from_ear(ear, cf.DAYS_PER_YEAR) * 100, 4),
           "flows": [{"day": d, "amount": round(a, 2)} for d, a in flows],
           "engine": "business.factoring.factor_invoice",
           "assumptions": assumptions("factoring_cost_basis", "factoring_characterization", "apr_method",
                                      *(() if prorate or fee_type != "per_period" else ("factoring_period_rounding",)))}
    out["criminal_rate"] = _rate_check(out["apr_pct"], net, recourse)
    return out


def factor_ledger(invoices: list[dict], advance_rate_pct: float, **terms) -> dict:
    """A batch of invoices on the same terms, each with ``face`` and ``days_to_collect``: blended effective cost
    from the combined dated flows (not an average of the per-invoice rates)."""
    if not invoices:
        raise ValueError("no invoices")
    results = [factor_invoice(float(i["face"]), advance_rate_pct, float(i["days_to_collect"]), **terms) for i in invoices]
    by_day: dict[float, float] = {}
    for r in results:
        for f in r["flows"]:
            by_day[f["day"]] = by_day.get(f["day"], 0.0) + f["amount"]
    flows = sorted(by_day.items())
    ear = cf.xirr(flows)
    face = sum(r["face"] for r in results)
    cost = sum(r["total_cost"] for r in results)
    net = sum(r["advance"] - r["upfront_fees"] for r in results)
    apr = cf.apr_from_ear(ear, cf.DAYS_PER_YEAR) * 100
    return {"invoices": len(results), "face_total": round(face, 2), "advance_total": round(sum(r["advance"] for r in results), 2),
            "total_cost": round(cost, 2), "cost_pct_of_face": round(cost / face * 100, 4),
            "repurchased": sum(r["repurchased_under_recourse"] for r in results),
            "weighted_days": round(sum(r["face"] * r["days_outstanding"] for r in results) / face, 2),
            "ear_pct": round(ear * 100, 4), "apr_pct": round(apr, 4),
            "per_invoice": [{k: r[k] for k in ("face", "days_outstanding", "discount_fee", "apr_pct",
                                               "repurchased_under_recourse")} for r in results],
            "criminal_rate": _rate_check(apr, net, results[0]["recourse"]),
            "engine": "business.factoring.factor_ledger", "assumptions": results[0]["assumptions"]}
