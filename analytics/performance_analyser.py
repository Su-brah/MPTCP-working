import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import logging

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Matplotlib Style ---
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (12, 7)
plt.rcParams['figure.dpi'] = 100

def get_db_connection():
    """Establishes a connection to the PostgreSQL database using environment variables."""
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            host=os.environ.get('DB_HOST', 'localhost'),
            port=os.environ.get('DB_PORT', '5432')
        )
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Could not connect to database: {e}")
        return None

def fetch_data():
    """Fetches performance data from the proxy_logs table."""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        logging.info("Fetching data from PostgreSQL...")
        # Query to select all completed and successful connections
        query = "SELECT * FROM proxy_logs WHERE status = 'closed' AND connection_duration_ms IS NOT NULL;"
        df = pd.read_sql_query(query, conn)
        logging.info(f"Successfully fetched {len(df)} records.")
        return df
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        return None
    finally:
        if conn:
            conn.close()

def analyze_and_visualize(df):
    """Performs analysis and creates visualizations."""
    if df.empty:
        logging.warning("DataFrame is empty. No data to analyze.")
        return

    # Convert data types for analysis
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['throughput_kbps'] = pd.to_numeric(df['throughput_kbps'])
    df['connection_duration_ms'] = pd.to_numeric(df['connection_duration_ms'])

    # --- Analysis & Print Summary ---
    logging.info("\n--- Performance Summary ---")
    total_data = (df['bytes_sent'].sum() + df['bytes_received'].sum()) / (1024**2)
    avg_throughput = df['throughput_kbps'].mean()
    avg_duration = df['connection_duration_ms'].mean()
    
    print(f"Total Connections Analyzed: {len(df)}")
    print(f"Total Data Transferred: {total_data:.2f} MB")
    print(f"Average Throughput: {avg_throughput:.2f} KB/s")
    print(f"Average Connection Duration: {avg_duration:.2f} ms")
    print("---------------------------\n")

    # --- Visualization 1: Throughput over Time ---
    logging.info("Generating plot: Throughput over Time")
    plt.figure()
    ax = sns.lineplot(data=df, x='start_time', y='throughput_kbps', marker='o', errorbar=None)
    ax.set_title('Proxy Throughput Over Time', fontsize=16)
    ax.set_xlabel('Time')
    ax.set_ylabel('Throughput (KB/s)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('analytics/throughput_over_time.png')
    logging.info("Saved plot to analytics/throughput_over_time.png")
    plt.close()

    # --- Visualization 2: Connection Duration Distribution ---
    logging.info("Generating plot: Connection Duration Distribution")
    plt.figure()
    ax = sns.histplot(df['connection_duration_ms'], bins=30, kde=True)
    ax.set_title('Distribution of Connection Durations', fontsize=16)
    ax.set_xlabel('Duration (ms)')
    ax.set_ylabel('Frequency')
    plt.tight_layout()
    plt.savefig('analytics/connection_duration_distribution.png')
    logging.info("Saved plot to analytics/connection_duration_distribution.png")
    plt.close()
    
    # --- Visualization 3: Top 10 Destinations by Data Transferred ---
    logging.info("Generating plot: Top 10 Destinations")
    df['total_bytes'] = df['bytes_sent'] + df['bytes_received']
    top_destinations = df.groupby('destination_address')['total_bytes'].sum().nlargest(10) / (1024**2) # in MB
    
    plt.figure()
    ax = top_destinations.sort_values().plot(kind='barh')
    ax.set_title('Top 10 Destinations by Data Transferred', fontsize=16)
    ax.set_xlabel('Total Data Transferred (MB)')
    ax.set_ylabel('Destination')
    plt.tight_layout()
    plt.savefig('analytics/top_destinations.png')
    logging.info("Saved plot to analytics/top_destinations.png")
    plt.close()

def main():
    """Main function to run the analysis."""
    # Check for DB environment variables
    if not all([os.environ.get(k) for k in ['DB_NAME', 'DB_USER', 'DB_PASSWORD']]):
        logging.error("Database environment variables (DB_NAME, DB_USER, DB_PASSWORD) are not set. Exiting.")
        return

    data_df = fetch_data()
    if data_df is not None:
        analyze_and_visualize(data_df)

if __name__ == '__main__':
    main()
