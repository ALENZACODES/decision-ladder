# Yorkville condo post: captions

## Instagram

Odds that a $1.88M Yorkville condo with 25% down goes underwater within 5 years? 🏙️📉

About 17%.

Funny thing: this was MY scenario. Bought Aug 2021, and now it's Aug 2026: exactly 5 years. Quant math can be used in even a small thing as investing in your own home.

Here's the setup. You put down $470K and borrow $1.41M. If the condo's value moves like a stock (geometric Brownian motion, 3% drift, 12% volatility), you're in negative equity the first time it touches $1.41M. Then it's a first-passage problem for Brownian motion with drift.

So that's roughly 1 in 6. Putting 25% down feels safe, but it doesn't make you bulletproof. Most people buy on vibes, not volatility.

Why do the math?
➡️ "20–25% down is safe" is a feeling. 17% is a number.
➡️ Volatility counts as much as the expected return.
➡️ Toronto condos have already done this to buyers from 2022.

Swap in your own price, down payment and volatility. The formula is on the slide. 👆

Save this for your next open house 🔖

#Toronto #Yorkville #TorontoRealEstate #CNTower #QuantFinance #Probability #StochasticCalculus #BrownianMotion #RealEstateMath #FinancialLiteracy #CanadaHousing #MathIsBeautiful

---

## LinkedIn

**What are the odds a $1.88M Yorkville condo goes underwater within 5 years?**

Quant math can be used in even a small thing as investing. Funny thing: this was my scenario: bought in August 2021, and August 2026 marks exactly 5 years. So I ran the numbers the way a quant would. The answer is about **17%**.

**The setup**
• Purchase price: $1,880,000 (Yorkville, Toronto)
• 25% down, which is $470,000
• $1,410,000 interest-only mortgage
• Value follows geometric Brownian motion with μ = 3% and σ = 12%

Negative equity is a first-passage problem. Let X = ln(P/P₀), which is Brownian motion with drift m = μ − σ²/2. Then find the probability that X hits ln(0.75) within 5 years:

P(τ ≤ T) = Φ((b − mT)/σ√T) + e^(2mb/σ²) · Φ((b + mT)/σ√T) ≈ 0.171

**Why this matters**
1. **Down payment is a buffer, not a guarantee.** At 25% down there's still roughly a 1-in-6 chance of being underwater.
2. **Volatility is the hidden variable.** Push σ from 12% to 18% and the probability rises sharply. Pre-construction condos and luxury units tend to be more volatile than the average home.
3. **Timing risk is real.** Being underwater only hurts if you have to sell or refinance then, and renewals arrive every 5 years in Canada.
4. **The model is simple on purpose.** It ignores closing costs, realtor fees and fat tails, and every one of those makes the real number worse.

Buyers spend weeks comparing finishes and minutes on downside risk. A five-line calculation flips that.

What volatility would you assume for downtown Toronto condos right now? 👇

#RealEstate #QuantitativeFinance #Toronto #RiskManagement #Mortgages #DataScience #CanadianRealEstate
