"""Cash-flow maths shared by the Business Lending Desk.

* :func:`irr` / :func:`xirr` solve for the rate that sets net present value to zero with a bracketed solver
  (Brent's method). A bracket is searched for first; if the cash flows never change sign there is no rate and
  a :class:`ValueError` is raised rather than returning something plausible-looking.
* ``npv``/``xnpv`` are the matching discount functions, so callers (and tests) can confirm a solved rate by
  discounting the flows back to about zero.
* Rate conversions between a per-period rate, the nominal annual rate (APR, compounded at the period
  frequency) and the effective annual rate (EAR).
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

DAYS_PER_YEAR = 365.0


def npv(rate: float, flows: Sequence[float]) -> float:
    """NPV of flows at periods 0, 1, 2, ... at a per-period rate."""
    if rate <= -1:
        raise ValueError("rate must be > -100%")
    v = 1.0 / (1.0 + rate)
    return sum(cf * v ** t for t, cf in enumerate(flows))


def xnpv(annual_rate: float, dated: Sequence[tuple[float, float]]) -> float:
    """NPV of (day, amount) flows at an effective annual rate, day 0 = today, 365-day year."""
    if annual_rate <= -1:
        raise ValueError("rate must be > -100%")
    lr = math.log1p(annual_rate)
    return sum(cf * math.exp(-lr * d / DAYS_PER_YEAR) for d, cf in dated)


def sign_changes(flows: Iterable[float]) -> int:
    """Number of sign changes (Descartes): more than one means the IRR may not be unique."""
    signs = [1 if f > 0 else -1 for f in flows if f != 0]
    return sum(1 for a, b in zip(signs, signs[1:]) if a != b)


def _bracket(f: Callable[[float], float], lo: float = -0.99, hi: float = 0.10, limit: float = 1e40) -> tuple[float, float]:
    """Find [a, b] with f(a), f(b) of opposite sign, scanning upward from ``lo`` and widening ``hi``.

    The scan walks a grid between ``lo`` and ``hi`` first (so the root nearest zero is preferred when there are
    several), then doubles ``hi`` until ``limit``.
    """
    grid = [lo + (hi - lo) * k / 40 for k in range(41)]
    while grid[-1] < limit:
        grid.append(grid[-1] * 2 + 1)
    prev_x = prev_f = None
    for x in grid:
        try:
            fx = f(x)
        except OverflowError:      # deep negative rates on long flow series: skip, keep scanning
            continue
        if prev_f is None:
            prev_x, prev_f = x, fx
            continue
        if prev_f == 0:
            return prev_x, prev_x
        if (prev_f < 0) != (fx < 0):
            return prev_x, x
        prev_x, prev_f = x, fx
    raise ValueError("no rate makes NPV zero (cash flows never change sign of NPV)")


def brent(f: Callable[[float], float], a: float, b: float, tol: float = 1e-12, max_iter: int = 200) -> float:
    """Brent's root finder on a sign-changing bracket [a, b]."""
    fa, fb = f(a), f(b)
    if fa == 0:
        return a
    if fb == 0:
        return b
    if (fa < 0) == (fb < 0):
        raise ValueError("bracket does not straddle a root")
    if abs(fa) < abs(fb):
        a, b, fa, fb = b, a, fb, fa
    c, fc, mflag, d = a, fa, True, 0.0
    for _ in range(max_iter):
        if fa != fc and fb != fc:      # inverse quadratic interpolation
            s = (a * fb * fc / ((fa - fb) * (fa - fc)) + b * fa * fc / ((fb - fa) * (fb - fc))
                 + c * fa * fb / ((fc - fa) * (fc - fb)))
        else:                          # secant
            s = b - fb * (b - a) / (fb - fa)
        lo, hi = sorted(((3 * a + b) / 4, b))
        if (not lo < s < hi or (mflag and abs(s - b) >= abs(b - c) / 2)
                or (not mflag and abs(s - b) >= abs(c - d) / 2)
                or (mflag and abs(b - c) < tol) or (not mflag and abs(c - d) < tol)):
            s, mflag = (a + b) / 2, True   # bisection
        else:
            mflag = False
        fs = f(s)
        d, c, fc = c, b, fb
        if (fa < 0) != (fs < 0):
            b, fb = s, fs
        else:
            a, fa = s, fs
        if abs(fa) < abs(fb):
            a, b, fa, fb = b, a, fb, fa
        if fb == 0 or abs(b - a) < tol:
            return b
    return b


def irr(flows: Sequence[float]) -> float:
    """Per-period internal rate of return of flows at periods 0, 1, 2, ..."""
    if sign_changes(flows) == 0:
        raise ValueError("IRR needs at least one inflow and one outflow")
    a, b = _bracket(lambda r: npv(r, flows))
    return a if a == b else brent(lambda r: npv(r, flows), a, b)


def xirr(dated: Sequence[tuple[float, float]]) -> float:
    """Effective annual rate for (day, amount) flows (365-day year)."""
    if sign_changes(cf for _, cf in sorted(dated)) == 0:
        raise ValueError("IRR needs at least one inflow and one outflow")
    a, b = _bracket(lambda r: xnpv(r, dated))
    return a if a == b else brent(lambda r: xnpv(r, dated), a, b)


def ear_from_periodic(r: float, periods_per_year: float) -> float:
    return (1 + r) ** periods_per_year - 1


def apr_from_periodic(r: float, periods_per_year: float) -> float:
    return r * periods_per_year


def periodic_from_ear(ear: float, periods_per_year: float) -> float:
    return (1 + ear) ** (1 / periods_per_year) - 1


def apr_from_ear(ear: float, periods_per_year: float) -> float:
    """Nominal annual rate, compounded ``periods_per_year`` times, equivalent to an effective annual rate."""
    return periodic_from_ear(ear, periods_per_year) * periods_per_year


def annuity_payment(principal: float, periodic_rate: float, n: int, due: bool = False) -> float:
    """Level payment amortizing ``principal`` over ``n`` periods (in arrears, or in advance when ``due``)."""
    if n <= 0:
        raise ValueError("number of payments must be positive")
    if periodic_rate == 0:
        return principal / n
    pmt = principal * periodic_rate / (1 - (1 + periodic_rate) ** -n)
    return pmt / (1 + periodic_rate) if due else pmt


def annuity_pv(payment: float, periodic_rate: float, n: int, due: bool = False) -> float:
    """Present value of ``n`` level payments (inverse of :func:`annuity_payment`)."""
    if n <= 0:
        return 0.0
    if periodic_rate == 0:
        return payment * n
    pv = payment * (1 - (1 + periodic_rate) ** -n) / periodic_rate
    return pv * (1 + periodic_rate) if due else pv


def rate_summary(periodic: float, periods_per_year: float) -> dict:
    """Per-period rate expressed as APR (nominal) and EAR, both in percent."""
    return {"periodic_rate_pct": round(periodic * 100, 6),
            "apr_pct": round(apr_from_periodic(periodic, periods_per_year) * 100, 4),
            "ear_pct": round(ear_from_periodic(periodic, periods_per_year) * 100, 4),
            "periods_per_year": periods_per_year}
