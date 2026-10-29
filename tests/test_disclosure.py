"""Disclosure & Compliance Desk: hand-checked APR arithmetic, day-count edge cases and missing-item cases."""
from datetime import date

import pytest

import decision_ladder.modules.disclosure  # noqa: F401  (registers the tools)
from decision_ladder.agent import tools as T
from decision_ladder.disclosure import calendar as cal, conduct, fintrac, interest_act, renewal
from decision_ladder.disclosure import cost_of_borrowing as cob
from decision_ladder.disclosure.sources import CHECKED


# ---------------------------------------------------------------- APR (O. Reg. 191/08 s. 3-5)
def test_apr_hand_checked_three_payment_loan():
    # $1,000 at 12% compounded monthly (1% a month), amortized and termed over 3 months, $30 admin fee.
    # payment = 1000 * 0.01 / (1 - 1.01**-3) = 340.0221 -> 340.02
    # month 1: interest 10.00, principal 330.02, balance 669.98
    # month 2: interest 6.6998 -> 6.70, principal 333.32, balance 336.66
    # month 3: interest 3.3666 -> 3.37, final payment 340.03 clears the balance
    # C = 10.00 + 6.70 + 3.37 + 30 = 50.07 ; T = 3/12 = 0.25
    # P = (1000 + 669.98 + 336.66) / 3 = 668.88 (opening principal of each period, before the payment)
    # APR = 100 * 50.07 / (0.25 * 668.88) = 100 * 50.07 / 167.22 = 29.9426 %
    r = cob.cost_of_borrowing(1000, 12, 0.25, 3, "monthly", "monthly", [{"type": "admin", "amount": 30}])
    assert r["payment"] == 340.02
    assert [x["interest"] for x in r["schedule"]] == [10.00, 6.70, 3.37]
    assert r["schedule"][-1]["payment"] == 340.03 and r["balance_at_maturity"] == 0
    assert r["cost_of_borrowing"] == 50.07 and r["average_principal"] == 668.88
    assert r["apr_formula_pct"] == pytest.approx(100 * 50.07 / (0.25 * 668.88), abs=1e-4)
    assert r["apr_pct"] == pytest.approx(29.9426, abs=1e-4)          # monthly basis: no restatement
    assert r["apr_rounded_eighth_pct"] == 30.0                       # 29.94 -> nearest 1/8 is 30.000
    assert r["total_payments"] == 1020.07                             # 340.02 + 340.02 + 340.03


def test_interest_only_cost_apr_equals_rate_s4_1():
    # same loan, no fee: formula gives 100 * 20.07 / 167.22 = 12.0022 %, but s. 4(1) makes the APR the 12 % rate
    r = cob.cost_of_borrowing(1000, 12, 0.25, 3, "monthly", "monthly")
    assert r["apr_formula_pct"] == pytest.approx(12.0022, abs=1e-4)
    assert r["apr_pct"] == 12.0 and "s. 4(1)" in r["apr_basis"]


def test_semi_annual_mortgage_federal_formula_differs():
    # 5 % compounded half-yearly paid monthly: periodic rate (1.025)**(1/6) - 1 = 0.0041239
    # with interest the only cost, C/(T*P) = 12 * periodic = 4.9487 % (federal s. 47, no s. 4(1) equivalent)
    r = cob.cost_of_borrowing(300000, 5, 25, 60)
    assert r["payment"] == 1744.81
    assert r["apr_pct"] == 5.0
    assert r["federal_comparison"]["apr_pct"] == pytest.approx(12 * (1.025 ** (1 / 6) - 1) * 100, abs=2e-3)
    assert r["federal_comparison"]["materially_different"] is True
    assert r["federal_comparison"]["apr_rounded_eighth_pct"] == 5.0


def test_fees_restated_to_half_yearly_basis_and_exclusions_ignored():
    fee = [{"type": "brokerage_fee", "amount": 3000}]
    r = cob.cost_of_borrowing(300000, 5, 25, 60, charges=fee)
    assert r["cost_of_borrowing"] == round(r["interest_over_term"] + 3000, 2)
    assert r["apr_pct"] == pytest.approx(cob.restate(r["apr_formula_pct"], 12, 2), abs=1e-4)
    assert 5.0 < r["apr_formula_pct"] < r["apr_pct"]
    r2 = cob.cost_of_borrowing(300000, 5, 25, 60, charges=fee + [
        {"type": "registration", "amount": 80}, {"type": "default_insurance", "amount": 9000},
        {"type": "discharge", "amount": 300}])
    assert r2["apr_pct"] == r["apr_pct"] and r2["non_interest_charges"] == 3000
    assert {c["type"] for c in r2["excluded_charges"]} == {"registration", "default_insurance", "discharge"}
    with pytest.raises(ValueError):
        cob.cost_of_borrowing(1000, 5, 1, 12, charges=[{"type": "mystery", "amount": 1}])


