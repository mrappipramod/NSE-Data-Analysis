import streamlit as st
import pandas as pd
import yfinance as yf
import datetime as dt
import plotly.express as px

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="NSE Stock Analyzer",
    page_icon="📈",
    layout="wide"
)

# =====================================================
# SAFE DATA LOADER
# =====================================================

@st.cache_data(ttl=3600)
def load_stock(symbol, start_date, end_date):

    df = yf.download(
        f"{symbol}.NS",
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False,
        threads=False
    )

    # empty check
    if df is None or df.empty:
        return None

    # fix multi-index columns (common Streamlit/Yahoo issue)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    # clean column names
    df.columns = [str(c).strip() for c in df.columns]

    return df


# =====================================================
# SAFE STATS CALCULATION (FIXED YOUR ERROR)
# =====================================================

def calculate_stats(df):

    if df is None or len(df) < 2:
        return None

    # SAFE scalar extraction (FIX FOR YOUR ERROR)
    start_price = float(pd.to_numeric(df["Close"].iloc[0], errors="coerce"))
    end_price = float(pd.to_numeric(df["Close"].iloc[-1], errors="coerce"))

    if pd.isna(start_price) or pd.isna(end_price):
        return None

    return_pct = ((end_price - start_price) / start_price) * 100

    return {
        "Return %": round(return_pct, 2),
        "High": round(float(df["High"].max()), 2),
        "Low": round(float(df["Low"].min()), 2),
        "Avg Volume": int(df["Volume"].fillna(0).mean())
    }


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("📊 Settings")

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
    "BAJFINAJ"
]

selected_stocks = st.sidebar.multiselect(
    "Select Stocks",
    stocks,
    default=["RELIANCE", "TCS"]
)

start_date = st.sidebar.date_input(
    "Start Date",
    dt.date.today() - dt.timedelta(days=180)
)

end_date = st.sidebar.date_input(
    "End Date",
    dt.date.today()
)

# =====================================================
# TITLE
# =====================================================

st.title("📈 NSE Stock Analyzer (Stable Version)")
st.caption("Yahoo Finance based analysis with safe production-grade handling")

# =====================================================
# RUN ANALYSIS
# =====================================================

if st.button("🚀 Run Analysis"):

    if len(selected_stocks) == 0:
        st.warning("Please select at least one stock.")
        st.stop()

    if start_date >= end_date:
        st.error("Start date must be before end date.")
        st.stop()

    results = []
    progress = st.progress(0)

    for i, stock in enumerate(selected_stocks):

        df = load_stock(stock, start_date, end_date)

        stats = calculate_stats(df)

        if df is not None and stats is not None:

            results.append({
                "Stock": stock,
                **stats
            })

        progress.progress((i + 1) / len(selected_stocks))

    if len(results) == 0:
        st.error("No valid stock data found.")
        st.stop()

    result_df = pd.DataFrame(results)

    result_df = result_df.sort_values(
        "Return %",
        ascending=False
    )

    # =====================================================
    # METRICS
    # =====================================================

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Stocks", len(result_df))
    c2.metric("Best Return", f"{result_df['Return %'].max():.2f}%")
    c3.metric("Worst Return", f"{result_df['Return %'].min():.2f}%")
    c4.metric("Avg Return", f"{result_df['Return %'].mean():.2f}%")

    st.divider()

    # =====================================================
    # TABLE
    # =====================================================

    st.subheader("🏆 Performance Ranking")

    st.dataframe(result_df, use_container_width=True)

    # =====================================================
    # DOWNLOAD CSV
    # =====================================================

    csv = result_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download CSV",
        csv,
        "stock_analysis.csv",
        "text/csv"
    )

    # =====================================================
    # BAR CHART
    # =====================================================

    st.subheader("📊 Returns Comparison")

    fig = px.bar(
        result_df,
        x="Stock",
        y="Return %",
        title="Stock Performance"
    )

    st.plotly_chart(fig, use_container_width=True)

    # =====================================================
    # INDIVIDUAL STOCK CHARTS
    # =====================================================

    st.subheader("📈 Stock Price Charts")

    for stock in selected_stocks:

        df = load_stock(stock, start_date, end_date)

        if df is None:
            continue

        fig = px.line(
            df,
            x="Date",
            y="Close",
            title=f"{stock} Price Trend"
        )

        st.plotly_chart(fig, use_container_width=True)

        with st.expander(f"📁 Raw Data - {stock}"):

            st.dataframe(df.tail(100), use_container_width=True)
