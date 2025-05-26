import requests
import pandas as pd
import streamlit as st
import math

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
                "name": f"[{attrs.get('action')}]({links.get('self').replace('.json', '')})" if links.get("self") else attrs.get('action'),
                "state": attrs.get("state"),
                "signatures": attrs.get("signature_count"),
                "created_at": attrs.get("created_at"),
                "rejected_at": attrs.get("rejected_at"),
                "opened_at": attrs.get("opened_at"),
                "closed_at": attrs.get("closed_at"),
                "response_threshold_reached_at": attrs.get("response_threshold_reached_at"),
                "government_response_at": attrs.get("government_response_at"),
                "debate_threshold_reached_at": attrs.get("debate_threshold_reached_at"),
                "scheduled_debate_date": attrs.get("scheduled_debate_date"),
                "debate_outcome_at": attrs.get("debate_outcome_at"),
                "response": response_data.get("summary"),
                "debate_url": debate.get("video_url"),
                "department": departments[0].get("name") if departments else None
            })

        next_link = data.get("links", {}).get("next")
        if not next_link:
            break

        page += 1

    df = pd.DataFrame(all_rows)
    return df

# Add Title
st.title("📋 UK Parliament Petitions Viewer")

# Add Refresh Data button
if st.button("🔄 Refresh Data"):
    fetch_petitions.clear()
    st.rerun()  # refresh the page after clearing cache

with st.spinner("Fetching petitions..."):
    df = fetch_petitions()

st.success(f"{len(df)} petitions")

# Optional filters
state_filter = st.selectbox("Filter by state:", ["All"] + sorted(df['state'].dropna().unique().tolist()))
department_filter = st.selectbox("Filter by department:", ["All"] + sorted(df['department'].dropna().unique().tolist()))

filtered_df = df.copy()

if state_filter != "All":
    filtered_df = filtered_df[filtered_df["state"] == state_filter]

if department_filter != "All":
    filtered_df = filtered_df[filtered_df["department"] == department_filter]

# Number of items per page
ITEMS_PER_PAGE = 20

# After filtering your DataFrame `filtered_df`
total_items = len(filtered_df)
total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

# Page selector (slider or number input)
page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)

# Calculate start and end index of the current page
start_idx = (page - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE

# Slice the DataFrame to the current page
paged_df = filtered_df.iloc[start_idx:end_idx]

st.write(f"Showing page {page} of {total_pages} ({total_items} petitions total)")

# Show the paginated DataFrame
st.dataframe(paged_df.sort_values(by="signatures", ascending=False).reset_index(drop=True))