def test_restate_round_trip_and_frequencies():
    assert cob.restate(cob.restate(6.0, 2, 12), 12, 2) == pytest.approx(6.0, abs=1e-12)
    r = cob.cost_of_borrowing(200000, 4, 25, 60, frequency="biweekly")
    assert r["payments_in_term"] == 130 and r["term_years"] == 5.0
    assert cob.cost_of_borrowing(200000, 4, 25, 60, frequency="weekly")["payments_in_term"] == 260


def test_trigger_rate():
    # $500/month on $100,000: interest-only at i = 0.005 a month -> 6.000 % compounded monthly
    assert cob.trigger_rate(100000, 500) == pytest.approx(6.0)


def test_disclosure_statement_items_missing_and_text():
    s = cob.disclosure_statement({"principal": 300000, "annual_rate": 5, "amort_years": 25, "term_months": 60,
                                  "advance_date": "2026-11-02", "first_payment_date": "2026-12-02",
                                  "charges": [{"type": "brokerage_fee", "amount": 3000}],
                                  "statement_date": "2026-10-28", "signing_date": "2026-10-29"})
    assert len([i for i in s["items"] if isinstance(i["item"], int)]) == 19
    assert any(m.startswith("16.") for m in s["missing"]) and any(m.startswith("13.") for m in s["missing"])
    sched = next(i for i in s["items"] if i["item"] == 9)["value"]
    assert sched["due_dates"][0] == "2026-12-02" and sched["due_dates"][-1] == "2031-11-02"
    assert s["timing"]["ok"] is False and s["timing"]["latest_compliant_date"] == "2026-10-27"
    assert "MISSING BEFORE DELIVERY" in s["text"] and "APR: 5.216%" in s["text"]
    assert s["engine"] == "disclosure.statement" and "Not legal advice" in s["note"]


def test_variable_rate_statement_adds_s9_items():
    s = cob.disclosure_statement({"principal": 100000, "annual_rate": 6, "amort_years": 25, "term_months": 36,
                                  "compounding": "monthly", "rate_type": "variable"})
    labels = {i["item"]: i for i in s["items"]}
    assert labels["9(1)3"]["status"] == "missing"
    assert labels["9(1)6"]["status"] == "provided"
    assert any("variable rate" in a for a in s["cost"]["assumptions"])


def test_month_end_due_dates():
    assert cob._due_dates("2027-01-31", "monthly", 3) == ["2027-01-31", "2027-02-28", "2027-03-31"]


# ---------------------------------------------------------------- calendars and day counts
def test_ontario_holidays():
    h26 = cal.ontario_holidays(2026)
    assert h26[date(2026, 4, 3)] == "Good Friday" and h26[date(2026, 4, 6)] == "Easter Monday"
    assert h26[date(2026, 2, 16)] == "Family Day"
    assert h26[date(2026, 5, 18)] == "Victoria Day"           # May 24, 2026 is a Sunday
    assert date(2026, 8, 3) not in h26                         # Civic Holiday is not a Legislation Act holiday
    assert cal.is_business_day("2026-08-03")
    assert date(2027, 12, 27) in cal.ontario_holidays(2027)    # Christmas 2027 on a Saturday
    assert date(2029, 7, 2) in cal.ontario_holidays(2029)      # Canada Day 2029 on a Sunday
    assert date(2022, 12, 27) in cal.ontario_holidays(2022)    # Christmas 2022 on a Sunday
    assert cal.easter(2024) == date(2024, 3, 31) and cal.easter(2025) == date(2025, 4, 20)


