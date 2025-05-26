import requests
import pandas as pd
import streamlit as st
import math
import numpy as np

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

def add_tooltip(text, max_len=50):
    if not text:
        return ""
    short_text = text if len(text) <= max_len else text[:max_len] + "..."
    # Escape quotes in text for title attribute
    escaped_text = text.replace('"', '&quot;').replace("'", "&apos;")
    return f'<span title="{escaped_text}">{short_text}</span>'


def avg_days_between(df, start_col, end_col):
    start_dates = pd.to_datetime(df[start_col], errors='coerce')
    end_dates = pd.to_datetime(df[end_col], errors='coerce')
    diffs = (end_dates - start_dates).dt.days
    return diffs.mean()

# Add Title
st.title("UK Parliament Petitions Viewer")

# Add Refresh Data button
if st.button("⟳ Refresh Data"):
    fetch_petitions.clear()
    st.rerun()

with st.spinner("Fetching petitions..."):
    df = fetch_petitions()

st.success(f"{len(df)} petitions")

# Number of items per page
ITEMS_PER_PAGE = 10

filtered_df = df.copy()

# Filters and page selector in one row using columns
col1, col2, col3 = st.columns(3)

with col1:
    state_filter = st.selectbox("Select State:", ["All"] + sorted(filtered_df['State'].dropna().unique().tolist()))
with col2:
    department_filter = st.selectbox("Select Department:", ["All"] + sorted(filtered_df['Department'].dropna().unique().tolist()))

# Apply filters before determining total pages and metrics
if state_filter != "All":
    filtered_df = filtered_df[filtered_df["State"] == state_filter]

if department_filter != "All":
    filtered_df = filtered_df[filtered_df["Department"] == department_filter]

# --- Calculate summary numbers ---
total_petitions = len(filtered_df)

avg_created_to_opened = avg_days_between(filtered_df, "Created at", "Opened at")
avg_opened_to_response_threshold = avg_days_between(filtered_df, "Opened at", "Response threshold (10,000) reached at")
avg_response_threshold_to_response = avg_days_between(filtered_df, "Response threshold (10,000) reached at", "Government response at")
avg_opened_to_debate_threshold = avg_days_between(filtered_df, "Opened at", "Debate threshold (100,000) reached at")
avg_debate_threshold_to_scheduled = avg_days_between(filtered_df, "Debate threshold (100,000) reached at", "Scheduled debate date")
avg_scheduled_to_outcome = avg_days_between(filtered_df, "Scheduled debate date", "Debate outcome at")

# Display summary in one row with columns
col_a, col_b, col_c, col_d, col_e, col_f, col_g = st.columns(7)

col_a.metric("Total Petitions", f"{total_petitions:,}")
col_b.metric("Created → Opened (days)", avg_created_to_opened)
col_c.metric("Opened → Resp Threshold (days)", avg_opened_to_response_threshold)
col_d.metric("Resp Threshold → Govt Response (days)", avg_response_threshold_to_response)
col_e.metric("Opened → Debate Threshold (days)", avg_opened_to_debate_threshold)
col_f.metric("Debate Threshold → Scheduled (days)", avg_debate_threshold_to_scheduled)
col_g.metric("Scheduled → Outcome (days)", avg_scheduled_to_outcome)

# Pagination calculations
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
df_display.index.name = None

# Format Signatures column
df_display["Signatures"] = df_display["Signatures"].map("{:,}".format)

# Apply tooltip truncation to Response column
df_display["Response"] = df_display["Response"].apply(add_tooltip)

# Replace NaN or None with empty string for clean HTML display
df_display = df_display.fillna("")

# Convert DataFrame to HTML, allow links and tooltips
html_table = df_display.to_html(escape=False, index=False)

# CSS to left align all cells except "Signatures" which is right aligned
signatures_col_index = df_display.columns.get_loc("Signatures") + 1

css = f"""
<style>
    table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }}
    table th, table td {{
        text-align: left !important;
        padding: 6px 8px;
        border: 1px solid #ddd;
        vertical-align: top;
        word-wrap: break-word;
        white-space: normal;
        overflow-wrap: break-word;
    }}
    table th:nth-child({signatures_col_index}), table td:nth-child({signatures_col_index}) {{
        text-align: right !important;
    }}
    table td:nth-child(1),
    table td:nth-child(12) {{
        max-width: 250px;
    }}
    table td span[title] {{
        cursor: help;
        border-bottom: 1px dotted #999;
    }}
</style>
"""

st.markdown(
    f"""
    <div style="overflow-x:auto;">
        {html_table}
    </div>
    {css}
    """,
    unsafe_allow_html=True
)
