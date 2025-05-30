import requests
import pandas as pd
import streamlit as st
import math

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
                "Petition_text": attrs.get("action"),
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
                "Department": departments[0].get("name") if departments else "Unassigned"
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
    escaped_text = text.replace('"', '&quot;').replace("'", "&apos;")
    return f'<span title="{escaped_text}">{short_text}</span>'

def avg_days_between(df, start_col, end_col):
    start_dates = pd.to_datetime(df[start_col], errors='coerce')
    end_dates = pd.to_datetime(df[end_col], errors='coerce')

    if start_dates.dt.tz is not None:
        start_dates = start_dates.dt.tz_convert(None)
    if end_dates.dt.tz is not None:
        end_dates = end_dates.dt.tz_convert(None)

    diffs = (end_dates - start_dates).dt.days.dropna()
    return int(diffs.mean()) if len(diffs) > 0 else None

st.title("UK Parliament Petitions Viewer")

if st.button("⟳ Refresh Data"):
    fetch_petitions.clear()
    st.rerun()

with st.spinner("Fetching petitions..."):
    df = fetch_petitions()

if df.empty:
    st.error("No petition data found. Please refresh or check API availability.")
    st.stop()

with st.sidebar:
    st.subheader("Filters")

    if "Department" not in df.columns or "State" not in df.columns or "Petition_text" not in df.columns:
        st.error("Expected columns missing in the data.")
        st.stop()

    df["Department"] = df["Department"].fillna("Unassigned")
    state_options = sorted(df["State"].dropna().unique().tolist())
    department_options = sorted(df["Department"].dropna().unique().tolist())

    state_filter = st.multiselect("State", options=state_options, default=[])
    department_filter = st.multiselect("Department", options=department_options, default=[])

    st.markdown("### Petition")
    petition_texts = df["Petition_text"].dropna().unique().tolist()

    selected_dropdown = st.multiselect("Choose petition(s)", petition_texts)
    custom_search = st.text_input("Or enter your own text")

    if selected_dropdown and custom_search:
        st.warning("Using both dropdown and custom text. Only dropdown will be used.")
        active_searches = selected_dropdown
    elif selected_dropdown:
        active_searches = selected_dropdown
    elif custom_search:
        active_searches = [custom_search]
    else:
        active_searches = []

    st.subheader("Sort Options")
    sort_column = st.selectbox("Column:", options=df.columns.tolist(), index=df.columns.get_loc("Signatures"))
    sort_ascending = st.radio("Order:", options=["Ascending", "Descending"]) == "Descending"

effective_state_filter = state_filter if state_filter else state_options
effective_department_filter = department_filter if department_filter else department_options

filtered_df = df[
    df["State"].isin(effective_state_filter) &
    df["Department"].isin(effective_department_filter) &
    df["Petition_text"].apply(lambda x: any(term.lower() in x.lower() for term in active_searches) if pd.notna(x) else False)
]

st.success(f"{len(df)} petitions loaded | {len(filtered_df)} shown after filtering")

avg_created_to_opened = avg_days_between(filtered_df, "Created at", "Opened at")
avg_opened_to_response_threshold = avg_days_between(filtered_df, "Opened at", "Response threshold (10,000) reached at")
avg_response_threshold_to_response = avg_days_between(filtered_df, "Response threshold (10,000) reached at", "Government response at")
avg_opened_to_debate_threshold = avg_days_between(filtered_df, "Opened at", "Debate threshold (100,000) reached at")
avg_debate_threshold_to_scheduled = avg_days_between(filtered_df, "Debate threshold (100,000) reached at", "Scheduled debate date")
avg_scheduled_to_outcome = avg_days_between(filtered_df, "Scheduled debate date", "Debate outcome at")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Avg Created → Opened", avg_created_to_opened or "N/A")
col2.metric("Avg Opened → Resp Threshold", avg_opened_to_response_threshold or "N/A")
col3.metric("Avg Resp Threshold → Response", avg_response_threshold_to_response or "N/A")
col4.metric("Avg Opened → Debate Threshold", avg_opened_to_debate_threshold or "N/A")
col5.metric("Avg Debate Threshold → Scheduled", avg_debate_threshold_to_scheduled or "N/A")
col6.metric("Avg Scheduled → Outcome", avg_scheduled_to_outcome or "N/A")

