import requests
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

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
                "Petition": attrs.get("action"),
                "Petition URL": links.get("self").replace(".json", "") if links.get("self") else "",
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
                "Debate video URL": debate.get("video_url") if debate.get("video_url") else "",
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
    st.rerun()

with st.spinner("Fetching petitions..."):
    df = fetch_petitions()

st.success(f"{len(df)} petitions fetched")

# Number of items per page for manual pagination controls (not used here since AgGrid has built-in pagination)
ITEMS_PER_PAGE = 50

filtered_df = df.copy()

# Filters in one row using columns
col1, col2 = st.columns(2)

with col1:
    state_filter = st.selectbox("Select State:", ["All"] + sorted(filtered_df['State'].dropna().unique().tolist()))
with col2:
    department_filter = st.selectbox("Select Department:", ["All"] + sorted(filtered_df['Department'].dropna().unique().tolist()))

# Apply filters
if state_filter != "All":
    filtered_df = filtered_df[filtered_df["State"] == state_filter]

if department_filter != "All":
    filtered_df = filtered_df[filtered_df["Department"] == department_filter]

# Format dates
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
    if col in filtered_df.columns:
        filtered_df[col] = pd.to_datetime(filtered_df[col], errors='coerce').dt.strftime('%d/%m/%Y')

# Format signatures with commas
filtered_df["Signatures"] = filtered_df["Signatures"].map("{:,}".format)

# Prepare clickable URLs in a new column for AgGrid cellRenderer
def make_link(url):
    if url:
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">Link</a>'
    return ""

filtered_df["Petition Link"] = filtered_df["Petition URL"].apply(make_link)
filtered_df["Debate Video"] = filtered_df["Debate video URL"].apply(make_link)

# Drop original URL columns from display if you want (optional)
filtered_df = filtered_df.drop(columns=["Petition URL", "Debate video URL"])

# Rearrange columns for better UX
cols_order = [
    "Petition", "Petition Link", "State", "Signatures", "Created at", "Opened at", "Closed at",
    "Response threshold (10,000) reached at", "Government response at", "Debate threshold (100,000) reached at",
    "Scheduled debate date", "Debate outcome at", "Response", "Debate Video", "Department"
]
filtered_df = filtered_df[cols_order]

# Build AgGrid options
gb = GridOptionsBuilder.from_dataframe(filtered_df)

# Freeze (pin) the first column ("Petition")
gb.configure_column("Petition", pinned="left", editable=False, filter=True, sortable=True, wrapText=True, autoHeight=True)

# Make "Petition Link" and "Debate Video" render HTML links
gb.configure_column("Petition Link", cellRenderer='agGroupCellRenderer', editable=False, filter=False, sortable=False)
gb.configure_column("Debate Video", cellRenderer='agGroupCellRenderer', editable=False, filter=False, sortable=False)

# Set other columns non-editable, enable filtering & sorting
for col in filtered_df.columns:
    if col not in ["Petition", "Petition Link", "Debate Video"]:
        gb.configure_column(col, editable=False, filter=True, sortable=True, wrapText=True, autoHeight=True)

# Enable pagination
gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=50)

grid_options = gb.build()

# Display the table
AgGrid(
    filtered_df,
    gridOptions=grid_options,
    enable_enterprise_modules=False,
    allow_unsafe_jscode=True,
    theme="material",  # optional: material, balham, alpine, dark
    height=600,
    fit_columns_on_grid_load=True,
    reload_data=False,
)

