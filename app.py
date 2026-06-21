import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="NSE Fundamental Analyzer",
    page_icon="📊",
    layout="wide"
)

st.title("📊 NSE Fundamental Stock Analyzer")
st.caption("Fundamental analysis using Yahoo Finance financial data")

# =====================================================
# DATA LOADER
# =====================================================

@st.cache_data(ttl=3600)
def get_fundamentals(symbol):

    try:
        stock = yf.Ticker(symbol + ".NS")

        info = stock.info

        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow

        return info, financials, balance_sheet, cashflow

    except Exception:
        return None, None, None, None


# =====================================================
# FUNDAMENTAL SCORE CALCULATION
# =====================================================

def calculate_score(info):

    score = 0
    reasons = []

    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    roe = info.get("returnOnEquity")
    debt_to_equity = info.get("debtToEquity")
    profit_margin = info.get("profitMargins")

    # PE Ratio
    if pe and pe > 0:
        if pe < 20:
            score += 25
            reasons.append("Good PE ratio")
        elif pe < 35:
            score += 15
        else:
            score -= 10

    # PB Ratio
    if pb and pb < 3:
        score += 20
        reasons.append("Good Price/Book value")

    # ROE
    if roe:
        roe_pct = roe * 100
        if roe_pct > 15:
            score += 25
            reasons.append("Strong ROE")

    # Debt to Equity
    if debt_to_equity is not None:
        if debt_to_equity < 1:
            score += 15
        else:
            score -= 10

    # Profit margin
    if profit_margin:
        if profit_margin > 0.1:
            score += 15
            reasons.append("Healthy profit margin")

    return score, reasons


# =====================================================
# STOCK LIST
# =====================================================

stocks = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "ITC",
    "LT",
    "AXISBANK",
    "BAJFINANCE",
    "HCLTECH",
    "WIPRO"
]

selected = st.multiselect(
    "Select Stocks",
    stocks,
    default=["RELIANCE", "TCS"]
)

# =====================================================
# RUN BUTTON
# =====================================================

if st.button("📊 Analyze Fundamentals"):

    results = []

    progress = st.progress(0)

    for i, stock in enumerate(selected):

        info, fin, bs, cf = get_fundamentals(stock)

        if not info:
            continue

        score, reasons = calculate_score(info)

        results.append({
            "Stock": stock,
            "Sector": info.get("sector"),
            "PE Ratio": info.get("trailingPE"),
            "PB Ratio": info.get("priceToBook"),
            "ROE": round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None,
            "Debt/Equity": info.get("debtToEquity"),
            "Profit Margin": round(info.get("profitMargins", 0) * 100, 2) if info.get("profitMargins") else None,
            "Market Cap": info.get("marketCap"),
            "Fundamental Score": score,
            "Strengths": ", ".join(reasons)
        })

        progress.progress((i + 1) / len(selected))

    if not results:
        st.error("No data found for selected stocks")
        st.stop()

    df = pd.DataFrame(results)

    df = df.sort_values("Fundamental Score", ascending=False)

    # =====================================================
    # METRICS
    # =====================================================

    c1, c2, c3 = st.columns(3)

    c1.metric("Stocks Analyzed", len(df))
    c2.metric("Best Score", df["Fundamental Score"].max())
    c3.metric("Avg Score", round(df["Fundamental Score"].mean(), 2))

    st.divider()

    # =====================================================
    # TABLE
    # =====================================================

    st.subheader("🏆 Fundamental Ranking")

    st.dataframe(df, use_container_width=True)

    # =====================================================
    # BEST STOCK
    # =====================================================

    st.subheader("⭐ Top Fundamental Stock")

    best = df.iloc[0]

    st.success(
        f"""
        **{best['Stock']}**

        Score: {best['Fundamental Score']}

        Strengths: {best['Strengths']}
        """
    )

    # =====================================================
    # DOWNLOAD
    # =====================================================

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Report",
        csv,
        "fundamental_analysis.csv",
        "text/csv"
    )
