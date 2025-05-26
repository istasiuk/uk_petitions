import requests
import pandas as pd
import streamlit as st
import math

# Cache the function to avoid refetching every time
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
                "Petition": f"[{attrs.get('action')}]({links.get('self').replace('.json', '')})" if links.get("self") else attrs.get('action'),
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
                "Debate video": debate.get("video_url"),
                "Department": departments[0].get("name") if departments else None
            })

        next_link = data.get("links", {}).get("next")
        if not next_link:
            break

        page += 1

    df = pd.DataFrame(all_rows)
    return df

# Title
st.title("🇬🇧 UK Parliament Petitions Viewer")

# Refresh Button
if st.button("⟳ Refresh Data"):
    fetch_petitions.clear()
    st.rerun()

# Spinner while loading data
with st.spinner("Fetching petitions..."):
    df = fetch_petitions()

st.success(f"{len(df)} petitions loaded")

# ----------- Compact Filter Layout -------------
col1, col2 = st.columns(2)

with col1:
    state_filter = st.selectbox(
        "State",
        ["All"] + sorted(df['State'].dropna().unique().tolist())
    )

with col2:
    department_filter = st.selectbox(
        "Department",
        ["All"] + sorted(df['Department'].dropna().unique().tolist())
    )

# Filter DataFrame
filtered_df = df.copy()

if state_filter != "All":
    filtered_df = filtered_df[filtered_df["State"] == state_filter]

if department_filter != "All":
    filtered_df = filtered_df[filtered_df["Department"] == department_filter]

# ----------- Pagination -------------
ITEMS_PER_PAGE = 50
total_items = len(filtered_df)
total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

page = st.selectbox(
    "Select page:",
    options=list(range(1, total_pages + 1)),
    index=0
)

start_idx = (page - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
paged_df = filtered_df.iloc[start_idx:end_idx]

# ----------- Date Formatting -------------
date_columns = [
    "Created at", "Rejected at", "Opened at", "Closed at",
    "Response threshold (10,000) reached at", "Government response at",
    "Debate threshold (100,000) reached at", "Scheduled debate date",
    "Debate outcome at",
]

for col in date_columns:
    if col in paged_df.columns:
        paged_df[col] = pd.to_datetime(paged_df[col], errors='coerce').dt.strftime('%d/%m/%Y')

# ----------- Display Data -------------
st.write(f"Showing page {page} of {total_pages}")

df_display = paged_df.sort_values(by="Signatures", ascending=False).reset_index(drop=True)
df_display.index = range(1, len(df_display) + 1)

# Format Signatures with thousands separator
styled_df = df_display.style.format({"Signatures": "{:,}"})

# Display in Streamlit
st.dataframe(styled_df, use_container_width=True)
