import requests
import pandas as pd
import streamlit as st
import math
import altair as alt
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

@st.cache_data(show_spinner=True, ttl=3600)
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
                "Debate transcript": f'<a href="{debate.get("transcript_url")}" target="_blank">Transcript</a>' if debate.get(
                    "transcript_url") else "",
                "Debate research": f'<a href="{debate.get("debate_pack_url")}" target="_blank">Research</a>' if debate.get(
                    "debate_pack_url") else "",
                "Department": departments[0].get("name") if departments else "Unassigned"
            })

        next_link = data.get("links", {}).get("next")
        if not next_link:
            break

        page += 1

    df = pd.DataFrame(all_rows)

    def days_between(start_date, end_date):
        start = pd.to_datetime(start_date, errors='coerce')
        end = pd.to_datetime(end_date, errors='coerce')

        if pd.isna(start) or pd.isna(end):
            return None

        if start.tz is not None:
            start = start.tz_convert(None)
        if end.tz is not None:
            end = end.tz_convert(None)

        diff = (end - start).days
        return int(diff) if diff >= 0 else None

    # Calculate the days-between columns here
    df["Opened → Resp Threshold, days"] = df.apply(lambda row: days_between(row["Opened at"], row["Response threshold (10,000) reached at"]), axis=1)
    df["Opened → Debate Threshold, days"] = df.apply(lambda row: days_between(row["Opened at"], row["Debate threshold (100,000) reached at"]), axis=1)
    df["Created → Opened, days"] = df.apply(lambda row: days_between(row["Created at"], row["Opened at"]), axis=1)
    df["Resp Threshold → Response, days"] = df.apply(lambda row: days_between(row["Response threshold (10,000) reached at"], row["Government response at"]), axis=1)
    df["Debate Threshold → Scheduled, days"] = df.apply(lambda row: days_between(row["Debate threshold (100,000) reached at"], row["Scheduled debate date"]), axis=1)
    df["Scheduled → Outcome, days"] = df.apply(lambda row: days_between(row["Scheduled debate date"], row["Debate outcome at"]), axis=1)

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

    effective_min_signatures = custom_min
    effective_max_signatures = custom_max

    st.subheader("Petitions")
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

    # Columns to exclude
    excluded_columns = {"Petition_text", "Debate video", "Debate transcript", "Debate research"}

    # Custom column list for dropdown (hide "Petition_text", show "Petition" instead)
    sort_columns_display = [
        "Petition" if col == "Petition_text" else col
        for col in df.columns
        if col not in excluded_columns
    ]

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

# Initialize session state variable if it doesn't exist
if "last_refreshed" not in st.session_state:
    st.session_state.last_refreshed = datetime.now()

col_last_updated, col_refresh, col_download, col_empty = st.columns([3, 1, 1, 7])

with col_last_updated:
    last_updated_plus_one = st.session_state.last_refreshed + timedelta(hours=1)
    st.markdown(
        f"**Last Updated:** {last_updated_plus_one.strftime('%Y-%m-%d %H:%M:%S')}<br>"
        "This app automatically refreshes every hour at **HH:00:00**",
        unsafe_allow_html=True
    )

with col_refresh:
    if st.button("⟳ Refresh Data"):
        fetch_petitions.clear()
        st.rerun()

with col_download:
    csv_data = filtered_df.to_csv(index=False, header=True).encode('utf-8')
    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name="uk_parliament_petitions.csv",
        mime="text/csv"
    )

with col_empty:
    pass

st.success(f"{len(df)} petitions loaded | {len(filtered_df)} shown after filtering")

# Additional Metrics
num_response_threshold = filtered_df["Response threshold (10,000) reached at"].notna().sum()
num_debate_threshold = filtered_df["Debate threshold (100,000) reached at"].notna().sum()
num_open_closed = filtered_df["State"].str.lower().isin(["open", "closed"]).notna().sum()
num_gov_response = filtered_df["Government response at"].notna().sum()
num_scheduled_debate = filtered_df["Scheduled debate date"].notna().sum()
num_debate_outcome = filtered_df["Debate outcome at"].notna().sum()

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Petitions with Response Threshold Reached", num_response_threshold)
col2.metric("Petitions with Debate Threshold Reached", num_debate_threshold)
col3.metric("Open + Closed Petitions", num_open_closed)
col4.metric("Petitions with Government Response", num_gov_response)
col5.metric("Petitions with Scheduled Debates", num_scheduled_debate)
col6.metric("Petitions with Debate Outcome", num_debate_outcome)

