#!/usr/bin/env python

try:
    # For Python 3.0 and later
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen, Request
    from urllib import urlencode

import json
import sys # Used for better error output
import csv
import yfinance as yf
import pandas as pd  
import matplotlib.pyplot as plt 
import math
import re
from datetime import datetime, timedelta
import calendar
import time # Added for delay

# --- API Call from Tradefeeds to get ETF holdings ---  

def get_jsonparsed_data(url):
    """
    Fetches content from 'url', parses it as JSON, and returns the object.

    Parameters
    ----------
    url : str
        The complete URL to fetch data from.

    Returns
    -------
    dict or None
        Parsed JSON data as a dictionary, or None if an error occurs.
    """
    try:
        # Some APIs might require specific headers, like User-Agent
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = Request(url, headers=headers)
        
        print(f"Requesting URL: {url}") # Print the URL being requested
        
        response = urlopen(req, timeout=30) # Added a timeout
        data = response.read().decode("utf-8")
        
        # Check if response code is successful
        if response.getcode() == 200:
            return json.loads(data)
        else:
            print(f"Error: Received status code {response.getcode()}")
            print(f"Response data: {data}")
            return None
            
    except Exception as e:
        print(f"An error occurred during the API request or parsing: {e}", file=sys.stderr)
        # Print response content if possible, even on error, for debugging
        if 'response' in locals() and hasattr(response, 'read'):
             try:
                 print(f"Error response content: {response.read().decode('utf-8')}", file=sys.stderr)
             except Exception as read_err:
                 print(f"Could not read error response content: {read_err}", file=sys.stderr)
        return None

