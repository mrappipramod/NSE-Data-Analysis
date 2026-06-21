import streamlit as st
import datetime as dt
import pandas as pd
import numpy as np
import requests
import zipfile
import io
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# DATA DOWNLOAD FUNCTIONS (Copy these from your original script)
# ============================================================

def download_bhavcopy(date_obj):
    year = date_obj.strftime("%Y")
    month = date_obj.strftime("%m")
    day = date_obj.strftime("%d")
    month_abbr = date_obj.strftime("%b").upper()
    year_short = date_obj.strftime("%y")
    
    file_name = f"cm{day}{month_abbr}{year_short}bhav.csv.zip"
    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{year}/{month}/{file_name}"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return None
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_name = f"cm{day}{month_abbr}{year_short}bhav.csv"
            with z.open(csv_name) as f:
                df = pd.read_csv(f)
        df['DATE'] = date_obj.strftime('%Y-%m-%d')
        df.columns = [col.strip().upper() for col in df.columns]
        required = ['SYMBOL', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'DATE']
        existing = [col for col in required if col in df.columns]
        return df[existing]
    except:
        return None

def download_range(start_date, end_date):
    all_dfs = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            df = download_bhavcopy(current)
            if df is not None:
                all_dfs.append(df)
        current += dt.timedelta(days=1)
    if not all_dfs:
        return None
    master_df = pd.concat(all_dfs, ignore_index=True)
    master_df['DATE'] = pd.to_datetime(master_df['DATE'])
    return master_df

# ============================================================
# ANALYSIS FUNCTION (Adapted for Streamlit display)
# ============================================================

def run_analysis(master_df):
    dates = sorted(master_df['DATE'].unique())
    stocks = master_df['SYMBOL'].unique()
    
    # Summary stats
    avg_close = master_df['CLOSE'].mean()
    max_close = master_df['CLOSE'].max()
    min_close = master_df['CLOSE'].min()
    total_volume = master_df['VOLUME'].sum()
    
    # Pivot for percentage change
    pivot = master_df.pivot(index='SYMBOL', columns='DATE', values='CLOSE')
    
    stats = {
        "start_date": dates[0].strftime('%d-%b-%Y'),
        "end_date": dates[-1].strftime('%d-%b-%Y'),
        "trading_days": len(dates),
        "total_stocks": len(stocks),
        "avg_close": avg_close,
        "max_close": max_close,
        "min_close": min_close,
        "total_volume": total_volume
    }
    
    # Top gainers/losers
    if len(pivot.columns) >= 2:
        first_date = pivot.columns[0]
        last_date = pivot.columns[-1]
        pct_change = (pivot[last_date] - pivot[first_date]) / pivot[first_date] * 100
        pct_change = pct_change.dropna()
        top_gainers = pct_change.nlargest(5)
        top_losers = pct_change.nsmallest(5)
    else:
        top_gainers = pd.Series()
        top_losers = pd.Series()
    
    return stats, top_gainers, top_losers, pivot

# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(page_title="NSE Stock Analyzer", layout="wide")

st.title("📊 NSE Stock Market Analyzer")
st.markdown("Download and analyze NSE bhavcopy data for any date range.")

# Date pickers
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", dt.date(2026, 1, 1))
with col2:
    end_date = st.date_input("End Date", dt.date(2026, 6, 21))

if st.button("🚀 Run Analysis"):
    if start_date > end_date:
        st.error("Start date must be before end date.")
    else:
        with st.spinner("Downloading data from NSE. This may take a few minutes..."):
            data = download_range(start_date, end_date)
        
        if data is None or data.empty:
            st.error("No data available for the selected date range.")
        else:
            st.success(f"✅ Successfully downloaded {len(data)} trading records.")
            
            with st.spinner("Generating analysis..."):
                stats, gainers, losers, pivot = run_analysis(data)
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Trading Days", stats["trading_days"])
            col2.metric("Stocks Analyzed", stats["total_stocks"])
            col3.metric("Avg Closing Price", f"₹{stats['avg_close']:,.2f}")
            col4.metric("Total Volume", f"{stats['total_volume']:,.0f}")
            
            # Gainers and Losers
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🚀 Top 5 Gainers")
                if not gainers.empty:
                    for sym, pct in gainers.items():
                        st.write(f"**{sym}**: +{pct:.2f}%")
                else:
                    st.write("Insufficient data")
            
            with col2:
                st.subheader("📉 Top 5 Losers")
                if not losers.empty:
                    for sym, pct in losers.items():
                        st.write(f"**{sym}**: {pct:.2f}%")
                else:
                    st.write("Insufficient data")
            
            # Show raw data preview
            with st.expander("📁 View Raw Data Preview"):
                st.dataframe(data.head(100))
