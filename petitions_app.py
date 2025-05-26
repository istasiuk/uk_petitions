import requests
import pandas as pd
import streamlit as st
import math

# Set wide layout to allow columns side-by-side
st.set_page_config(layout="wide")

@st.cache_data(show_spinner=True)
def fetch_petitions():
    all_rows = []
    page = 1

    while True:
        url = f"https://petition.parliament.uk/petitions.json?page={page}&state=all"
        response = requests.get(url)
        if response.status_code != 200:
            break

        data = response.json()
        petitions = data.get("data", [])

        for petition in petitions:
            attrs = petition.get("attributes", {})
            links = petition.get("links", {})
            response_data = attrs.get("government_response") or {}
            debate = attrs.get("debate") or {}
            departments = attrs.get("departments", [])

            all_rows.append({
                "Petition": f'<a href="{links.get("self").replace(".json", "")}" target="_blank">{attrs.get("action")}</a>' if links.get("self") else attrs.get("action"),
                "State": attrs.get("state"),
                "Signatures": attrs.get("signature_count"),
                "Created at": attrs.get("created_at"),
                "Rejected at": attrs.get("rejected_at"),
                "Opened at": attrs.get("opened_at"),
                "Closed at": attrs.get("closed_at"),
                "Response threshold (10,000) reached at": attrs.get("response_threshold_reached_at"),
                "Government response at": attrs.get("government_response_at"),
                "Debate threshold (100,000) reached at": attrs.get("debate_threshold_reached_at"),
                "Scheduled debate date": attrs.get("scheduled_debate_date"),
                "Debate outcome at": attrs.get("debate_outcome_at"),
                "Response": response_data.get("summary"),
                "Debate video": f'<a href="{debate.get("video_url")}" target="_blank">Video</a>' if debate.get("video_url") else "",
                "Department": departments[0].get("name") if departments else None
            })

        next_link = data.get("links", {}).get("next")
        if not next_link:
            break

        page += 1

    df = pd.DataFrame(all_rows)
    return df

# Add Title
st.title("UK Parliament Petitions Viewer")

# Add Refresh Data button
if st.button("⟳ Refresh Data"):
    fetch_petitions.clear()
    st.rerun()  # refresh the page after clearing cache

with st.spinner("Fetching petitions..."):
    df = fetch_petitions()

st.success(f"{len(df)} petitions")

# Number of items per page
ITEMS_PER_PAGE = 50

filtered_df = df.copy()

# Filters and page selector in one row using columns
col1, col2, col3 = st.columns(3)

with col1:
    state_filter = st.selectbox("Select State:", ["All"] + sorted(filtered_df['State'].dropna().unique().tolist()))
with col2:
    department_filter = st.selectbox("Select Department:", ["All"] + sorted(filtered_df['Department'].dropna().unique().tolist()))

# Apply filters before determining total pages
if state_filter != "All":
    filtered_df = filtered_df[filtered_df["State"] == state_filter]

if department_filter != "All":
    filtered_df = filtered_df[filtered_df["Department"] == department_filter]

total_items = len(filtered_df)
total_pages = max(1, math.ceil(total_items / ITEMS_PER_PAGE))

with col3:
    page = st.selectbox(
        "Select page:",
        options=list(range(1, total_pages + 1)),
        index=0  # default to first page
    )

start_idx = (page - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE

paged_df = filtered_df.iloc[start_idx:end_idx]

date_columns = [
    "Created at",
    "Rejected at",
    "Opened at",
    "Closed at",
    "Response threshold (10,000) reached at",
    "Government response at",
    "Debate threshold (100,000) reached at",
    "Scheduled debate date",
    "Debate outcome at",
]

for col in date_columns:
    if col in paged_df.columns:
        paged_df[col] = pd.to_datetime(paged_df[col], errors='coerce').dt.strftime('%d/%m/%Y')

st.write(f"Showing page {page} of {total_pages}")

# Sort and reset index as before
df_display = paged_df.sort_values(by="Signatures", ascending=False).reset_index(drop=True)
df_display.index = range(1, len(df_display) + 1)
df_display.index.name = None

# Format Signatures column
df_display["Signatures"] = df_display["Signatures"].map("{:,}".format)

# Replace NaN or None with empty string for clean HTML display
df_display = df_display.fillna("")

# Convert DataFrame to HTML, allow links
html_table = df_display.to_html(escape=False)

# CSS to left align all cells except "Signatures" which is right aligned
# Use nth-child to target the column by position (find out the "Signatures" column index +2)
signatures_col_index = df_display.columns.get_loc("Signatures") + 2

css = f"""
<style>
    table {{
        width: 100%;
        border-collapse: collapse;
    }}
    /* Force all headers and cells to left align */
    table th, table td {{
        text-align: left !important;
        padding: 6px 8px;
        border: 1px solid #ddd;
    }}
    /* Override only Signatures column header and cells to right align */
    table th:nth-child({signatures_col_index}), table td:nth-child({signatures_col_index}) {{
        text-align: right !important;
    }}
</style>
"""

st.markdown(css + html_table, unsafe_allow_html=True)