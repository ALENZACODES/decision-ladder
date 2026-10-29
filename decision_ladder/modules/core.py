"""Registers the OS core and MortgageLoanOps (the engines Decision Ladder is built on)."""
from .registry import AppModule, add_module

add_module(AppModule(
    key="mortgageloanops", name="MortgageLoanOps", stages=["underwriting", "servicing"], kind="data",
    description="B-20 qualification, insured rules, IRD quick estimate, home-value index, guardrailed borrower "
                "messaging on AWS. Its engines power the Decision Ladder rungs (decision_ladder/engines).",
    directory="mortgageloanops", repo="ALENZACODES/mortgageloanops",
    tools=["qualify_purchase", "insurance_premium", "penalty_quick", "lender_match", "message_guardrail", "identity_screening"]))
