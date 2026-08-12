"""Snowflake Native Streamlit dashboard backed by the Gold analyst review queue."""

import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session


st.set_page_config(
    page_title="Fraud Risk Operations Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px;}
      [data-testid="stSidebar"] {background: linear-gradient(180deg, #111827 0%, #172554 100%);}
      [data-testid="stSidebar"] * {color: #eef2ff;}
      .hero {padding: 1.6rem 1.8rem; border-radius: 18px; color: #f8fafc;
             background: linear-gradient(120deg, #172554 0%, #312e81 54%, #6d28d9 100%);
             box-shadow: 0 18px 35px rgba(49, 46, 129, .22); margin-bottom: 1.2rem;}
      .hero h1 {font-size: 2.1rem; margin: 0 0 .35rem 0; color: #ffffff;}
      .hero p {margin: 0; color: #dbeafe; font-size: 1rem;}
      .kpi-card {border: 1px solid #e2e8f0; border-radius: 15px; padding: 1.15rem 1.25rem;
                 background: linear-gradient(145deg, #ffffff, #f8fafc); min-height: 150px;
                 box-shadow: 0 8px 20px rgba(15, 23, 42, .06);}
      .kpi-label {font-size: .78rem; font-weight: 700; letter-spacing: .03em; color: #64748b; text-transform: uppercase; white-space: nowrap;}
      .kpi-value {font-size: 1.85rem; font-weight: 750; color: #0f172a; margin-top: .35rem;}
      .kpi-note {font-size: .78rem; color: #64748b; margin-top: .55rem; white-space: nowrap;}
      .priority-high {border-left: 5px solid #dc2626;}
      .priority-medium {border-left: 5px solid #f59e0b;}
      .priority-low {border-left: 5px solid #16a34a;}
      .section-caption {color: #64748b; margin-bottom: .7rem;}
      div[data-testid="stMetric"] {background: #ffffff; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

QUEUE_SQL = """
SELECT
    REVIEW_TRANSACTION_ID,
    TRANSACTION_TIME,
    TRANSACTION_AMOUNT,
    AMOUNT_RANGE,
    TIME_SEGMENT,
    TIME_WINDOW,
    RAPID_REPEAT_INDICATOR,
    AMOUNT_DEVIATION_SCORE,
    AMOUNT_PERCENTILE_RANK,
    REVIEW_PRIORITY
FROM FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE
"""


@st.cache_data(ttl=60, show_spinner="Loading Gold analytics data...")
def load_gold_queue() -> pd.DataFrame:
    session = get_active_session()
    data = session.sql(QUEUE_SQL).to_pandas()
    data.columns = [column.upper() for column in data.columns]
    data["TRANSACTION_TIME"] = pd.to_datetime(data["TRANSACTION_TIME"], errors="coerce")
    data["TRANSACTION_AMOUNT"] = pd.to_numeric(
        data["TRANSACTION_AMOUNT"], errors="coerce"
    ).fillna(0)
    data["RAPID_REPEAT_INDICATOR"] = pd.to_numeric(
        data["RAPID_REPEAT_INDICATOR"], errors="coerce"
    ).fillna(0).astype(int)
    data["TRANSACTION_DATE"] = data["TRANSACTION_TIME"].dt.date
    return data


def ordered_options(data: pd.DataFrame, column: str, preferred_order: list[str]) -> list[str]:
    values = data[column].dropna().astype(str).unique().tolist()
    return [value for value in preferred_order if value in values] + sorted(
        value for value in values if value not in preferred_order
    )


def compact_currency(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.2f}"


def compact_number(value: float) -> str:
    """Short display label while retaining exact values in chart hover labels."""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def human_date(value) -> str:
    """Consistent, unambiguous date label such as Aug 9."""
    return pd.Timestamp(value).strftime("%b %d").replace(" 0", " ")


def combined_volume_amount_chart(data: pd.DataFrame, category: str, title: str) -> dict:
    """One chart for operational volume and financial exposure, with exact hover values."""
    chart_data = data.copy()
    chart_data["Display Label"] = chart_data[category].map(human_date) if category == "TRANSACTION_DATE" else chart_data[category].astype(str)
    return {
        "title": title,
        "height": 390,
        "layer": [
            {"mark": {"type": "bar", "color": "#3b82f6"}, "encoding": {
                "x": {"field": "Display Label", "type": "nominal", "title": None},
                "y": {"field": "Transaction Count", "type": "quantitative", "title": "Transactions", "axis": {"format": "~s"}},
                "tooltip": [{"field": "Display Label", "title": "Period"}, {"field": "Transaction Count", "title": "Transactions", "format": ",.0f"}, {"field": "Transaction Amount", "title": "Total amount", "format": "$,.2f"}],
            }},
            {"mark": {"type": "line", "point": True, "color": "#f59e0b", "strokeWidth": 3}, "encoding": {
                "x": {"field": "Display Label", "type": "nominal", "title": None},
                "y": {"field": "Transaction Amount", "type": "quantitative", "title": "Amount", "axis": {"format": "$~s", "orient": "right"}},
                "tooltip": [{"field": "Display Label", "title": "Period"}, {"field": "Transaction Amount", "title": "Total amount", "format": "$,.2f"}, {"field": "Transaction Count", "title": "Transactions", "format": ",.0f"}],
            }},
        ],
        "resolve": {"scale": {"y": "independent"}},
    }


def metric_chart(data: pd.DataFrame, category: str, metric: str, title: str, color: str, currency: bool = False, line: bool = False) -> tuple[pd.DataFrame, dict]:
    """Separate compact-axis chart with exact value tooltips."""
    chart_data = data.copy()
    chart_data["Display Label"] = chart_data[category].map(human_date) if category == "TRANSACTION_DATE" else chart_data[category].astype(str)
    chart_data["Display Order"] = range(len(chart_data))
    return chart_data, {
        "title": title, "height": 370,
        "mark": {"type": "line" if line else "bar", "color": color, "point": line, "strokeWidth": 3 if line else 1},
        "encoding": {
            "x": {"field": "Display Label", "type": "nominal", "title": None, "sort": {"field": "Display Order", "order": "ascending"}},
            "y": {"field": metric, "type": "quantitative", "title": metric, "axis": {"format": "$~s" if currency else "~s"}},
            "tooltip": [{"field": "Display Label", "title": "Category"}, {"field": metric, "title": metric, "format": "$,.2f" if currency else ",.0f"}],
        },
    }


def amount_pie_chart(data: pd.DataFrame, metric: str, title: str, currency: bool = False) -> tuple[pd.DataFrame, dict]:
    """Simple pie chart for the five amount buckets, with percentages and exact hover values."""
    chart_data = data.copy()
    chart_data["Amount Bucket"] = chart_data["Amount Range"].astype(str)
    bucket_order = ["Very Low", "Low", "Medium", "High", "Very High"]
    bucket_colors = ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#ffd92f"]
    total = chart_data[metric].sum()
    chart_data["Percentage"] = 0 if total == 0 else (chart_data[metric] / total) * 100
    chart_data["Percentage Label"] = chart_data["Percentage"].map(lambda value: f"{value:.1f}%")
    pie_encoding = {
        "theta": {"field": metric, "type": "quantitative", "stack": True},
        "color": {
            "field": "Amount Bucket",
            "type": "nominal",
            "sort": bucket_order,
            "scale": {"domain": bucket_order, "range": bucket_colors},
            "legend": {"title": "Amount Bucket", "orient": "bottom"},
        },
        "order": {"field": "Display Order", "type": "ordinal"},
    }
    return chart_data, {
        "title": title,
        "height": 370,
        "layer": [
            {
                "mark": {"type": "arc", "stroke": "#ffffff", "strokeWidth": 2},
                "encoding": {
                    **pie_encoding,
                    "tooltip": [
                        {"field": "Amount Bucket", "title": "Amount Bucket"},
                        {"field": "Percentage Label", "title": "Share"},
                        {"field": metric, "title": metric, "format": "$,.2f" if currency else ",.0f"},
                    ],
                },
            },
            {
                "mark": {"type": "text", "radius": 105, "fontSize": 15, "fontWeight": "bold", "color": "#1f2937"},
                "encoding": {
                    "theta": {"field": metric, "type": "quantitative", "stack": True},
                    "order": {"field": "Display Order", "type": "ordinal"},
                    "text": {"field": "Percentage Label", "type": "nominal"},
                },
            },
        ],
    }


def priority_mix_chart(data: pd.DataFrame, dimension: str, title: str) -> tuple[pd.DataFrame, dict]:
    """100% stacked view keeps small priority groups visible despite count imbalance."""
    counts = priority_counts(data, dimension).reset_index()
    label_column = dimension
    counts["Display Label"] = counts[dimension].map(human_date) if dimension == "TRANSACTION_DATE" else counts[dimension].astype(str)
    long_counts = counts.melt(id_vars=["Display Label"], value_vars=["High", "Medium", "Low"], var_name="Review Priority", value_name="Transaction Count")
    return long_counts, {
        "title": title, "height": 390,
        "mark": {"type": "bar"},
        "encoding": {
            "x": {"field": "Display Label", "type": "nominal", "title": None},
            "y": {"aggregate": "sum", "field": "Transaction Count", "type": "quantitative", "stack": "normalize", "title": "Share of transactions", "axis": {"format": ".0%"}},
            "color": {"field": "Review Priority", "type": "nominal", "scale": {"domain": ["High", "Medium", "Low"], "range": ["#ef4444", "#f59e0b", "#22c55e"]}},
            "tooltip": [{"field": "Display Label", "title": "Period"}, {"field": "Review Priority", "title": "Priority"}, {"field": "Transaction Count", "title": "Transactions", "format": ",.0f"}],
        },
    }


def priority_counts(data: pd.DataFrame, dimension: str) -> pd.DataFrame:
    return (
        data.groupby([dimension, "REVIEW_PRIORITY"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["High", "Medium", "Low"], fill_value=0)
    )


def priority_order(value: str) -> int:
    return {"High": 1, "Medium": 2, "Low": 3}.get(value, 4)


try:
    df = load_gold_queue()
except Exception as error:
    st.error("The Gold analyst review queue could not be loaded.")
    st.exception(error)
    st.stop()

if df.empty:
    st.warning("No records are currently available in the Gold analyst review queue.")
    st.stop()

with st.sidebar:
    st.markdown("## Control Centre")
    st.caption("Use filters to focus the operational review queue.")
    if st.button("Clear all filters", use_container_width=True, type="primary"):
        for key in [
            "filter_priority", "filter_time_segment", "filter_time_window",
            "filter_amount_range", "filter_date_range", "filter_search", "filter_amount_range_slider",
        ]:
            st.session_state.pop(key, None)
        st.rerun()
    if st.button("Refresh Gold data", use_container_width=True):
        load_gold_queue.clear()
        st.rerun()

    st.divider()
    st.markdown("### Review filters")
    selected_priority = st.multiselect(
        "Review Priority",
        ordered_options(df, "REVIEW_PRIORITY", ["High", "Medium", "Low"]),
        key="filter_priority",
        placeholder="All priorities",
    )
    selected_time_segment = st.multiselect(
        "Time Segment",
        ordered_options(df, "TIME_SEGMENT", ["Morning", "Afternoon", "Evening", "Night"]),
        key="filter_time_segment",
        placeholder="All time segments",
    )
    selected_time_window = st.multiselect(
        "Time Window",
        ordered_options(df, "TIME_WINDOW", ["Midnight", "Business Hours", "Evening"]),
        key="filter_time_window",
        placeholder="All time windows",
    )
    selected_amount_range = st.multiselect(
        "Amount Range",
        ordered_options(df, "AMOUNT_RANGE", ["Very Low", "Low", "Medium", "High", "Very High"]),
        key="filter_amount_range",
        placeholder="All amount ranges",
    )
    selected_dates = st.date_input(
        "Transaction Date Range",
        value=(df["TRANSACTION_DATE"].min(), df["TRANSACTION_DATE"].max()),
        min_value=df["TRANSACTION_DATE"].min(),
        max_value=df["TRANSACTION_DATE"].max(),
        key="filter_date_range",
    )
    minimum_available_amount = float(df["TRANSACTION_AMOUNT"].min())
    maximum_available_amount = float(df["TRANSACTION_AMOUNT"].max())
    selected_min_amount, selected_max_amount = st.slider(
        "Transaction Amount Range",
        min_value=minimum_available_amount,
        max_value=maximum_available_amount,
        value=(minimum_available_amount, maximum_available_amount),
        step=max((maximum_available_amount - minimum_available_amount) / 500, 0.01),
        format="$%.2f",
        key="filter_amount_range_slider",
    )
    search_text = st.text_input(
        "Search Transaction ID",
        placeholder="Enter all or part of an ID",
        key="filter_search",
    )

filtered_df = df.copy()
if selected_priority:
    filtered_df = filtered_df[filtered_df["REVIEW_PRIORITY"].isin(selected_priority)]
if selected_time_segment:
    filtered_df = filtered_df[filtered_df["TIME_SEGMENT"].isin(selected_time_segment)]
if selected_time_window:
    filtered_df = filtered_df[filtered_df["TIME_WINDOW"].isin(selected_time_window)]
if selected_amount_range:
    filtered_df = filtered_df[filtered_df["AMOUNT_RANGE"].isin(selected_amount_range)]
if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    filtered_df = filtered_df[filtered_df["TRANSACTION_DATE"].between(selected_dates[0], selected_dates[1])]
filtered_df = filtered_df[
    filtered_df["TRANSACTION_AMOUNT"].between(selected_min_amount, selected_max_amount)
]
if search_text.strip():
    filtered_df = filtered_df[
        filtered_df["REVIEW_TRANSACTION_ID"].astype(str).str.contains(search_text.strip(), case=False, na=False)
    ]

st.markdown(
    """
    <div class="hero">
      <h1>🛡️ Fraud Risk Operations Dashboard</h1>
      <p>Prioritise transaction review using Gold-layer risk indicators. A review priority is not a confirmed fraud decision.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if filtered_df.empty:
    st.warning("No transactions match the selected filters. Select Clear all filters to reset the dashboard.")
    st.stop()

total_transactions = len(filtered_df)
total_amount = float(filtered_df["TRANSACTION_AMOUNT"].sum())
high_count = int((filtered_df["REVIEW_PRIORITY"] == "High").sum())
medium_count = int((filtered_df["REVIEW_PRIORITY"] == "Medium").sum())
rapid_repeat_count = int(filtered_df["RAPID_REPEAT_INDICATOR"].sum())

cards = st.columns(5)
card_values = [
    ("Transactions", compact_number(total_transactions), "Review queue volume", ""),
    ("Total Amount", compact_currency(total_amount), "Value under review", ""),
    ("High Risk", compact_number(high_count), "Immediate attention", "priority-high"),
    ("Medium Risk", compact_number(medium_count), "Review next", "priority-medium"),
    ("Rapid Repeats", compact_number(rapid_repeat_count), "Repeat-pattern alerts", "priority-low"),
]
for column, (label, value, note, style) in zip(cards, card_values):
    with column:
        st.markdown(
            f'<div class="kpi-card {style}"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
summary_tab, daily_tab, risk_tab, amount_tab, analyst_tab = st.tabs([
    "Executive Summary", "Daily Overview", "Risk & Time", "Amount Analysis", "Analyst Review Queue"
])

with summary_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Review Queue by Priority")
        st.caption("High-priority transactions appear first in the analyst queue.")
        counts = filtered_df.groupby("REVIEW_PRIORITY").size().reindex(["High", "Medium", "Low"], fill_value=0).rename("Transaction Count").reset_index()
        counts.columns = ["Review Priority", "Transaction Count"]
        chart_data, chart_spec = metric_chart(counts, "Review Priority", "Transaction Count", "Review queue by priority", "#7c3aed")
        st.vega_lite_chart(chart_data, chart_spec, use_container_width=True)
    with right:
        st.subheader("Transaction Amount by Priority")
        st.caption("Shows financial exposure represented by each review-priority band.")
        amounts = filtered_df.groupby("REVIEW_PRIORITY")["TRANSACTION_AMOUNT"].sum().reindex(["High", "Medium", "Low"], fill_value=0).rename("Transaction Amount").reset_index()
        amounts.columns = ["Review Priority", "Transaction Amount"]
        chart_data, chart_spec = metric_chart(amounts, "Review Priority", "Transaction Amount", "Transaction amount by priority", "#0891b2", currency=True)
        st.vega_lite_chart(chart_data, chart_spec, use_container_width=True)

    st.subheader("Operational Snapshot")
    snapshot = pd.DataFrame({
        "Review Priority": ["High", "Medium", "Low"],
        "Transaction Count": [
            int((filtered_df["REVIEW_PRIORITY"] == "High").sum()),
            int((filtered_df["REVIEW_PRIORITY"] == "Medium").sum()),
            int((filtered_df["REVIEW_PRIORITY"] == "Low").sum()),
        ],
        "Transaction Amount": [
            float(filtered_df.loc[filtered_df["REVIEW_PRIORITY"] == "High", "TRANSACTION_AMOUNT"].sum()),
            float(filtered_df.loc[filtered_df["REVIEW_PRIORITY"] == "Medium", "TRANSACTION_AMOUNT"].sum()),
            float(filtered_df.loc[filtered_df["REVIEW_PRIORITY"] == "Low", "TRANSACTION_AMOUNT"].sum()),
        ],
    })
    st.dataframe(
        snapshot,
        use_container_width=True,
        hide_index=True,
        column_config={"Transaction Amount": st.column_config.NumberColumn(format="$%.2f")},
    )

with daily_tab:
    daily = filtered_df.groupby("TRANSACTION_DATE").agg(
        Transaction_Count=("REVIEW_TRANSACTION_ID", "count"),
        Transaction_Amount=("TRANSACTION_AMOUNT", "sum"),
    ).sort_index()
    daily = daily.rename(columns={"Transaction_Count": "Transaction Count", "Transaction_Amount": "Transaction Amount"}).reset_index()
    first, second = st.columns(2)
    with first:
        chart_data, chart_spec = metric_chart(daily, "TRANSACTION_DATE", "Transaction Count", "Daily transaction count", "#2563eb", line=True)
        st.vega_lite_chart(chart_data, chart_spec, use_container_width=True)
    with second:
        chart_data, chart_spec = metric_chart(daily, "TRANSACTION_DATE", "Transaction Amount", "Daily transaction amount", "#14b8a6", currency=True, line=True)
        st.vega_lite_chart(chart_data, chart_spec, use_container_width=True)
    st.caption("Hover any bar for the exact count or transaction amount.")

with risk_tab:
    first, second = st.columns(2)
    with first:
        st.subheader("Review Priority by Time Window")
        st.caption("100% stacked bars keep High and Medium priorities visible even when Low priority dominates.")
        priority_data, priority_spec = priority_mix_chart(filtered_df, "TIME_WINDOW", "Priority mix by time window")
        st.vega_lite_chart(priority_data, priority_spec, use_container_width=True)
    with second:
        st.subheader("Daily Review Priority Trend")
        st.caption("Each day totals 100%; hover a segment to see its exact transaction count.")
        priority_data, priority_spec = priority_mix_chart(filtered_df, "TRANSACTION_DATE", "Daily priority mix")
        st.vega_lite_chart(priority_data, priority_spec, use_container_width=True)
    st.subheader("Time Segment Review Mix")
    priority_data, priority_spec = priority_mix_chart(filtered_df, "TIME_SEGMENT", "Priority mix by time segment")
    st.vega_lite_chart(priority_data, priority_spec, use_container_width=True)

with amount_tab:
    amount_summary = filtered_df.groupby("AMOUNT_RANGE").agg(
        Transaction_Count=("REVIEW_TRANSACTION_ID", "count"),
        Transaction_Amount=("TRANSACTION_AMOUNT", "sum"),
        High_Priority_Count=("REVIEW_PRIORITY", lambda values: int((values == "High").sum())),
    ).reindex(["Very Low", "Low", "Medium", "High", "Very High"], fill_value=0)
    amount_summary["Low Amount"] = filtered_df.groupby("AMOUNT_RANGE")["TRANSACTION_AMOUNT"].min()
    amount_summary["High Amount"] = filtered_df.groupby("AMOUNT_RANGE")["TRANSACTION_AMOUNT"].max()
    amount_chart = amount_summary.reset_index().rename(columns={"AMOUNT_RANGE": "Amount Range", "Transaction_Count": "Transaction Count", "Transaction_Amount": "Transaction Amount"})
    amount_chart["Amount Range"] = amount_summary.index.astype(str)
    amount_chart["Display Order"] = range(len(amount_chart))
    first, second = st.columns(2)
    with first:
        chart_data, chart_spec = amount_pie_chart(amount_chart, "Transaction Count", "Transaction count by amount bucket")
        st.vega_lite_chart(chart_data, chart_spec, use_container_width=True)
    with second:
        chart_data, chart_spec = amount_pie_chart(amount_chart, "Transaction Amount", "Transaction amount by amount bucket", currency=True)
        st.vega_lite_chart(chart_data, chart_spec, use_container_width=True)
    st.caption("Charts use amount-bucket labels. Hover for exact transaction counts and dollar amounts.")
    st.subheader("Amount Range Index")
    range_index = amount_summary.reset_index().rename(columns={"AMOUNT_RANGE": "Amount Bucket"})
    range_index["Amount Range"] = range_index.apply(
        lambda row: (
            "No transactions after filters"
            if pd.isna(row["Low Amount"]) or pd.isna(row["High Amount"])
            else f"${row['Low Amount']:,.2f} to ${row['High Amount']:,.2f}"
        ),
        axis=1,
    )
    st.dataframe(
        range_index[["Amount Bucket", "Amount Range"]],
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Amount Range Summary")
    amount_summary["Transaction Amount (K)"] = amount_summary["Transaction_Amount"] / 1_000
    amount_summary["Low Amount (K)"] = amount_summary["Low Amount"] / 1_000
    amount_summary["High Amount (K)"] = amount_summary["High Amount"] / 1_000
    st.dataframe(
        amount_summary[["Transaction_Count", "High_Priority_Count", "Transaction Amount (K)", "Low Amount (K)", "High Amount (K)"]],
        use_container_width=True,
        column_config={
            "Transaction Amount (K)": st.column_config.NumberColumn("Transaction Amount", format="$%.1fK"),
            "Low Amount (K)": st.column_config.NumberColumn("Low Amount", format="$%.1fK"),
            "High Amount (K)": st.column_config.NumberColumn("High Amount", format="$%.1fK"),
        },
    )

with analyst_tab:
    st.subheader("Analyst Review Queue")
    st.caption("Sorted by review priority, rapid-repeat indicator, amount percentile rank, then transaction time.")
    show_rows = st.select_slider("Rows to display", options=[25, 50, 100, 250, 500], value=100)
    queue = filtered_df.copy()
    queue["Priority_Order"] = queue["REVIEW_PRIORITY"].map(priority_order)
    queue = queue.sort_values(
        ["Priority_Order", "RAPID_REPEAT_INDICATOR", "AMOUNT_PERCENTILE_RANK", "TRANSACTION_TIME"],
        ascending=[True, False, False, False],
    ).rename(columns={
        "REVIEW_TRANSACTION_ID": "Transaction ID",
        "TRANSACTION_TIME": "Transaction Time",
        "TRANSACTION_AMOUNT": "Transaction Amount",
        "AMOUNT_RANGE": "Amount Range",
        "TIME_SEGMENT": "Time Segment",
        "TIME_WINDOW": "Time Window",
        "RAPID_REPEAT_INDICATOR": "Rapid Repeat Indicator",
        "AMOUNT_DEVIATION_SCORE": "Amount Deviation Score",
        "AMOUNT_PERCENTILE_RANK": "Amount Percentile Rank",
        "REVIEW_PRIORITY": "Review Priority",
    })
    display_columns = [
        "Review Priority", "Transaction ID", "Transaction Time", "Transaction Amount",
        "Amount Range", "Time Segment", "Time Window", "Rapid Repeat Indicator",
        "Amount Deviation Score", "Amount Percentile Rank",
    ]
    st.dataframe(
        queue[display_columns].head(show_rows),
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "Transaction Amount": st.column_config.NumberColumn(format="$%.2f"),
            "Amount Deviation Score": st.column_config.NumberColumn(format="%.2f"),
            "Amount Percentile Rank": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.download_button(
        "Download filtered review queue (CSV)",
        data=queue[display_columns].to_csv(index=False).encode("utf-8"),
        file_name="fraud_analyst_review_queue.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption("Gold source: FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE")
