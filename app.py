"""
main.py
=======
NSE Fundamental Analysis PRO — Enterprise Screener
Entry point. Run with: streamlit run app/main.py
"""

import sys
from pathlib import Path

# Make `utils/` importable when run as `streamlit run app/main.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np

from utils.data_fetcher import load_universe, fetch_universe, YFinanceSource
from utils.scoring_engine import composite_score, safe
from utils.valuation import simple_dcf, graham_number, relative_valuation, blended_intrinsic_value
from utils.peer_comparison import compute_sector_medians, attach_peer_context, get_sector_median
from utils.trend_analysis import compute_trends

st.set_page_config(
    page_title="NSE Fundamental Screener PRO",
    page_icon="📊",
    layout="wide",
)

st.title("📊 NSE Fundamental Analysis — Enterprise Screener")
st.caption(
    "Full-universe fundamental screening: valuation, profitability, stability, "
    "multi-year growth trends, DCF/intrinsic value, and sector peer comparison."
)

with st.expander("ℹ️ Methodology & honest limitations — please read before trusting the scores"):
    st.markdown(
        """
**Data source:** Yahoo Finance (`yfinance`), an unofficial API. It is generally reliable for
large/mid-cap NSE stocks but can have missing fields, especially for banks/NBFCs
(different statement structure) and recently-listed companies (short history).

**Scoring (0-100):** Five weighted pillars — Valuation (20), Profitability (20),
Stability (20), Growth & Trend (25), Valuation Upside (15). Each pillar is shown
separately in the deep-dive view so the total is never a black box.

**Intrinsic value / DCF:** Built from 2-4 years of public cash flow data with generic
growth/discount-rate assumptions. This is a *directional estimate*, not a price target.
Treat "undervalued by X%" as "worth a closer look," not as investment advice.

**This tool is for research/educational purposes only and is not investment advice.**
        """
    )

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------

st.sidebar.header("⚙️ Screener Settings")

universe_choice = st.sidebar.radio(
    "Universe",
    ["Nifty 50 (fast)", "Nifty 500 (full — slower)", "Custom list"],
    index=0,
)

if universe_choice == "Custom list":
    custom_input = st.sidebar.text_area(
        "Enter NSE symbols (comma-separated, no .NS suffix)",
        value="RELIANCE, TCS, INFY",
    )
    symbols_requested = [s.strip().upper() for s in custom_input.split(",") if s.strip()]
    universe_df = pd.DataFrame({"Symbol": symbols_requested, "Company Name": symbols_requested, "Industry": "Unknown"})
else:
    index_key = "NIFTY50" if universe_choice.startswith("Nifty 50") else "NIFTY500"
    try:
        universe_df = load_universe(index_key)
    except Exception as e:
        st.sidebar.error(f"Failed to load universe list: {e}")
        st.stop()

max_stocks = st.sidebar.slider(
    "Max stocks to analyze this run",
    min_value=5,
    max_value=min(500, len(universe_df)),
    value=min(50, len(universe_df)),
    step=5,
    help="Nifty 500 full run can take a long time on first fetch (no cache yet) due to yfinance rate limits. "
         "Subsequent runs reuse the 6-hour disk cache and are much faster.",
)

sector_filter = st.sidebar.multiselect(
    "Filter by Industry (optional)",
    sorted(universe_df["Industry"].dropna().unique().tolist()) if "Industry" in universe_df.columns else [],
)

use_cache = st.sidebar.checkbox("Use cached data (6hr TTL)", value=True)

st.sidebar.markdown("---")
st.sidebar.caption(f"Universe loaded: **{len(universe_df)}** symbols")

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

filtered_df = universe_df.copy()
if sector_filter:
    filtered_df = filtered_df[filtered_df["Industry"].isin(sector_filter)]

filtered_df = filtered_df.head(max_stocks)
selected_symbols = filtered_df["Symbol"].tolist()

st.write(f"**{len(selected_symbols)} stocks** selected for analysis.")

