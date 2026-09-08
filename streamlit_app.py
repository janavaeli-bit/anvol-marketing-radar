import streamlit as st
import pandas as pd
import feedparser
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime, timezone

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except Exception:
    PYTRENDS_AVAILABLE = False

st.set_page_config(page_title="Anvol Marketing Radar", page_icon="📈", layout="wide")
DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_keywords():
    return pd.read_csv(DATA_DIR / "keywords.csv")

@st.cache_data
def load_news_queries():
    return pd.read_csv(DATA_DIR / "news_queries.csv")

def classify_signal(row):
    text = f"{row['Headline']} {row['Search signal']} {row['Category']}".lower()
    if row['Category'] == 'Retailer' or any(x in text for x in ['store opening', 'retailer', 'kampanj', 'sale ', 'promotion']):
        return '🏪 COMPETITOR'
    if row['Market'] == 'Asia Trend Scout' or any(x in text for x in ['viral', 'trend', 'blind box', 'collectible']):
        return '🔥 EARLY TREND'
    return '🆕 MARKET NEWS'

def score_signal(row):
    score = 35 if row['Priority'] == 'High' else 20
    if row['Market'] == 'Asia Trend Scout': score += 20
    if row['Market'] == 'Global Scout': score += 12
    if row['Market'] in ['Sweden', 'Finland']: score += 15
    if row['Category'] in ['Blind Boxes', 'Collectibles', 'Asia Trends', 'Anime', 'Gaming']: score += 15
    text = f"{row['Headline']} {row['Search signal']}".lower()
    if any(x in text for x in ['launch', 'new ', 'collaboration', 'license', 'licensed']): score += 8
    if any(x in text for x in ['viral', 'trend', 'surge', 'growing', 'sold out']): score += 12
    return min(score, 100)

@st.cache_data(ttl=3600)
def fetch_market_news(queries, max_per_query=3):
    rows = []
    for _, q in queries.iterrows():
        search = quote_plus(str(q['Query']))
        url = f"https://news.google.com/rss/search?q={search}&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_per_query]:
            rows.append({
                'Published': entry.get('published', ''),
                'Headline': entry.get('title', ''),
                'Market': q['Market'],
                'Category': q['Category'],
                'Priority': q['Priority'],
                'Search signal': q['Query'],
                'Source': entry.get('source', {}).get('title', 'Google News') if isinstance(entry.get('source', {}), dict) else 'Google News',
                'Link': entry.get('link', ''),
            })
    cols = ['Published','Headline','Market','Category','Priority','Search signal','Source','Link']
    if not rows:
        return pd.DataFrame(columns=cols + ['Signal type','Trend Score'])
    df = pd.DataFrame(rows).drop_duplicates(subset=['Headline'])
    df['Signal type'] = df.apply(classify_signal, axis=1)
    df['Trend Score'] = df.apply(score_signal, axis=1)
    return df.sort_values(['Trend Score','Priority'], ascending=[False, True])

@st.cache_data(ttl=21600, show_spinner=False)
def fetch_search_demand(keyword_tuple, geo):
    if not PYTRENDS_AVAILABLE:
        return None, 'Google Trends connector is not available in this deployment.'
    if not keyword_tuple:
        return pd.DataFrame(), None
    try:
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 25), retries=1, backoff_factor=0.3)
        pytrends.build_payload(list(keyword_tuple), timeframe='today 3-m', geo=geo)
        df = pytrends.interest_over_time()
        if df is None or df.empty:
            return pd.DataFrame(), None
        if 'isPartial' in df.columns:
            df = df.drop(columns=['isPartial'])
        return df, None
    except Exception as exc:
        return None, f'Google Trends could not be loaded right now: {exc}'