def get_jsonparsed_data_multiple(url):
    """
    Fetches content from 'url', splits concatenated JSON objects, parses each as JSON, and returns a list of objects. Necessary for batch fetching
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = Request(url, headers=headers)
        print(f"Requesting URL: {url}")
        response = urlopen(req, timeout=30)
        data = response.read().decode("utf-8")
        # Split on '}{' and re-add braces
        if not data.strip():
            return []
        json_strings = []
        if data.startswith('{') and data.endswith('}'):
            # If there are multiple objects, they'll be concatenated like }{
            parts = data.split('}{')
            for i, part in enumerate(parts):
                if i == 0:
                    json_strings.append(part + '}')
                elif i == len(parts) - 1:
                    json_strings.append('{' + part)
                else:
                    json_strings.append('{' + part + '}')
        else:
            # Unexpected format
            print("Unexpected API response format.")
            return []
        return [json.loads(obj) for obj in json_strings]
    except Exception as e:
        print(f"An error occurred during the API request or parsing: {e}", file=sys.stderr)
        return []

# --- Tradefeeds Configuration ---
api_key = ""  # *** Replace with your actual Tradefeeds API Key ***
# ticker = "WINN" 
#date_from = "2024-02-01"
#date_to = "2025-01-31"
base_url = "https://data.tradefeeds.com/api/v1/etf_holdings"

# --- NOTE: This is the main parameter set for Tradefeeds API Calls---
param_sets = [
    {
        'key': api_key,
        'ticker': "WINN",
        'date_from': "2024-02-01",
        'date_to': "2025-01-31"
    },
    {
        'key': api_key,
        'ticker': "ILCG",
        'date_from': "2024-02-01",
        'date_to': "2025-01-31"
    }
]

dataframes = []  # DataFrames to store each ETF's data

for params in param_sets:
    ticker = params['ticker']
    # Encode parameters for the URL query string
    query_string = urlencode(params)
    url = f"{base_url}?{query_string}"

    print(f"\nAttempting to fetch data for {ticker}")
    etf_data = get_jsonparsed_data(url)

    if etf_data:
        print("\nAPI Response Received:")
        # print(json.dumps(etf_data, indent=4)) 

        json_data_string = json.dumps(etf_data)
        data = json.loads(json_data_string)
        output_items = data.get('result', {}).get('output', [])

        # Transform JSON output into a DataFrame
        attribute_keys = set()
        signature_keys = set()
        invstOrSec_keys = set()

        for item in output_items:
            attribute_keys.update(item.get('attributes', {}).keys())
            signature_keys.update(item.get('signature', {}).keys())
            for inv_sec in item.get('invstOrSecs', []):
                invstOrSec_keys.update(inv_sec.get('invstOrSec', {}).keys())

        # Combine all keys for DataFrame columns
        all_keys = list(attribute_keys) + list(signature_keys) + list(invstOrSec_keys)

        # Flatten the data for DataFrame rows
        rows = []
        for item in output_items:
            attributes = item.get('attributes', {})
            signature = item.get('signature', {})
            invstOrSecs = item.get('invstOrSecs', [])
            for inv_sec in invstOrSecs:
                invstOrSec = inv_sec.get('invstOrSec', {})
                row = {}
                row.update(attributes)
                row.update(signature)
                row.update(invstOrSec)
                rows.append(row)

        # Create DataFrame
        df = pd.DataFrame(rows, columns=all_keys)

        if not df.empty:
            print(f"\nDataFrame created from etf_data for {ticker}:")
            print(df.head())
            # csv_filename = f"{ticker}_etf_data.csv"
            # df.to_csv(csv_filename, index=False)
            # print(f"DataFrame saved to '{csv_filename}'")
            dataframes.append(df)  # <-- Add this line
        else:
            print("No tabular data found to create DataFrame.")

    else:
        print(f"\nFailed to retrieve data for {ticker}.")



# --- Download ticker data for all securities in the two DataFrames using isin as unique identifier from Tradefeeds API, necessary because Tradefeeds holdings data do not include tickers ---

# Combine the two DataFrames and extract unique ISINs
combined_df = pd.concat(dataframes, ignore_index=True)
# Remove duplicate columns if any
combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]
# Now extract unique ISINs
unique_isins = combined_df['isin'].dropna().unique()
df_isin = pd.DataFrame({'isin': unique_isins})

# Helper function to batch a list into chunks of size n
def batch_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

isin_to_ticker = {}

# manually add tickers for ISINs that are not available in the Tradefeeds API; this list overrides the yfinance ticker lookup   
manual_isin_to_ticker = {
    # items below are missing securities from Tradefeeds ticker lookup
    "US0404132054": "ANET",
    "US04626A1034": "ALAB",
    "US0669224778": "XTSLA",
    "US0669225197": "WKN",
    "US2166485019": "COO",
    "US26142V1052": "DKNG",
    "US29109X1063": "AZPN",
    "US31488V1070": "FERG",
    "US3696043013": "GE",
    "US45687V1061": "IR",
    "US46982L1089": "J",
    "US5128073062": "LRCX",
    "US5312297550": "FWONK",
    "US5312297717": "FWONA",
    "US53566V1061": "LINE",
    "US75734B1008": "RDDT",
    "US86800U3023": "SMCI",
    "IE00BLP1HW54": "XLOM",
    "JE00BTDN8H13": "APTV",
    "KYG3730V1059": "FTAI",
    "IE000IVNQZ81": "TEL",
    "US53223X1072": "LSI",
    "US77634L1052": "RCM",
    "IE00BZ12WP82": "LIN",
    "US8621211007": "STOR",
    "US0036541003": "ABMD",
    "US98936J1016": "ZEN",
    # items below are overrides for comapnies with different tickers due to corporate events, identified manually
    "US03073E1055": "COR",
    "US8522341036": "XYZ",
    "IE00BLP1HW54": "AON",
    "US15677J1088": "DAY",
    "US42250P1030": "DOC",
    "US3390411052": "CPAY"
}
# Batch ticker lookup API calls from Tradefeeds 
isin_list = df_isin['isin'].tolist()
batch_size = 60

for batch in batch_list(isin_list, batch_size):
    isin_params = ''.join([f"&isin={isin}" for isin in batch])
    url = f"https://data.tradefeeds.com/api/v1/comp_id?key={api_key}{isin_params}"
    print(f"Fetching tickers for ISINs: {batch}")
    responses = get_jsonparsed_data_multiple(url)
    for response in responses:
        if response and 'result' in response and 'output' in response['result']:
            output = response['result']['output']
            isin = output.get('isin')
            ticker = output.get('ticker')
            isin_to_ticker[isin] = ticker

df_isin['stock_ticker'] = df_isin['isin'].map(isin_to_ticker)

for isin, ticker in manual_isin_to_ticker.items():
    df_isin.loc[df_isin['isin'] == isin, 'stock_ticker'] = ticker

# Add stock_ticker to each original DataFrame
enriched_dataframes = []
for df in dataframes:
    # Remove duplicate columns in each DataFrame before merging
    df = df.loc[:, ~df.columns.duplicated()]
    enriched_df = df.merge(df_isin, on='isin', how='left')
    enriched_dataframes.append(enriched_df)
    print(enriched_df.head())
    # enriched_df.to_csv(f"{enriched_df['ticker'].iloc[0]}_enriched.csv", index=False)
df_isin = df_isin.loc[:, ~df_isin.columns.duplicated()]

# Concatenate all enriched DataFrames
final_enriched_df = pd.concat(enriched_dataframes, ignore_index=True)
print("Final enriched DataFrame saved to 'all_enriched_etf_data.csv'")

# --- Get Sector, Industry, and Period Return from yfinance ---

# 1. Identify unique tickers and date range needed
unique_tickers = final_enriched_df['stock_ticker'].dropna().unique().tolist()

# --- Add ETF tickers to the list ---
if 'param_sets' in locals() and isinstance(param_sets, list) and len(param_sets) >= 2:
    etf1_ticker = param_sets[0].get('ticker')
    etf2_ticker = param_sets[1].get('ticker')
    if etf1_ticker and etf1_ticker not in unique_tickers:
        unique_tickers.append(etf1_ticker)
    if etf2_ticker and etf2_ticker not in unique_tickers:
        unique_tickers.append(etf2_ticker)
# --- End Add ETF tickers ---

if not unique_tickers:
    print("No valid stock tickers found to process.")
    # Handle case with no tickers (e.g., save the df as is or exit)
    final_enriched_df.to_csv('all_enriched_etf_data_with_yf.csv', index=False)
    print("Final enriched DataFrame saved (no yfinance data added).")
    sys.exit() # Or continue if appropriate

# Convert repPdDate to datetime objects safely
final_enriched_df['repPdDate_dt'] = pd.to_datetime(final_enriched_df['repPdDate'], errors='coerce')

# Calculate required start/end dates for downloads
min_req_start_date = (final_enriched_df['repPdDate_dt'] - pd.DateOffset(months=3)).min()
max_req_end_date = final_enriched_df['repPdDate_dt'].max()

# Add buffer for download range (yfinance needs end date + 1 day)
download_start_str = (min_req_start_date - timedelta(days=7)).strftime('%Y-%m-%d') # Buffer start
download_end_str = (max_req_end_date + timedelta(days=7)).strftime('%Y-%m-%d')   # Buffer end

# Set start date to be 3 month + 1 day to avoid double counting of end/start day over 2 periods
# download_start_str = ( - timedelta(days=7)).strftime('%Y-%m-%d') # Buffer start


print(f"Batch downloading data for {len(unique_tickers)} tickers from {download_start_str} to {download_end_str}...")

# 2. Batch download historical price return and dividend data for 3 month periods from yfinance
try:
    # group_by='column' creates multi-level columns: ('Close', 'AAPL'), ('Dividends', 'AAPL'), etc.
    all_data = yf.download(
        unique_tickers,
        start=download_start_str,
        end=download_end_str,
        actions=True,
        progress=True, # Show progress for batch download
        group_by='column'
    )
    all_data = all_data.sort_index() # Ensure data is sorted by date
except Exception as e:
    print(f"Error during batch download: {e}")
    all_data = pd.DataFrame() # Create empty df to avoid errors later

print("Batch download complete.")

# 3. Batch fetch sector/industry info from yfinance
print("Batch fetching sector/industry info...")
ticker_info = {}
tickers_obj = yf.Tickers(unique_tickers)
for ticker in unique_tickers:
    try:
        # Access the specific Ticker object from the Tickers collection
        info = tickers_obj.tickers[ticker].info
        ticker_info[ticker] = {
            'sector': info.get('sector'),
            'industry': info.get('industry')
        }
    except Exception as e:
        # print(f"Could not fetch info for {ticker}: {e}") # Optional: print errors
        ticker_info[ticker] = {'sector': None, 'industry': None}
    # Add a small delay to avoid overwhelming the server
    time.sleep(0.1) # Sleep for 100 milliseconds between requests

print("Info fetching complete.")


# 4. Process Data and Calculate Returns (Iterate through original DataFrame)
results = []
print("Calculating returns for each holding...")

for idx, row in final_enriched_df.iterrows():
    ticker = row.get('stock_ticker')
    repPdDate_dt = row.get('repPdDate_dt')

    # Initialize results for this row
    sector = None
    industry = None
    period_return = None

    if pd.isna(ticker) or pd.isna(repPdDate_dt) or ticker not in ticker_info:
        results.append({'Sector': sector, 'Industry': industry, 'Period Return': period_return})
        continue

    # Get sector/industry from cached info
    sector = ticker_info[ticker]['sector']
    industry = ticker_info[ticker]['industry']

    # Calculate target start/end for this specific row
    target_end_date = repPdDate_dt
    month = target_end_date.month - 3
    year = target_end_date.year
    if month <= 0:
        month += 12
        year -= 1
    last_day = calendar.monthrange(year, month)[1]
    target_start_date = datetime(year, month, last_day)

    # --- Extract data for THIS ticker from the BATCHED download ---
    # Check if columns exist for this ticker in the downloaded data
    close_col = ('Close', ticker)
    div_col = ('Dividends', ticker)

    if close_col not in all_data.columns:
        # print(f"No 'Close' data found for {ticker} in batch download.") # Optional debug
        results.append({'Sector': sector, 'Industry': industry, 'Period Return': period_return})
        continue

    ticker_df = all_data[[close_col, div_col] if div_col in all_data.columns else [close_col]].copy()
    # Remove multi-index for easier processing within the loop
    ticker_df.columns = [col[0] for col in ticker_df.columns]

    # Find actual start/end dates within this ticker's data slice
    start_slice = ticker_df[ticker_df.index >= target_start_date]
    end_slice = ticker_df[ticker_df.index <= target_end_date]

    if start_slice.empty or end_slice.empty:
        # print(f"Could not find valid start/end dates for {ticker} around {repPdDate_dt.date()}") # Optional
        results.append({'Sector': sector, 'Industry': industry, 'Period Return': period_return})
        continue

    actual_start_price = float(start_slice['Close'].iloc[0])
    actual_end_price = float(end_slice['Close'].iloc[-1])
    actual_start_date = start_slice.index[0]
    actual_end_date = end_slice.index[-1]

    # Check if valid range found
    if actual_start_date > actual_end_date:
         results.append({'Sector': sector, 'Industry': industry, 'Period Return': period_return})
         continue

    # Extract the actual period data
    period_df = ticker_df.loc[actual_start_date:actual_end_date]

    if period_df.empty:
         results.append({'Sector': sector, 'Industry': industry, 'Period Return': period_return})
         continue

    # Use the prices we already found
    start_price = actual_start_price
    end_price = actual_end_price

    # Calculate price return
    price_return = (end_price - start_price) / start_price if start_price != 0 else 0.0

    # Calculate dividends within the *actual* period
    dividends = float(period_df['Dividends'].sum()) if 'Dividends' in period_df.columns else 0.0
    dividend_return = dividends / start_price if start_price != 0 else 0.0

    period_return = price_return + dividend_return # Calculated total return

    results.append({'Sector': sector, 'Industry': industry, 'Period Return': period_return})

# --- Calculate and Print ETF Returns ---
etf_results = []
print("\nCalculating returns for the ETFs themselves...")

if 'param_sets' in locals() and len(param_sets) >= 2 and 'final_enriched_df' in locals() and not final_enriched_df.empty and 'repPdDate_dt' in final_enriched_df.columns:
    etf_tickers_to_process = [param_sets[0]['ticker'], param_sets[1]['ticker']]
    # Use the already calculated repPdDate_dt column and ensure it exists
    all_repPdDates_dt = sorted(final_enriched_df['repPdDate_dt'].dropna().unique())

    if not all_repPdDates_dt:
         print("Warning: No valid reporting dates found to calculate ETF returns.")
    else:
        for etf_ticker in etf_tickers_to_process:
            if not etf_ticker: # Skip if ticker is None or empty
                continue
            print(f"Processing ETF: {etf_ticker}")
            for repPdDate_dt in all_repPdDates_dt:
                # --- Reuse the return calculation logic ---
                ticker = etf_ticker # Set ticker to the ETF ticker

                # Initialize results for this ETF/date
                sector = None
                industry = None
                period_return = None

                # Get sector/industry from cached info (might be None for ETFs)
                if ticker in ticker_info:
                    sector = ticker_info[ticker].get('sector', 'N/A') # Use N/A if None
                    industry = ticker_info[ticker].get('industry', 'N/A') # Use N/A if None
                else:
                     # This case should be less likely now that ETFs are in unique_tickers
                     print(f"Warning: Info not found for ETF {ticker} in ticker_info cache.")
                     sector = 'N/A'
                     industry = 'N/A'

                # Calculate target start/end for this specific date
                target_end_date = repPdDate_dt
                month = target_end_date.month - 3
                year = target_end_date.year
                if month <= 0:
                    month += 12
                    year -= 1
                # Handle potential error if month/year is invalid for calendar.monthrange
                try:
                    # Ensure month is valid (1-12) before calling monthrange
                    if 1 <= month <= 12:
                        last_day = calendar.monthrange(year, month)[1]
                        target_start_date = datetime(year, month, last_day)
                    else:
                        print(f"Warning: Invalid month ({month}) calculated for {ticker} on {repPdDate_dt.date()}. Skipping date.")
                        etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                        continue
                except ValueError as e:
                     print(f"Warning: Could not calculate target_start_date for {ticker} on {repPdDate_dt.date()} (Error: {e}). Skipping date.")
                     etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                     continue

                # --- Extract data for THIS ETF ticker from the BATCHED download ---
                close_col = ('Close', ticker)
                div_col = ('Dividends', ticker)

                if close_col not in all_data.columns:
                    print(f"No 'Close' data found for ETF {ticker} in batch download for period ending {repPdDate_dt.date()}.")
                    etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                    continue

                # Make sure 'all_data' index is datetime if not already
                if not isinstance(all_data.index, pd.DatetimeIndex):
                     all_data.index = pd.to_datetime(all_data.index)

                # Extract columns safely
                cols_to_extract = [close_col]
                if div_col in all_data.columns:
                    cols_to_extract.append(div_col)

                # Check if all columns exist before trying to access
                if not all(col in all_data.columns for col in cols_to_extract):
                    print(f"Missing expected columns for ETF {ticker} in batch download for period ending {repPdDate_dt.date()}.")
                    etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                    continue

                ticker_df = all_data[cols_to_extract].copy()
                ticker_df.columns = [col[0] for col in ticker_df.columns] # 'Close', 'Dividends'

                # Find actual start/end dates
                # Ensure target dates are timezone-naive like the index
                target_start_date_naive = target_start_date.replace(tzinfo=None)
                target_end_date_naive = repPdDate_dt.replace(tzinfo=None) # Use the report date directly as target end

                # Find first trading day ON OR AFTER target_start_date
                start_slice = ticker_df[ticker_df.index >= target_start_date_naive].sort_index()
                # Find last trading day ON OR BEFORE target_end_date
                end_slice = ticker_df[ticker_df.index <= target_end_date_naive].sort_index()

                if start_slice.empty or end_slice.empty:
                    print(f"Could not find valid start/end slice for ETF {ticker} for period ending {repPdDate_dt.date()}")
                    etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                    continue

                try:
                    actual_start_price = float(start_slice['Close'].iloc[0])
                    actual_start_date = start_slice.index[0]
                    actual_end_price = float(end_slice['Close'].iloc[-1])
                    actual_end_date = end_slice.index[-1]
                except (IndexError, ValueError) as e:
                     print(f"Error extracting price/date for ETF {ticker} for period ending {repPdDate_dt.date()}: {e}")
                     etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                     continue

                # Check if valid range found (start date must be <= end date)
                if actual_start_date > actual_end_date:
                     print(f"Invalid date range found for ETF {ticker} for period ending {repPdDate_dt.date()} (start > end). Actual Start: {actual_start_date}, Actual End: {actual_end_date}")
                     etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                     continue

                # Extract the actual period data (inclusive)
                period_df = ticker_df.loc[actual_start_date:actual_end_date]

                if period_df.empty:
                     print(f"Empty period_df for ETF {ticker} from {actual_start_date.date()} to {actual_end_date.date()}")
                     etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': None})
                     continue

                # Use the prices we already found
                start_price = actual_start_price
                end_price = actual_end_price

                # Calculate price return
                price_return = (end_price - start_price) / start_price if start_price != 0 else 0.0

                # Calculate dividends within the *actual* period
                # Ensure 'Dividends' column exists before summing
                dividends = float(period_df['Dividends'].sum()) if 'Dividends' in period_df.columns else 0.0
                dividend_return = dividends / start_price if start_price != 0 else 0.0

                period_return = price_return + dividend_return # Calculated total return

                etf_results.append({'ETF Ticker': ticker, 'Report Date': repPdDate_dt, 'Sector': sector, 'Industry': industry, 'Period Return': period_return})

# Print the collected ETF results
if etf_results:
    print("\n--- ETF Period Returns ---")
    etf_results_df = pd.DataFrame(etf_results)
    # Ensure Report Date is datetime before sorting and formatting
    etf_results_df['Report Date'] = pd.to_datetime(etf_results_df['Report Date'])
    etf_results_df.sort_values(by=['ETF Ticker', 'Report Date'], inplace=True)
    # Format Report Date for printing AFTER sorting
    etf_results_df['Report Date'] = etf_results_df['Report Date'].dt.strftime('%Y-%m-%d')
    # Select and order columns for printing
    print_cols = ['ETF Ticker', 'Report Date', 'Period Return', 'Sector', 'Industry']
    print(etf_results_df[print_cols].to_string(index=False, float_format="%.4f", na_rep="N/A"))
else:
    print("\nNo ETF period returns were calculated (check data availability and parameters).")

# --- End Calculate and Print ETF Returns ---

# 5. Merge results back into the DataFrame
print("Merging results...")
results_df = pd.DataFrame(results, index=final_enriched_df.index)
final_enriched_df['Sector'] = results_df['Sector']
final_enriched_df['Industry'] = results_df['Industry']
final_enriched_df['Period Return'] = results_df['Period Return']

# Clean up temporary date column
final_enriched_df = final_enriched_df.drop(columns=['repPdDate_dt'])

# Save to CSV
final_enriched_df.to_csv('all_enriched_etf_data_with_yf.csv', index=False)
print("Final enriched DataFrame with yfinance data saved to 'all_enriched_etf_data_with_yf.csv'")