avg_opened_to_response_threshold = avg_days_between(filtered_df, "Opened at", "Response threshold (10,000) reached at")
avg_opened_to_debate_threshold = avg_days_between(filtered_df, "Opened at", "Debate threshold (100,000) reached at")
avg_created_to_opened = avg_days_between(filtered_df, "Created at", "Opened at")
avg_response_threshold_to_response = avg_days_between(filtered_df, "Response threshold (10,000) reached at", "Government response at")
avg_debate_threshold_to_scheduled = avg_days_between(filtered_df, "Debate threshold (100,000) reached at", "Scheduled debate date")
avg_scheduled_to_outcome = avg_days_between(filtered_df, "Scheduled debate date", "Debate outcome at")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Avg Opened → Resp Threshold, days", avg_opened_to_response_threshold or "N/A")
col2.metric("Avg Opened → Debate Threshold, days", avg_opened_to_debate_threshold or "N/A")
col3.metric("Avg Created → Opened, days", avg_created_to_opened or "N/A")
col4.metric("Avg Resp Threshold → Response, days", avg_response_threshold_to_response or "N/A")
col5.metric("Avg Debate Threshold → Scheduled, days", avg_debate_threshold_to_scheduled or "N/A")
col6.metric("Avg Scheduled → Outcome, days", avg_scheduled_to_outcome or "N/A")

# Initialize the session state for tab if not set
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 0

