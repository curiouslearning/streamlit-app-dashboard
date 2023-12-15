# Izzy Bryant
# Last updated Dec 2022
# 02_Campaign_Details.py
import streamlit as st
from google.oauth2 import service_account
from google.cloud import bigquery
from gsheetsdb import connect
import datetime
import pandas as pd
import db_dtypes
import json
import plotly
import plotly.express as px
import plotly.graph_objects as go
from millify import millify

# from plotly_calplot import calplot
import calplot

# --- DATA ---
# Create a Google Sheets connection object.
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
    ],
)
conn = connect(credentials=credentials)
# Create BigQuery API client.
bq_credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=bq_credentials)


def run_query(query):
    rows = conn.execute(query, headers=1)
    rows = rows.fetchall()
    return rows


@st.cache_data
def get_campaign_data():
    campaign_sheet_url = st.secrets["Campaign_gsheets_url"]
    campaign_rows = run_query(f'SELECT * FROM "{campaign_sheet_url}"')
    campaign_data = pd.DataFrame(
        columns=[
            "Campaign Name",
            "Language",
            "Country",
            "Start Date",
            "End Date",
            "Total Cost (USD)",
        ],
        data=campaign_rows,
    )
    campaign_data["Start Date"] = (pd.to_datetime(campaign_data["Start Date"])).dt.date
    campaign_data["End Date"] = (
        pd.to_datetime(campaign_data["End Date"])
        + pd.DateOffset(months=1)
        - pd.Timedelta(1, unit="D")
    ).dt.date
    campaign_data = campaign_data.astype({"Total Cost (USD)": "float"})
    return campaign_data


