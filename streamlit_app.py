import streamlit as st
import pandas as pd
import feedparser
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime, timezone

st.set_page_config(page_title="Anvol Marketing Radar", page_icon="📈", layout="wide")
DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_keywords():
    return pd.read_csv(DATA_DIR / "keywords.csv")

@st.cache_data
def load_launches():
    return pd.read_csv(DATA_DIR / "launches.csv")

@st.cache_data
def load_news_queries():
    return pd.read_csv(DATA_DIR / "news_queries.csv")

@st.cache_data(ttl=3600)
def fetch_market_news(queries, max_per_query=4):
    rows = []
    for _, q in queries.iterrows():
        search = quote_plus(str(q["Query"]))
        url = f"https://news.google.com/rss/search?q={search}&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_per_query]:
            published = entry.get("published", "")
            rows.append({
                "Published": published,
                "Headline": entry.get("title", ""),
                "Market": q["Market"],
                "Category": q["Category"],
                "Priority": q["Priority"],
                "Search signal": q["Query"],
                "Source": entry.get("source", {}).get("title", "Google News") if isinstance(entry.get("source", {}), dict) else "Google News",
                "Link": entry.get("link", ""),
            })
    if not rows:
        return pd.DataFrame(columns=["Published", "Headline", "Market", "Category", "Priority", "Search signal", "Source", "Link"])
    df = pd.DataFrame(rows).drop_duplicates(subset=["Headline", "Market"])
    return df

keywords = load_keywords()
launches = load_launches()
news_queries = load_news_queries()

st.title("Anvol Marketing Radar")
st.caption("Toy, collectible and retail signals for Sweden & Finland")

tab1, tab2, tab3, tab4 = st.tabs(["Today", "Keywords", "Live Radar", "Watchlist"])

with tab1:
    st.subheader("Today")
    live_news = fetch_market_news(news_queries)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Keywords watched", len(keywords))
    c2.metric("High-priority keywords", int((keywords["Priority"] == "High").sum()))
    c3.metric("Live signals", len(live_news))
    c4.metric("Markets", keywords["Market"].nunique())

    st.markdown("### Priority watchlist")
    high_priority = keywords[keywords["Priority"] == "High"].copy()
    st.dataframe(high_priority[["Keyword", "Brand", "Category", "Market", "Type"]], use_container_width=True, hide_index=True)

    st.markdown("### Latest high-priority market signals")
    if live_news.empty:
        st.warning("No live news could be loaded right now. Try refreshing later.")
    else:
        priority_news = live_news[live_news["Priority"] == "High"].head(12)
        for _, row in priority_news.iterrows():
            st.markdown(f"**{row['Headline']}**  \n{row['Market']} · {row['Category']} · signal: {row['Search signal']}  \n[Open source]({row['Link']})")

with tab2:
    st.subheader("Keyword Watchlist")
    market_options = sorted(keywords["Market"].dropna().unique().tolist())
    category_options = sorted(keywords["Category"].dropna().unique().tolist())
    priority_options = sorted(keywords["Priority"].dropna().unique().tolist())
    c1, c2, c3 = st.columns(3)
    selected_market = c1.multiselect("Market", market_options, default=market_options)
    selected_category = c2.multiselect("Category", category_options, default=category_options)
    selected_priority = c3.multiselect("Priority", priority_options, default=priority_options)
    filtered = keywords[keywords["Market"].isin(selected_market) & keywords["Category"].isin(selected_category) & keywords["Priority"].isin(selected_priority)]
    search = st.text_input("Search keywords or brands")
    if search:
        filtered = filtered[filtered["Keyword"].str.contains(search, case=False, na=False) | filtered["Brand"].str.contains(search, case=False, na=False)]
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button("Download filtered watchlist", filtered.to_csv(index=False).encode("utf-8"), file_name="keyword_watchlist.csv", mime="text/csv")

with tab3:
    st.subheader("Live Market & Launch Radar")
    st.caption("Live public-news signals based on the watch queries. Results are cached for one hour.")
    if st.button("Refresh radar"):
        fetch_market_news.clear()
        st.rerun()
    live_news = fetch_market_news(news_queries)
    c1, c2 = st.columns(2)
    selected_markets = c1.multiselect("Market", sorted(news_queries["Market"].unique()), default=sorted(news_queries["Market"].unique()), key="news_market")
    selected_priorities = c2.multiselect("Priority", sorted(news_queries["Priority"].unique()), default=sorted(news_queries["Priority"].unique()), key="news_priority")
    display_news = live_news[live_news["Market"].isin(selected_markets) & live_news["Priority"].isin(selected_priorities)] if not live_news.empty else live_news
    if display_news.empty:
        st.warning("No live signals are available right now.")
    else:
        st.dataframe(display_news[["Headline", "Market", "Category", "Priority", "Search signal", "Source", "Link"]], use_container_width=True, hide_index=True, column_config={"Link": st.column_config.LinkColumn("Source link")})
    st.info("This is the first live layer. A news mention is a signal, not proof of consumer demand. Next we can add search-volume/trend data and score the signals together.")

with tab4:
    st.subheader("Radar Watchlist")
    st.caption("These searches currently drive the live radar. We can expand or narrow them at any time.")
    st.dataframe(news_queries, use_container_width=True, hide_index=True)
    st.markdown("### Current keyword universe")
    st.dataframe(keywords, use_container_width=True, hide_index=True)

st.divider()
st.caption(f"Radar app · live feeds refresh hourly · viewed {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