def test_two_business_days_over_christmas():
    # Thu Dec 24 -> Mon Dec 28 2026: Fri 25 holiday, Sat, Sun, Mon 28 counts -> 1 business day
    t = cob.delivery_timing("2026-12-24", signing_date="2026-12-28")
    assert t["business_days"] == 1 and t["ok"] is False
    assert t["latest_compliant_date"] == "2026-12-23"
    assert cob.delivery_timing("2026-12-24", "2026-12-28", waiver_date="2026-12-24")["ok"] is True
    assert cob.delivery_timing("2026-12-24", "2026-12-28", waiver_date="2026-12-28")["ok"] is False
    assert cob.delivery_timing("2026-10-26", "2026-10-28")["ok"] is True         # Monday -> Wednesday
    assert cob.delivery_timing("2026-10-28", "2026-10-28")["ok"] is False        # same day
    # earliest event governs: a payment on Tuesday comes before Thursday signing
    t = cob.delivery_timing("2026-10-26", signing_date="2026-10-29", payment_date="2026-10-27")
    assert t["earliest_event"] == "payment" and t["ok"] is False
    with pytest.raises(ValueError):
        cob.delivery_timing("2026-10-26")


def test_at_least_conventions_differ():
    # statement Nov 10, renewal Dec 1: 21 days apart
    on = cal.at_least_days_before("2026-11-10", "2026-12-01", 21, "ontario")
    fed = cal.at_least_days_before("2026-11-10", "2026-12-01", 21, "federal")
    assert on["ok"] is True and fed["ok"] is False and fed["short_by_days"] == 1
    assert fed["latest_compliant_date"] == "2026-11-09" and on["latest_compliant_date"] == "2026-11-10"
    assert cal.add_years("2024-02-29", 5) == date(2029, 2, 28)


# ---------------------------------------------------------------- renewal
def test_renewal_federal_late_extends_rights():
    r = renewal.check({"maturity_date": "2026-12-01", "statement_date": "2026-11-15", "received_date": "2026-11-20",
                       "includes_cost_information": True, "includes_no_increase_statement": True,
                       "includes_rights_statement": True})
    assert r["ok"] is False and r["timing"]["short_by_days"] == 6
    assert r["renewal_effective_no_earlier_than"] == "2026-12-11" and r["rights_extended"] is True
    assert r["citations"][0]["section"] == "s. 45" and r["citations"][0]["checked"] == CHECKED


def test_renewal_ontario_content_and_non_renewal():
    r = renewal.check({"maturity_date": "2026-12-01", "statement_date": "2026-11-10", "regime": "ontario_lender"})
    assert r["timing"]["ok"] is True and r["ok"] is False and len(r["missing_content"]) == 3
    assert renewal.check({"maturity_date": "2026-12-01", "regime": "ontario_lender",
                          "brokerage_is_lender": False})["applies"] is False
    n = renewal.check({"maturity_date": "2026-12-01", "regime": "ontario_lender", "will_not_renew": True,
                       "notice_date": "2026-11-12"})
    assert n["ok"] is False and n["timing"]["latest_compliant_date"] == "2026-11-10"
    rc = renewal.check({"maturity_date": "2026-12-01", "statement_date": "2026-11-01",
                        "renewal_terms": {"balance": 250000, "annual_rate": 4.5, "amort_years": 20, "term_months": 36}})
    assert rc["renewal_cost"]["apr_pct"] == 4.5


# ---------------------------------------------------------------- Interest Act
def test_interest_act_clean_individual_five_year():
    pmt = cob.cost_of_borrowing(300000, 5, 25, 60)["payment"]
    r = interest_act.check({"stated_rate_pct": 5, "stated_compounding": "half-yearly", "principal": 300000,
                            "payment": pmt, "amort_years": 25, "term_months": 60, "arrears_rate_pct": 5})
    assert r["clean"] is True
    assert r["computed"]["implied_rate_pct"] == pytest.approx(5.0, abs=0.001)
    assert next(p for p in r["provisions"] if p["section"] == "s. 10")["applies"] is False


def test_interest_act_red_flags():
    r = interest_act.check({"stated_rate_pct": 5, "stated_compounding": "monthly", "principal": 300000,
                            "payment": 1800, "amort_years": 25, "mortgage_date": "2020-02-29", "term_months": 84,
                            "balance_at_five_years": 250000, "penalty_after_five_years": 9000,
                            "prepayment_clause": "ird", "arrears_rate_pct": 7, "arrears_penalty": "$250 late fee"})
    sections = [f["section"] for f in r["red_flags"]]
    assert sections.count("s. 6") == 1 and "s. 7" in sections and sections.count("s. 8") == 2
    assert sections.count("s. 10") == 2
    # 5 % monthly -> half-yearly equivalent 2 * ((1 + .05/12)**6 - 1) = 5.0524 %
    assert r["computed"]["half_yearly_equivalent_pct"] == pytest.approx(5.0524, abs=1e-4)
    # three months' interest on 250,000 at 5 % monthly: 250000 * ((1 + .05/12)**3 - 1) = 3138.04
    assert r["computed"]["s10_max_charge"] == 3138.04
    assert r["computed"]["s10_open_from"] == "2025-02-28"
    assert any(c["section"] == "s. 9" for c in r["citations"])


