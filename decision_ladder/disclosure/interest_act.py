"""Interest Act (R.S.C. 1985, c. I-15) checks on mortgage terms.

* s. 6  blended-payment mortgages: no interest is chargeable unless the mortgage states the principal and the
        rate "calculated yearly or half-yearly, not in advance".
* s. 7  if the s. 6 statement shows a lower rate than the other terms produce, the stated rate is the maximum.
        Checked here by solving the rate the payment actually implies and comparing it to the stated rate.
* s. 8  no fine, penalty or rate on arrears that makes the charge on arrears exceed the rate on principal not
        in arrears.
* s. 10 a mortgage not payable until more than five years after its date may, after five years, be paid off with
        three months' further interest in lieu of notice; s. 10(2) excludes mortgages given by a joint stock
        company or other corporation (and prescribed ones).
"""
from __future__ import annotations

from .calendar import _d, add_years
from .cost_of_borrowing import FREQ, periodic_rate, restate
from .sources import cite, envelope

COMP = {"monthly": 12, "half-yearly": 2, "semi": 2, "yearly": 1}


def _periodic(rate_pct: float, compounding: str, ppy: int) -> float:
    if compounding == "yearly":
        return (1 + rate_pct / 100) ** (1 / ppy) - 1
    return periodic_rate(rate_pct, "semi" if compounding in ("semi", "half-yearly") else "monthly", ppy)


def implied_rate(principal: float, payment: float, amort_years: float, frequency: str = "monthly",
                 compounding: str = "half-yearly") -> float:
    """Annual rate on the given compounding basis that makes ``payment`` amortize ``principal`` exactly."""
    ppy = FREQ[frequency]
    n = round(amort_years * ppy)
    if payment * n <= principal:
        return 0.0

    def pv(rate):
        i = _periodic(rate, compounding, ppy)
        return payment * n if i == 0 else payment * (1 - (1 + i) ** -n) / i

    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if pv(mid) > principal:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def three_months_interest(balance: float, rate_pct: float, compounding: str = "half-yearly") -> float:
    return round(balance * ((1 + _periodic(rate_pct, compounding, 12)) ** 3 - 1), 2)


