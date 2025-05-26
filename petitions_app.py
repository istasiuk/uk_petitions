import requests
import pandas as pd
import streamlit as st

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

def df_to_html_table(df):
    # Escape text for safety (if needed)
    def safe_html(text):
        import html
        return html.escape(str(text))

    html_rows = []
    # Build header row
    headers = df.columns.tolist()
    header_html = "<tr>" + "".join(f"<th>{safe_html(col)}</th>" for col in headers) + "</tr>"
    html_rows.append(header_html)

    # Build data rows
    for _, row in df.iterrows():
        cells = []
        for col in headers:
            val = row[col]
            if col == "name" and isinstance(val, str):
                # `name` already contains markdown link format, convert to HTML <a> tag manually
                # The markdown format: [text](url)
                import re
                match = re.match(r'\[(.*?)\]\((.*?)\)', val)
                if match:
                    text, url = match.groups()
                    val = f'<a href="{url}" target="_blank">{safe_html(text)}</a>'
            else:
                val = safe_html(val) if val is not None else ""
            cells.append(f"<td>{val}</td>")
        html_rows.append("<tr>" + "".join(cells) + "</tr>")

    table_html = f"""
    <table border="1" style="border-collapse:collapse; width: 100%;">
        {''.join(html_rows)}
    </table>
    """
    return table_html


# Then, render this in Streamlit:
st.markdown(
    df_to_html_table(
        filtered_df.sort_values(by="signatures", ascending=False).reset_index(drop=True)
    ),
    unsafe_allow_html=True
)
