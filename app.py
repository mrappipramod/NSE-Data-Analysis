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

# CACHE

# =====================================================

@st.cache_data(ttl=3600)
def load_stock(symbol, start_date, end_date):

```
try:

    data = yf.download(
        f"{symbol}.NS",
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False,
        threads=False
    )

    if data.empty:
        return None

    data.reset_index(inplace=True)

    return data

except Exception as e:
    return None
```

# =====================================================

# ANALYSIS

# =====================================================

def calculate_stats(df):

```
first_price = float(df["Close"].iloc[0])
last_price = float(df["Close"].iloc[-1])

return_pct = (
    (last_price - first_price)
    / first_price
) * 100

return {
    "Return %": round(return_pct, 2),
    "High": round(df["High"].max(), 2),
    "Low": round(df["Low"].min(), 2),
    "Avg Volume": int(df["Volume"].mean())
}
```

# =====================================================

# SIDEBAR

# =====================================================

st.sidebar.title("Settings")

default_stocks = [
"RELIANCE",
"TCS",
"INFY",
"HDFCBANK",
"ICICIBANK",
"SBIN",
"ITC",
"LT",
"AXISBANK",
"BAJFINANCE"
]

stocks = st.sidebar.multiselect(
"Select Stocks",
default_stocks,
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

# HEADER

# =====================================================

st.title("📈 NSE Stock Analyzer")

st.caption(
"Historical analysis using Yahoo Finance"
)

# =====================================================

# RUN BUTTON

# =====================================================

if st.button("🚀 Analyze Stocks"):

```
if not stocks:

    st.warning(
        "Please select at least one stock."
    )
    st.stop()

if start_date >= end_date:

    st.error(
        "Start Date must be before End Date."
    )
    st.stop()

results = []

progress = st.progress(0)

for idx, stock in enumerate(stocks):

    df = load_stock(
        stock,
        start_date,
        end_date
    )

    if df is not None:

        stats = calculate_stats(df)

        stats["Stock"] = stock

        results.append(stats)

    progress.progress(
        (idx + 1) / len(stocks)
    )

if len(results) == 0:

    st.error(
        "No data downloaded."
    )
    st.stop()

result_df = pd.DataFrame(results)

result_df = result_df[
    [
        "Stock",
        "Return %",
        "High",
        "Low",
        "Avg Volume"
    ]
]

result_df = result_df.sort_values(
    "Return %",
    ascending=False
)

# =================================================
# METRICS
# =================================================

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

# =================================================
# TABLE
# =================================================

st.subheader("🏆 Performance Ranking")

st.dataframe(
    result_df,
    use_container_width=True
)

# =================================================
# DOWNLOAD CSV
# =================================================

csv = result_df.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    "⬇ Download Results",
    csv,
    "stock_analysis.csv",
    "text/csv"
)

# =================================================
# BAR CHART
# =================================================

st.subheader("📊 Return Comparison")

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

# =================================================
# STOCK CHARTS
# =================================================

st.subheader("📈 Individual Charts")

for stock in stocks:

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
        title=f"{stock} Close Price"
    )

    st.plotly_chart(
        chart,
        use_container_width=True
    )

    with st.expander(
        f"View Data - {stock}"
    ):
        st.dataframe(
            df.tail(100),
            use_container_width=True
        )
```
