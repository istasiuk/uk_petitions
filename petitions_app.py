import requests
import pandas as pd
import streamlit as st
import math
import altair as alt

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

    st.subheader("Signatures")
    max_signatures = int(df["Signatures"].max()) if not df["Signatures"].isnull().all() else 0
    min_signatures = int(df["Signatures"].min()) if not df["Signatures"].isnull().all() else 0

    min_possible = 0
    max_possible = max_signatures

    col1, col2 = st.columns(2)  # create two columns

    with col1:
        custom_min = st.number_input(
            "Min Signatures",
            min_value=min_possible,
            max_value=max_possible,
            value=st.session_state.get('custom_min', min_signatures),
            step=1,
            key="custom_min"
        )
    with col2:
        custom_max = st.number_input(
            "Max Signatures",
            min_value=min_possible,
            max_value=max_possible,
            value=st.session_state.get('custom_max', max_signatures),
            step=1,
            key="custom_max"
        )

    if custom_min > custom_max:
        st.error("Min cannot be greater than Max.")
        st.stop()

    signature_range = st.slider(
        "Select Signature Range",
        min_value=min_possible,
        max_value=max_possible,
        value=(custom_min, custom_max),
        step=1,
        key="signature_slider"
    )

    # Sync session state values if slider changes
    if signature_range[0] != custom_min or signature_range[1] != custom_max:
        st.session_state.custom_min = signature_range[0]
        st.session_state.custom_max = signature_range[1]

    effective_min_signatures, effective_max_signatures = signature_range

    st.markdown("### Petition")
    petition_texts = df["Petition_text"].dropna().unique().tolist()

    selected_dropdowns = st.multiselect("Choose petition(s)", petition_texts)
    custom_search = st.text_input("Or enter your own text")

    # Decide which petition filter to use
    if selected_dropdowns and custom_search:
        st.warning("Using both dropdown and custom text. Only dropdown will be used.")
        active_searches = selected_dropdowns
        use_exact_match = True
    elif selected_dropdowns:
        active_searches = selected_dropdowns
        use_exact_match = True
    elif custom_search:
        active_searches = [custom_search]
        use_exact_match = False
    else:
        active_searches = None  # No filtering on petitions
        use_exact_match = False

    st.subheader("Sort Options")
    # Custom column list for dropdown (hide "Petition_text", show "Petition" instead)
    sort_columns_display = ["Petition" if col == "Petition_text" else col for col in df.columns if
                            col != "Petition_text"]
    sort_column_display = st.selectbox("Column:", options=sort_columns_display, index=sort_columns_display.index(
        "Signatures") if "Signatures" in sort_columns_display else 0)

    # Map display name back to actual column name
    sort_column = "Petition_text" if sort_column_display == "Petition" else sort_column_display

    order = st.radio("Order:", options=["Ascending", "Descending"], index=1)
    sort_ascending = order == "Ascending"

effective_state_filter = state_filter if state_filter else state_options
effective_department_filter = department_filter if department_filter else department_options

# Filter petitions based on petition text filter
if active_searches is None:
    petition_filter = [True] * len(df)
else:
    if use_exact_match:
        # Filter by exact match
        petition_filter = df["Petition_text"].apply(
            lambda text: text in active_searches if pd.notnull(text) else False
        )
    else:
        # Filter by substring (case-insensitive)
        petition_filter = df["Petition_text"].apply(
            lambda text: any(s.lower() in text.lower() for s in active_searches) if pd.notnull(text) else False
        )

filtered_df = df[
    df["State"].isin(effective_state_filter) &
    df["Department"].isin(effective_department_filter) &
    petition_filter &
    df["Signatures"].between(effective_min_signatures, effective_max_signatures)]

st.success(f"{len(df)} petitions loaded | {len(filtered_df)} shown after filtering")

avg_created_to_opened = avg_days_between(filtered_df, "Created at", "Opened at")
avg_opened_to_response_threshold = avg_days_between(filtered_df, "Opened at", "Response threshold (10,000) reached at")
avg_response_threshold_to_response = avg_days_between(filtered_df, "Response threshold (10,000) reached at", "Government response at")
avg_opened_to_debate_threshold = avg_days_between(filtered_df, "Opened at", "Debate threshold (100,000) reached at")
avg_debate_threshold_to_scheduled = avg_days_between(filtered_df, "Debate threshold (100,000) reached at", "Scheduled debate date")
avg_scheduled_to_outcome = avg_days_between(filtered_df, "Scheduled debate date", "Debate outcome at")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Avg Created → Opened, days", avg_created_to_opened or "N/A")
col2.metric("Avg Opened → Resp Threshold, days", avg_opened_to_response_threshold or "N/A")
col3.metric("Avg Resp Threshold → Response, days", avg_response_threshold_to_response or "N/A")
col4.metric("Avg Opened → Debate Threshold, days", avg_opened_to_debate_threshold or "N/A")
col5.metric("Avg Debate Threshold → Scheduled, days", avg_debate_threshold_to_scheduled or "N/A")
col6.metric("Avg Scheduled → Outcome, days", avg_scheduled_to_outcome or "N/A")

tab1, tab2 = st.tabs(["Petition List", "Statistics"])

# Tab 1: Table only
with tab1:
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

    st.markdown('<div style="margin-top: 30px;"></div>', unsafe_allow_html=True)

    # Add empty space at the beginning to push to the right
    pagination_cols = st.columns([10, 1, 1, 2, 1, 1])

    # Empty spacer
    with pagination_cols[0]:
        pass

    # ⏮ First
    with pagination_cols[1]:
        if st.button("⏮ First"):
            st.session_state.page = 1
            st.rerun()

    # ◀ Prev
    with pagination_cols[2]:
        if st.button("◀ Prev") and st.session_state.page > 1:
            st.session_state.page -= 1
            st.rerun()

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
            st.rerun()

    # Last ⏭
    with pagination_cols[5]:
        if st.button("Last ⏭"):
            st.session_state.page = total_pages
            st.rerun()

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

    # First inject CSS
    st.markdown(css, unsafe_allow_html=True)

    # Then render HTML table
    st.markdown(
        f"""
        <div class="dataframe-wrapper">
            {html_table}
        </div>
        """,
        unsafe_allow_html=True
    )


with tab2:
    st.subheader("Top Petitions by Signatures")
    top_n = st.slider("Number of petitions to display", 5, 20, 10)

    chart_data = (
        filtered_df[["Petition_text", "Signatures"]]
        .dropna(subset=["Petition_text", "Signatures"])
        .sort_values("Signatures", ascending=False)
        .head(top_n)
        .copy()
    )

    if chart_data.empty:
        st.info("No petitions to show in chart with the current filters.")
    else:
        base = alt.Chart(chart_data).encode(
            x=alt.X("Signatures:Q", axis=alt.Axis(labels=False, ticks=False, title=None, grid=False)),  # Remove x-axis labels and ticks
            y=alt.Y("Petition_text:N", sort='-x', axis=alt.Axis(title=None, ticks=False, labelLimit=1000)),  # No y-axis title
            tooltip=[
                alt.Tooltip("Petition_text:N", title="Petition"),
                alt.Tooltip("Signatures:Q", format=",", title="Signatures")
            ]
        )

        bars = base.mark_bar()

        text = base.mark_text(
            align="left",
            baseline="middle",
            dx=7,  # position just outside right edge of bars
            color='white'
        ).encode(
            text=alt.Text("Signatures:Q", format=",")
        )

        chart = (bars + text).properties(height=top_n * 40)
        st.altair_chart(chart, use_container_width=True)
