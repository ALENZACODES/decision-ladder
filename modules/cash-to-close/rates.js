/* Every rule the planner uses lives here, with its source and the date it was checked.
   Change a number here and the whole page follows. */
const RATES = {
  checked: "2026-10-18",
  minDown: {
    // 5% of the first $500,000, 10% of the part from $500,000 to $1,500,000, 20% at $1.5M or more
    firstTier: 500000, firstPct: 0.05, secondPct: 0.10, insuredCap: 1500000, uninsuredPct: 0.20,
    source: "https://www.canada.ca/en/financial-consumer-agency/services/mortgages/down-payment.html"
  },
  cmhc: {
    // premium on the loan amount, by loan-to-value; 30-year amortization adds 0.20 points
    tiers: [ { maxLtv: 0.85, pct: 0.028 }, { maxLtv: 0.90, pct: 0.031 }, { maxLtv: 0.95, pct: 0.040 } ],
    surcharge30: 0.002,
    source: "https://www.cmhc-schl.gc.ca/professionals/project-funding-and-mortgage-financing/mortgage-loan-insurance/mortgage-loan-insurance-homeownership-programs/home-start"
  },
  ontarioPstOnPremium: {
    pct: 0.08,
    source: "https://www.canada.ca/en/financial-consumer-agency/services/mortgages/down-payment.html#toc2"
  },
  ontarioLtt: {
    // single-family homes (1 or 2 units)
    brackets: [ [55000, 0.005], [250000, 0.01], [400000, 0.015], [2000000, 0.02], [Infinity, 0.025] ],
    firstTimeRefundMax: 4000,
    source: "https://www.ontario.ca/document/land-transfer-tax/calculating-land-transfer-tax"
  },
  torontoMltt: {
    // single-family homes; rates above $3M took effect April 1, 2026
    brackets: [ [55000, 0.005], [250000, 0.01], [400000, 0.015], [2000000, 0.02], [3000000, 0.025],
                [4000000, 0.044], [5000000, 0.0545], [10000000, 0.065], [20000000, 0.0755], [Infinity, 0.086] ],
    firstTimeRebateMax: 4475,
    source: "https://www.toronto.ca/services-payments/property-taxes-utilities/municipal-land-transfer-tax-mltt/municipal-land-transfer-tax-mltt-rates-and-fees/"
  },
  // Typical amounts, not rules. Shown as "approx." and editable.
  typical: {
    depositPct: 0.05,      // common in the GTA, set in the offer
    inspection: 500,
    legal: 2000,           // fees plus disbursements and HST, varies by firm
    titleInsurance: 400,
    adjustments: 1000,     // property tax or condo fees the seller prepaid
    moving: 1500
  }
};
if (typeof module !== "undefined") module.exports = RATES;
