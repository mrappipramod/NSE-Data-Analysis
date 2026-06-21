import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Fundamental Screener PRO", layout="wide")

st.title("📊 NSE Fundamental Screener PRO")
st.caption("With custom search + Nifty universe filtering")

# =====================================================
# STOCK UNIVERSES (CLEAN + NON DUPLICATE)
# =====================================================

NIFTY_50 = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN",
    "ITC","LT","AXISBANK","BAJFINANCE","KOTAKBANK","HINDUNILVR",
    "ASIANPAINT","MARUTI","SUNPHARMA","TITAN","ULTRACEMCO",
    "NESTLEIND","WIPRO","POWERGRID","NTPC","ONGC","COALINDIA"
]

MIDCAP = [
    "AUBANK","DMART","VBL","SRF","PIIND","BERGEPAINT",
    "GODREJCP","MUTHOOTFIN","NAUKRI","TORNTPHARM"
]

SMALLCAP = [
    "IRCTC","KPITTECH","RVNL","HAL","BEL","POLYCAB",
    "LTIM","OFSS","PAGEIND","CONCOR"
]

# =====================================================
# CUSTOM SEARCH INPUT
# =====================================================

st.sidebar.header("🔎 Stock Universe Builder")

search_input = st.sidebar.text_input(
    "Custom Stock (comma separated)",
    placeholder="e.g. RELIANCE, TCS, INFY"
)

use_nifty50 = st.sidebar.checkbox("Include Nifty 50", True)
use_midcap = st.sidebar.checkbox("Include Midcap")
use_smallcap = st.sidebar.checkbox("Include Smallcap")

# =====================================================
# BUILD FINAL LIST (NO DUPLICATES)
# =====================================================

final_stocks = []

if use_nifty50:
    final_stocks += NIFTY_50

if use_midcap:
    final_stocks += MIDCAP

if use_smallcap:
    final_stocks += SMALLCAP

# Custom user input
if search_input:
    custom = [x.strip().upper() for x in search_input.split(",")]
    final_stocks += custom

# REMOVE DUPLICATES (IMPORTANT FIX)
final_stocks = sorted(list(set(final_stocks)))

# =====================================================
# MULTI SELECT UI
# =====================================================

selected = st.multiselect(
    "Select Stocks to Analyze",
    final_stocks,
    default=final_stocks[:5]
)

st.write(f"Total Universe Size: {len(final_stocks)} stocks")

# =====================================================
# DATA LOADER
# =====================================================

@st.cache_data(ttl=3600)
def get_data(symbol):

    stock = yf.Ticker(symbol + ".NS")
    return stock.info

# =====================================================
# SCORE ENGINE (IMPROVED)
# =====================================================

def score(info):

    score = 0

    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    roe = (info.get("returnOnEquity") or 0) * 100
    debt = info.get("debtToEquity") or 0
    margin = (info.get("profitMargins") or 0) * 100

    growth = (info.get("earningsGrowth") or 0) * 100

    # valuation
    if pe and pe > 0:
        if pe < 20: score += 15
        elif pe < 35: score += 8

    if pb and pb < 3:
        score += 10

    # profitability
    if roe > 15:
        score += 20

    if margin > 10:
        score += 15

    # stability
    if debt < 1:
        score += 15

    # growth
    if growth > 10:
        score += 25

    return min(score, 100)

# =====================================================
# RUN
# =====================================================

if st.button("📊 Run Analysis"):

    results = []
    progress = st.progress(0)

    for i, stock in enumerate(selected):

        try:
            info = get_data(stock)
        except:
            continue

        if not info:
            continue

        s = score(info)

        if s >= 70:
            rating = "🟢 STRONG BUY"
        elif s >= 50:
            rating = "🟡 HOLD"
        else:
            rating = "🔴 AVOID"

        results.append({
            "Stock": stock,
            "Sector": info.get("sector"),
            "PE": info.get("trailingPE"),
            "PB": info.get("priceToBook"),
            "ROE %": round((info.get("returnOnEquity") or 0)*100,2),
            "Debt/Equity": info.get("debtToEquity"),
            "Margin %": round((info.get("profitMargins") or 0)*100,2),
            "Growth %": round((info.get("earningsGrowth") or 0)*100,2),
            "Score": s,
            "Rating": rating
        })

        progress.progress((i+1)/len(selected))

    df = pd.DataFrame(results)

    if df.empty:
        st.error("No data found")
        st.stop()

    df = df.sort_values("Score", ascending=False)

    # =================================================
    # OUTPUT
    # =================================================

    st.subheader("🏆 Ranking")

    st.dataframe(df, use_container_width=True)

    st.success(
        f"Top Stock: {df.iloc[0]['Stock']} | Score: {df.iloc[0]['Score']}"
    )

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Report",
        csv,
        "nse_fundamental_report.csv",
        "text/csv"
    )
