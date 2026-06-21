import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt
import plotly.express as px

st.set_page_config(
page_title="NSE Stock Analyzer",
page_icon="📈",
layout="wide"
)

# --------------------------------------------------

# CACHE

# --------------------------------------------------

@st.cache_data(ttl=3600)
def download_stock(symbol, start_date, end_date):

```
try:

    df = yf.download(
        symbol + ".NS",
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        return None

    df.reset_index(inplace=True)
    return df

except Exception:
    return None
```

# --------------------------------------------------

# ANALYSIS

# --------------------------------------------------

def calculate_metrics(df):

```
first_close = float(df["Close"].iloc[0])
last_close = float(df["Close"].iloc[-1])

total_return = (
    (last_close - first_close)
    / first_close
) * 100

high = float(df["High"].max())
low = float(df["Low"].min())

avg_volume = int(df["Volume"].mean())

return {
    "return_pct": total_return,
    "high": high,
    "low": low,
    "avg_volume": avg_volume
}
```

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
"MARUTI",
"TATAMOTORS",
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

st.markdown(
"Analyze NSE stocks with historical performance, charts and rankings."
)

# --------------------------------------------------

# RUN

# --------------------------------------------------

if st.button("🚀 Run Analysis"):

```
if start_date >= end_date:

    st.error("Start Date must be before End Date.")
    st.stop()

results = []

progress = st.progress(0)

for idx, stock in enumerate(selected_stocks):

    df = download_stock(
        stock,
        start_date,
        end_date
    )

    if df is None:
        continue

    metrics = calculate_metrics(df)

    results.append({
        "Stock": stock,
        "Return %": round(
            metrics["return_pct"], 2
        ),
        "High": round(
            metrics["high"], 2
        ),
        "Low": round(
            metrics["low"], 2
        ),
        "Avg Volume":
            metrics["avg_volume"]
    })

    progress.progress(
        (idx + 1)
        / len(selected_stocks)
    )

if len(results) == 0:

    st.error(
        "No stock data found."
    )
    st.stop()

result_df = pd.DataFrame(results)

# ----------------------------------------------
# METRICS
# ----------------------------------------------

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

# ----------------------------------------------
# PERFORMANCE TABLE
# ----------------------------------------------

st.subheader("🏆 Performance Ranking")

result_df = result_df.sort_values(
    "Return %",
    ascending=False
)

st.dataframe(
    result_df,
    use_container_width=True
)

# ----------------------------------------------
# BAR CHART
# ----------------------------------------------

st.subheader("📊 Return Comparison")

fig = px.bar(
    result_df,
    x="Stock",
    y="Return %",
    title="Stock Returns"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ----------------------------------------------
# INDIVIDUAL CHARTS
# ----------------------------------------------

st.subheader("📈 Stock Price Charts")

for stock in selected_stocks:

    df = download_stock(
        stock,
        start_date,
        end_date
    )

    if df is None:
        continue

    st.markdown(
        f"### {stock}"
    )

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

    with st.expander(
        f"View Raw Data - {stock}"
    ):
        st.dataframe(
            df.tail(100),
            use_container_width=True
        )
```
