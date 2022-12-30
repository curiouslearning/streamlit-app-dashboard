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

# --- DATA ---
# Create a Google Sheets connection object.
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
    ]
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

@st.experimental_memo
def get_campaign_data():
    campaign_sheet_url = st.secrets["Campaign_gsheets_url"]
    campaign_rows = run_query(f'SELECT * FROM "{campaign_sheet_url}"')
    campaign_data = pd.DataFrame(columns = ['Campaign Name', 'Language', 'Country', 'Start Date', 'End Date', 'Total Cost (USD)'],
                            data = campaign_rows)
    campaign_data['Start Date'] = (pd.to_datetime(campaign_data['Start Date'])).dt.date
    campaign_data['End Date'] = (pd.to_datetime(campaign_data['End Date'])
                                    + pd.DateOffset(months=1) - pd.Timedelta(1, unit='D')).dt.date
    campaign_data = campaign_data.astype({
        'Total Cost (USD)': 'float'
    })
    return campaign_data

@st.experimental_memo
def get_user_data():
    sql_query = f"""
        SELECT * FROM `dataexploration-193817.user_data.ftm_users`
    """
    rows_raw = client.query(sql_query)
    rows = [dict(row) for row in rows_raw]
    df = pd.DataFrame(rows)
    df['LA_date'] = (pd.to_datetime(df['LA_date'])).dt.date
    df['max_lvl_date'] = (pd.to_datetime(df['max_lvl_date'])).dt.date
    return df

@st.experimental_memo
def get_apps_data():
    apps_sheet_url = st.secrets["ftm_apps_gsheets_url"]
    apps_rows = run_query(f'SELECT app_id, language, bq_property_id, bq_project_id, total_lvls FROM "{apps_sheet_url}"')
    apps_data = pd.DataFrame(columns = ['app_id', 'language', 'bq_property_id', 'bq_project_id', 'total_lvls'],
        data = apps_rows)
    return apps_data

@st.experimental_memo
def get_ra_segments(campagin_cost, app_data, user_data):
    df = pd.DataFrame(columns = ['segment', 'la', 'perc_la', 'ra', 'rac'])
    total_lvls = app_data['total_lvls'][0]
    seg = []
    ra = []
    for lvl in user_data['max_lvl']:
        perc = lvl / total_lvls
        ra.append(perc)
        if perc < .1:
            seg.append(.1)
        elif .1 <= perc < .2:
            seg.append(.2)
        elif .2 <= perc < .3:
            seg.append(.3)
        elif .3 <= perc < .4:
            seg.append(.4)
        elif .4 <= perc < .5:
            seg.append(.5)
        elif .5 <= perc < .6:
            seg.append(.6)
        elif .6 <= perc < .7:
            seg.append(.7)
        elif .7 <= perc < .8:
            seg.append(.8)
        elif .8 <= perc < .9:
            seg.append(.9)
        else:
            seg.append(1)
    user_data['seg'] = seg
    user_data['ra'] = ra
    res = user_data.groupby('seg').agg(la=('user_pseudo_id','count'), ra=('ra','mean')).reset_index()
    res['la_perc'] = res['la'] / res['la'].sum()
    res['rac'] = campaign_cost * res['la_perc'] / (res['ra'] * res['la'].sum())
    return res

def get_daily_la_fig(daily_la):
    daily_la_fig = px.line(daily_la,
        x='LA_date',
        y='Learners Acquired',
        color='campaign',
        labels={'LA_date': "Date",
            'campaign': 'Campaign',
            'Learners Acquired': 'LA'},
        title="Daily LA")
    return daily_la_fig

def get_weekly_la_fig(daily_la):
    daily_la['Weekly Rolling Mean'] = daily_la['Learners Acquired'].rolling(7).mean()
    weekly_la_fig = px.line(daily_la,
        x='LA_date',
        y='Weekly Rolling Mean',
        color='campaign',
        labels={'LA_date': 'Date',
            'campaign': 'Campaign',
            'Weekly Rolling Mean': 'LA'},
        title='Weekly LA')
    return weekly_la_fig

def get_monthly_la_fig(daily_la):
    daily_la['Monthly Rolling Mean'] = daily_la['Learners Acquired'].rolling(30).mean()
    monthly_la_fig = px.line(daily_la,
        x='LA_date',
        y='Monthly Rolling Mean',
        color='campaign',
        labels={'LA_date': 'Date',
            'campaign': 'Campaign',
            'Monthly Rolling Mean': 'LA'},
        title='Monthly LA')
    return monthly_la_fig

