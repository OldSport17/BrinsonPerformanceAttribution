#!/usr/bin/env python

import pandas as pd
import numpy as np
import sys
import os # Import os for path joining

# --- Helper for Geometric Linking (used in summary and attribution) ---
def geometric_linking_local(df, effect_col):
    """Helper to geometrically link period effects."""
    # Ensure df is sorted by date, might be pre-sorted
    df = df.sort_values('date')
    # Handles potential inf/-inf and NaN before linking
    effect_series = df[effect_col].copy().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    if effect_series.empty:
        return 0.0
    linked_effect = (1 + effect_series)
    cumulative_product = linked_effect.cumprod()
    # Ensure we handle the case where cumulative_product might be empty
    return cumulative_product.iloc[-1] - 1 if not cumulative_product.empty else 0.0

# --- Function to Generate Summary Table ---
def generate_summary_table(portfolio_group_data, benchmark_group_data,
                           portfolio_overall_returns, benchmark_overall_returns,
                           group_by, portfolio_ticker, benchmark_ticker):
    """Generates and prints a summary table comparing weights and returns."""
    print(f"\n--- {group_by} Weight & Return Summary ({portfolio_ticker} vs {benchmark_ticker}) ---")

    # Find common dates for weights (use the latest)
    common_dates = sorted(list(set(portfolio_group_data['date']) & set(benchmark_group_data['date'])))
    if not common_dates:
        print(f"Warning: No common dates found for {group_by} summary.")
        return
    latest_date = common_dates[-1]

    # Get latest weights
    port_weights = portfolio_group_data[portfolio_group_data['date'] == latest_date][['date', group_by, 'percentage_value']].set_index(group_by)
    bench_weights = benchmark_group_data[benchmark_group_data['date'] == latest_date][['date', group_by, 'percentage_value']].set_index(group_by)

    # Calculate overall linked returns for each group
    group_returns_list = []
    all_groups = sorted(list(set(portfolio_group_data[group_by].unique()) | set(benchmark_group_data[group_by].unique())))

    for group in all_groups:
        port_group_df = portfolio_group_data[portfolio_group_data[group_by] == group]
        bench_group_df = benchmark_group_data[benchmark_group_data[group_by] == group]

        port_return_linked = geometric_linking_local(port_group_df, 'period_return')
        bench_return_linked = geometric_linking_local(bench_group_df, 'period_return')

        group_returns_list.append({
            group_by: group,
            f'{portfolio_ticker} Return': port_return_linked,
            f'{benchmark_ticker} Return': bench_return_linked
        })

    group_returns_df = pd.DataFrame(group_returns_list).set_index(group_by)

    # Merge weights and returns
    summary_df = pd.merge(port_weights[['percentage_value']], bench_weights[['percentage_value']],
                          left_index=True, right_index=True, how='outer', suffixes=(f' {portfolio_ticker}', f' {benchmark_ticker}'))
    summary_df = pd.merge(summary_df, group_returns_df, left_index=True, right_index=True, how='outer')

    # Rename columns for clarity
    summary_df.rename(columns={
        f'percentage_value {portfolio_ticker}': f'{portfolio_ticker} Weight',
        f'percentage_value {benchmark_ticker}': f'{benchmark_ticker} Weight'
    }, inplace=True)

    # Fill NaNs (groups present in one ETF but not the other)
    summary_df.fillna(0.0, inplace=True)

    # Calculate difference columns
    summary_df['Weight Differ'] = summary_df[f'{portfolio_ticker} Weight'] - summary_df[f'{benchmark_ticker} Weight']
    summary_df['Return Differ'] = summary_df[f'{portfolio_ticker} Return'] - summary_df[f'{benchmark_ticker} Return']

    # Reorder columns
    cols_order = [f'{portfolio_ticker} Weight', f'{benchmark_ticker} Weight', 'Weight Differ',
                  f'{portfolio_ticker} Return', f'{benchmark_ticker} Return', 'Return Differ']
    summary_df = summary_df[cols_order]

    # Calculate total portfolio/benchmark linked returns
    total_port_return = geometric_linking_local(portfolio_overall_returns, 'overall_period_return')
    total_bench_return = geometric_linking_local(benchmark_overall_returns, 'overall_period_return')
    total_return_diff = total_port_return - total_bench_return

    # Create Total Row - use .loc to ensure correct assignment
    total_row_data = {
        f'{portfolio_ticker} Weight': summary_df[f'{portfolio_ticker} Weight'].sum(), # Should be close to 1.0
        f'{benchmark_ticker} Weight': summary_df[f'{benchmark_ticker} Weight'].sum(), # Should be close to 1.0
        'Weight Differ': summary_df['Weight Differ'].sum(), # Should be close to 0.0
        f'{portfolio_ticker} Return': total_port_return,
        f'{benchmark_ticker} Return': total_bench_return,
        'Return Differ': total_return_diff
    }
    # Use .loc for assignment to avoid potential SettingWithCopyWarning if summary_df is a slice
    summary_df.loc['Total Sum', :] = total_row_data

    # --- Save Summary Table to CSV (before formatting) ---
    summary_csv_filename = f'{portfolio_ticker}_vs_{benchmark_ticker}_summary_{group_by}_BrinsonVer.csv'
    try:
        # Save with index as it contains the group names
        summary_df.to_csv(summary_csv_filename, index=True) 
        print(f"Summary table saved to '{summary_csv_filename}'")
    except Exception as e:
        print(f"Error saving summary table CSV '{summary_csv_filename}': {e}")
    # -----------------------------------------------------

    # Format as percentages for printing
    percent_cols_weights = [f'{portfolio_ticker} Weight', f'{benchmark_ticker} Weight', 'Weight Differ']
    percent_cols_returns = [f'{portfolio_ticker} Return', f'{benchmark_ticker} Return', 'Return Differ']

    for col in percent_cols_weights + percent_cols_returns:
         # Check if column exists before formatting
         if col in summary_df.columns:
             # Apply formatting using .map, handle potential non-numeric types gracefully
             try:
                 summary_df[col] = summary_df[col].map('{:.1%}'.format)
             except (TypeError, ValueError):
                 print(f"Warning: Could not format column '{col}' as percentage.")
                 # Optionally keep original or fill with placeholder
                 pass

    # Print the table
    print(summary_df.to_string()) # Use to_string for better console output
    print("-" * 80) # Separator

