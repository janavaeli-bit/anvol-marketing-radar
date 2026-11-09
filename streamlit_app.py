import streamlit as st
import pandas as pd
from radar_news import collect
from pathlib import Path
from datetime import datetime, timezone

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except Exception:
    PYTRENDS_AVAILABLE = False

st.set_page_config(page_title="Anvol Marketing Radar", page_icon="📈", layout="wide")
DATA_DIR=Path(__file__).parent/'data'
MARKET_GEO={'Sweden':'SE','Finland':'FI','Estonia':'EE','Latvia':'LV','Lithuania':'LT'}
CORE_MARKETS=list(MARKET_GEO.keys())

# Read small watchlists on every rerun so GitHub CSV updates are visible immediately.
def load_csv(name): return pd.read_csv(DATA_DIR/name)

def classify_signal(row):
    text=str(row['Headline']).lower()
    if row['Category']=='Retailer' or any(x in text for x in ['store opening','retailer','kampanj','sale ','promotion','parduotuv','veikals','mänguasjapood']): return '🏪 COMPETITOR'
    if row['Market']=='Asia Trend Scout' or row['Category'] in ['Local Trend','Asia Trends'] or any(x in text for x in ['viral','trend','blind box','collectible','kollek','kolek']): return '🔥 EARLY TREND'
    return '🆕 MARKET NEWS'

def score_signal(row):
    score=35 if row['Priority']=='High' else 20
    if row['Market']=='Asia Trend Scout': score+=20
    if row['Market']=='Global Scout': score+=12
    if row['Market'] in CORE_MARKETS: score+=15
    if row['Category'] in ['Blind Boxes','Collectibles','Asia Trends','Local Trend','Anime','Gaming']: score+=15
    text=str(row['Headline']).lower()
    if any(x in text for x in ['launch','new ','collaboration','license','licensed','uued','jaunas','nauji']): score+=8
    if any(x in text for x in ['viral','trend','surge','growing','sold out','tendenc']): score+=12
    return min(score,100)

@st.cache_data(ttl=3600)
def fetch_market_news(queries, days=7):
    df, status = collect(queries, days=days)
    df['Signal type'] = df.apply(classify_signal, axis=1) if not df.empty else pd.Series(dtype=str)
    df['Relevance score'] = df.apply(score_signal, axis=1) if not df.empty else pd.Series(dtype=int)
    return df.sort_values(['Published', 'Relevance score'], ascending=[False, False]), status

@st.cache_data(ttl=3600)
def fetch_social_scout(queries, days=7):
    df, status = collect(queries, days=days, social=True)
    def relevance(r):
        text = str(r['Headline']).lower()
        score = 45 if r['Priority'] == 'High' else 30
        if any(x in text for x in ['viral', 'trend', 'million', 'sold out', 'tiktok', 'youtube']): score += 20
        if r['Category'] in ['Blind Boxes', 'Collectibles', 'Anime', 'Gaming', 'Toy Trends']: score += 15
        return min(score, 100)
    df['Social relevance'] = df.apply(relevance, axis=1) if not df.empty else pd.Series(dtype=int)
    return df.sort_values(['Published', 'Social relevance'], ascending=[False, False]), status


def show_collection_status(label, status):
    last = status['last_success'] or 'No successful feed retrieval'
    st.caption(f"{label}: {status['successful']}/{status['attempted']} feeds retrieved · Last successful retrieval: {last} · {status['excluded']} old, future or undated entries excluded")
    if status['errors']:
        st.warning(f"{label}: {len(status['errors'])} feeds failed. Results may be incomplete.")
        with st.expander(f'{label} collection details'):
            st.text('\n'.join(status['errors']))

@st.cache_data(ttl=21600,show_spinner=False)
def fetch_search_demand(keyword_tuple,geo):
    if not PYTRENDS_AVAILABLE:return None,'Google Trends connector is not available in this deployment.'
    try:
        pytrends=TrendReq(hl='en-US',tz=0,timeout=(10,25)); pytrends.build_payload(list(keyword_tuple),timeframe='today 3-m',geo=geo); df=pytrends.interest_over_time()
        if df is None or df.empty:return pd.DataFrame(),None
        if 'isPartial' in df.columns:df=df.drop(columns=['isPartial'])
        return df,None
    except Exception as exc:return None,f'Google Trends could not be loaded right now: {exc}'

def demand_summary(df):
    rows=[]
    if df is None or df.empty:return pd.DataFrame()
    for k in df.columns:
        s=pd.to_numeric(df[k],errors='coerce').fillna(0); recent=s.tail(14).mean(); previous=s.iloc[-28:-14].mean() if len(s)>=28 else 0; momentum=((recent-previous)/previous)*100 if previous>0 else (100 if recent>0 else 0)
        direction='🔥 Rising fast' if momentum>=25 else ('↑ Rising' if momentum>=8 else ('↓ Falling fast' if momentum<=-25 else ('↘ Falling' if momentum<=-8 else '→ Stable')))
        rows.append({'Keyword':k,'Current index':round(recent,1),'Previous index':round(previous,1),'Momentum %':round(momentum,1),'Direction':direction})
    return pd.DataFrame(rows).sort_values('Momentum %',ascending=False)