def check(a: dict) -> dict:
    """Return the Interest Act provisions that apply to the described mortgage and any red flags."""
    provisions, flags, computed = [], [], {}
    rate = a.get("stated_rate_pct")
    comp = (a.get("stated_compounding") or "").lower()
    blended = a.get("blended_payments", True)

    # s. 6 / s. 7
    if blended:
        provisions.append({"section": "s. 6", "applies": True,
                           "why": "repayable by blended payments of principal and interest"})
        if not a.get("principal_stated", True):
            flags.append({"section": "s. 6", "issue": "principal not stated in the mortgage",
                          "consequence": "no interest chargeable until the s. 6 statement is made"})
        if rate is None or not a.get("rate_stated", True):
            flags.append({"section": "s. 6", "issue": "no annual rate stated",
                          "consequence": "no interest chargeable until the s. 6 statement is made"})
        if a.get("in_advance") or comp == "in advance":
            flags.append({"section": "s. 6", "issue": "rate is stated as calculated in advance",
                          "consequence": "s. 6 requires a rate calculated yearly or half-yearly, not in advance"})
        if rate is not None and comp and comp not in ("yearly", "half-yearly", "semi", "in advance"):
            if comp in COMP:
                eq = restate(rate, COMP[comp], 2)
                computed["half_yearly_equivalent_pct"] = round(eq, 4)
                computed["yearly_equivalent_pct"] = round(restate(rate, COMP[comp], 1), 4)
                if not a.get("equivalent_rate_stated"):
                    flags.append({"section": "s. 6", "issue": f"rate stated only as compounded {comp}",
                                  "consequence": f"state the equivalent rate calculated half-yearly, not in advance "
                                                 f"({eq:.4f}%) or yearly ({computed['yearly_equivalent_pct']:.4f}%)"})
            else:
                raise ValueError("stated_compounding must be yearly, half-yearly, monthly or 'in advance'")
        if rate is not None and a.get("payment") and a.get("principal") and a.get("amort_years"):
            basis = "half-yearly" if comp in ("", "in advance") else comp
            imp = implied_rate(float(a["principal"]), float(a["payment"]), float(a["amort_years"]),
                               a.get("frequency", "monthly"), basis)
            computed["implied_rate_pct"] = round(imp, 4)
            provisions.append({"section": "s. 7", "applies": True,
                               "why": "the stated rate caps the rate the other terms produce"})
            if imp > rate + 0.005:
                flags.append({"section": "s. 7", "issue": f"payment implies {imp:.4f}% ({basis}) but the stated rate "
                                                         f"is {rate}%",
                              "consequence": "the lender can charge no more than the stated rate on the principal"})
    else:
        provisions.append({"section": "s. 6", "applies": False, "why": "not a blended-payment or sinking-fund plan"})

    # s. 8
    arrears_rate = a.get("arrears_rate_pct")
    provisions.append({"section": "s. 8", "applies": True, "why": "applies to arrears on any mortgage on real property"})
    if arrears_rate is not None and rate is not None and arrears_rate > rate:
        flags.append({"section": "s. 8", "issue": f"arrears rate {arrears_rate}% exceeds the {rate}% rate on "
                                                  "principal not in arrears",
                      "consequence": "the excess is not chargeable and is recoverable (s. 9)"})
    if a.get("arrears_penalty"):
        flags.append({"section": "s. 8", "issue": f"fine or penalty on arrears: {a['arrears_penalty']}",
                      "consequence": "prohibited where it raises the charge on arrears above the regular rate; review "
                                     "whether it is a genuine cost-recovery fee"})

    # s. 10
    term_months = a.get("term_months")
    if a.get("mortgage_date") and a.get("maturity_date"):
        md, mat = _d(a["mortgage_date"]), _d(a["maturity_date"])
        over_five = mat > add_years(md, 5)
    else:
        md = _d(a["mortgage_date"]) if a.get("mortgage_date") else None
        over_five = term_months is not None and int(term_months) > 60
    corporate = a.get("borrower_type", "individual") in ("corporation", "company", "joint stock company")
    if over_five and not corporate:
        computed["s10_open_from"] = add_years(md, 5).isoformat() if md else "five years after the mortgage date"
        provisions.append({"section": "s. 10", "applies": True,
                           "why": "principal not payable until more than five years after the mortgage date"})
        if a.get("balance_at_five_years") and rate is not None:
            cap = three_months_interest(float(a["balance_at_five_years"]), rate,
                                        "half-yearly" if comp in ("", "in advance") else comp)
            computed["s10_max_charge"] = cap
            pen = a.get("penalty_after_five_years")
            if pen is not None and float(pen) > cap + 0.005:
                flags.append({"section": "s. 10", "issue": f"penalty after year five ${float(pen):,.2f} exceeds three "
                                                           f"months' interest ${cap:,.2f}",
                              "consequence": "after five years the borrower may repay with three months' interest"})
        if a.get("prepayment_clause") in ("closed", "ird", "greater_of_3m_ird"):
            flags.append({"section": "s. 10", "issue": f"prepayment clause '{a['prepayment_clause']}' applies after "
                                                       "year five",
                          "consequence": "cannot override the s. 10 right to repay with three months' interest"})
    elif over_five and corporate:
        provisions.append({"section": "s. 10", "applies": False, "why": "s. 10(2)(a): mortgage given by a corporation"})
    else:
        provisions.append({"section": "s. 10", "applies": False, "why": "payable within five years of its date"})
    if over_five and a.get("renewal_or_extension"):
        flags.append({"section": "s. 10", "issue": "term was set by a renewal or extension agreement",
                      "consequence": "s. 10 counts five years from 'the date of the mortgage'; whether a renewal date "
                                     "restarts the clock is a legal question for counsel"})

    out = {"provisions": provisions, "red_flags": flags, "computed": computed, "clean": not flags}
    secs = sorted({p["section"] for p in provisions} | {f["section"] for f in flags} | ({"s. 9"} if flags else set()))
    return envelope(out, "disclosure.interest_act", [cite("INTEREST_ACT", s) for s in secs])
