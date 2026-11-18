import os
import re
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from scanner import DEFAULT_TICKERS, scan, compare_history
from risk_profile import TARGET, ACTIVE_WEIGHT, allocations, risk_score, portfolio_stats

st.set_page_config(page_title='Private Growth Scanner',page_icon='📈',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>div.block-container{padding-top:1.1rem;max-width:1050px} [data-testid="stMetric"]{background:#18233512;border-radius:12px;padding:12px} @media(max-width:600px){h1{font-size:1.7rem!important}}</style>''',unsafe_allow_html=True)

required=['SUPABASE_URL','SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY','ADMIN_EMAIL']
config={k:st.secrets.get(k,os.environ.get(k,'')) for k in required}
if any(not config[k] for k in required):
    st.error('Setup required. Add the four keys shown in .streamlit/secrets.toml.example to your deployment secrets.')
    st.stop()

# Never cache authenticated Supabase clients across Streamlit user sessions.
# The privileged admin client is created only inside the administrator-only section.

def current_client():
    # Fresh client per rerun avoids cross-user auth state leakage in shared cached objects.
    client=create_client(config['SUPABASE_URL'],config['SUPABASE_ANON_KEY'])
    session=st.session_state.get('auth_session')
    if not session: return None
    try:
        response=client.auth.set_session(session['access_token'],session['refresh_token'])
        if response.session:
            st.session_state.auth_session={'access_token':response.session.access_token,'refresh_token':response.session.refresh_token}
        user=client.auth.get_user().user
        if not user: return None
        return client,user
    except Exception:
        st.session_state.pop('auth_session',None)
        return None

st.title('📈 Private Growth Scanner')
st.caption('Passive ETF purchases + active value research • private watchlists • no automated trading')
auth = current_client()
if not isinstance(auth, tuple) or len(auth) != 2:
    st.subheader('Sign in')
    st.info('Invitation-only: an administrator must create your account before you can sign in.')
    with st.form('login'):
        email=st.text_input('Email').strip().lower()
        password=st.text_input('Password',type='password')
        submit=st.form_submit_button('Sign in',use_container_width=True)
    if submit:
        try:
            client=create_client(config['SUPABASE_URL'],config['SUPABASE_ANON_KEY'])
            response=client.auth.sign_in_with_password({'email':email,'password':password})
            if not response.session: raise ValueError('No session returned')
            st.session_state.auth_session={'access_token':response.session.access_token,'refresh_token':response.session.refresh_token}
            st.rerun()
        except Exception as exc:
            # Do not show exception details: they may contain sensitive request data.
            st.error(f'Sign-in failed ({type(exc).__name__}). Check credentials and Supabase Auth logs.')
    # A first-time visitor has no session. Do not continue into the dashboard.
    st.stop()

client,user=auth
is_admin=(user.email or '').lower()==config['ADMIN_EMAIL'].lower()
with st.sidebar:
    st.write(f'Logged in: **{user.email}**')
    if st.button('Sign out'):
        st.session_state.pop('auth_session',None)
        st.rerun()
    st.caption('Data provided by Yahoo Finance via yfinance; not guaranteed real-time or complete.')

tabs=['ETF + stock plan','Active stock scanner','Company history','My watchlist']+(['Manage access'] if is_admin else [])
sections=st.tabs(tabs)

@st.cache_data(ttl=21600,show_spinner='Retrieving market and financial data…')
def cached_scan(tickers): return scan(list(tickers))

@st.cache_data(ttl=21600,show_spinner='Loading historical prices…')
def cached_history(ticker,years): return compare_history(ticker,years=years)

with sections[0]:
    st.subheader('Always be buying ETFs; research stocks selectively')
    st.caption('Jaspreet Singh-inspired educational adaptation, not his verified personal allocation. 100% equities when fully invested; drawdowns can exceed 30%.')
    monthly=st.number_input('Monthly contribution ($)',min_value=0,max_value=100000,value=500,step=25)
    plan=pd.DataFrame([{'Holding':t,'Target':f'{w:.0%}','Monthly amount ($)':allocations(monthly)[t]} for t,w in TARGET.items()] +
                      [{'Holding':'Active stock reserve','Target':f'{ACTIVE_WEIGHT:.0%}','Monthly amount ($)':allocations(monthly)['Active stock reserve']}])
    st.dataframe(plan,hide_index=True,use_container_width=True)
    st.success(f'Automate ${monthly*(1-ACTIVE_WEIGHT):,.0f}/month in ETFs. Set aside ${monthly*ACTIVE_WEIGHT:,.0f}/month for individually researched stocks; do not force a purchase.')
    st.write('**Buying discipline:** ETFs on schedule regardless of headlines; individual stocks only after checking business quality, free cash flow, balance sheet, and conservative valuation. Start with ≤5% portfolio exposure per direct stock and review ETF overlap.')
    st.info('Active reserve is temporarily uninvested cash until a qualified opportunity appears. It is not a long-term bond or Treasury allocation; cash drag may reduce returns.')
    if st.button('Backtest passive ETF sleeve (illustrative)'):
        try:
            import yfinance as yf
            raw=yf.download(list(TARGET),period='10y',auto_adjust=True,progress=False,threads=False)
            close=raw['Close'] if isinstance(raw.columns,pd.MultiIndex) else raw[['Close']]
            normalized={ticker:weight/(1-ACTIVE_WEIGHT) for ticker,weight in TARGET.items()}
            result=portfolio_stats(close,normalized,monthly*(1-ACTIVE_WEIGHT))
            a,b,c=st.columns(3)
            a.metric('ETF sleeve annualized return',f"{result['portfolio']['annualized_return']:.1%}")
            b.metric('ETF sleeve max drawdown',f"{result['portfolio']['max_drawdown']:.1%}")
            c.metric('ETF sleeve volatility',f"{result['portfolio']['annualized_volatility']:.1%}")
            st.write(f"Shared history: {result['start']} to {result['end']}")
            st.line_chart((1+result['monthly_returns']).cumprod())
            st.caption('ETF sleeve only, rebalanced monthly. Does not model the 20% active stock sleeve, cash reserve, taxes, spreads, or fees. Historical results are not forecasts. VUG and VOO overlap.')
        except Exception as exc:
            st.warning(f'ETF backtest unavailable: {str(exc)[:180]}')
    st.warning('Your preferred 25–30% loss tolerance is not a guaranteed maximum. This all-equity strategy may fall much further. Consider reducing equity exposure if a 30% loss would require selling.')

with sections[1]:
    st.subheader('Find strong companies at potentially attractive prices')
    st.caption('Prioritize free cash flow, financial strength, growth, valuation and risk. A price drop alone is not evidence of undervaluation.')
    universe=st.multiselect('Companies to scan',DEFAULT_TICKERS,default=DEFAULT_TICKERS[:15],help='Start with 15 to reduce free data source throttling. You can add more.')
    if st.button('Refresh data now',key='refresh'):
        cached_scan.clear()
        st.rerun()
    if not universe:
        st.info('Select at least one ticker.')
    else:
        df,errors=cached_scan(tuple(sorted(universe)))
        st.caption(f'Scan generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC • cached up to 6 hours • data may be delayed')
        if not df.empty:
            a,b,c=st.columns(3)
            a.metric('Scanned',len(df));b.metric('Research priority',int((df.category=='Research priority').sum()));c.metric('Data errors',len(errors))
            scored=df.apply(lambda row: risk_score(row),axis=1)
            df['risk_adjusted_score']=[v[0] for v in scored]
            df['risk_category']=[v[1] for v in scored]
            df['risk_flags']=[v[2] for v in scored]
            df=df.sort_values('risk_adjusted_score',ascending=False)
            show=df[['ticker','company','risk_adjusted_score','risk_category','revenue_growth','operating_margin','fcf_yield','volatility_annual','max_drawdown_5y']].copy()
            for k in ['revenue_growth','operating_margin','fcf_yield','volatility_annual','max_drawdown_5y']:
                show[k]=show[k].map(lambda v:f'{v:.1%}' if pd.notna(v) else 'N/A')
            st.dataframe(show,hide_index=True,use_container_width=True)
            st.download_button('Download ranked CSV',df.to_csv(index=False).encode(),'growth_rankings.csv','text/csv')
            selected=st.selectbox('Explain a stock',df.ticker.tolist())
            item=df[df.ticker==selected].iloc[0]
            st.write(f"**{item['company']} — {item['risk_adjusted_score']}/100 ({item['risk_category']})**")
            st.write('**Risk-adjusted flags:**',item['risk_flags'])
            st.write('**Risk / data flags:**',item['risks'])
            st.write('**Valuation checkpoint:**', 'FCF yield '+(f"{item['fcf_yield']:.1%}" if pd.notna(item['fcf_yield']) else 'unavailable')+'; compare with peers, growth, capital needs and historical valuations before considering a purchase.')
            st.caption('Research-only signals. Current financial metrics are NOT historical point-in-time backtests. A high score is not a buy recommendation; this app does not calculate intrinsic value or a defensible buy price.')
        if not errors.empty:
            with st.expander(f'Data retrieval errors ({len(errors)})'):
                st.dataframe(errors,hide_index=True,use_container_width=True)

with sections[2]:
    st.subheader('Historical performance vs VTI')
    symbol=st.text_input('Ticker',value='MSFT',key='history_ticker').strip().upper()
    years=st.select_slider('Historical period',options=[1,3,5,10],value=5)
    if re.fullmatch(r'[A-Z0-9.^-]{1,15}',symbol):
        try:
            history=cached_history(symbol,years)
            if not history.empty:
                long=history.reset_index().melt(id_vars=history.index.name or 'Date',var_name='Ticker',value_name='Index (starts at 100)')
                fig=px.line(long,x=history.index.name or 'Date',y='Index (starts at 100)',color='Ticker',title='Historical total price performance (adjusted)')
                st.plotly_chart(fig,use_container_width=True)
                st.caption('Adjusted closing prices, indexed to 100. Historical comparison is not a point-in-time stock-selection backtest; dividends/splits adjustment depends on data source.')
            else: st.warning('Not enough historical data returned.')
        except Exception as exc: st.warning(f'Unable to retrieve price history: {str(exc)[:160]}')
    else: st.warning('Enter a valid ticker.')

with sections[3]:
    st.subheader('My private watchlist')
    try:
        rows=client.table('watchlists').select('ticker,created_at').eq('user_id',str(user.id)).order('created_at',desc=True).execute().data or []
        st.dataframe(pd.DataFrame(rows) if rows else pd.DataFrame(columns=['ticker','created_at']),hide_index=True,use_container_width=True)
    except Exception:
        st.error('Could not load watchlist. Verify schema.sql was run and row-level security is enabled.')
        rows=[]
    new=st.text_input('Add ticker',placeholder='e.g. MSFT').strip().upper()
    if st.button('Add to watchlist'):
        if not re.fullmatch(r'[A-Z0-9.^-]{1,15}',new): st.warning('Enter a valid ticker.')
        else:
            try:
                client.table('watchlists').upsert({'user_id':str(user.id),'ticker':new}).execute()
                st.rerun()
            except Exception: st.error('Could not add ticker.')
    if rows:
        remove=st.selectbox('Remove ticker',[r['ticker'] for r in rows])
        if st.button('Remove selected ticker'):
            try:
                client.table('watchlists').delete().eq('user_id',str(user.id)).eq('ticker',remove).execute()
                st.rerun()
            except Exception: st.error('Could not remove ticker.')

if is_admin:
    # Service-role operations are restricted to the verified administrator view.
    # Never use this client for regular watchlist requests (RLS must apply).
    admin=create_client(config['SUPABASE_URL'],config['SUPABASE_SERVICE_ROLE_KEY'])
    with sections[4]:
        st.subheader('Invite-only access')
        st.caption('Admin creates an account with a temporary password and shares credentials through a secure channel. This version does not email invitations automatically.')
        with st.form('create_user'):
            invite_email=st.text_input('Invitee email').strip().lower()
            temp_password=st.text_input('Temporary password (at least 12 characters)',type='password')
            create=st.form_submit_button('Create approved user')
        if create:
            if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',invite_email) or len(temp_password)<12:
                st.error('Enter a valid email and a temporary password of at least 12 characters.')
            else:
                try:
                    admin.auth.admin.create_user({'email':invite_email,'password':temp_password,'email_confirm':True})
                    st.success('User created. Share the temporary password securely; do not send it in a public message.')
                except Exception as exc: st.error(f'Unable to create user: {str(exc)[:160]}')
        st.divider()
        st.write('**Revoke access**')
        try:
            result=admin.auth.admin.list_users()
            users=result if isinstance(result,list) else getattr(result,'users',[])
            candidates={u.email:str(u.id) for u in users if u.email and u.email.lower()!=config['ADMIN_EMAIL'].lower()}
            if candidates:
                revoke_email=st.selectbox('Approved user',list(candidates))
                confirm=st.checkbox('I understand this permanently removes this account and its watchlist')
                if st.button('Revoke selected user',disabled=not confirm):
                    admin.auth.admin.delete_user(candidates[revoke_email])
                    st.success('User removed.');st.rerun()
            else: st.info('No other users found.')
        except Exception as exc: st.error(f'Unable to list users: {str(exc)[:160]}')
        st.warning('For production, add password reset / forced password change, audit logging, rate limiting and more robust administrator roles. Supabase service-role credentials must never be exposed to users or committed to Git.')

st.divider()
st.caption('Singh-inspired strategy, not affiliated with Minority Mindset. Educational research tool only. No brokerage connection, trading, guaranteed returns, or validated investment signals. Free market-data providers can rate-limit or change availability.')
