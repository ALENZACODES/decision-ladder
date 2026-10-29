import json

import pytest

from decision_ladder.intake.documents import classify, read, read_document
from decision_ladder.ladder.runner import climb
from decision_ladder.llm.client import NemotronClient
from decision_ladder.llm.offline import offline_client
from decision_ladder.samples import SAMPLES
from decision_ladder.samples_docs import EMPLOYMENT_LETTER, PAY_STUB, RENEWAL_LETTER, SAMPLE_DOCS, T4_SLIP


@pytest.mark.parametrize("key", sorted(SAMPLE_DOCS))
def test_classifier_on_samples(key):
    kind, conf = classify(SAMPLE_DOCS[key])
    assert kind == key and conf >= 0.66


def test_unknown_document():
    assert classify("Grocery list: eggs, milk")[0] == "unknown"


def test_pay_stub_annualized_by_frequency():
    r = read(PAY_STUB)
    assert r["extracted"]["annual_income"] == 4125 * 24 and r["extracted"]["pay_frequency"] == "semi-monthly"
    assert r["quotes"]["annual_income"] in PAY_STUB and r["notes"]


def test_t4_and_letter():
    assert read(T4_SLIP)["extracted"]["annual_income"] == 97450
    e = read(EMPLOYMENT_LETTER)["extracted"]
    assert e["annual_income"] == 168000 and e["employment_start"] == "2019-03-03" and e["permanent"] is True


def test_renewal_letter_figures():
    e = read(RENEWAL_LETTER)["extracted"]
    assert e == {**e, "balance": 504200, "contract_rate": 1.99, "maturity": "2026-12-15", "renewal_rate": 4.84, "lender": "RBC"}
    assert e["renewal_offers"] == [5.04, 4.84, 4.95]


def test_letter_flags_probation():
    r = read(EMPLOYMENT_LETTER.replace("permanent, full-time", "full-time, on probation until January,"))
    assert any("probation" in n for n in r["notes"])


class OneShot:
    def __init__(self, obj):
        self.obj = obj

    def __call__(self, path, payload, method="POST"):
        return {"choices": [{"message": {"content": json.dumps(self.obj)}}], "usage": {}}


def test_model_read_grounding_conflicts_and_additions():
    model = {"type": "renewal_letter", "fields": {
        "balance": {"value": 504200, "quote": "Outstanding balance at maturity: $504,200.00"},
        "contract_rate": {"value": 2.99, "quote": "Your current interest rate: 1.99%"},
        "annual_income": {"value": 250000, "quote": "income of 250k"},
    }}
    out = read_document(RENEWAL_LETTER, NemotronClient(OneShot(model)))
    m = out["model"]
    assert "balance" in m["agree"] and m["conflicts"][0]["field"] == "contract_rate" and m["dropped"] == ["annual_income"]
    assert out["extracted"]["contract_rate"] == 1.99  # reader value kept; conflict surfaced, not resolved silently


def test_offline_document_read_agrees():
    out = read_document(PAY_STUB, offline_client())
    assert not out["model"]["conflicts"] and out["model"]["agree"]


def _file(**kw):
    f = {k: v for k, v in SAMPLES["oakville_stretch"].items() if k != "label"}
    f.update(kw)
    return f


def _docs_rung(f):
    return next(r for r in climb(f)[0] if r["key"] == "documents")


def test_documents_rung_partial_income_refers():
    r = _docs_rung(_file(documents=[read(PAY_STUB), read(T4_SLIP)]))
    assert r["status"] == "REFER" and r["metrics"]["documented_income"] == 99000
    assert "covers" in r["findings"][0]


def test_documents_rung_two_borrowers_summed():
    d1 = read(PAY_STUB) | {"borrower": "Priya"}
    d2 = {"type": "employment_letter", "extracted": {"annual_income": 90000}, "borrower": "Arjun"}
    r = _docs_rung(_file(documents=[d1, d2]))
    assert r["status"] == "PASS" and r["metrics"]["documented_income"] == 189000


def test_documents_rung_renewal_letter_reconciles_balance_and_rate():
    f = {k: v for k, v in SAMPLES["pandemic_renewal_rbc"].items() if k != "label"}
    f["documents"] = [read(RENEWAL_LETTER)]
    r = _docs_rung(f)
    assert r["status"] == "PASS" and r["metrics"]["reconciled"] >= 4
    f["documents"] = [read(RENEWAL_LETTER.replace("504,200.00", "514,200.00"))]
    assert _docs_rung(f)["status"] == "REFER"
