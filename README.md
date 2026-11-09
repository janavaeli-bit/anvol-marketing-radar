# Anvol Marketing Radar

A simple internal starter dashboard for monitoring marketing-relevant keywords and product/launch signals.

## Current behavior

- News and social coverage default to a 7-day publication window, with 30/90-day options.
- Dates are validated in UTC. Old, undated, invalid and future-dated entries are excluded.
- Newest stories appear first. Relevance scores describe watchlist fit and headline wording, not measured demand or growth.
- Publication dates, article age, feed success counts and actual successful retrieval timestamps are visible.
- Individual feed failures are reported without discarding successful feeds. A valid empty feed is distinguished from a failed request.
- Google News searches include a time window; Swedish and Finnish searches use local editions. Baltic/global discovery currently uses the English edition and the configured search terms.
- Social Scout monitors Google News coverage, not direct platform engagement.
- Public feeds are cached for up to one hour on app use; a refresh button clears both news caches. This is not a background hourly scheduler.
- Google Trends remains experimental with a six-hour cache.

No internal sales, advertising or confidential data is connected.

## Validation

```bash
python -m unittest -v test_radar_news
```

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

## Future improvements

Add curated brand/trade/retailer feeds, additional local-language queries and an independent scheduled collector with persistent first-seen history. These are not enabled by the freshness fix.
