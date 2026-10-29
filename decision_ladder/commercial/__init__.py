"""Commercial Lending Desk: CMHC MLI Select / Standard, conventional underwriting, construction, bridge and rent rolls.

Deterministic, stdlib-only engines. Each result carries ``engine``, its ``sources`` (with the date they were
checked) and the ``assumptions`` that are not from a primary source. Tool wiring is in
:mod:`decision_ladder.modules.commercial`; the deal screener for an already-sized loan stays in the author's
Private Credit Deal Screener module.
"""
from . import bridge, cmhc, construction, rentroll, underwriting  # noqa: F401
