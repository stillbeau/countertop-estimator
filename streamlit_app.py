import streamlit as st
import pandas as pd
import requests
import io

# --- Configuration ---
# Make sure your Google Sheet is published to the web as a CSV.
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/166G-39R1YSGTjlJLulWGrtE-Reh97_F__EcMlLPa1iQ/export?format=csv"
)
GST_RATE = 0.10  # GST Rate (10%)

# --- Data Loading Function ---
# Use caching if you want to avoid refetching data unnecessarily. 
# To force a refresh, click the "Refresh Data" button.
@st.cache_data(show_spinner=False)
def load_data(url):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            st.error(f"❌ Failed to fetch data. HTTP Status: {response.status_code}")
            return None
        # Read CSV data from the response
        df = pd.read_csv(io.StringIO(response.text))
        # Clean column names (strip any extra whitespace)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# --- Pricing Calculation Functions ---
def calculate_aggregated_costs(row, sq_ft_used):
    """
    Example cost aggregation.
    If a 'Cost per Sq Ft' column exists, we use it;
    otherwise, we assume 'Serialized On Hand Cost' divided by 'Available Sq Ft'.
    """
    try:
        if "Cost per Sq Ft" in row:
            unit_cost = row["Cost per Sq Ft"]
        else:
            # Avoid division by zero and missing values.
            available = row.get("Available Sq Ft", None)
            if pd.isna(available) or available == 0:
                st.error("Available Sq Ft is missing or zero; cannot calculate cost per Sq Ft.")
                return {"total_cost": 0}
            unit_cost = row["Serialized On Hand Cost"] / available
        total_cost = unit_cost * sq_ft_used
        return {"total_cost": total_cost}
    except Exception as e:
        st.error(f"Error calculating aggregated costs: {e}")
        return {"total_cost": 0}

def compute_final_price(row, sq_ft_used):
    cost_info = calculate_aggregated_costs(row, sq_ft_used)
    total = cost_info["total_cost"]
    # Final price includes GST
    final_price = total + (total * GST_RATE)
    return final_price

# --- Main App ---
def main():
    st.title("Google Sheets Data & Pricing App")
    st.write("Fetching data from your Google Sheet...")

    # Option to refresh data
    if st.button("Refresh Data"):
        load_data.clear()  # Clear cache to force reloading

    df = load_data(GOOGLE_SHEET_URL)
    if df is None:
        st.stop()

    st.success("Data loaded successfully!")
    st.write("**Columns found:**", df.columns.tolist())

    # --- Data Cleaning ---
    # Clean numeric columns as needed. Adjust column names as per your sheet.
    if "Serialized On Hand Cost" in df.columns:
        df["Serialized On Hand Cost"] = (
            pd.to_numeric(df["Serialized On Hand Cost"].replace("[\$,]", "", regex=True), errors="coerce")
        )
    if "Available Sq Ft" in df.columns:
        df["Available Sq Ft"] = pd.to_numeric(df["Available Sq Ft"], errors="coerce")
    if "Serial Number" in df.columns:
        df["Serial Number"] = pd.to_numeric(df["Serial Number"], errors="coerce").fillna(0).astype(int)

    # --- Color Selection Widget ---
    if "Color" in df.columns:
        # Ensure values are strings and strip whitespace
        df["Color"] = df["Color"].astype(str).str.strip()
        color_options = sorted(df["Color"].dropna().unique())
        st.write("**Available Colors:**", color_options)
        selected_color = st.selectbox("Select a color", color_options)
    else:
        st.error("Color column is missing from the data!")
        selected_color = None

    # --- Filter Data Based on Color ---
    if selected_color:
        df_filtered = df[df["Color"] == selected_color]
    else:
        df_filtered = df

    st.subheader("Filtered Data")
    st.dataframe(df_filtered)

    # --- Pricing Calculation Example ---
    st.subheader("Pricing Calculation")
    sq_ft_used = st.number_input("Enter square footage used:", value=100.0, min_value=0.0, step=10.0)
    if not df_filtered.empty:
        # For demonstration, we calculate the final price for the first row.
        first_row = df_filtered.iloc[0]
        final_price = compute_final_price(first_row, sq_ft_used)
        st.write(f"**Final Price for the first entry:** ${final_price:.2f}")
    else:
        st.error("No data available for the selected color.")

if __name__ == "__main__":
    main()