run = st.button("🚀 Run Deep Fundamental Analysis", type="primary")

# ---------------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------------

if run:
    if not selected_symbols:
        st.warning("No symbols selected.")
        st.stop()

    progress_bar = st.progress(0, text="Starting...")
    status_text = st.empty()

    def _progress(done, total, symbol):
        progress_bar.progress(done / total, text=f"Fetching {symbol} ({done}/{total})")

    source = YFinanceSource()
    fetch_results = fetch_universe(selected_symbols, source=source, progress_callback=_progress, use_cache=use_cache)

    progress_bar.progress(1.0, text="Fetch complete. Running analysis...")

    rows = []
    failures = []
    deep_data = {}  # symbol -> dict of everything needed for deep-dive / peer comparison later

    for symbol in selected_symbols:
        fr = fetch_results[symbol]
        if not fr.ok:
            failures.append((symbol, fr.error))
            continue

        info = fr.info
        trends = compute_trends(fr.financials)

        dcf = simple_dcf(fr.cashflow, info, growth_rate_yr1_5=trends.get("revenue_cagr"))
        graham = graham_number(info)
        # Sector median PE/PB filled in after first pass (need full df first) — placeholder for now
        relative = relative_valuation(info, None, None)
        blended = blended_intrinsic_value(dcf, graham, relative)

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if blended.get("blended_value") and current_price:
            blended["upside_pct"] = round((blended["blended_value"] - current_price) / current_price * 100, 1)
        else:
            blended["upside_pct"] = None

        result = composite_score(info, fr.financials, blended)

        rows.append({
            "Symbol": symbol,
            "Company": info.get("longName", symbol),
            "Sector": info.get("sector", "Unknown"),
            "Industry": info.get("industry", "Unknown"),
            "Price": current_price,
            "PE": info.get("trailingPE"),
            "PB": info.get("priceToBook"),
            "ROE %": round(safe(info.get("returnOnEquity")) * 100, 2),
            "Debt/Equity": info.get("debtToEquity"),
            "Profit Margin %": round(safe(info.get("profitMargins")) * 100, 2),
            "Revenue CAGR %": round(trends.get("revenue_cagr"), 1) if trends.get("revenue_cagr") is not None else None,
            "Net Income CAGR %": round(trends.get("net_income_cagr"), 1) if trends.get("net_income_cagr") is not None else None,
            "Margin Trend": trends.get("margin_trend"),
            "Blended Fair Value": blended.get("blended_value"),
            "Est. Upside %": blended.get("upside_pct"),
            "Valuation Models Used": blended.get("models_used"),
            "Score": result["total_score"],
            "Rating": result["rating"],
            "Valuation Pillar": result["pillar_scores"]["Valuation"],
            "Profitability Pillar": result["pillar_scores"]["Profitability"],
            "Stability Pillar": result["pillar_scores"]["Stability"],
            "Growth Pillar": result["pillar_scores"]["Growth"],
            "Upside Pillar": result["pillar_scores"]["Valuation Upside"],
            "Strengths": ", ".join(result["notes"][:4]),
        })

        deep_data[symbol] = {
            "info": info, "trends": trends, "dcf": dcf, "graham": graham,
            "result": result, "fetch": fr,
        }

    if not rows:
        st.error("No data could be fetched for any selected symbol. Check network/rate limits and try again.")
        if failures:
            with st.expander("See failure details"):
                st.write(pd.DataFrame(failures, columns=["Symbol", "Error"]))
        st.stop()

    df = pd.DataFrame(rows)

    # Second pass: now that we have the full df, compute proper sector-relative valuation & re-blend
    sector_medians_lookup_pe = df.groupby("Sector")["PE"].median()
    sector_medians_lookup_pb = df.groupby("Sector")["PB"].median()

    for symbol in df["Symbol"]:
        d = deep_data[symbol]
        sector = d["info"].get("sector")
        med_pe = sector_medians_lookup_pe.get(sector)
        med_pb = sector_medians_lookup_pb.get(sector)
        d["relative"] = relative_valuation(d["info"], med_pe, med_pb)
        d["blended"] = blended_intrinsic_value(d["dcf"], d["graham"], d["relative"])
        current_price = d["info"].get("currentPrice") or d["info"].get("regularMarketPrice")
        if d["blended"].get("blended_value") and current_price:
            d["blended"]["upside_pct"] = round((d["blended"]["blended_value"] - current_price) / current_price * 100, 1)

        # Recompute composite score with proper sector-aware valuation pillar + upside pillar
        d["result"] = composite_score(d["info"], d["fetch"].financials, d["blended"], sector_median_pe=med_pe)

    # Update df with refined scores
    df["Score"] = df["Symbol"].map(lambda s: deep_data[s]["result"]["total_score"])
    df["Rating"] = df["Symbol"].map(lambda s: deep_data[s]["result"]["rating"])
    df["Blended Fair Value"] = df["Symbol"].map(lambda s: deep_data[s]["blended"].get("blended_value"))
    df["Est. Upside %"] = df["Symbol"].map(lambda s: deep_data[s]["blended"].get("upside_pct"))

    df = attach_peer_context(df.rename(columns={"Sector": "Sector"}))
    df = df.sort_values("Score", ascending=False).reset_index(drop=True)

    st.session_state["screener_df"] = df
    st.session_state["deep_data"] = deep_data
    st.session_state["failures"] = failures