keywords=load_csv('keywords.csv'); news_queries=load_csv('news_queries.csv'); social_queries=load_csv('social_queries.csv')
st.title('Anvol Marketing Radar')
st.caption('Recent toy launches, retail activity and discovery leads across Nordics & Baltics')
days = st.sidebar.selectbox('Publication window (days)', [7, 30, 90], index=0)
st.sidebar.caption('Only articles with a valid publication date inside this window are shown. Newest stories appear first.')
st.sidebar.caption(f'Watchlists: {len(keywords)} keyword entries · {len(news_queries)} news searches · {len(social_queries)} social searches')
if st.sidebar.button('Refresh all news'):
    fetch_market_news.clear()
    fetch_social_scout.clear()
    st.rerun()
with st.spinner('Collecting recent news and social coverage…'):
    live_news, news_status = fetch_market_news(news_queries, days)
    social, social_status = fetch_social_scout(social_queries, days)
show_collection_status('Market news', news_status)
show_collection_status('Social coverage', social_status)
t1,t2,t3,t4,t5,t6,t7=st.tabs(['Today','Trend Intelligence','Social Scout','Search Demand','Keywords','Live Radar','Watchlist'])

with t1:
    st.subheader(f'Latest signals · past {days} days'); c1,c2,c3,c4=st.columns(4); c1.metric('Market signals',len(live_news)); c2.metric('Early trends',int((live_news['Signal type']=='🔥 EARLY TREND').sum()) if not live_news.empty else 0); c3.metric('Social signals',len(social)); c4.metric('Core markets',5)
    st.markdown('### Latest market signals')
    if live_news.empty:
        st.info('No recent market signals found in this publication window.' if news_status['successful'] else 'Market news could not be retrieved. Check the collection details above.')
    for _,r in live_news.head(8).iterrows():st.markdown(f"**{r['Signal type']} · {r['Relevance score']}/100 — {r['Headline']}**  \n{r['Published'].strftime('%d %b %Y %H:%M UTC')} · {r['Market']} · {r['Category']} · [source]({r['Link']})")
    if not social.empty:
        st.markdown('### 📱 Social/emerging signals')
        st.dataframe(social.head(8)[['Published','Age (days)','Social relevance','Platform','Headline','Category','Watch term','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Open')})

with t2:
    st.subheader('Trend Intelligence'); st.caption('Newest articles first. Relevance scores reflect watchlist fit and headline wording; they do not measure demand or growth.')
    if not live_news.empty:
        c1,c2,c3=st.columns(3); markets=c1.multiselect('Scout market',sorted(live_news['Market'].unique()),default=sorted(live_news['Market'].unique())); types=c2.multiselect('Signal type',sorted(live_news['Signal type'].unique()),default=sorted(live_news['Signal type'].unique())); minimum=c3.slider('Minimum score',0,100,55); view=live_news[live_news['Market'].isin(markets)&live_news['Signal type'].isin(types)&(live_news['Relevance score']>=minimum)]; st.dataframe(view[['Published','Age (days)','Relevance score','Signal type','Headline','Market','Category','Search signal','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Source')})

with t3:
    st.subheader('Social Scout'); st.caption('Recent Google News coverage mentioning social platforms and toy trends. This does not measure platform views, engagement or growth.')
    if st.button('Refresh social scout'):fetch_social_scout.clear();st.rerun()
    if social.empty:st.info('No recent social coverage found, or sources could not be retrieved. Check collection status above.')
    else:
        c1,c2,c3=st.columns(3); cats=c1.multiselect('Category',sorted(social['Category'].unique()),default=sorted(social['Category'].unique())); platforms=c2.multiselect('Platform/source type',sorted(social['Platform'].unique()),default=sorted(social['Platform'].unique())); minimum=c3.slider('Minimum Social relevance',0,100,50); sv=social[social['Category'].isin(cats)&social['Platform'].isin(platforms)&(social['Social relevance']>=minimum)]; st.dataframe(sv[['Published','Age (days)','Social relevance','Platform','Headline','Category','Watch term','Source','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Open')}); st.info('Next upgrade: direct platform APIs where commercially available. TikTok Research API is restricted to qualifying non-commercial research, so the commercial radar should not depend on it.')

with t4:
    st.subheader('Search Demand'); st.caption('Experimental Google Trends layer. Values are relative interest, not absolute search volume.'); c1,c2=st.columns([1,2]); market=c1.selectbox('Market',CORE_MARKETS); terms=keywords[keywords['Market']==market]['Keyword'].dropna().drop_duplicates().tolist(); selected=c2.multiselect('Compare up to 5 keywords',terms,default=terms[:5],max_selections=5)
    if st.button('Refresh search demand'):fetch_search_demand.clear();st.rerun()
    if selected:
        df,err=fetch_search_demand(tuple(selected),MARKET_GEO[market])
        if err:st.warning(err)
        elif df is None or df.empty:st.info('No data returned. Try broader terms, especially in smaller markets.')
        else:st.line_chart(df,use_container_width=True);st.dataframe(demand_summary(df),use_container_width=True,hide_index=True)

with t5:
    st.subheader('Keyword Watchlist'); st.dataframe(keywords,use_container_width=True,hide_index=True)
with t6:
    st.subheader('Live Market & Launch Radar'); st.dataframe(live_news[['Published','Age (days)','Relevance score','Signal type','Headline','Market','Category','Priority','Search signal','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Source')})
with t7:
    st.subheader('Watchlists'); st.markdown('### Market/news queries');st.dataframe(news_queries,use_container_width=True,hide_index=True);st.markdown('### Social/emerging queries');st.dataframe(social_queries,use_container_width=True,hide_index=True);st.markdown('### Search keyword universe');st.dataframe(keywords,use_container_width=True,hide_index=True)
st.divider();st.caption(f"Radar · news cache up to 1h on app use · search demand cache up to 6h · Page rendered: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

