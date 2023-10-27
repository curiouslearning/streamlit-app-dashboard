# Izzy Bryant
# Last updated Dec 2022
# 04_Manual_Analysis.py
import streamlit as st
from google.oauth2 import service_account
from google.cloud import bigquery
from gsheetsdb import connect
import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from millify import millify
import numpy as np

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
def get_user_data(start_date, end_date, apps, countries):
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    sql_query = f"""
        SELECT * FROM `dataexploration-193817.user_data.ftm_users`
        WHERE LA_date BETWEEN @start AND @end
        AND app_id IN UNNEST(@apps)
        AND country IN UNNEST(@countries)
    """
    query_parameters = [
        bigquery.ScalarQueryParameter("start", "STRING", start),
        bigquery.ScalarQueryParameter("end", "STRING", end),
        bigquery.ArrayQueryParameter("apps", "STRING", apps),
        bigquery.ArrayQueryParameter("countries", "STRING", countries),
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


@st.cache_data
def get_ra_segments(total_lvls, user_data):
    df = pd.DataFrame(columns=["segment", "la", "perc_la", "ra"])
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
    return res


@st.cache_data
def get_daily_activity(
    user_data, start_date, langs, apps, countries, bq_ids, property_ids
):
    user_ids = user_data["user_pseudo_id"].tolist()
    res = pd.DataFrame()
    for l in langs:
        sql_query = f"""
            SELECT event_date, COUNT(event_name) AS levels_played FROM `{bq_ids[l]}.analytics_{property_ids[l]}.events_20*`,
            UNNEST(event_params) AS params
            WHERE PARSE_DATE('%y%m%d', _table_suffix) BETWEEN @start AND @end
            AND app_info.id IN UNNEST(@apps)
            AND geo.country IN UNNEST(@countries)
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
                "end",
                "DATE",
                pd.to_datetime("today").date() - pd.Timedelta(1, unit="D"),
            ),
            bigquery.ArrayQueryParameter("apps", "STRING", apps),
            bigquery.ArrayQueryParameter("countries", "STRING", countries),
            bigquery.ArrayQueryParameter("user_ids", "STRING", user_ids),
        ]
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        rows_raw = client.query(sql_query, job_config=job_config)
        rows = [dict(row) for row in rows_raw]
        df = pd.DataFrame(rows)
        df["event_date"] = pd.to_datetime(df["event_date"])
        res = pd.concat([res, df])
    res = (
        res.groupby(["event_date"])["levels_played"]
        .sum()
        .reset_index(name="levels_played")
    )
    return res


# --- UI ---
st.title("Manual Analysis")
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
            "EstRA",
            "Estimated Reading Acquisition",
            "The estimated average percentage of FTM levels completed per learner from start date to today.",
            "AVG Max Level Reached / AVG Total Levels",
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

select_date_range = st.sidebar.date_input(
    "Select Date Range",
    (
        pd.to_datetime("today").date() - pd.Timedelta(30, unit="d"),
        pd.to_datetime("today").date() - pd.Timedelta(1, unit="d"),
    ),
    key="date_range",
)
st.sidebar.markdown("***")
ftm_apps = get_apps_data()
langs = ftm_apps["language"]
container_lang = st.sidebar.container()
all_langs = container_lang.checkbox("Select All Languages", value=True)
if all_langs:
    select_languages = container_lang.multiselect(
        "Select Languages", langs, default=langs, key="languages"
    )
else:
    select_languages = container_lang.multiselect(
        "Select Languages", langs, key="languages"
    )
st.sidebar.markdown("***")
countries_df = pd.read_csv("countries.csv")
container_country = st.sidebar.container()
all_countries = container_country.checkbox("Select All Countries", value=True)
if all_countries:
    select_countries = container_country.multiselect(
        "Select Countries",
        countries_df["name"],
        default=countries_df["name"],
        key="countries",
    )
else:
    select_countries = container_country.multiselect(
        "Select Countries", countries_df["name"], key="countries"
    )

# SET VARIABLES
start_date = st.session_state["date_range"][0]
end_date = st.session_state["date_range"][1]
languages = st.session_state["languages"]
apps = {}
bq_ids = {}
property_ids = {}
for l in languages:
    apps.update({l: ftm_apps.loc[ftm_apps["language"] == l, "app_id"].item()})
    bq_ids.update({l: ftm_apps.loc[ftm_apps["language"] == l, "bq_project_id"].item()})
    property_ids.update(
        {l: ftm_apps.loc[ftm_apps["language"] == l, "bq_property_id"].item()}
    )
apps_list = list(apps.values())
countries = st.session_state["countries"]
users_df = get_user_data(start_date, end_date, apps_list, countries)

# METRICS
container_metrics = st.container()
col1, col2 = container_metrics.columns(2)
col1.metric("Total LA", millify(str(len(users_df))))

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

if len(st.session_state["countries"]) > 1:
    country_la = (
        users_df.groupby(["country"])["user_pseudo_id"]
        .count()
        .reset_index(name="Learners Acquired")
    )
    country_fig = px.choropleth(
        country_la,
        locations="country",
        color="Learners Acquired",
        color_continuous_scale=["#1584A3", "#DB830F", "#E6DF15"],
        locationmode="country names",
        labels={"Learners Acquired": "LA", "country": "Country"},
        title="LA by Country",
    )
    country_fig.update_layout(geo=dict(bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(country_fig)

# READING ACQUISITION DECILES
apps_df = ftm_apps
apps_df[apps_df["total_lvls"] == 0] = np.nan
apps_df = apps_df[apps_df["language"].isin(st.session_state["languages"])]
avg_total_levels = np.nanmean(apps_df["total_lvls"])
ra_segs = get_ra_segments(avg_total_levels, users_df)
ra_segs["la_perc"] = round(ra_segs["la_perc"], 2)
ra_segs_fig = px.bar(
    ra_segs,
    x="seg",
    y="la_perc",
    hover_data=["la"],
    labels={"la_perc": "% LA", "seg": "EstRA Decile", "la": "LA"},
    title="LA by EstRA Decile",
)
st.plotly_chart(ra_segs_fig)

ra = users_df["max_lvl"].mean() / avg_total_levels
col2.metric("EstRA", millify(ra, 2))

# DAILY READING ACTIVITY
# st.markdown('''***
# ##### Daily Reading Activity''')
# col5, col6 = st.columns(2)
# cb = col5.checkbox('View')
# if cb == True:
#     daily_activity = get_daily_activity(users_df, start_date, languages, apps_list, countries, bq_ids, property_ids)
#     col6.metric('Total Levels Played', millify(daily_activity['levels_played'].sum()))
#     tab1, tab2 = st.tabs(['Timeseries', 'Heatmap'])
#     daily_activity_fig = px.bar(daily_activity,
#         x='event_date',
#         y='levels_played',
#         labels={
#             'event_date': 'Date',
#             'levels_played': '# Levels Played'
#         })
#     tab1.plotly_chart(daily_activity_fig)

#     da_fig = calplot(daily_activity, x='event_date', y='levels_played', dark_theme=False, gap=.5,
#         years_title=True, name='Levels Played', colorscale=['ghostwhite','royalblue'], space_between_plots=0.2)
#     tab2.plotly_chart(da_fig)
# st.markdown('***')
