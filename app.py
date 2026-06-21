import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ==============================
# PAGE
# ==============================

st.set_page_config(
    page_title="Fundamental Stock Analyzer PRO",
    layout="wide"
)

st.title("📊 NSE Fundamental Analysis PRO")
st.caption("Deep financial analysis (Valuation + Growth + Stability)")

# ==============================
# DATA
# ==============================

@st.cache_data(ttl=3600)
def get_data(symbol):

    stock = yf.Ticker(symbol + ".NS")
    info = stock.info

    try:
        financials = stock.financials
    except:
        financials = None

    return info, financials

# ==============================
# SAFE VALUE HELPER
# ==============================

def safe(val):
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return val
    return 0

# ==============================
# SCORE ENGINE (REAL FUNDAMENTAL MODEL)
# ==============================

def score_stock(info):

    score = 0
    notes = []

    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    roe = safe(info.get("returnOnEquity")) * 100
    roe = roe if roe else 0

    debt = info.get("debtToEquity") or 0
    profit_margin = safe(info.get("profitMargins")) * 100

    revenue_growth = safe(info.get("revenueGrowth")) * 100
    earnings_growth = safe(info.get("earningsGrowth")) * 100

    # ---------------- VALUATION (25)
    if pe and pe > 0:
        if pe < 20:
            score += 10
        elif pe < 35:
            score += 5
        else:
            score -= 5

    if pb and pb < 3:
        score += 10

    # ---------------- PROFITABILITY (25)
    if roe > 15:
        score += 15
        notes.append("Strong ROE")

    if profit_margin > 10:
        score += 10
        notes.append("Healthy margin")

    # ---------------- STABILITY (25)
    if debt < 1:
        score += 20
        notes.append("Low debt")

    # ---------------- GROWTH (25)
    if revenue_growth > 10:
        score += 10
    if earnings_growth > 10:
        score += 15
        notes.append("Strong earnings growth")

    # FINAL SCORE CAP
    score = max(0, min(100, score))

    return score, notes

# ==============================
# STOCK LIST
# ==============================

stocks = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK",
    "ICICIBANK", "SBIN", "ITC", "LT",
    "AXISBANK", "BAJFINAJ"
]

selected = st.multiselect(
    "Select Stocks",
    stocks,
    default=["RELIANCE", "TCS"]
)

# ==============================
# RUN
# ==============================

if st.button("📊 Run Deep Fundamental Analysis"):

    results = []

    progress = st.progress(0)

    for i, s in enumerate(selected):

        info, fin = get_data(s)

        if not info:
            continue

        score, notes = score_stock(info)

        # BUY / HOLD / SELL logic
        if score >= 70:
            rating = "🟢 BUY"
        elif score >= 45:
            rating = "🟡 HOLD"
        else:
            rating = "🔴 AVOID"

        results.append({
            "Stock": s,
            "Sector": info.get("sector"),
            "PE": info.get("trailingPE"),
            "PB": info.get("priceToBook"),
            "ROE %": round(safe(info.get("returnOnEquity")) * 100, 2),
            "Debt/Equity": info.get("debtToEquity"),
            "Profit Margin %": round(safe(info.get("profitMargins")) * 100, 2),
            "Revenue Growth %": round(safe(info.get("revenueGrowth")) * 100, 2),
            "Earnings Growth %": round(safe(info.get("earningsGrowth")) * 100, 2),
            "Score": score,
            "Rating": rating,
            "Strengths": ", ".join(notes)
        })

        progress.progress((i + 1) / len(selected))

    df = pd.DataFrame(results)

    df = df.sort_values("Score", ascending=False)

    # ==============================
    # METRICS
    # ==============================

    c1, c2, c3 = st.columns(3)

    c1.metric("Stocks", len(df))
    c2.metric("Best Score", df["Score"].max())
    c3.metric("Avg Score", round(df["Score"].mean(), 2))

    st.divider()

    # ==============================
    # TABLE
    # ==============================

    st.subheader("🏆 Fundamental Ranking")

    st.dataframe(df, use_container_width=True)

    # ==============================
    # TOP STOCK
    # ==============================

    top = df.iloc[0]

    st.success(
        f"""
        ⭐ **Best Stock: {top['Stock']}**
        Score: {top['Score']}
        Rating: {top['Rating']}
        Strengths: {top['Strengths']}
        """
    )

    # ==============================
    # DOWNLOAD
    # ==============================

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Report",
        csv,
        "fundamental_pro_analysis.csv",
        "text/csv"
    )
