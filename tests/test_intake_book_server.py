import json
import threading
import urllib.error
import urllib.request

import pytest

from decision_ladder.book.scan import parse_book, scan
from decision_ladder.intake.extract import extract, model_extract, pattern_extract, reconcile
from decision_ladder.llm.client import NemotronClient
from decision_ladder.llm.offline import offline_client
from decision_ladder.samples import SAMPLE_BOOK_CSV, SAMPLE_EMAIL


# ------------------------------------------------------------------ intake
def test_pattern_extract_sample_email():
    f = {k: v["value"] for k, v in pattern_extract(SAMPLE_EMAIL).items()}
    assert f == {**f, "price": 1_100_000, "down_payment": 220_000, "annual_income": 185_000, "credit_score": 742,
                 "contract_rate": 4.19, "amort_years": 30, "property_tax_annual": 7_900, "other_debt_monthly": 850,
                 "province": "ON", "first_time_buyer": True, "purpose": "purchase", "borrower_name": "Priya Raman"}


def test_pattern_extract_renewal_text():
    t = "Our renewal offer from TD is 4.79% fixed. Balance of $388,000. We live in Alberta. Postal code T2P 1J9."
    f = {k: v["value"] for k, v in pattern_extract(t).items()}
    assert f["purpose"] == "renewal" and f["renewal_rate"] == 4.79 and f["balance"] == 388_000
    assert f["province"] == "AB" and f["postal_code"] == "T2P 1J9"


class OneShot:
    def __init__(self, content):
        self.content = content

    def __call__(self, path, payload, method="POST"):
        return {"choices": [{"message": {"content": self.content}}], "usage": {}}


def test_model_values_without_grounded_quotes_are_dropped():
    model = json.dumps({"fields": {
        "price": {"value": 1100000, "quote": "listed at $1.1M"},
        "annual_income": {"value": 250000, "quote": "we make 250k"},   # hallucinated quote
        "credit_score": {"value": "742", "quote": "credit score is 742"},
    }})
    out = model_extract(NemotronClient(OneShot(model)), SAMPLE_EMAIL)
    assert out["price"]["grounded"] and out["credit_score"]["value"] == 742
    assert not out["annual_income"]["grounded"]
    rec = reconcile(pattern_extract(SAMPLE_EMAIL), out)
    assert rec["file"]["annual_income"] == 185_000  # pattern value kept, model value dropped
    assert rec["dropped"][0]["field"] == "annual_income"


def test_conflicts_are_flagged_not_hidden():
    pat = {"price": {"value": 1_100_000, "quote": "a"}}
    mod = {"price": {"value": 1_000_000, "quote": "b", "grounded": True}}
    rec = reconcile(pat, mod)
    assert rec["conflicts"][0]["field"] == "price" and rec["fields"]["price"]["source"] == "model (conflict)"


def test_extract_with_offline_model_agrees_with_patterns():
    out = extract(SAMPLE_EMAIL, offline_client())
    assert not out["conflicts"] and not out["dropped"]
    assert all(v["source"] == "both" for v in out["fields"].values())


def test_unknown_fields_ignored():
    out = model_extract(NemotronClient(OneShot('{"fields": {"sin": {"value": "123", "quote": "x"}}}')), "x")
    assert out == {}


# ------------------------------------------------------------------ book
def test_book_scan_ranks_and_summarizes():
    out = scan(SAMPLE_BOOK_CSV, "2026-10-28")
    q = out["queue"]
    assert out["summary"]["loans"] == 6 and not out["errors"]
    assert [r["priority"] for r in q] == sorted((r["priority"] for r in q), reverse=True)
    assert q[0]["tier"] == "call this week" and q[-1]["borrower"] == "Raj Patel"
    assert all("why" in r for r in q)


def test_book_bad_rows_reported():
    rows, errors = parse_book("borrower,lender,balance,contract_rate,maturity\nA,TD,x,2,2027-01-01\nB,TD,1,2,13/01/2027\n")
    assert not rows and len(errors) == 2


def test_book_missing_columns():
    rows, errors = parse_book("name,balance\nA,1\n")
    assert not rows and "missing column" in errors[0]


def test_book_drafts_outreach_with_guardrail():
    out = scan(SAMPLE_BOOK_CSV, "2026-10-28", offline_client(), 2)
    drafted = [r for r in out["queue"] if "outreach" in r]
    assert len(drafted) == 2 and all(r["outreach"]["guardrail"]["allowed"] for r in drafted)


# ------------------------------------------------------------------ server
@pytest.fixture(scope="module")
def base_url():
    from http.server import ThreadingHTTPServer

    from decision_ladder.web.server import RateLimiter, Services, make_handler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Services(offline=True), RateLimiter(1000)))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.headers, r.read()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health_reports_offline(base_url):
    s, _, b = _get(base_url + "/api/health")
    h = json.loads(b)
    assert s == 200 and h["mode"] == "offline" and h["tools"] > 15


def test_samples_tools_market_history(base_url):
    for p in ("/api/samples", "/api/tools", "/api/market", "/api/history"):
        s, _, b = _get(base_url + p)
        assert s == 200 and json.loads(b)


def test_ladder_endpoint(base_url):
    _, samples = 0, json.loads(_get(base_url + "/api/samples")[2])
    s, out = _post(base_url + "/api/ladder", {"file": samples["files"]["oakville_stretch"], "research": True})
    assert s == 200 and out["verdict"] == "RESTRUCTURE" and len(out["rungs"]) == 11 and out["research"]


def test_intake_endpoint_runs_ladder(base_url):
    s, out = _post(base_url + "/api/intake", {"text": SAMPLE_EMAIL, "run": True})
    assert s == 200 and out["file"]["price"] == 1_100_000 and out["ladder"]["verdict"]


def test_ask_book_tool_endpoints(base_url):
    s, out = _post(base_url + "/api/ask", {"question": "What is the Bank of Canada policy rate?"})
    assert s == 200 and out["steps"]
    s, out = _post(base_url + "/api/book", {"csv": SAMPLE_BOOK_CSV, "as_of": "2026-10-28", "drafts": 1})
    assert s == 200 and out["summary"]["loans"] == 6
    s, out = _post(base_url + "/api/tool", {"name": "mortgage_payment", "args": {"principal": 1e5, "annual_rate": 5, "amort_years": 25}})
    assert s == 200 and out["monthly_payment"] > 0


def test_bad_requests(base_url):
    assert _post(base_url + "/api/ladder", {})[0] == 400
    assert _post(base_url + "/api/ask", {"question": ""})[0] == 400
    assert _post(base_url + "/api/nope", {})[0] == 404
    req = urllib.request.Request(base_url + "/api/ladder", data=b"[1,2]", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400


def test_static_path_traversal_blocked(base_url):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(base_url + "/static/../server.py")
    assert e.value.code == 404


def test_rate_limiter():
    from decision_ladder.web.server import RateLimiter
    rl = RateLimiter(2)
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a") and rl.allow("b")