@st.cache_data
def get_user_data(start_date, end_date, app, country):
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    if country == "All":
        sql_query = f"""
            SELECT * FROM `dataexploration-193817.user_data.ftm_users`
            WHERE LA_date BETWEEN @start AND @end
            AND app_id = @app
        """
    else:
        sql_query = f"""
            SELECT * FROM `dataexploration-193817.user_data.ftm_users`
            WHERE LA_date BETWEEN @start AND @end
            AND app_id = @app
            AND country = @country
        """
    query_parameters = [
        bigquery.ScalarQueryParameter("start", "STRING", start),
        bigquery.ScalarQueryParameter("end", "STRING", end),
        bigquery.ScalarQueryParameter("app", "STRING", app),
        bigquery.ScalarQueryParameter("country", "STRING", country),
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
    rows_raw = client.query(sql_query, job_config=job_config)
    rows = [dict(row) for row in rows_raw]
    df = pd.DataFrame(rows)
    df["LA_date"] = (pd.to_datetime(df["LA_date"])).dt.date
    df["max_lvl_date"] = (pd.to_datetime(df["max_lvl_date"])).dt.date
    return df


@st.cache_data
def get_apps_data():
    apps_sheet_url = st.secrets["ftm_apps_gsheets_url"]
    apps_rows = run_query(
        f'SELECT app_id, language, bq_property_id, bq_project_id, total_lvls FROM "{apps_sheet_url}"'
    )
    apps_data = pd.DataFrame(
        columns=["app_id", "language", "bq_property_id", "bq_project_id", "total_lvls"],
        data=apps_rows,
    )
    return apps_data


# @st.cache_data
def get_ra_segments(campaign_data, total_lvls, user_data):
    df = pd.DataFrame(columns=["segment", "la", "perc_la", "ra", "rac"])
    seg = []
    ra = []
    for lvl in user_data["max_lvl"]:
        perc = lvl / total_lvls
        ra.append(perc)
        if perc < 0.1:
            seg.append(0.1)
        elif 0.1 <= perc < 0.2:
            seg.append(0.2)
        elif 0.2 <= perc < 0.3:
            seg.append(0.3)
        elif 0.3 <= perc < 0.4:
            seg.append(0.4)
        elif 0.4 <= perc < 0.5:
            seg.append(0.5)
        elif 0.5 <= perc < 0.6:
            seg.append(0.6)
        elif 0.6 <= perc < 0.7:
            seg.append(0.7)
        elif 0.7 <= perc < 0.8:
            seg.append(0.8)
        elif 0.8 <= perc < 0.9:
            seg.append(0.9)
        else:
            seg.append(1)
    user_data["seg"] = seg
    user_data["ra"] = ra
    res = (
        user_data.groupby("seg")
        .agg(la=("user_pseudo_id", "count"), ra=("ra", "mean"))
        .reset_index()
    )
    res["la_perc"] = res["la"] / res["la"].sum()
    res["rac"] = round(
        campaign_data["Total Cost (USD)"][0]
        * res["la_perc"]
        / (res["ra"] * res["la"].sum()),
        2,
    )
    return res


@st.cache_data
def get_campaign_metrics():
    camp_metrics_url = st.secrets["campaign_metrics_gsheets_url"]
    camp_metrics_rows = run_query(f'SELECT * FROM "{camp_metrics_url}"')
    camp_metrics_data = pd.DataFrame(
        columns=["campaign_name", "la", "lac", "ra", "rac"], data=camp_metrics_rows
    )
    camp_metrics_data = camp_metrics_data.fillna(0)
    camp_metrics_data = camp_metrics_data.astype(
        {"la": "int", "lac": "float", "ra": "float", "rac": "float"}
    )
    return camp_metrics_data


@st.cache_data
def get_daily_activity(user_data, start_date, app, country, bq_id, property_id):
    user_ids = user_data["user_pseudo_id"].tolist()
    if country == "All":
        sql_query = f"""
            SELECT event_date, COUNT(event_name) AS levels_played FROM `{bq_id}.analytics_{property_id}.events_20*`,
            UNNEST(event_params) AS params
            WHERE PARSE_DATE('%y%m%d', _table_suffix) BETWEEN @start AND @end
            AND app_info.id = @app
            AND user_pseudo_id IN UNNEST(@user_ids)
            AND event_name LIKE 'GamePlay'
            AND params.key = 'action'
            AND (params.value.string_value LIKE '%LevelSuccess%'
            OR params.value.string_value LIKE '%LevelFail%')
            GROUP BY event_date
            ORDER BY event_date
        """
    else:
        sql_query = f"""
            SELECT event_date, COUNT(event_name) AS levels_played FROM `{bq_id}.analytics_{property_id}.events_20*`,
            UNNEST(event_params) AS params
            WHERE PARSE_DATE('%y%m%d', _table_suffix) BETWEEN @start AND @end
            AND app_info.id = @app
            AND geo.country = @country
            AND user_pseudo_id IN UNNEST(@user_ids)
            AND event_name LIKE 'GamePlay'
            AND params.key = 'action'
            AND (params.value.string_value LIKE '%LevelSuccess%'
            OR params.value.string_value LIKE '%LevelFail%')
            GROUP BY event_date
            ORDER BY event_date 
        """
    query_parameters = [
        bigquery.ScalarQueryParameter("start", "DATE", start_date),
        bigquery.ScalarQueryParameter(
            "end", "DATE", pd.to_datetime("today").date() - pd.Timedelta(1, unit="D")
        ),
        bigquery.ScalarQueryParameter("app", "STRING", app),
        bigquery.ScalarQueryParameter("country", "STRING", country),
        bigquery.ScalarQueryParameter("bq_id", "STRING", bq_id),
        bigquery.ScalarQueryParameter("property_id", "STRING", property_id),
        bigquery.ArrayQueryParameter("user_ids", "STRING", user_ids),
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
    rows_raw = client.query(sql_query, job_config=job_config)
    rows = [dict(row) for row in rows_raw]
    df = pd.DataFrame(rows)
    df["event_date"] = pd.to_datetime(df["event_date"])
    return df


# --- UI ---
st.title("Campaign Details")
expander = st.expander("Definitions")
# CSS to inject contained in a string
hide_table_row_index = """
            <style>
            thead tr th:first-child {display:none}
            tbody th {display:none}
            </style>
            """
# Inject CSS with Markdown
st.markdown(hide_table_row_index, unsafe_allow_html=True)
def_df = pd.DataFrame(
    [
        [
            "LA",
            "Learner Acquisition",
            "The number of users that have completed at least one FTM level.",
            "COUNT(Learners)",
        ],
        [
            "LAC",
            "Learner Acquisition Cost",
            "The cost (USD) of acquiring one learner.",
            "Total Spend / LA",
        ],
        [
            "RA",
            " Reading Acquisition",
            "The  average percentage of FTM levels completed per learner from start date to today.",
            "AVG Max Level Reached / Total Levels",
        ],
        [
            "RAC",
            "Reading Acquisition Cost",
            "The cost (USD) associated with one learner reaching the average percentage of FTM levels (RA).",
            "Total Spend / RA * LA",
        ],
    ],
    columns=["Acronym", "Name", "Definition", "Formula"],
)
expander.table(def_df)
ftm_campaigns = get_campaign_data()
select_campaigns = st.sidebar.selectbox(
    "Select Campaign", ftm_campaigns["Campaign Name"], 0, key="campaign"
)

# SET VARIABLES
campaign = st.session_state["campaign"]
ftm_apps = get_apps_data()
start_date = ftm_campaigns.loc[
    ftm_campaigns["Campaign Name"] == campaign, "Start Date"
].item()
end_date = ftm_campaigns.loc[
    ftm_campaigns["Campaign Name"] == campaign, "End Date"
].item()
language = ftm_campaigns.loc[
    ftm_campaigns["Campaign Name"] == campaign, "Language"
].item()
app = ftm_apps.loc[ftm_apps["language"] == language, "app_id"].item()
country = ftm_campaigns.loc[
    ftm_campaigns["Campaign Name"] == campaign, "Country"
].item()
bq_id = ftm_apps.loc[ftm_apps["language"] == language, "bq_project_id"].item()
property_id = ftm_apps.loc[ftm_apps["language"] == language, "bq_property_id"].item()
users_df = get_user_data(start_date, end_date, app, country)
campaign_data = get_campaign_metrics()

# METRICS
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total LA", millify(str(len(users_df))))
col2.metric(
    "Avg RA",
    millify(
        campaign_data.loc[campaign_data["campaign_name"] == campaign, "ra"].item(), 2
    ),
)
col3.metric(
    "Avg LAC",
    millify(
        campaign_data.loc[campaign_data["campaign_name"] == campaign, "lac"].item(), 2
    ),
)
col4.metric(
    "Avg RAC",
    millify(
        campaign_data.loc[campaign_data["campaign_name"] == campaign, "rac"].item(), 2
    ),
)
col5.metric(
    "Total Spend (USD)",
    millify(
        ftm_campaigns.loc[
            ftm_campaigns["Campaign Name"] == campaign, "Total Cost (USD)"
        ].item(),
        1,
    ),
)

# DAILY LEARNERS ACQUIRED
daily_la = (
    users_df.groupby(["LA_date"])["user_pseudo_id"]
    .count()
    .reset_index(name="Learners Acquired")
)
daily_la["7 Day Rolling Mean"] = daily_la["Learners Acquired"].rolling(7).mean()
daily_la["30 Day Rolling Mean"] = daily_la["Learners Acquired"].rolling(30).mean()
daily_la_fig = px.line(
    daily_la,
    x="LA_date",
    y="Learners Acquired",
    labels={"LA_date": "Date", "Learners Acquired": "LA"},
    title="Daily LA",
)
rm_fig = px.line(
    daily_la,
    x="LA_date",
    y=["7 Day Rolling Mean", "30 Day Rolling Mean"],
    color_discrete_map={"7 Day Rolling Mean": "green", "30 Day Rolling Mean": "red"},
)
daily_la_fig.add_trace(rm_fig.data[0])
daily_la_fig.add_trace(rm_fig.data[1])
st.plotly_chart(daily_la_fig)

if country == "All":
    country_la = (
        users_df.groupby(["country"])["user_pseudo_id"].count().reset_index(name="LA")
    )
    country_fig = px.choropleth(
        country_la,
        locations="country",
        color="LA",
        color_continuous_scale=[
            "#1584A3",
            "#DB830F",
            "#E6DF15",
        ],  # ['blue', 'red', 'yellow'],
        locationmode="country names",
        title="LA by Country",
    )
    country_fig.update_layout(geo=dict(bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(country_fig)

# READING ACQUISITION DECILES
total_lvls = ftm_apps.loc[ftm_apps["language"] == language, "total_lvls"].item()
ra_segs = get_ra_segments(ftm_campaigns, total_lvls, users_df)
ra_segs["la_perc"] = round(ra_segs["la_perc"], 2)
ra_segs_fig = px.bar(
    ra_segs,
    x="seg",
    y="la_perc",
    hover_data=["la", "rac"],
    labels={"seg": "RA Decile", "rac": "RAC (USD)", "la_perc": "% LA", "la": "LA"},
    text_auto=True,
    title="LA by RA Decile",
)
st.plotly_chart(ra_segs_fig)
st.caption(
    """The chart above displays LA by *RA Decile*.
    RA Deciles represent the progression of reading acquisition split into ten percentage groups.
    E.g. A learner that has completed 55% of the total FTM levels is included in the 0.5 RA Decile above."""
)

# DAILY READING ACTIVITY
st.markdown(
    """***
##### Daily Reading Activity"""
)
col5, col6 = st.columns(2)
cb = col5.checkbox("View")
if cb == True:
    daily_activity = get_daily_activity(
        users_df, start_date, app, country, bq_id, property_id
    )
    col6.metric("Total Levels Played", millify(daily_activity["levels_played"].sum()))
    tab1, tab2 = st.tabs(["Timeseries", "Heatmap"])
    daily_activity_fig = px.bar(
        daily_activity,
        x="event_date",
        y="levels_played",
        labels={"event_date": "Date", "levels_played": "# Levels Played"},
    )
    tab1.plotly_chart(daily_activity_fig)

    import numpy as np

    fig = px.scatter(
        daily_activity,
        x="event_date",
        y="levels_played",
        size="levels_played",
        title="Levels Played Over Time",
    )

    tab2.plotly_chart(fig, use_container_width=True)

st.markdown("***")
