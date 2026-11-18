# Private Growth Scanner (free-tier prototype)

A mobile-friendly Streamlit web app with Supabase email/password sign-in, admin-created approved users, private watchlists with row-level security, on-demand growth stock rankings, and historical price comparisons.

## What is and isn't included
- **Included:** Login, admin user creation/revocation, personal watchlists, starter list of 30 stocks, 6-hour cached on-demand Yahoo Finance data through `yfinance`, growth heuristics, CSV download, 1/3/5/10-year adjusted-price comparisons to VTI.
- **Not included:** Publicly accessible deployed URL, automatic unattended scheduled scans, automatic emailed invitations, password reset flow, guaranteed live exchange data, historical point-in-time fundamental backtesting, trades or broker connectivity.
- **Privacy:** Website login required. The hosting page itself can be discovered, but stock pages require authentication. Streamlit session isolation and Supabase RLS protect watchlists; do not expose service-role secrets. This is a prototype, not a security audit.
- **$0:** Streamlit Community Cloud and Supabase free tiers can work within their usage limits, subject to policy, sleep/pauses and pricing changes. Yahoo Finance data is unofficial and can throttle; check data licensing before broader distribution. No guaranteed SLA.

## Setup (about 20–40 minutes)
1. Create a **Supabase** free project at https://supabase.com . Under Authentication → Providers → Email, enable email/password sign-in. Disable public user sign-ups if available in the project settings. This app does not expose a signup form, but disabling public signups at the provider is still important.
2. Open Supabase SQL Editor and run `schema.sql`. This enables **row-level security** so users can only read/write their own watchlist.
3. In Supabase Authentication → Users, manually **Add user** for yourself, with your email and a strong password, and mark email confirmed. This email must match `ADMIN_EMAIL` exactly (case-insensitive).
4. Create a GitHub repository containing this folder. For Streamlit Community Cloud, repositories may need to be public; **never commit your secrets file**. Code is not private merely because app data is behind login. If a public repo is unacceptable, use a host supporting private source repositories (free availability may vary).
5. Visit https://share.streamlit.io , deploy `app.py` from your GitHub repository. Add the four secrets from `.streamlit/secrets.toml.example` in Streamlit app settings → Secrets. Copy values from Supabase Project Settings → API Keys / project URL. The **service role key is highly sensitive**: only put it in Streamlit's secret settings, never in Git or client-side code.
6. Open the deployed URL on your iPhone, sign in with your Supabase account, and choose **Manage access** to create an approved user. Share their temporary password privately. Note: this prototype does not force a password change or offer self-service reset; use only with trusted users until improved.
7. Test isolation: create a second account, add a watchlist ticker, sign out, and confirm that the admin's watchlist remains separate.

## Local test
```
python -m pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit secrets.toml with your own keys
streamlit run app.py
```

## Scoring methodology (heuristic, not backtested)
- Revenue growth: 25 points, linearly 0–30% growth.
- Earnings growth: 10 points, linearly 0–30% growth.
- Operating margin: 15 points, linearly 0–35% margin.
- Positive free cash flow: 15 points.
- Free-cash-flow yield: 15 points, linearly 0–7%.
- Balance sheet: 10 points if cash >= debt; 5 if unavailable.
- Price above 200-day average: 10 points.
Missing metrics get zero except debt/cash. Labels: >=70 research priority, >=50 watchlist, otherwise low priority; >=3 missing fundamentals means insufficient data. **These scores have no validated predictive power** and the current Yahoo Finance financial figures are not point-in-time historical observations.

## Security and operations caveats
- Use Supabase project email authentication, disabled public signups, strong passwords, RLS, and Streamlit secrets. Service role is used only on the server for admin functions. Supabase's server-side `service_role` key bypasses RLS; keep it secret.
- Admin identity is configured by an email in deployment secrets; only that signed-in email may access admin controls. Production apps should use a server-managed role/claims table and audit logs.
- Temporary passwords must be shared securely. No forced reset or recovery workflow is implemented.
- Market-data fetching occurs when an authenticated user loads the Scanner tab, cached for six hours. This is **not a background scheduler**. True daily unattended scans require an external scheduled job, persistence and alert delivery.
- A free plan can sleep, rate-limit, or expire. Expect some tickers to fail or have missing financial fields.
- Data uses adjusted historical prices and currently available fundamental fields. Comparing a stock's past price against VTI is **not** a valid backtest of buying stocks based on historical growth scores. For that, acquire point-in-time fundamentals, delisted companies, timestamps, and model transaction costs.

## Singh-inspired passive + active strategy (November 2026)

This build replaces the fixed-income allocation with an **all-equity target**: 45% VOO (S&P 500), 20% VXUS (international), 15% VUG (U.S. growth), and 20% researched individual stocks. At $500/month: $225, $100, $75, and $100. These are **our illustrative settings**, not a claim about Jaspreet Singh's exact portfolio. VOO and VUG overlap substantially.

- **Passive engine:** Automatically invest $400/month in ETFs through your brokerage's recurring purchase feature. The app calculates allocations but **does not place trades**.
- **Active engine:** Reserve $100/month until a stock passes independent due diligence. Review growth, operating margin, free cash flow, FCF yield, debt, volatility and business valuation. The scanner **does not compute intrinsic value**, and its research scores have not been validated as buy signals.
- **Backtest:** Only the normalized 80% ETF sleeve is historically tested; **the 20% active sleeve is not backtested**, and its temporarily uninvested cash is not included. Backtest is illustrative, monthly-rebalanced, and ignores taxes and transaction costs.
- **Risk:** A 100% equity portfolio can lose more than 25–30% in a severe downturn. Position-size direct stocks to no more than 5% of total portfolio as an initial guideline, and consider overlap with VOO/VUG.
- **Privacy:** Supabase authentication and row-level-security-backed individual watchlists remain. Deployment and credentials are still required. The app is not yet hosted or end-to-end tested with live market data.
- **Cost:** Free-tier hosting and unofficial data access have usage, licensing, reliability and throttling limitations. There is no unattended background scheduler or automatic trade execution.

### Validation
Run `python -m compileall -q .` and `python -m unittest discover -s tests -v`. Tests use synthetic prices; no external services are called.
