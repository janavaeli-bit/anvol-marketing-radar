# Anvol Marketing Radar

A simple internal starter dashboard for monitoring marketing-relevant keywords and product/launch signals.

## What this first version does

- Shows a keyword watchlist
- Filters by market, category and priority
- Shows a manual launch radar
- Creates a simple "Today" overview

No internal sales, advertising or confidential data is connected yet.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy with Streamlit Community Cloud

1. Push these files to a private GitHub repository.
2. Sign in to Streamlit Community Cloud with GitHub.
3. Create a new app.
4. Select repository: `anvol-marketing-radar`
5. Select branch: `main`
6. Main file path: `streamlit_app.py`
7. Deploy.

## Suggested next development step

Add a live external-data collector for:
- launch/news monitoring
- search-demand signals
- country-specific trend tracking

After that, connect Google Search Console / Google Ads data, then internal sales data.