def geometric_brinson_attribution(portfolio_df, benchmark_df, group_by='sector'):
    """
    Performs multi-period Brinson attribution with geometric linking.
    Accepts aggregated group-level data per period.

    Args:
        portfolio_df (pd.DataFrame): Aggregated portfolio data.
                                     Expected columns: 'date', group_by, 'percentage_value', 'period_return'.
        benchmark_df (pd.DataFrame): Aggregated benchmark data.
                                     Expected columns: 'date', group_by, 'percentage_value', 'period_return'.
        group_by (str): Column name used for grouping (e.g., 'sector', 'industry').

    Returns:
        pd.DataFrame: DataFrame containing the attribution results (Allocation, Selection, Interaction, Total)
                      for each group and overall, geometrically linked over the periods.
    """
    # Ensure date is datetime
    portfolio_df['date'] = pd.to_datetime(portfolio_df['date'])
    benchmark_df['date'] = pd.to_datetime(benchmark_df['date'])

    # Sort data
    portfolio_df = portfolio_df.sort_values(['date', group_by])
    benchmark_df = benchmark_df.sort_values(['date', group_by])

    # Get unique dates present in *both* portfolio and benchmark
    common_dates = sorted(list(set(portfolio_df['date'].unique()) & set(benchmark_df['date'].unique())))

    if not common_dates:
        print(f"Warning: No common dates found between portfolio and benchmark for group '{group_by}'. Cannot perform attribution.")
        return pd.DataFrame(columns=[group_by, 'allocation', 'selection', 'interaction', 'total'])

    # Get unique groups across both portfolio and benchmark
    all_groups = sorted(list(set(portfolio_df[group_by].unique()) |
                             set(benchmark_df[group_by].unique())))

    period_results = []

    # Loop over each common period (date)
    for date in common_dates:
        port_period = portfolio_df[portfolio_df['date'] == date]
        bench_period = benchmark_df[benchmark_df['date'] == date]

        # Merge aggregated portfolio and benchmark data for the current period
        merged = pd.merge(
            port_period[[group_by, 'percentage_value', 'period_return']],
            bench_period[[group_by, 'percentage_value', 'period_return']],
            on=group_by, how='outer', suffixes=('_p', '_b')
        )

        # Fill NaNs for groups missing in one source for this date
        merged.fillna({
            'percentage_value_p': 0.0, 'period_return_p': 0.0,
            'percentage_value_b': 0.0, 'period_return_b': 0.0
        }, inplace=True)

        # --- Brinson Calculations (on aggregated group data) ---
        merged['allocation'] = (merged['percentage_value_p'] - merged['percentage_value_b']) * merged['period_return_b']
        merged['selection'] = merged['percentage_value_b'] * (merged['period_return_p'] - merged['period_return_b'])
        merged['interaction'] = (merged['percentage_value_p'] - merged['percentage_value_b']) * (merged['period_return_p'] - merged['period_return_b'])
        merged['total'] = merged['allocation'] + merged['selection'] + merged['interaction']

        # Store results for the period (one row per group for this date)
        for _, row in merged.iterrows():
            period_results.append({
                'date': date,
                group_by: row[group_by],
                'allocation': row['allocation'],
                'selection': row['selection'],
                'interaction': row['interaction'],
                'total': row['total']
            })

    if not period_results:
        print("Error: No period results generated for attribution.")
        return pd.DataFrame(columns=[group_by, 'allocation', 'selection', 'interaction', 'total'])

    # period_df now contains aggregated effects per group per date
    period_df = pd.DataFrame(period_results)

    # --- Geometric Linking --- Helper Function --- (Remains the same)
    def geometric_linking(df, effect_col):
        df = df.sort_values('date')
        # Handles potential inf/-inf and NaN before linking
        effect_series = df[effect_col].copy().replace([np.inf, -np.inf], 0.0).fillna(0.0)
        if effect_series.empty:
            return 0.0
        linked_effect = (1 + effect_series)
        cumulative_product = linked_effect.cumprod()
        # Ensure we handle the case where cumulative_product might be empty
        return cumulative_product.iloc[-1] - 1 if not cumulative_product.empty else 0.0

    # Calculate multi-period attribution by group
    multi_period_results = []
    for group in all_groups:
        # group_df now contains only num_dates rows for this group
        group_df = period_df[period_df[group_by] == group]
        if group_df.empty:
            # It's possible a group exists in one ETF but not the other across all dates
            print(f"Skipping group '{group}' as it had no data in common periods after aggregation.")
            continue

        # Removed the linking debug logic

        # Linking now correctly uses the period-level aggregated effects
        alloc_linked = geometric_linking(group_df, 'allocation')
        select_linked = geometric_linking(group_df, 'selection')
        interact_linked = geometric_linking(group_df, 'interaction')
        total_linked = geometric_linking(group_df, 'total')

        multi_period_results.append({
            group_by: group,
            'allocation': alloc_linked,
            'selection': select_linked,
            'interaction': interact_linked,
            'total': total_linked
        })

    multi_period_df = pd.DataFrame(multi_period_results)

    # Calculate overall portfolio attribution by linking the *sum* of group effects per period
    period_totals = period_df.groupby('date')[['allocation', 'selection', 'interaction', 'total']].sum().reset_index()

    overall_alloc = geometric_linking(period_totals, 'allocation')
    overall_select = geometric_linking(period_totals, 'selection')
    overall_interact = geometric_linking(period_totals, 'interaction')
    overall_total = geometric_linking(period_totals, 'total')

    overall_df = pd.DataFrame([{
        group_by: 'Overall',
        'allocation': overall_alloc,
        'selection': overall_select,
        'interaction': overall_interact,
        'total': overall_total
    }])

    # Combine group and overall results
    result_df = pd.concat([multi_period_df, overall_df], ignore_index=True)

    return result_df