def test_interest_act_corporate_and_missing_statement():
    r = interest_act.check({"borrower_type": "corporation", "term_months": 120, "rate_stated": False,
                            "in_advance": True})
    s10 = next(p for p in r["provisions"] if p["section"] == "s. 10")
    assert s10["applies"] is False and "10(2)(a)" in s10["why"]
    assert {f["issue"] for f in r["red_flags"]} >= {"no annual rate stated", "rate is stated as calculated in advance"}


# ---------------------------------------------------------------- conduct checklist
ON_FILE = {"suitability_documented": True, "recommendation_rationale": True, "client_ack_options": True,
           "kyc": {k: True for k in conduct.KYC_FIELDS}, "material_risks_disclosed": True,
           "material_risks_acknowledged": True, "role_disclosed": True, "lenders_count_disclosed": True,
           "fees_disclosed": True, "identity_verified": True, "cost_of_borrowing_disclosed": True,
           "principal": 500000, "disclosure_date": "2026-10-26", "signing_date": "2026-10-28"}


def test_conduct_ontario_complete_file():
    r = conduct.evaluate(ON_FILE, "ON")
    assert r["complete"] is True, r["missing"]
    assert next(x for x in r["results"] if x["id"] == "ON-ADV")["status"] == "n/a"   # over $400,000


def test_conduct_ontario_missing_items():
    f = {**ON_FILE, "principal": 350000, "conflicts": ["lender pays a volume bonus"], "lender_type": "private",
         "conflicts_disclosed_in_writing": True, "kyc": {"income": True}, "signing_date": "2026-10-27"}
    r = conduct.evaluate(f, "ON")
    ids = {m["id"]: m["missing"] for m in r["missing"]}
    assert ids["ON-COI"] == ["conflicts_acknowledged"]
    assert ids["ON-ADV"] == ["no_advance_fee"]
    assert "kyc.employment" in ids["ON-KYC"] and "kyc.income" not in ids["ON-KYC"]
    assert "ON-TIME" in ids
    # s. 27(3): no conflict disclosure duty where the lender is another brokerage
    r2 = conduct.evaluate({**f, "lender_type": "brokerage"}, "ON")
    assert next(x for x in r2["results"] if x["id"] == "ON-COI")["status"] == "n/a"


def test_conduct_alberta_fee_timing():
    base = {"compensation_disclosed": True, "service_agreement_signed": True, "service_agreement_copy_delivered": True,
            "relationship_disclosure_delivered": True, "verification_steps_disclosed": True,
            "verification_docs_on_file": True, "disclosure_before_commitment": True, "borrower_fee_charged": True,
            "funding_confirmation_accepted": True, "initial_disclosure_date": "2026-11-02", "fee_date": "2026-11-03"}
    r = conduct.evaluate(base, "AB")
    assert [m["id"] for m in r["missing"]] == ["AB-FEE"]
    assert conduct.evaluate({**base, "fee_date": "2026-11-04"}, "AB")["complete"] is True
    assert conduct.evaluate({**base, "funding_confirmation_accepted": False, "fee_date": "2026-11-04"},
                            "AB")["complete"] is False
    with pytest.raises(ValueError):
        conduct.evaluate({}, "BC")


# ---------------------------------------------------------------- FINTRAC
PERSON = {"name": "Jane Borrower", "method": "dual_process", "verified_date": "2026-10-20",
          "dual_process": {"sources": [{"name": "Equifax", "info": "name_address", "reference": "EQ1"},
                                       {"name": "Utility Co", "info": "name_dob", "reference": "U9"}]},
          "address": "1 Main St", "dob": "1985-01-01", "occupation": "nurse", "third_party_determined": True,
          "pep_hio_determined": True}


def test_fintrac_complete_person_and_retention():
    r = fintrac.check({"clients": [PERSON], "record_date": "2024-02-29"})
    assert r["complete"] is True and r["retain_until"] == "2029-02-28"