# ---------------------------------------------------------------------------
# Display results (persisted across reruns via session_state)
# ---------------------------------------------------------------------------

if "screener_df" in st.session_state:
    df = st.session_state["screener_df"]
    deep_data = st.session_state["deep_data"]
    failures = st.session_state["failures"]

    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks Analyzed", len(df))
    c2.metric("Best Score", int(df["Score"].max()) if not df.empty else "—")
    c3.metric("Avg Score", round(df["Score"].mean(), 1) if not df.empty else "—")
    c4.metric("Failed Fetches", len(failures))

    if failures:
        with st.expander(f"⚠️ {len(failures)} symbols failed to fetch"):
            st.dataframe(pd.DataFrame(failures, columns=["Symbol", "Error"]), use_container_width=True)

    st.divider()
    st.subheader("🏆 Fundamental Ranking")

    display_cols = [
        "Symbol", "Company", "Sector", "Score", "Rating", "Price", "PE", "PB", "ROE %",
        "Debt/Equity", "Profit Margin %", "Revenue CAGR %", "Net Income CAGR %",
        "Margin Trend", "Blended Fair Value", "Est. Upside %", "Strengths",
    ]
    display_cols = [c for c in display_cols if c in df.columns]

    st.dataframe(
        df[display_cols],
        use_container_width=True,
        height=500,
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            "Est. Upside %": st.column_config.NumberColumn("Est. Upside %", format="%.1f%%"),
        },
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download Full Report (CSV)", csv, "fundamental_pro_analysis.csv", "text/csv")

    st.divider()

    # -----------------------------------------------------------------
    # Sector overview
    # -----------------------------------------------------------------
    st.subheader("🏭 Sector Comparison")
    sector_medians = compute_sector_medians(df.rename(columns={"Sector": "Sector"}))
    if not sector_medians.empty:
        st.dataframe(sector_medians.round(2), use_container_width=True)
    else:
        st.caption("Not enough sector data to compute medians.")

    st.divider()

    # -----------------------------------------------------------------
    # Deep dive selector
    # -----------------------------------------------------------------
    st.subheader("🔍 Stock Deep Dive")
    selected_stock = st.selectbox("Select a stock for full breakdown", df["Symbol"].tolist())

    if selected_stock:
        d = deep_data[selected_stock]
        info = d["info"]
        result = d["result"]
        trends = d["trends"]
        dcf = d["dcf"]
        graham = d["graham"]
        relative = d.get("relative", {})
        blended = d.get("blended", {})

        st.markdown(f"### {info.get('longName', selected_stock)} ({selected_stock})")
        st.caption(f"{info.get('sector', 'Unknown')} | {info.get('industry', 'Unknown')}")

        pillar_cols = st.columns(5)
        pillars = result["pillar_scores"]
        for col, (name, val) in zip(pillar_cols, pillars.items()):
            max_val = {"Valuation": 20, "Profitability": 20, "Stability": 20, "Growth": 25, "Valuation Upside": 15}[name]
            col.metric(name, f"{val}/{max_val}")

        st.markdown(f"**Overall Score: {result['total_score']}/100 — {result['rating']}**")

        with st.expander("📌 Score notes / key strengths & weaknesses"):
            for n in result["notes"]:
                st.write(f"- {n}")

        st.markdown("#### 📈 Multi-Year Trend")
        tcol1, tcol2 = st.columns(2)
        with tcol1:
            if trends.get("revenue_series") and any(v is not None for v in trends["revenue_series"]):
                st.caption("Revenue (Cr, oldest → newest)")
                st.line_chart(pd.Series([v for v in trends["revenue_series"] if v is not None]))
            else:
                st.caption("Revenue trend data unavailable.")
        with tcol2:
            if trends.get("net_income_series") and any(v is not None for v in trends["net_income_series"]):
                st.caption("Net Income (Cr, oldest → newest)")
                st.line_chart(pd.Series([v for v in trends["net_income_series"] if v is not None]))
            else:
                st.caption("Net income trend data unavailable.")

        st.markdown("#### 💰 Intrinsic Value Estimates")
        vcol1, vcol2, vcol3, vcol4 = st.columns(4)
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        vcol1.metric("Current Price", f"₹{current_price:.2f}" if current_price else "—")

        if dcf.get("fair_value_per_share"):
            vcol2.metric("DCF Fair Value", f"₹{dcf['fair_value_per_share']:.2f}",
                         f"{dcf.get('upside_pct', 0):.1f}%" if dcf.get("upside_pct") is not None else None)
            if dcf.get("warning"):
                vcol2.caption(f"⚠️ {dcf['warning']}")
        else:
            vcol2.metric("DCF Fair Value", "N/A")
            if dcf.get("warning"):
                vcol2.caption(dcf["warning"])

        if graham.get("graham_value"):
            vcol3.metric("Graham Number", f"₹{graham['graham_value']:.2f}",
                         f"{graham.get('upside_pct', 0):.1f}%" if graham.get("upside_pct") is not None else None)
        else:
            vcol3.metric("Graham Number", "N/A")
            if graham.get("warning"):
                vcol3.caption(graham["warning"])

        if blended.get("blended_value"):
            vcol4.metric("Blended Fair Value", f"₹{blended['blended_value']:.2f}",
                         f"{blended.get('upside_pct', 0):.1f}%" if blended.get("upside_pct") is not None else None)
            vcol4.caption(f"Based on {blended['models_used']} model(s), range ₹{blended['low']:.2f}–₹{blended['high']:.2f}")
        else:
            vcol4.metric("Blended Fair Value", "N/A")

        st.caption(
            "⚠️ These are rough model-based estimates from limited public data — treat as a starting "
            "point for further research, not a price target."
        )

        st.markdown("#### 🏭 Peer / Sector Context")
        pcol1, pcol2 = st.columns(2)
        med_pe = get_sector_median(df, info.get("sector"), "PE")
        med_roe = get_sector_median(df, info.get("sector"), "ROE %")
        with pcol1:
            st.write(f"**Sector median PE:** {med_pe:.1f}" if med_pe else "Sector median PE: N/A")
            st.write(f"**This stock's PE:** {info.get('trailingPE', 'N/A')}")
        with pcol2:
            st.write(f"**Sector median ROE:** {med_roe:.1f}%" if med_roe else "Sector median ROE: N/A")
            st.write(f"**This stock's ROE:** {round(safe(info.get('returnOnEquity'))*100, 1)}%")

else:
    st.info("Configure settings in the sidebar and click **Run Deep Fundamental Analysis** to begin.")