if "page" not in st.session_state:
    st.session_state.page = 1

ITEMS_PER_PAGE = 50
total_items = len(filtered_df)
total_pages = max(1, math.ceil(total_items / ITEMS_PER_PAGE))

sorted_df = filtered_df.sort_values(by=sort_column, ascending=sort_ascending).reset_index(drop=True)
start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
paged_df = sorted_df.iloc[start_idx:end_idx].copy()

date_columns = [
    "Created at", "Opened at", "Closed at",
    "Response threshold (10,000) reached at", "Government response at",
    "Debate threshold (100,000) reached at", "Scheduled debate date", "Debate outcome at"
]
for col in date_columns:
    if col in paged_df.columns:
        paged_df[col] = pd.to_datetime(paged_df[col], errors='coerce').dt.strftime('%d/%m/%Y')

# Add empty space at the beginning to push to the right
pagination_cols = st.columns([10, 1, 1, 2, 1, 1])

# Empty spacer
with pagination_cols[0]:
    pass

# ⏮ First
with pagination_cols[1]:
    if st.button("⏮ First"):
        st.session_state.page = 1

# ◀ Prev
with pagination_cols[2]:
    if st.button("◀ Prev") and st.session_state.page > 1:
        st.session_state.page -= 1

# [ Page input ] of [ total pages ]
with pagination_cols[3]:
    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        page_input = st.text_input(
            "", str(st.session_state.page),
            key="page_input",
            label_visibility="collapsed"
        )
    with col2:
        st.markdown("<div style='padding-top: 0.45rem;'>of</div>", unsafe_allow_html=True)
    with col3:
        st.markdown(
            f"<div style='padding-top: 0.45rem;'><strong>{total_pages}</strong></div>",
            unsafe_allow_html=True
        )

    try:
        input_page = int(page_input)
        if 1 <= input_page <= total_pages:
            st.session_state.page = input_page
        else:
            st.warning(f"Page must be between 1 and {total_pages}")
    except ValueError:
        st.warning("Enter a valid page number")

# Next ▶
with pagination_cols[4]:
    if st.button("Next ▶") and st.session_state.page < total_pages:
        st.session_state.page += 1

# Last ⏭
with pagination_cols[5]:
    if st.button("Last ⏭"):
        st.session_state.page = total_pages

df_display = paged_df.copy()
df_display["Signatures"] = df_display["Signatures"].map("{:,}".format)
df_display["Response"] = df_display["Response"].apply(add_tooltip)
df_display = df_display.fillna("")

if "Petition_text" in df_display.columns:
    df_display = df_display.drop(columns=["Petition_text"])

html_table = df_display.to_html(escape=False, index=False)
signatures_col_index = df_display.columns.get_loc("Signatures") + 1

css = f"""
<style>
    div.dataframe-wrapper {{
        max-height: 600px;
        overflow-y: auto;
        border: 1px solid #ddd;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }}
    thead th {{
        position: sticky;
        top: 0;
        background: #0e1117;
        color: #f0f0f0;
        z-index: 2;
        text-align: left !important;
        padding: 6px 8px;
        border: 1px solid #ddd;
        font-weight: bold;
        box-shadow: inset 0 -1px 0 #ccc, 0 2px 5px rgba(0,0,0,0.1);
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
    table td:nth-child(1), table td:nth-child(12) {{
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
    <div class="dataframe-wrapper">
        {html_table}
    </div>
    {css}
    """,
    unsafe_allow_html=True
)