def demand_summary(df):
    rows = []
    if df is None or df.empty:
        return pd.DataFrame()
    for keyword in df.columns:
        s = pd.to_numeric(df[keyword], errors='coerce').fillna(0)
        recent = s.tail(14).mean() if len(s) >= 14 else s.mean()
        previous = s.iloc[-28:-14].mean() if len(s) >= 28 else s.head(max(len(s)-14, 1)).mean()
        if previous > 0:
            momentum = ((recent - previous) / previous) * 100
        elif recent > 0:
            momentum = 100.0
        else:
            momentum = 0.0
        if momentum >= 25:
            direction = '🔥 Rising fast'
        elif momentum >= 8:
            direction = '↑ Rising'
        elif momentum <= -25:
            direction = '↓ Falling fast'
        elif momentum <= -8:
            direction = '↘ Falling'
        else:
            direction = '→ Stable'
        rows.append({
            'Keyword': keyword,
            'Current index': round(recent, 1),
            'Previous index': round(previous, 1),
            'Momentum %': round(momentum, 1),
            'Direction': direction,
        })
    return pd.DataFrame(rows).sort_values('Momentum %', ascending=False)

keywords = load_keywords()
news_queries = load_news_queries()
live_news = fetch_market_news(news_queries)

st.title('Anvol Marketing Radar')
st.caption('Early trend, search demand, toy, collectible, licence and Nordic retail intelligence')

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(['Today', 'Trend Intelligence', 'Search Demand', 'Keywords', 'Live Radar', 'Watchlist'])

with tab1:
    st.subheader('Today')
    c1,c2,c3,c4 = st.columns(4)
    c1.metric('Signals found', len(live_news))
    c2.metric('Early trends', int((live_news['Signal type']=='🔥 EARLY TREND').sum()) if not live_news.empty else 0)
    c3.metric('High-score signals', int((live_news['Trend Score']>=70).sum()) if not live_news.empty else 0)
    c4.metric('Radar queries', len(news_queries))
    st.markdown('### 🔥 What deserves attention first')
    if live_news.empty:
        st.warning('No live signals could be loaded right now.')
    else:
        top = live_news.head(12)
        for _, row in top.iterrows():
            st.markdown(f"**{row['Signal type']} · {row['Trend Score']}/100 — {row['Headline']}**  \n{row['Market']} · {row['Category']} · watched via: {row['Search signal']}  \n[Open source]({row['Link']})")
    st.caption('Trend Score is an experimental radar score. Use Search Demand to see whether consumer search interest is also moving.')

with tab2:
    st.subheader('Trend Intelligence')
    st.caption('Designed to surface weak signals before they become obvious in Sweden or Finland.')
    if live_news.empty:
        st.warning('No live signals available.')
    else:
        c1,c2,c3 = st.columns(3)
        markets = c1.multiselect('Scout market', sorted(live_news['Market'].unique()), default=sorted(live_news['Market'].unique()), key='trend_market')
        types = c2.multiselect('Signal type', sorted(live_news['Signal type'].unique()), default=sorted(live_news['Signal type'].unique()))
        min_score = c3.slider('Minimum Trend Score', 0, 100, 55)
        trend = live_news[live_news['Market'].isin(markets) & live_news['Signal type'].isin(types) & (live_news['Trend Score']>=min_score)]
        st.dataframe(trend[['Trend Score','Signal type','Headline','Market','Category','Search signal','Source','Link']], use_container_width=True, hide_index=True, column_config={'Link': st.column_config.LinkColumn('Source')})
        st.markdown('### Early-opportunity view')
        early = live_news[(live_news['Signal type']=='🔥 EARLY TREND') & (live_news['Trend Score']>=65)].head(15)
        if early.empty:
            st.info('No strong early-trend signals in the current refresh.')
        else:
            st.dataframe(early[['Trend Score','Headline','Market','Category','Search signal']], use_container_width=True, hide_index=True)