def test_fintrac_identity_method_gaps():
    expired = {**PERSON, "method": "photo_id", "photo_id": {"doc_type": "DL", "doc_number": "X", "jurisdiction": "ON",
                                                            "country": "CA", "expiry_date": "2026-01-01",
                                                            "authenticated": True, "photo_matched": True}}
    assert any("expired" in m for m in fintrac.check({"clients": [expired]})["missing"])
    thin = {**PERSON, "method": "credit_file", "credit_file": {"bureau": "TransUnion", "reference_number": "T1",
                                                               "history_years": 2, "searched_at_verification": True}}
    assert any("at least 3" in m for m in fintrac.check({"clients": [thin]})["missing"])
    same_kind = {**PERSON, "dual_process": {"sources": [{"name": "A", "info": "name_address", "reference": "1"},
                                                        {"name": "B", "info": "name_address", "reference": "2"}]}}
    assert any("two different kinds" in m for m in fintrac.check({"clients": [same_kind]})["missing"])


def test_fintrac_entity_pep_and_cash_24_hour_rule():
    ent = {"name": "Holdco Inc", "type": "entity", "method": "registry", "verified_date": "2026-10-01",
           "address": "2 Bay St", "nature_of_business": "real estate", "third_party_determined": True,
           "pep_hio_determined": True, "pep_hio": True, "high_risk_date": "2026-09-01",
           "source_of_wealth_date": "2026-10-15"}
    r = fintrac.check({"clients": [ent]})
    assert any("beneficial_owners" in m for m in r["missing"])
    assert any("due by 2026-10-01" in m for m in r["missing"])
    tx = [{"datetime": "2026-10-01T10:00", "amount": 6000, "cash": True, "payer": "Jane", "receipt_of_funds_record": True,
           "payer_verified": True},
          {"datetime": "2026-10-02T09:00", "amount": 5000, "cash": True, "payer": "Jane", "receipt_of_funds_record": True,
           "payer_verified": True},
          {"datetime": "2026-10-05T09:00", "amount": 50000, "cash": True, "from_financial_entity": True,
           "payer": "Bank", "receipt_of_funds_record": True, "payer_verified": True}]
    t = fintrac.check({"clients": [PERSON], "transactions": tx})["transactions"]
    assert t[0]["ok"] is True                                       # $6,000 alone is under $10,000
    assert any("large cash report (11,000.00" in m for m in t[1]["missing"])
    assert t[2]["ok"] is True                                       # from a financial entity: exempt


def test_fintrac_program_review_age():
    p = {"compliance_officer": "A", "policies": True, "risk_assessment": True, "training": True,
         "effectiveness_review_date": "2024-06-01"}
    assert fintrac.check({"clients": [PERSON], "program": p, "as_of": "2026-10-29"})["program"]["ok"] is False
    p["effectiveness_review_date"] = "2025-06-01"
    assert fintrac.check({"clients": [PERSON], "program": p, "as_of": "2026-10-29"})["program"]["ok"] is True


# ---------------------------------------------------------------- tool wiring
def test_tools_registered_and_enveloped():
    names = ["disclosure_cost_of_borrowing", "disclosure_statement", "disclosure_delivery_timing", "interest_act_check",
             "conduct_checklist", "disclosure_rules", "fintrac_check", "renewal_disclosure_timing"]
    assert all(n in T.TOOLS for n in names)
    r = T.run("disclosure_cost_of_borrowing", {"principal": 1000, "annual_rate": 12, "amort_years": 0.25,
                                               "term_months": 3, "compounding": "monthly"})
    assert "schedule" not in r and r["engine"] == "disclosure.cost_of_borrowing"
    assert all(c["url"].startswith("https://") and c["checked"] == CHECKED for c in r["citations"])
    assert "error" in T.run("interest_act_check", {"stated_compounding": "fortnightly", "stated_rate_pct": 5})
    assert T.run("disclosure_rules", {"jurisdiction": "AB"})["rules"][0]["jurisdiction"] == "AB"
    assert T.run("conduct_checklist", {"file": {}, "jurisdiction": "ON"})["complete"] is False


def test_tools_routed_to_stages():
    from decision_ladder.agent.router import stage_tools
    st = stage_tools()
    assert "renewal_disclosure_timing" in st["servicing"] and "fintrac_check" in st["compliance"]