def prepare_attribution_input(df, group_col_name, ticker_name):
    """Prepares the DataFrame for Brinson: aggregates to group level, calculates weighted return, normalizes group weights."""
    if df.empty:
        print(f"Warning: Input DataFrame for preparation (ticker: {ticker_name}, group: {group_col_name}) is empty.")
        return pd.DataFrame(), pd.DataFrame()

    required_cols = ['repPdDate', group_col_name, 'pctVal', 'Period Return']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error (ticker: {ticker_name}): Missing required columns: {missing_cols}.")
        return pd.DataFrame(), pd.DataFrame()

    input_df = df[required_cols].copy()

    # 1. Basic Cleaning & Type Conversion
    input_df['pctVal'] = pd.to_numeric(input_df['pctVal'], errors='coerce') / 100.0
    input_df['Period Return'] = pd.to_numeric(input_df['Period Return'], errors='coerce')
    input_df[group_col_name] = input_df[group_col_name].astype(str).fillna('Unknown')
    # Strip whitespace from date column before conversion
    if 'repPdDate' in input_df.columns and input_df['repPdDate'].dtype == 'object':
        input_df['repPdDate'] = input_df['repPdDate'].str.strip()
    # Attempt conversion, letting pandas infer the format
    input_df['repPdDate'] = pd.to_datetime(input_df['repPdDate'], errors='coerce') # Removed format='%Y-%m-%d'

    # Drop rows where essential conversions failed
    """
    print(f"--- Debug: Before dropna for {ticker_name} ({group_col_name}) ---")
    print("DataFrame head before dropna:")
    print(input_df.head())
    print("\nNull counts before dropna:")
    print(input_df.isnull().sum())
    print("Data types before dropna:")
    print(input_df.dtypes)
    print("----------------------------------------------------------")
    input_df.dropna(subset=['repPdDate', 'pctVal', 'Period Return'], inplace=True)
    if input_df.empty:
        print(f"Warning (ticker: {ticker_name}): DataFrame empty after initial cleaning/conversion.")
        return pd.DataFrame(), pd.DataFrame()
    """
    # Rename for consistency later
    input_df.rename(columns={'repPdDate': 'date'}, inplace=True)
    group_col_lower = group_col_name.lower()
    input_df.rename(columns={group_col_name: group_col_lower}, inplace=True)

    # 2. Calculate Weighted Return Component per Security
    input_df['weighted_return_component'] = input_df['pctVal'] * input_df['Period Return']

    # --- Calculate overall ETF return per date ---
    # Sum of weighted components IS the overall return for that period
    overall_returns = input_df.groupby('date')[['weighted_return_component']].sum().reset_index()
    overall_returns.rename(columns={'weighted_return_component': 'overall_period_return'}, inplace=True)
    # ---------------------------------------------

    # 3. Aggregate to Group Level per Date
    grouped = input_df.groupby(['date', group_col_lower])
    aggregated_df = grouped.agg(
        group_weight=('pctVal', 'sum'),
        weighted_return_sum=('weighted_return_component', 'sum')
    ).reset_index()

    # 4. Calculate Weighted Average Group Return
    # Avoid division by zero if group_weight is 0
    aggregated_df['period_return'] = np.where(
        aggregated_df['group_weight'] != 0,
        aggregated_df['weighted_return_sum'] / aggregated_df['group_weight'],
        0.0
    )

    # Keep only necessary columns
    aggregated_df = aggregated_df[['date', group_col_lower, 'group_weight', 'period_return']]

    # 5. Normalize Group Weights per Date
    aggregated_df['percentage_value'] = aggregated_df.groupby('date')['group_weight'].transform(
        lambda x: x / x.sum() if x.sum() != 0 else 0
    )

    # Fill potential NaNs from normalization (if sum was 0)
    aggregated_df['percentage_value'] = aggregated_df['percentage_value'].fillna(0.0)

    # 6. Final Selection and Renaming
    # Ensure group_col_lower is used for the final DataFrame column name
    final_df = aggregated_df[['date', group_col_lower, 'percentage_value', 'period_return']].rename(
        columns={group_col_lower: group_col_name} # Rename back to original required name like 'sector'
    )

    # Final checks
    if final_df.empty:
        print(f"Warning (ticker: {ticker_name}): Aggregated DataFrame is empty.")
    # Add other checks if needed (e.g., for NaNs in final columns)

    # Return both the group-aggregated data and the overall period returns
    return final_df, overall_returns