@st.experimental_memo
def get_normalized_start_df(daily_la):
    res = daily_la
    res['day'] = -1
    camp = res['campaign'][0]
    counter = 0
    for index, row in res.iterrows():
        if row['campaign'] == camp:
            counter +=1
            res['day'][index] = counter
        else:
            counter = 1
            res['day'][index] = counter
            camp = row['campaign']
    return res

# --- UI ---
st.title('Campaign Comparison Details')
expander = st.expander('Definitions')
expander.write('Learner Acquisition (LA) = number of users that have successfully completed at least one FTM level')
expander.write('Learner Acquisition Cost (LAC) = the cost (USD) of acquiring one learner')
expander.write('Reading Acquisition (RA) = the average percentage of FTM levels completed per learner')
expander.write('Reading Acquisition Cost (RAC) = the cost (USD) of acquiring the average amount of reading per learner')

ftm_campaigns = get_campaign_data()
select_campaigns = st.sidebar.multiselect(
    "Select Campaign(s)",
    ftm_campaigns['Campaign Name'],
    ftm_campaigns['Campaign Name'],
    key = 'campaigns'
)

# DAILY LEARNERS ACQUIRED
ftm_users = get_user_data()
ftm_apps = get_apps_data()
users_df = pd.DataFrame()
for campaign in st.session_state['campaigns']:
    start_date = ftm_campaigns.loc[ftm_campaigns['Campaign Name'] == campaign, 'Start Date'].item()
    end_date = ftm_campaigns.loc[ftm_campaigns['Campaign Name'] == campaign, 'End Date'].item()
    language = ftm_campaigns.loc[ftm_campaigns['Campaign Name'] == campaign, 'Language'].item()
    app = ftm_apps.loc[ftm_apps['language'] == language, 'app_id'].item()
    country = ftm_campaigns.loc[ftm_campaigns['Campaign Name'] == campaign, 'Country'].item()
    if country == 'All':
        temp = ftm_users[(ftm_users['LA_date'] >= start_date) & (ftm_users['LA_date'] <= end_date) & (ftm_users['app_id'] == app)]
    else:
        temp = ftm_users[(ftm_users['LA_date'] >= start_date) & (ftm_users['LA_date'] <= end_date) & (ftm_users['app_id'] == app) & (ftm_users['country'] == country)]
    temp['campaign'] = campaign
    users_df = pd.concat([users_df, temp])

daily_la = users_df.groupby(['campaign', 'LA_date'])['user_pseudo_id'].count().reset_index(name='Learners Acquired')
st.metric('Total LA', millify(str(len(users_df))))
st.markdown('***')
col1, col2 = st.columns(2)
radio1 = col1.radio('Start Date Toggle', ('Original', 'Normalized Start'))
radio = col2.radio('Rolling Mean Toggle', ('Daily LA', 'Weekly LA Rolling Mean', 'Monthly LA Rolling Mean'))
if radio1 == 'Normalized Start':
    daily_la = get_normalized_start_df(daily_la)
    daily_la = daily_la.rename(columns={'LA_date':'orig_date', 'day': 'LA_date'})
if radio == 'Daily LA':
    la_fig = get_daily_la_fig(daily_la)
elif radio == 'Weekly LA Rolling Mean':
    la_fig = get_weekly_la_fig(daily_la)
elif radio == 'Monthly LA Rolling Mean':
    la_fig = get_monthly_la_fig(daily_la)
st.plotly_chart(la_fig)
st.markdown('***')

ra_segs = pd.DataFrame()
for campaign in st.session_state['campaigns']:
    campaign_cost = ftm_campaigns.loc[ftm_campaigns['Campaign Name'] == campaign, 'Total Cost (USD)']
    temp = get_ra_segments(campaign_cost, ftm_apps, users_df[users_df['campaign'] == campaign])
    temp['campaign'] = campaign
    ra_segs = pd.concat([ra_segs, temp])

ra_segs_fig = px.bar(ra_segs,
    x='seg',
    y='la_perc',
    color='campaign',
    barmode='group',
    hover_data=['rac', 'la'],
    labels={
        'la_perc': '% LA',
        'seg': 'RA Decile',
        'rac': 'RAC (USD)',
        'la': 'LA'
    },
    title='LA by RA Decile' 
)
st.plotly_chart(ra_segs_fig)