# Inject custom CSS to style the tabs
st.markdown("""
    <style>
    /* Increase font size and padding */
    .stTabs [data-baseweb="tab"] {
        font-size: 18px;
        padding: 12px 24px;
        font-weight: 600;
        border-bottom: 3px solid transparent;
    }
    </style>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Petition List", "Top 10 Petitions by Metric"])

# Tab 1: Table only
with tab1:
    st.session_state.active_tab = 0

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
                if st.session_state.page != input_page:
                    st.session_state.page = input_page
                    st.rerun()  # Rerun after page change
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

    int_cols = [
        "Opened → Resp Threshold, days",
        "Opened → Debate Threshold, days",
        "Created → Opened, days",
        "Resp Threshold → Response, days",
        "Debate Threshold → Scheduled, days",
        "Scheduled → Outcome, days"
    ]

    for col in int_cols:
        df_display[col] = df_display[col].astype("Int64")

    df_display["Response"] = df_display["Response"].apply(add_tooltip)

    str_cols = df_display.select_dtypes(include=["object", "string"]).columns
    df_display.loc[:, str_cols] = df_display.loc[:, str_cols].fillna("")

    if "Petition_text" in df_display.columns:
        df_display = df_display.drop(columns=["Petition_text"])

    # Get index positions (1-based) of the columns to right-align
    right_align_cols = [
        "Signatures",
        "Opened → Resp Threshold, days",
        "Opened → Debate Threshold, days",
        "Created → Opened, days",
        "Resp Threshold → Response, days",
        "Debate Threshold → Scheduled, days",
        "Scheduled → Outcome, days"
    ]

    right_align_indices = [df_display.columns.get_loc(col) + 1 for col in right_align_cols if col in df_display.columns]


    # Helper function to safely convert values to float (preserving ints if possible)
    def safe_float(val):
        if pd.isna(val):
            return val
        if isinstance(val, str):
            try:
                return int(val.replace(',', ''))
            except ValueError:
                try:
                    return float(val.replace(',', ''))
                except ValueError:
                    return val
        return val

    # Convert hex color string to RGB tuple
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    # Convert RGB tuple to hex color string
    def rgb_to_hex(rgb_color):
        return '#{:02x}{:02x}{:02x}'.format(*rgb_color)


    def interpolate_color(value, vmin, vmax, start_color, end_color):
        if pd.isna(value):
            return ""

        norm_val = (value - vmin) / (vmax - vmin) if vmax > vmin else 0.5

        def parse_color(color):
            if isinstance(color, str):
                if color.startswith('#'):
                    return hex_to_rgb(color)
                elif color.startswith('rgb'):
                    # Extract the numbers inside 'rgb(...)'
                    return tuple(map(int, color.strip('rgb()').split(',')))
            # fallback or error
            raise ValueError(f"Unsupported color format: {color}")

        start_rgb = parse_color(start_color)
        end_rgb = parse_color(end_color)

        interp_rgb = tuple(
            int(start_c + (end_c - start_c) * norm_val)
            for start_c, end_c in zip(start_rgb, end_rgb)
        )
        return rgb_to_hex(interp_rgb)


    # Use custom gradient colors here
    def color_scale(value, vmin, vmax):
        return interpolate_color(value, vmin, vmax, 'rgb(184,95,75)', '#0e1117')

    # Styling function to be applied via Styler.applymap
    def style_val_factory(vmin, vmax):
        def style_val(val):
            numeric_val = safe_float(val)
            color = color_scale(numeric_val, vmin, vmax)
            return f'background-color: {color}; padding: 4px; text-align: right;'

        return style_val

    # Reset index first to remove it from the HTML output
    df_display_reset = df_display.reset_index(drop=True)

    # Apply styles via Styler without modifying data
    styler = df_display.style

    for col in int_cols:
        if col in df_display_reset.columns:
            clean_col = df_display_reset[col].apply(safe_float)
            vmin = clean_col.min()
            vmax = clean_col.max()
            styler = styler.map(style_val_factory(vmin, vmax), subset=[col])

    # Hide the index explicitly (though index is now default RangeIndex)
    styler = styler.hide(axis="index")

    html_table = styler.to_html(escape=False)

    css = f"""
    <style>
        div.dataframe-wrapper {{
            max-height: 600px;
            overflow-y: auto;
            border: 1px solid #ddd;
        }}
        table {{
            width: max-content;
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
            min-width: 150px;
        }}
    """ + "\n".join([
        f"table th:nth-child({i}), table td:nth-child({i}) {{ text-align: right !important; }}"
        for i in right_align_indices
    ]) + """
        table td:nth-child(2),
        table td:nth-child(3),
        table td:nth-child(4),
        table td:nth-child(5),
        table td:nth-child(6),
        table td:nth-child(7),
        table td:nth-child(8),
        table td:nth-child(9),
        table td:nth-child(10),
        table td:nth-child(11),
        table td:nth-child(13),
        table td:nth-child(14),
        table td:nth-child(15),
        table td:nth-child(17),
        table td:nth-child(18),
        table td:nth-child(19),
        table td:nth-child(20),
        table td:nth-child(21),
        table td:nth-child(22) {
            width: 100px;
            max-width: 100px;
        }
        table td:nth-child(1), table td:nth-child(12), table td:nth-child(16) {
            max-width: 250px;
        }
        /* First column sticky */
        table th:nth-child(1), table td:nth-child(1) {
            position: sticky;
            left: 0;
            background: #0e1117;
            z-index: 3;
        }
        /* Top-left cell (both row and column header) */
        table thead th:nth-child(1) {
            position: sticky;
            top: 0;
            left: 0;
            background: #0e1117;
            z-index: 5;
        }
        table td span[title] {
            cursor: help;
            border-bottom: 1px dotted #999;
        }
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
    st.session_state.active_tab = 1

    # Choose metric in chart
    metric_options = [
        "Signatures",
        "Opened → Resp Threshold, days",
        "Opened → Debate Threshold, days",
        "Created → Opened, days",
        "Resp Threshold → Response, days",
        "Debate Threshold → Scheduled, days",
        "Scheduled → Outcome, days"
    ]
    selected_metric = st.selectbox("Metric (Select ascending or descending order in the sidebar)", metric_options)

    # Sort and limit
    chart_data = (
        filtered_df[["Petition_text", selected_metric]]
        .dropna(subset=["Petition_text", selected_metric])
        .sort_values(by=selected_metric, ascending=sort_ascending)
        .head(10)
        .copy()
    )

    if chart_data.empty:
        st.info("No petitions to show in chart with the current filters.")
    else:
        base = alt.Chart(chart_data).encode(
            x=alt.X(f"{selected_metric}:Q", axis=alt.Axis(labels=False, ticks=False, title=None, grid=False)),
            y=alt.Y(
                "Petition_text:N",
                sort='-x' if not sort_ascending else 'x',
                axis=alt.Axis(
                    title=None,
                    ticks=False,
                    labels=True,
                    labelLimit=1000,
                    labelAngle=0,   # horizontal labels, try changing to 45 or -45 if needed
                    labelAlign='right'
                )
            ),
            tooltip=[
                alt.Tooltip("Petition_text:N", title="Petition"),
                alt.Tooltip(f"{selected_metric}:Q", format=",", title=selected_metric)
            ]
        )

        bars = base.mark_bar()

        text = base.mark_text(
            align="left",
            baseline="middle",
            dx=7,
            color='white'
        ).encode(
            text=alt.Text(f"{selected_metric}:Q", format=",")
        )

        # Calculate average of the selected metric over all filtered data (not just top_n)
        average_value = filtered_df[selected_metric].mean()

        # Create vertical line at the average
        average_line = alt.Chart(pd.DataFrame({selected_metric: [average_value]})).mark_rule(color='red').encode(
            x=alt.X(f"{selected_metric}:Q")
        )

        # Create label text for the average line
        average_label = alt.Chart(pd.DataFrame({
            selected_metric: [average_value],
            'label': [f"Average: {average_value:,.0f}"]  # Format number as integer
        })).mark_text(
            align='left',
            baseline='bottom',
            dx=5,
            dy=-5,
            color='white',
            fontWeight='bold',
            tooltip=None
        ).encode(
            x=alt.X(f"{selected_metric}:Q"),
            y=alt.value(0),
            text='label:N'
        )

        chart = (bars + text + average_line + average_label).properties(
            height=600,  # Increased height for more space for labels
            width=700
        )

        st.altair_chart(chart, use_container_width=True)