# --- Main Execution Block ---

def run_attribution_analysis(csv_path, portfolio_ticker, benchmark_ticker):
    """
    Loads data from CSV and runs the Brinson attribution analysis.
    """
    print("\n--- Starting Multiperiod Brinson Attribution ---")
    try:
        # Load the data from the CSV file
        all_data_df = pd.read_csv(csv_path)
        print(f"Successfully loaded data from '{csv_path}'")
    except FileNotFoundError:
        print(f"Error: CSV file not found at '{csv_path}'. Please ensure the file exists.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading or processing CSV file '{csv_path}': {e}")
        sys.exit(1)

    # Check if required 'ticker' column exists
    if 'ticker' not in all_data_df.columns:
        print("Error: 'ticker' column not found in the loaded CSV data.")
        sys.exit(1)

    # Filter the DataFrame for each ETF
    df_portfolio = all_data_df[all_data_df['ticker'] == portfolio_ticker].copy()
    df_benchmark = all_data_df[all_data_df['ticker'] == benchmark_ticker].copy()

    if df_portfolio.empty:
         print(f"Warning: No data found for portfolio ticker '{portfolio_ticker}' in the CSV.")
    if df_benchmark.empty:
         print(f"Warning: No data found for benchmark ticker '{benchmark_ticker}' in the CSV.")

    if df_portfolio.empty or df_benchmark.empty:
        print("Cannot perform attribution due to missing data for one or both ETFs.")
        sys.exit(1)

    # --- Attribution by Sector ---
    print(f"\n--- Running Brinson Attribution ({portfolio_ticker} vs {benchmark_ticker}) by Sector ---")
    if 'Sector' not in df_portfolio.columns or 'Sector' not in df_benchmark.columns:
         print("Skipping Sector attribution: 'Sector' column missing in one or both ETF sections of the data.")
    else:
        # Prepare data, getting both group-level and overall period returns
        portfolio_sector_data, portfolio_overall_returns = prepare_attribution_input(df_portfolio, 'Sector', portfolio_ticker)
        benchmark_sector_data, benchmark_overall_returns = prepare_attribution_input(df_benchmark, 'Sector', benchmark_ticker)

        # Check if dataframes are sufficient for summary/attribution
        if portfolio_sector_data.empty or benchmark_sector_data.empty or portfolio_overall_returns.empty or benchmark_overall_returns.empty:
            print(f"Skipping Sector attribution/summary: Not enough prepared data for {portfolio_ticker} or {benchmark_ticker}.")
        else:
            # Generate and print the summary table FIRST
            generate_summary_table(portfolio_sector_data, benchmark_sector_data,
                                   portfolio_overall_returns, benchmark_overall_returns,
                                   'Sector', portfolio_ticker, benchmark_ticker)
            
            # Now run the attribution analysis
            attribution_sector = geometric_brinson_attribution(portfolio_sector_data, benchmark_sector_data, group_by='Sector')
            if not attribution_sector.empty:
                print("\nSector Attribution Results:")
                # Format output for better readability
                print(attribution_sector.to_string(float_format="%.4f"))
                # Optional: Save to CSV
                sector_csv_filename = f'{portfolio_ticker}_vs_{benchmark_ticker}_attribution_sector_BrinsonVer.csv'
                try:
                    attribution_sector.to_csv(sector_csv_filename, index=False)
                    print(f"Sector attribution saved to '{sector_csv_filename}'")
                except Exception as e:
                    print(f"Error saving sector attribution CSV: {e}")
            else:
                print("Sector attribution resulted in an empty DataFrame.")


    # --- Attribution by Industry ---
    print(f"\n--- Running Brinson Attribution ({portfolio_ticker} vs {benchmark_ticker}) by Industry ---")
    if 'Industry' not in df_portfolio.columns or 'Industry' not in df_benchmark.columns:
         print("Skipping Industry attribution: 'Industry' column missing in one or both ETF sections of the data.")
    else:
        # Prepare data
        portfolio_industry_data, portfolio_overall_returns_ind = prepare_attribution_input(df_portfolio, 'Industry', portfolio_ticker)
        benchmark_industry_data, benchmark_overall_returns_ind = prepare_attribution_input(df_benchmark, 'Industry', benchmark_ticker)

        # Check data
        if portfolio_industry_data.empty or benchmark_industry_data.empty or portfolio_overall_returns_ind.empty or benchmark_overall_returns_ind.empty:
            print(f"Skipping Industry attribution/summary: Not enough prepared data for {portfolio_ticker} or {benchmark_ticker}.")
        else:
            # Generate and print the summary table
            generate_summary_table(portfolio_industry_data, benchmark_industry_data,
                                   portfolio_overall_returns_ind, benchmark_overall_returns_ind,
                                   'Industry', portfolio_ticker, benchmark_ticker)
            
            # Run attribution
            attribution_industry = geometric_brinson_attribution(portfolio_industry_data, benchmark_industry_data, group_by='Industry')
            if not attribution_industry.empty:
                print("\nIndustry Attribution Results:")
                # Format output for better readability
                print(attribution_industry.to_string(float_format="%.4f"))
                # Optional: Save to CSV
                industry_csv_filename = f'{portfolio_ticker}_vs_{benchmark_ticker}_attribution_industry_BrinsonVer.csv'
                try:
                    attribution_industry.to_csv(industry_csv_filename, index=False)
                    print(f"Industry attribution saved to '{industry_csv_filename}'")
                except Exception as e:
                    print(f"Error saving industry attribution CSV: {e}")
            else:
                print("Industry attribution resulted in an empty DataFrame.")

    print("\n--- Finished Multiperiod Brinson Attribution ---")


if __name__ == "__main__":
    # Define the path to your CSV and the tickers
    # You can modify these values or use command-line arguments
    CSV_FILE_PATH = 'all_enriched_etf_data_with_yf.csv'
    PORTFOLIO_TICKER = 'WINN' # Replace with your actual portfolio ETF ticker from the CSV
    BENCHMARK_TICKER = 'ILCG' # Replace with your actual benchmark ETF ticker from the CSV

    # Example usage with potential command-line arguments
    if len(sys.argv) > 1:
        CSV_FILE_PATH = sys.argv[1]
    if len(sys.argv) > 2:
        PORTFOLIO_TICKER = sys.argv[2]
    if len(sys.argv) > 3:
        BENCHMARK_TICKER = sys.argv[3]

    run_attribution_analysis(CSV_FILE_PATH, PORTFOLIO_TICKER, BENCHMARK_TICKER) 