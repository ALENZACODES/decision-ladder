"""Business Lending Desk: CSBFP loans, invoice factoring, unsecured credit (term loan, line, merchant cash
advance) with the criminal-rate check, borrower DSCR capacity, and equipment lease versus buy.

Every calculator is deterministic and stdlib-only. Program and legal parameters live in :mod:`.params` with the
page they were checked on; modelling choices are listed there as assumptions and echoed in each result.
"""
from . import capacity, cashflow, csbfp, factoring, lease, params, unsecured, usury  # noqa: F401
