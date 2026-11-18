"""Transparent risk-adjusted allocation and historical diagnostics (not forecasts)."""
import numpy as np
import pandas as pd

MONTHLY = 500
TARGET = {'VOO': 0.45, 'VXUS': 0.20, 'VUG': 0.15}
ACTIVE_WEIGHT = 0.20
# ETF target weights total 80%; remaining 20% reserved for researched stocks.
BENCHMARK = {'VTI': 0.70, 'VXUS': 0.30}

def allocations(monthly=MONTHLY, target=TARGET):
    if monthly < 0 or abs(sum(target.values())+ACTIVE_WEIGHT-1)>1e-8: raise ValueError('Invalid contribution or allocation')
    return {**{ticker: round(monthly*weight,2) for ticker,weight in target.items()}, 'Active stock reserve': round(monthly*ACTIVE_WEIGHT,2)}

def portfolio_stats(prices, weights, monthly=500):
    """Monthly-rebalanced portfolio returns; adjusted closing prices from provider.
    Not an investable backtest: no trading costs, taxes, spreads or cash flows modeled.
    Only dates common to every asset are used. No historical fundamental screening.
    """
    if prices.empty: raise ValueError('No price history')
    if abs(sum(weights.values())-1)>1e-8: raise ValueError('Backtest weights must total 100%; active stock picks cannot be backtested without historical holdings')
    cols=list(weights)
    close=prices[cols].dropna().resample('ME').last().dropna()
    if len(close)<25: raise ValueError('At least 25 month-end observations required')
    ret=close.pct_change().dropna()
    portfolio=ret.dot(pd.Series(weights))
    equity=ret[list(BENCHMARK)].dot(pd.Series(BENCHMARK)) if set(BENCHMARK).issubset(ret.columns) else None
    def stats(r):
        wealth=(1+r).cumprod(); years=len(r)/12
        return {'annualized_return':float(wealth.iloc[-1]**(1/years)-1),
                'annualized_volatility':float(r.std(ddof=1)*np.sqrt(12)),
                'max_drawdown':float((wealth/wealth.cummax()-1).min()),
                'worst_month':float(r.min()),
                'months':len(r)}
    # Contribution simulation, month-end deposits; useful comparison, not a promise.
    value=0.0
    for r in portfolio: value=value*(1+r)+monthly
    result={'portfolio':stats(portfolio),'monthly_contribution':monthly,
            'simulated_contribution_value':round(value,2),
            'simulated_contributions':monthly*len(portfolio),
            'start':str(ret.index[0].date()),'end':str(ret.index[-1].date()),
            'monthly_returns':portfolio}
    if equity is not None: result['equity_benchmark']=stats(equity)
    return result

def risk_score(row):
    """0-100 research heuristic; missing data never gets full credit."""
    def n(k):
        try:
            v=float(row.get(k)); return v if np.isfinite(v) else None
        except (TypeError,ValueError): return None
    def scale(v,low,high,points):
        return 0 if v is None else points*min(1,max(0,(v-low)/(high-low)))
    rev=n('revenue_growth'); earn=n('earnings_growth'); margin=n('operating_margin')
    fcf=n('free_cash_flow'); fcf_yield=n('fcf_yield'); debt=n('debt'); cash=n('cash')
    vol=n('volatility_annual'); dd=n('max_drawdown_5y')
    score=(scale(rev,0,.25,15)+scale(earn,0,.25,10)+scale(margin,0,.3,15)
           +(10 if fcf is not None and fcf>0 else 0)+scale(fcf_yield,0,.06,15)
           +(15 if debt is not None and cash is not None and debt<=cash else (7 if debt is None or cash is None else 0))
           +scale(vol,.65,.15,10)+scale(dd,-.75,-.15,10))
    # Large drawdowns and volatility are not necessarily predictive of future losses.
    missing=sum(v is None for v in (rev,earn,margin,fcf,fcf_yield,vol,dd))
    if missing>=4: label='Insufficient data'
    elif score>=75: label='Research priority'
    elif score>=55: label='Watchlist'
    else: label='Low priority'
    flags=[]
    if dd is not None and dd<-.30: flags.append('Past drawdown exceeded your 30% comfort level')
    if vol is not None and vol>.4: flags.append('High historical volatility')
    if fcf is not None and fcf<=0: flags.append('Nonpositive free cash flow')
    if missing: flags.append(f'{missing} missing inputs')
    return round(score,1),label,'; '.join(flags) or 'No threshold flags'
