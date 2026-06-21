import streamlit as st
import pandas as pd
import yfinance as yf
import datetime as dt
import plotly.express as px

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="NSE Stock Analyzer",
    page_icon="📈",
    layout="wide"
)

# --------------------------------------------------
# CACHE
# --------------------------------------------------

@st.cache_data(ttl=3600)
def load_stock(symbol, start_date, end_date):
    try:
        df = yf.download(
            f"{symbol}.NS",
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
            threads=False
        )

        if df.empty:
            return None

        df.reset_index(inplace=True)
        return df

    except Exception:
        return None


# --------------------------------------------------
# ANALYSIS
# --------------------------------------------------

def calculate_stats(df):

    start_price = float(df["Close"].iloc[0])
    end_price = float(df["Close"].iloc[-1])

    return_pct = (
        (end_price - start_price)
        / start_price
    ) * 100

    return {
        "Return %": round(return_pct, 2),
        "High": round(float(df["High"].max()), 2),
        "Low": round(float(df["Low"].min()), 2),
        "Avg Volume": int(df["Volume"].mean())
    }


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.header("Settings")

stock_list = [
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
    "WIPRO",
    "TATAMOTORS",
    "MARUTI",
    "HCLTECH",
    "SUNPHARMA"
]

selected_stocks = st.sidebar.multiselect(
    "Select Stocks",
    stock_list,
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

# --------------------------------------------------
# TITLE
# --------------------------------------------------

st.title("📈 NSE Stock Analyzer")

st.write(
    "Analyze NSE stocks using Yahoo Finance historical data."
)

# --------------------------------------------------
# RUN ANALYSIS
# --------------------------------------------------

if st.button("🚀 Analyze"):

    if len(selected_stocks) == 0:
        st.warning("Please select at least one stock.")
        st.stop()

    if start_date >= end_date:
        st.error("Start date must be before end date.")
        st.stop()

    results = []

    progress_bar = st.progress(0)

    for idx, stock in enumerate(selected_stocks):

        df = load_stock(
            stock,
            start_date,
            end_date
        )

        if df is not None:

            stats = calculate_stats(df)

            results.append({
                "Stock": stock,
                **stats
            })

        progress_bar.progress(
            (idx + 1) / len(selected_stocks)
        )

    if len(results) == 0:
        st.error("No stock data found.")
        st.stop()

    result_df = pd.DataFrame(results)

    result_df = result_df.sort_values(
        "Return %",
        ascending=False
    )

    # --------------------------------------------------
    # METRICS
    # --------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Stocks",
        len(result_df)
    )

    c2.metric(
        "Best Return",
        f"{result_df['Return %'].max():.2f}%"
    )

    c3.metric(
        "Worst Return",
        f"{result_df['Return %'].min():.2f}%"
    )

    c4.metric(
        "Average Return",
        f"{result_df['Return %'].mean():.2f}%"
    )

    st.divider()

    # --------------------------------------------------
    # RESULTS TABLE
    # --------------------------------------------------

    st.subheader("Performance Ranking")

    st.dataframe(
        result_df,
        use_container_width=True
    )

    # --------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------

    csv = result_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download CSV",
        csv,
        "stock_analysis.csv",
        "text/csv"
    )

    # --------------------------------------------------
    # BAR CHART
    # --------------------------------------------------

    st.subheader("Returns Comparison")

    fig = px.bar(
        result_df,
        x="Stock",
        y="Return %",
        title="Stock Return Comparison"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # --------------------------------------------------
    # INDIVIDUAL STOCK CHARTS
    # --------------------------------------------------

    st.subheader("Price Charts")

    for stock in selected_stocks:

        df = load_stock(
            stock,
            start_date,
            end_date
        )

        if df is None:
            continue

        chart = px.line(
            df,
            x="Date",
            y="Close",
            title=f"{stock} Closing Price"
        )

        st.plotly_chart(
            chart,
            use_container_width=True
        )

        with st.expander(f"View Data - {stock}"):

            st.dataframe(
                df.tail(100),
                use_container_width=True
            )
