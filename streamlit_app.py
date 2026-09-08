import streamlit as st
import pandas as pd
import feedparser
import re
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime, timezone

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
    if not rows: return pd.DataFrame(columns=cols + ['Signal type','Trend Score'])
    df = pd.DataFrame(rows).drop_duplicates(subset=['Headline'])
    df['Signal type'] = df.apply(classify_signal, axis=1)
    df['Trend Score'] = df.apply(score_signal, axis=1)
    return df.sort_values(['Trend Score','Priority'], ascending=[False, True])

keywords = load_keywords()
news_queries = load_news_queries()
live_news = fetch_market_news(news_queries)

st.title('Anvol Marketing Radar')
st.caption('Early trend, toy, collectible, licence and Nordic retail intelligence')

tab1, tab2, tab3, tab4, tab5 = st.tabs(['Today', 'Trend Intelligence', 'Keywords', 'Live Radar', 'Watchlist'])

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
    st.caption('Trend Score is currently an experimental radar score based on source market, category, priority and language signals — not yet consumer search volume.')

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
        if early.empty: st.info('No strong early-trend signals in the current refresh.')
        else: st.dataframe(early[['Trend Score','Headline','Market','Category','Search signal']], use_container_width=True, hide_index=True)

with tab3:
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
    if search: filtered = filtered[filtered['Keyword'].str.contains(search,case=False,na=False)|filtered['Brand'].str.contains(search,case=False,na=False)]
    st.dataframe(filtered,use_container_width=True,hide_index=True)

with tab4:
    st.subheader('Live Market & Launch Radar')
    if st.button('Refresh radar'):
        fetch_market_news.clear(); st.rerun()
    if live_news.empty:
        st.warning('No live signals are available right now.')
    else:
        c1,c2 = st.columns(2)
        sm = c1.multiselect('Market', sorted(live_news['Market'].unique()), default=sorted(live_news['Market'].unique()), key='news_market')
        sc = c2.multiselect('Category', sorted(live_news['Category'].unique()), default=sorted(live_news['Category'].unique()), key='news_cat')
        display = live_news[live_news['Market'].isin(sm)&live_news['Category'].isin(sc)]
        st.dataframe(display[['Trend Score','Signal type','Headline','Market','Category','Priority','Search signal','Source','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Source link')})

with tab5:
    st.subheader('Radar Watchlist')
    st.caption('Asia Trend Scout looks upstream for emerging collectible, character and toy signals; Global Scout monitors launches and licences; Sweden/Finland track local market and retailers.')
    st.dataframe(news_queries,use_container_width=True,hide_index=True)
    st.markdown('### Keyword universe')
    st.dataframe(keywords,use_container_width=True,hide_index=True)

st.divider()
st.caption(f"Radar app · public feeds refresh hourly · viewed {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
