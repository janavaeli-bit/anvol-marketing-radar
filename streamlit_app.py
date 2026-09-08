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
DATA_DIR=Path(__file__).parent/'data'
MARKET_GEO={'Sweden':'SE','Finland':'FI','Estonia':'EE','Latvia':'LV','Lithuania':'LT'}
CORE_MARKETS=list(MARKET_GEO.keys())

@st.cache_data
def load_csv(name): return pd.read_csv(DATA_DIR/name)

def classify_signal(row):
    text=f"{row['Headline']} {row['Search signal']} {row['Category']}".lower()
    if row['Category']=='Retailer' or any(x in text for x in ['store opening','retailer','kampanj','sale ','promotion','parduotuv','veikals','mänguasjapood']): return '🏪 COMPETITOR'
    if row['Market']=='Asia Trend Scout' or row['Category'] in ['Local Trend','Asia Trends'] or any(x in text for x in ['viral','trend','blind box','collectible','kollek','kolek']): return '🔥 EARLY TREND'
    return '🆕 MARKET NEWS'

def score_signal(row):
    score=35 if row['Priority']=='High' else 20
    if row['Market']=='Asia Trend Scout': score+=20
    if row['Market']=='Global Scout': score+=12
    if row['Market'] in CORE_MARKETS: score+=15
    if row['Category'] in ['Blind Boxes','Collectibles','Asia Trends','Local Trend','Anime','Gaming']: score+=15
    text=f"{row['Headline']} {row['Search signal']}".lower()
    if any(x in text for x in ['launch','new ','collaboration','license','licensed','uued','jaunas','nauji']): score+=8
    if any(x in text for x in ['viral','trend','surge','growing','sold out','tendenc']): score+=12
    return min(score,100)

@st.cache_data(ttl=3600)
def fetch_market_news(queries,max_per_query=3):
    rows=[]
    for _,q in queries.iterrows():
        feed=feedparser.parse(f"https://news.google.com/rss/search?q={quote_plus(str(q['Query']))}&hl=en&gl=US&ceid=US:en")
        for e in feed.entries[:max_per_query]:
            rows.append({'Published':e.get('published',''),'Headline':e.get('title',''),'Market':q['Market'],'Category':q['Category'],'Priority':q['Priority'],'Search signal':q['Query'],'Source':e.get('source',{}).get('title','Google News') if isinstance(e.get('source',{}),dict) else 'Google News','Link':e.get('link','')})
    cols=['Published','Headline','Market','Category','Priority','Search signal','Source','Link']
    if not rows:return pd.DataFrame(columns=cols+['Signal type','Trend Score'])
    df=pd.DataFrame(rows).drop_duplicates(subset=['Headline']); df['Signal type']=df.apply(classify_signal,axis=1); df['Trend Score']=df.apply(score_signal,axis=1)
    return df.sort_values('Trend Score',ascending=False)

@st.cache_data(ttl=3600)
def fetch_social_scout(queries,max_per_query=4):
    rows=[]
    for _,q in queries.iterrows():
        searches=[('YouTube',f"site:youtube.com {q['Query']}"),('TikTok web',f"site:tiktok.com {q['Query']}"),('Social web',f"{q['Query']} viral trend")]
        for platform,search_term in searches:
            feed=feedparser.parse(f"https://news.google.com/rss/search?q={quote_plus(search_term)}&hl=en&gl=US&ceid=US:en")
            for e in feed.entries[:max_per_query]:
                rows.append({'Platform':platform,'Headline':e.get('title',''),'Category':q['Category'],'Priority':q['Priority'],'Watch term':q['Query'],'Source':e.get('source',{}).get('title','Web') if isinstance(e.get('source',{}),dict) else 'Web','Link':e.get('link',''),'Published':e.get('published','')})
    if not rows:return pd.DataFrame(columns=['Platform','Headline','Category','Priority','Watch term','Source','Link','Published','Social Score'])
    df=pd.DataFrame(rows).drop_duplicates(subset=['Headline'])
    def social_score(r):
        text=f"{r['Headline']} {r['Watch term']}".lower(); score=45 if r['Priority']=='High' else 30
        if any(x in text for x in ['viral','trend','million','sold out','obsessed','tiktok','youtube']):score+=20
        if r['Category'] in ['Blind Boxes','Collectibles','Anime','Gaming','Toy Trends']:score+=15
        return min(score,100)
    df['Social Score']=df.apply(social_score,axis=1)
    return df.sort_values('Social Score',ascending=False)

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
live_news=fetch_market_news(news_queries); social=fetch_social_scout(social_queries)
st.title('Anvol Marketing Radar'); st.caption('Early trend, social discovery, search demand, licences and retail intelligence across Nordics & Baltics')
t1,t2,t3,t4,t5,t6,t7=st.tabs(['Today','Trend Intelligence','Social Scout','Search Demand','Keywords','Live Radar','Watchlist'])

