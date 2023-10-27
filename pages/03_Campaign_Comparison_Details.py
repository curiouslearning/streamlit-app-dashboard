# Izzy Bryant
# Last updated Dec 2022
# 03_Campaign_Comparison_Details.py
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
def get_user_data(today):
    sql_query = f"""
        SELECT * FROM `dataexploration-193817.user_data.ftm_users`
    """
    rows_raw = client.query(sql_query)
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
def get_ra_segments(campagin_cost, app_data, user_data):
    df = pd.DataFrame(columns=["segment", "la", "perc_la", "ra", "rac"])
    total_lvls = app_data["total_lvls"][0]
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
    res["la_perc"] = round(res["la"] / res["la"].sum(), 2)
    res["rac"] = round(
        campaign_cost * res["la_perc"] / (res["ra"] * res["la"].sum()), 2
    )
    return res


# def get_daily_la_fig(daily_la):
#     daily_la_fig = px.line(daily_la,
#         x='LA_date',
#         y='Learners Acquired',
#         color='campaign',
#         labels={'LA_date': "Date",
#             'campaign': 'Campaign',
#             'Learners Acquired': 'LA'},
#         title="Daily LA")
#     return daily_la_fig

# def get_weekly_la_fig(daily_la):
#     daily_la['Weekly Rolling Mean'] = daily_la['Learners Acquired'].rolling(7).mean()
#     weekly_la_fig = px.line(daily_la,
#         x='LA_date',
#         y='Weekly Rolling Mean',
#         color='campaign',
#         labels={'LA_date': 'Date',
#             'campaign': 'Campaign',
#             'Weekly Rolling Mean': 'LA'},
#         title='Weekly LA')
#     return weekly_la_fig

# def get_monthly_la_fig(daily_la):
#     daily_la['Monthly Rolling Mean'] = daily_la['Learners Acquired'].rolling(30).mean()
#     monthly_la_fig = px.line(daily_la,
#         x='LA_date',
#         y='Monthly Rolling Mean',
#         color='campaign',
#         labels={'LA_date': 'Date',
#             'campaign': 'Campaign',
#             'Monthly Rolling Mean': 'LA'},
#         title='Monthly LA')
#     return monthly_la_fig


def get_daily_la_fig(daily_la, norm):
    if norm == True:
        daily_la_fig = px.line(
            daily_la,
            x="LA_date",
            y="LA",
            color="campaign",
            labels={
                "LA_date": "Day",
                "campaign": "Campaign",
                "Learners Acquired": "LA",
            },
            title="Daily LA",
        )
        daily_la_fig.update_xaxes(
            tickmode="array",
            tickvals=np.arange(0, len(daily_la["LA_date"]), 30),
            ticktext=np.arange(0, 13, 1),
        )
        daily_la_fig.update_layout(xaxis_title="Date (Month)")
    else:
        daily_la_fig = px.line(
            daily_la,
            x="LA_date",
            y="LA",
            color="campaign",
            labels={
                "LA_date": "Date",
                "campaign": "Campaign",
                "Learners Acquired": "LA",
            },
            title="Daily LA",
        )
    return daily_la_fig


def get_weekly_la_fig(daily_la, norm):
    daily_la["Weekly Rolling Mean"] = daily_la["LA"].rolling(7).mean()
    if norm == True:
        weekly_la_fig = px.line(
            daily_la,
            x="LA_date",
            y="Weekly Rolling Mean",
            color="campaign",
            labels={
                "LA_date": "Day",
                "campaign": "Campaign",
                "Weekly Rolling Mean": "LA",
            },
            title="Weekly LA",
        )
        weekly_la_fig.update_xaxes(
            tickmode="array",
            tickvals=np.arange(0, len(daily_la["LA_date"]), 30),
            ticktext=np.arange(0, 13, 1),
        )
        weekly_la_fig.update_layout(xaxis_title="Date (Month)")
    else:
        weekly_la_fig = px.line(
            daily_la,
            x="LA_date",
            y="Weekly Rolling Mean",
            color="campaign",
            labels={
                "LA_date": "Date",
                "campaign": "Campaign",
                "Weekly Rolling Mean": "LA",
            },
            title="Weekly LA",
        )
    return weekly_la_fig


def get_monthly_la_fig(daily_la, norm):
    daily_la["Monthly Rolling Mean"] = daily_la["LA"].rolling(30).mean()
    if norm == True:
        monthly_la_fig = px.line(
            daily_la,
            x="LA_date",
            y="Monthly Rolling Mean",
            color="campaign",
            labels={
                "LA_date": "Day",
                "campaign": "Campaign",
                "Monthly Rolling Mean": "LA",
            },
            title="Monthly LA",
        )
        monthly_la_fig.update_xaxes(
            tickmode="array",
            tickvals=np.arange(0, len(daily_la["LA_date"]), 30),
            ticktext=np.arange(0, 13, 1),
        )
        monthly_la_fig.update_layout(xaxis_title="Date (Month)")
    else:
        monthly_la_fig = px.line(
            daily_la,
            x="LA_date",
            y="Monthly Rolling Mean",
            color="campaign",
            labels={
                "LA_date": "Date",
                "campaign": "Campaign",
                "Monthly Rolling Mean": "LA",
            },
            title="Monthly LA",
        )
    return monthly_la_fig