with tab3:
    st.subheader('Search Demand')
    st.caption('Experimental Google Trends layer. Index values are relative search interest (0–100), not absolute monthly search volume.')
    c1, c2 = st.columns([1, 2])
    market = c1.radio('Market', ['Sweden', 'Finland'], horizontal=True)
    geo = 'SE' if market == 'Sweden' else 'FI'
    market_terms = keywords[keywords['Market'] == market]['Keyword'].dropna().drop_duplicates().tolist()
    defaults = market_terms[:5]
    selected_terms = c2.multiselect('Compare up to 5 keywords', market_terms, default=defaults, max_selections=5)

    if st.button('Refresh search demand'):
        fetch_search_demand.clear()
        st.rerun()

    if not selected_terms:
        st.info('Choose at least one keyword to compare.')
    else:
        with st.spinner('Loading search demand...'):
            demand_df, demand_error = fetch_search_demand(tuple(selected_terms), geo)
        if demand_error:
            st.warning(demand_error)
            st.info('The rest of the radar still works. Google Trends may temporarily rate-limit cloud requests; try again later or choose fewer terms.')
        elif demand_df is None or demand_df.empty:
            st.info('No Google Trends data was returned for this combination. Try broader terms or fewer keywords.')
        else:
            summary = demand_summary(demand_df)
            rising = int((summary['Momentum %'] >= 8).sum())
            fastest = summary.iloc[0]['Keyword'] if not summary.empty else '—'
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric('Keywords compared', len(summary))
            mc2.metric('Rising keywords', rising)
            mc3.metric('Fastest momentum', fastest)
            st.markdown('### 90-day search-interest trend')
            st.line_chart(demand_df, use_container_width=True)
            st.markdown('### Momentum: recent 14 days vs previous 14 days')
            st.dataframe(summary, use_container_width=True, hide_index=True, column_config={'Momentum %': st.column_config.NumberColumn(format='%.1f%%')})
            st.info('Important: Google Trends normalizes values within the selected comparison. Use Momentum % mainly to see direction and acceleration, not as absolute market size.')

with tab4:
    st.subheader('Keyword Watchlist')
    markets = sorted(keywords['Market'].dropna().unique())
    cats = sorted(keywords['Category'].dropna().unique())
    priorities = sorted(keywords['Priority'].dropna().unique())
    c1,c2,c3 = st.columns(3)
    sm = c1.multiselect('Market', markets, default=markets)
    sc = c2.multiselect('Category', cats, default=cats)
    sp = c3.multiselect('Priority', priorities, default=priorities)
    filtered = keywords[keywords['Market'].isin(sm)&keywords['Category'].isin(sc)&keywords['Priority'].isin(sp)]
    search = st.text_input('Search keywords or brands')
    if search:
        filtered = filtered[filtered['Keyword'].str.contains(search,case=False,na=False)|filtered['Brand'].str.contains(search,case=False,na=False)]
    st.dataframe(filtered,use_container_width=True,hide_index=True)

with tab5:
    st.subheader('Live Market & Launch Radar')
    if st.button('Refresh radar'):
        fetch_market_news.clear()
        st.rerun()
    if live_news.empty:
        st.warning('No live signals are available right now.')
    else:
        c1,c2 = st.columns(2)
        sm = c1.multiselect('Market', sorted(live_news['Market'].unique()), default=sorted(live_news['Market'].unique()), key='news_market')
        sc = c2.multiselect('Category', sorted(live_news['Category'].unique()), default=sorted(live_news['Category'].unique()), key='news_cat')
        display = live_news[live_news['Market'].isin(sm)&live_news['Category'].isin(sc)]
        st.dataframe(display[['Trend Score','Signal type','Headline','Market','Category','Priority','Search signal','Source','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Source link')})

with tab6:
    st.subheader('Radar Watchlist')
    st.caption('Asia Trend Scout looks upstream for emerging collectible, character and toy signals; Global Scout monitors launches and licences; Sweden/Finland track local market and retailers.')
    st.dataframe(news_queries,use_container_width=True,hide_index=True)
    st.markdown('### Keyword universe')
    st.dataframe(keywords,use_container_width=True,hide_index=True)

st.divider()
st.caption(f"Radar app · public feeds refresh hourly · search demand caches for 6 hours · viewed {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