with t1:
    st.subheader('Today'); c1,c2,c3,c4=st.columns(4); c1.metric('Market signals',len(live_news)); c2.metric('Early trends',int((live_news['Signal type']=='🔥 EARLY TREND').sum()) if not live_news.empty else 0); c3.metric('Social signals',len(social)); c4.metric('Core markets',5)
    st.markdown('### 🔥 What deserves attention first')
    for _,r in live_news.head(8).iterrows():st.markdown(f"**{r['Signal type']} · {r['Trend Score']}/100 — {r['Headline']}**  \n{r['Market']} · {r['Category']} · [source]({r['Link']})")
    if not social.empty:
        st.markdown('### 📱 Social/emerging signals')
        st.dataframe(social.head(8)[['Social Score','Platform','Headline','Category','Watch term','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Open')})

with t2:
    st.subheader('Trend Intelligence'); st.caption('Weak-signal discovery: use high scores as leads to investigate, not proof of demand.')
    if not live_news.empty:
        c1,c2,c3=st.columns(3); markets=c1.multiselect('Scout market',sorted(live_news['Market'].unique()),default=sorted(live_news['Market'].unique())); types=c2.multiselect('Signal type',sorted(live_news['Signal type'].unique()),default=sorted(live_news['Signal type'].unique())); minimum=c3.slider('Minimum score',0,100,55); view=live_news[live_news['Market'].isin(markets)&live_news['Signal type'].isin(types)&(live_news['Trend Score']>=minimum)]; st.dataframe(view[['Trend Score','Signal type','Headline','Market','Category','Search signal','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Source')})

with t3:
    st.subheader('Social Scout'); st.caption('Discovery layer for social-web signals around toys, collectibles, gaming and licences. This is not yet direct TikTok engagement data.')
    if st.button('Refresh social scout'):fetch_social_scout.clear();st.rerun()
    if social.empty:st.info('No social-web signals returned in this refresh.')
    else:
        c1,c2,c3=st.columns(3); cats=c1.multiselect('Category',sorted(social['Category'].unique()),default=sorted(social['Category'].unique())); platforms=c2.multiselect('Platform/source type',sorted(social['Platform'].unique()),default=sorted(social['Platform'].unique())); minimum=c3.slider('Minimum Social Score',0,100,50); sv=social[social['Category'].isin(cats)&social['Platform'].isin(platforms)&(social['Social Score']>=minimum)]; st.dataframe(sv[['Social Score','Platform','Headline','Category','Watch term','Source','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Open')}); st.info('Next upgrade: direct platform APIs where commercially available. TikTok Research API is restricted to qualifying non-commercial research, so the commercial radar should not depend on it.')

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
    st.subheader('Live Market & Launch Radar'); st.dataframe(live_news[['Trend Score','Signal type','Headline','Market','Category','Priority','Search signal','Link']],use_container_width=True,hide_index=True,column_config={'Link':st.column_config.LinkColumn('Source')})
with t7:
    st.subheader('Watchlists'); st.markdown('### Market/news queries');st.dataframe(news_queries,use_container_width=True,hide_index=True);st.markdown('### Social/emerging queries');st.dataframe(social_queries,use_container_width=True,hide_index=True);st.markdown('### Search keyword universe');st.dataframe(keywords,use_container_width=True,hide_index=True)
st.divider();st.caption(f"Radar · public feeds hourly · search demand 6h cache · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