@st.cache_data
def get_normalized_start_df(daily_la):
    res = daily_la
    res["day"] = -1
    camp = res["campaign"][0]
    counter = 0
    for index, row in res.iterrows():
        if row["campaign"] == camp:
            counter += 1
            res["day"][index] = counter
        else:
            counter = 1
            res["day"][index] = counter
            camp = row["campaign"]
    return res


@st.cache_data
def get_campaign_metrics():
    camp_metrics_url = st.secrets["campaign_metrics_gsheets_url"]
    camp_metrics_rows = run_query(f'SELECT * FROM "{camp_metrics_url}"')
    camp_metrics_data = pd.DataFrame(
        columns=["campaign_name", "la", "lac", "ra", "rac"], data=camp_metrics_rows
    )
    camp_metrics_data = camp_metrics_data.astype(
        {"la": "int", "lac": "float", "ra": "float", "rac": "float"}
    )
    return camp_metrics_data


# --- UI ---
st.title("Campaign Comparison Details")
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
select_campaigns = st.sidebar.multiselect(
    "Select Campaign(s)",
    ftm_campaigns["Campaign Name"],
    ftm_campaigns["Campaign Name"],
    key="campaigns",
)

# DAILY LEARNERS ACQUIRED
ftm_users = get_user_data(pd.to_datetime("today").date())
ftm_apps = get_apps_data()
users_df = pd.DataFrame()
for campaign in st.session_state["campaigns"]:
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
    if country == "All":
        temp = ftm_users[
            (ftm_users["LA_date"] >= start_date)
            & (ftm_users["LA_date"] <= end_date)
            & (ftm_users["app_id"] == app)
        ]
    else:
        temp = ftm_users[
            (ftm_users["LA_date"] >= start_date)
            & (ftm_users["LA_date"] <= end_date)
            & (ftm_users["app_id"] == app)
            & (ftm_users["country"] == country)
        ]
    temp["campaign"] = campaign
    users_df = pd.concat([users_df, temp])

daily_la = (
    users_df.groupby(["campaign", "LA_date"])["user_pseudo_id"]
    .count()
    .reset_index(name="LA")
)

campaign_data = get_campaign_metrics()
campaign_data = campaign_data[
    campaign_data["campaign_name"].isin(st.session_state["campaigns"])
]
# convert NaN values to 0
campaign_data = campaign_data.fillna(0)

col1, col2 = st.columns(2)
col1.metric("Total LA", millify(str(len(users_df))))
avg_ra = np.average(campaign_data["ra"], weights=campaign_data["la"])

col2.metric("Avg RA (Weighted)", millify(avg_ra, precision=2))
st.markdown("***")
col1, col2 = st.columns(2)
radio1 = col1.radio("Start Date Toggle", ("Original", "Normalized Start"))
radio = col2.radio(
    "Rolling Mean Toggle",
    ("Daily LA", "Weekly LA Rolling Mean", "Monthly LA Rolling Mean"),
)
norm = False
if radio1 == "Normalized Start":
    norm = True
    daily_la = get_normalized_start_df(daily_la)
    daily_la = daily_la.rename(columns={"LA_date": "orig_date", "day": "LA_date"})
if radio == "Daily LA":
    la_fig = get_daily_la_fig(daily_la, norm)
elif radio == "Weekly LA Rolling Mean":
    la_fig = get_weekly_la_fig(daily_la, norm)
elif radio == "Monthly LA Rolling Mean":
    la_fig = get_monthly_la_fig(daily_la, norm)
st.plotly_chart(la_fig)
st.markdown("***")

# LA BY RA DECILE
ra_segs = pd.DataFrame()
for campaign in st.session_state["campaigns"]:
    campaign_cost = ftm_campaigns.loc[
        ftm_campaigns["Campaign Name"] == campaign, "Total Cost (USD)"
    ].item()
    temp = get_ra_segments(
        campaign_cost, ftm_apps, users_df[users_df["campaign"] == campaign]
    )
    temp["campaign"] = campaign
    temp["campaign_cost"] = round(campaign_cost, 2)
    ra_segs = pd.concat([ra_segs, temp])
ra_segs = ra_segs.sort_values(by=["campaign"])

ra_segs_fig = px.bar(
    ra_segs,
    x="seg",
    y="la_perc",
    color="campaign",
    barmode="group",
    hover_data=["la", "campaign_cost", "rac"],
    labels={
        "la_perc": "% LA",
        "seg": "RA Decile",
        "rac": "RAC (USD)",
        "la": "LA",
        "campaign": "Campaign",
        "campaign_cost": "Total Spend (USD)",
    },
    text_auto=True,
    title="LA by RA Decile",
)
st.plotly_chart(ra_segs_fig)
st.caption(
    """The chart above displays LA by *RA Decile*.
    RA Deciles represent the progression of reading acquisition split into ten percentage groups.
    E.g. A learner that has completed 55% of the total FTM levels is included in the 0.5 RA Decile above."""
)
