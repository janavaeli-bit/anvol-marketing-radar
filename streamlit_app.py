import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Anvol Marketing Radar",
    page_icon="📈",
    layout="wide"
)

DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_keywords():
    return pd.read_csv(DATA_DIR / "keywords.csv")

@st.cache_data
def load_launches():
    return pd.read_csv(DATA_DIR / "launches.csv")

keywords = load_keywords()
launches = load_launches()

st.title("Anvol Marketing Radar")
st.caption("Starter version — keyword watchlist and launch radar")

tab1, tab2, tab3 = st.tabs(["Today", "Keywords", "Launches"])

with tab1:
    st.subheader("Today")
    c1, c2, c3 = st.columns(3)
    c1.metric("Keywords watched", len(keywords))
    c2.metric("High-priority keywords", int((keywords["Priority"] == "High").sum()))
    c3.metric("Launch signals", len(launches))

    st.markdown("### High-priority watchlist")
    high_priority = keywords[keywords["Priority"] == "High"].copy()
    st.dataframe(
        high_priority[["Keyword", "Brand", "Category", "Market"]],
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        "Next step: connect live sources so this page can show rising searches, "
        "new launches and daily marketing opportunities automatically."
    )

with tab2:
    st.subheader("Keyword Watchlist")

    market_options = sorted(keywords["Market"].dropna().unique().tolist())
    category_options = sorted(keywords["Category"].dropna().unique().tolist())
    priority_options = sorted(keywords["Priority"].dropna().unique().tolist())

    c1, c2, c3 = st.columns(3)
    selected_market = c1.multiselect("Market", market_options, default=market_options)
    selected_category = c2.multiselect("Category", category_options, default=category_options)
    selected_priority = c3.multiselect("Priority", priority_options, default=priority_options)

    filtered = keywords[
        keywords["Market"].isin(selected_market)
        & keywords["Category"].isin(selected_category)
        & keywords["Priority"].isin(selected_priority)
    ]

    search = st.text_input("Search keywords or brands")
    if search:
        mask = (
            filtered["Keyword"].str.contains(search, case=False, na=False)
            | filtered["Brand"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered watchlist",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="keyword_watchlist.csv",
        mime="text/csv",
    )

with tab3:
    st.subheader("Launch Radar")
    st.caption("Manual starter feed. Later this can be populated automatically from selected online sources.")

    market_filter = st.multiselect(
        "Market",
        sorted(launches["Market"].dropna().unique()),
        default=sorted(launches["Market"].dropna().unique()),
        key="launch_market",
    )

    launch_filtered = launches[launches["Market"].isin(market_filter)]
    st.dataframe(launch_filtered, use_container_width=True, hide_index=True)

    st.markdown("### What we will automate next")
    st.markdown(
        """
        - Detect new toy/product launches and collaborations
        - Flag rising search demand by market
        - Rank signals by priority
        - Create a daily 'what changed?' summary
        - Later compare external demand with sales and marketing performance
        """
    )
