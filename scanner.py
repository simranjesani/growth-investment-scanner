"""Growth-stock research signals, not investment advice. Financial data may be delayed/incomplete."""
import math
import pandas as pd
import numpy as np
import yfinance as yf

DEFAULT_TICKERS = ["AAPL","MSFT","GOOGL","AMZN","META","NVDA","AVGO","AMD","CRM","ADBE","NOW","INTU","ORCL","PANW","CRWD","SHOP","UBER","MELI","COST","V","MA","NFLX","BKNG","ISRG","TTD","SNPS","CDNS","PLTR","ANET","TSM"]

def number(value):
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def _metric(info, *keys):
    for key in keys:
        v=number(info.get(key))
        if v is not None: return v
    return None

def _score_growth(v, low, high, points):
    if v is None: return 0
    return round(points * min(1,max(0,(v-low)/(high-low))),1)

def _price_metrics(history):
    if history is None or history.empty: return {}
    px=history['Close'].dropna().astype(float)
    if len(px)<40: return {}
    peak=px.cummax()
    dd=px/peak-1
    rets=px.pct_change().dropna()
    return {
        'last_price': number(px.iloc[-1]),
        'return_1y': number(px.iloc[-1]/px.iloc[-min(253,len(px))]-1),
        'max_drawdown_5y': number(dd.min()),
        'volatility_annual': number(rets.std()*np.sqrt(252)),
        'above_200d': bool(px.iloc[-1]>px.tail(200).mean()) if len(px)>=200 else None,
        'history_start':str(px.index[0].date()),
        'history_end':str(px.index[-1].date()),
    }

def research_ticker(symbol):
    t=yf.Ticker(symbol)
    info=t.info or {}
    hist=t.history(period='5y',auto_adjust=True)
    m=_price_metrics(hist)
    rev=_metric(info,'revenueGrowth')
    earn=_metric(info,'earningsGrowth')
    margin=_metric(info,'operatingMargins')
    fcf=_metric(info,'freeCashflow')
    cap=_metric(info,'marketCap')
    debt=_metric(info,'totalDebt')
    cash=_metric(info,'totalCash')
    fcf_yield=fcf/cap if fcf is not None and cap and cap>0 else None
    # Explicitly heuristic, not validated predictive probabilities.
    score=0
    score+=_score_growth(rev,0,0.3,25)
    score+=_score_growth(earn,0,0.3,10)
    score+=_score_growth(margin,0,0.35,15)
    score+=15 if fcf is not None and fcf>0 else 0
    score+=_score_growth(fcf_yield,0,0.07,15)
    score+=10 if debt is not None and cash is not None and debt<=cash else (5 if debt is None or cash is None else 0)
    score+=10 if m.get('above_200d') is True else 0
    missing=sum(v is None for v in (rev,earn,margin,fcf,cap))
    label='Insufficient data' if missing>=3 else ('Research priority' if score>=70 else 'Watchlist' if score>=50 else 'Low priority')
    risks=[]
    if fcf is not None and fcf<=0: risks.append('Nonpositive free cash flow')
    if fcf_yield is not None and fcf_yield<0.015: risks.append('Low FCF yield / possible valuation risk')
    if m.get('max_drawdown_5y') is not None and m['max_drawdown_5y']<-.5: risks.append('Historical drawdown exceeded 50%')
    if debt is not None and cash is not None and debt>cash*3: risks.append('Debt substantially exceeds cash')
    if missing: risks.append(f'{missing} missing fundamental metrics')
    return {'ticker':symbol,'company':info.get('shortName') or symbol,'sector':info.get('sector','Unknown'),
            'score':round(score,1),'category':label,'revenue_growth':rev,'earnings_growth':earn,
            'operating_margin':margin,'free_cash_flow':fcf,'fcf_yield':fcf_yield,'market_cap':cap,
            'debt':debt,'cash':cash,'risks':'; '.join(risks) or 'No heuristic flags',**m}

def scan(tickers):
    records=[]; errors=[]
    for symbol in tickers:
        try: records.append(research_ticker(symbol))
        except Exception as exc: errors.append({'ticker':symbol,'error':str(exc)[:220]})
    return pd.DataFrame(records).sort_values('score',ascending=False) if records else pd.DataFrame(), pd.DataFrame(errors)

def compare_history(ticker,benchmark='VTI',years=5):
    raw=yf.download([ticker,benchmark],period=f'{years}y',auto_adjust=True,progress=False,threads=False)
    if raw.empty: return pd.DataFrame()
    close=raw['Close'] if isinstance(raw.columns,pd.MultiIndex) else raw[['Close']].rename(columns={'Close':ticker})
    if ticker not in close or benchmark not in close: return pd.DataFrame()
    close=close[[ticker,benchmark]].dropna()
    if close.empty: return pd.DataFrame()
    return close.div(close.iloc[0]).mul(100)
