import streamlit as st
import datetime as dt
import pandas as pd
import requests
import zipfile
import io
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# DATA DOWNLOAD FUNCTIONS
# ============================================================

# Simulate a real browser to prevent NSE from blocking the request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

@st.cache_data(show_spinner=False, ttl=3600)
def download_bhavcopy(date_obj):
    year = date_obj.strftime("%Y")
    month = date_obj.strftime("%m")
    day = date_obj.strftime("%d")
    month_abbr = date_obj.strftime("%b").upper()
    year_short = date_obj.strftime("%y")
    
    file_name = f"cm{day}{month_abbr}{year_short}bhav.csv.zip"
    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{year}/{month_abbr}/{file_name}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        # 404 means the file doesn't exist (likely a weekend or market holiday)
        if response.status_code == 404:
            return None
            
        # 403 means we are being blocked by NSE
        if response.status_code == 403:
            st.warning(f"NSE blocked the request for {date_obj.strftime('%Y-%m-%d')}.")
            return None
            
        if response.status_code != 200:
            return None
            
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_name = f"cm{day}{month_abbr}{year_short}bhav.csv"
            with z.open(csv_name) as f:
                df = pd.read_csv(f)
                
        df['DATE'] = date_obj.strftime('%Y-%m-%d')
        df.columns = [col.strip().upper() for col in df.columns]
        
        required = ['SYMBOL', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'TOTTRDQTY', 'DATE']
        
        # NSE sometimes uses 'TOTTRDQTY' instead of 'VOLUME' in historical bhavcopies
        if 'TOTTRDQTY' in df.columns:
            df.rename(columns={'TOTTRDQTY': 'VOLUME'}, inplace=True)
            
        required_renamed = ['SYMBOL', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'DATE']
        existing = [col for col in required_renamed if col in df.columns]
        
        return df[existing]
        
    except requests.exceptions.RequestException as e:
        return None
    except zipfile.BadZipFile:
        return None

def download_range(start_date, end_date):
    all_dfs = []
    current = start_date
    
    # Create a progress bar
    progress_bar = st.progress(0)
    total_days = (end_date - start_date).days + 1
    days_processed = 0
    
    while current <= end_date:
        if current.weekday() < 5: # Monday to Friday
            df = download_bhavcopy(current)
            if df is not None and not df.empty:
                all_dfs.append(df)
                
        days_processed += 1
        progress_bar.progress(days_processed / total_days)
        current += dt.timedelta(days=1)
        
    progress_bar.empty() # Clear the progress bar when done
    
    if not all_dfs:
        return None
        
    master_df = pd.concat(all_dfs, ignore_index=True)
    master_df['DATE'] = pd.to_datetime(master_df['DATE'])
    return master_df

# ============================================================
# ANALYSIS FUNCTION
# ============================================================

def run_analysis(master_df):
    dates = sorted(master_df['DATE'].unique())
    stocks = master_df['SYMBOL'].unique()
    
    avg_close = master_df['CLOSE'].mean()
    max_close = master_df['CLOSE'].max()
    min_close = master_df['CLOSE'].min()
    total_volume = master_df['VOLUME'].sum()
    
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
    
    if len(pivot.columns) >= 2:
        first_date = pivot.columns[0]
        last_date = pivot.columns[-1]
        pct_change = (pivot[last_date] - pivot[first_date]) / pivot[first_date] * 100
        pct_change = pct_change.dropna()
        top_gainers = pct_change.nlargest(5)
        top_losers = pct_change.nsmallest(5)
    else:
        top_gainers = pd.Series(dtype=float)
        top_losers = pd.Series(dtype=float)
        
    return stats, top_gainers, top_losers, pivot

# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(page_title="NSE Stock Analyzer", layout="wide")

st.title("📊 NSE Stock Market Analyzer")
st.markdown("Download and analyze NSE bhavcopy data for any date range.")

# Date pickers (Default to a 7-day window ending today)
today = dt.date.today()
default_start = today - dt.timedelta(days=7)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", default_start)
with col2:
    end_date = st.date_input("End Date", today)

if st.button("🚀 Run Analysis"):
    if start_date > end_date:
        st.error("Start date must be before end date.")
    elif end_date > today:
        st.error("Cannot fetch data for future dates.")
    else:
        with st.spinner("Downloading data from NSE. This may take a moment..."):
            data = download_range(start_date, end_date)
        
        if data is None or data.empty:
            st.error("No data available for the selected date range. Ensure the dates aren't weekends or public holidays.")
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
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🚀 Top 5 Gainers")
                if not gainers.empty:
                    for sym, pct in gainers.items():
                        st.write(f"**{sym}**: +{pct:.2f}%")
                else:
                    st.info("Need at least 2 trading days to calculate gainers.")
            
            with col2:
                st.subheader("📉 Top 5 Losers")
                if not losers.empty:
                    for sym, pct in losers.items():
                        st.write(f"**{sym}**: {pct:.2f}%")
                else:
                    st.info("Need at least 2 trading days to calculate losers.")
            
            # Show raw data preview
            st.divider()
            with st.expander("📁 View Raw Data Preview"):
                st.dataframe(data.head(100), use_container_width=True)
