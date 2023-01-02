# -*- coding: utf-8 -*-
# Izzy Bryant
# Last updated Dec 2022
# Summary.py
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
def get_annual_campaign_data():
    ann_campaign_sheet_url = st.secrets["ann_camp_metrics_gsheets_url"]
    year = pd.to_datetime("today").date().year
    ann_camp_rows = run_query(f'''
        SELECT * FROM "{ann_campaign_sheet_url}" 
    ''')
    ann_camp_data = pd.DataFrame(columns = ['name', 'year', 'la', 'ra'],
                            data = ann_camp_rows)
    ann_camp_data = ann_camp_data.astype({
        'year': 'int',
    })
    ann_camp_data = ann_camp_data[ann_camp_data['year'] < year+1]
    return ann_camp_data

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
def get_campaign_metrics():
    camp_metrics_url = st.secrets["campaign_metrics_gsheets_url"]
    camp_metrics_rows = run_query(f'SELECT * FROM "{camp_metrics_url}"')
    camp_metrics_data = pd.DataFrame(columns = ['campaign_name', 'la', 'lac', 'ra', 'rac'],
                            data = camp_metrics_rows)
    return camp_metrics_data

def get_daily_la_fig(daily_la, norm):
    if norm == True:
        daily_la_fig = px.line(daily_la,
            x='LA_date',
            y='LA',
            color='campaign',
            labels={'LA_date': 'Day',
                'campaign': 'Campaign',
                'Learners Acquired': 'LA'},
            title="Daily LA")
        daily_la_fig.update_xaxes(
            tickmode='array',
            tickvals = np.arange(0, len(daily_la['LA_date']), 30),
            ticktext=np.arange(0, 13, 1)
        )
        daily_la_fig.update_layout(
            xaxis_title='Date (Month)'
        )
    else:
        daily_la_fig = px.line(daily_la,
            x='LA_date',
            y='LA',
            color='campaign',
            labels={'LA_date': 'Date',
                'campaign': 'Campaign',
                'Learners Acquired': 'LA'},
            title='Daily LA')
    return daily_la_fig

def get_weekly_la_fig(daily_la, norm):
    daily_la['Weekly Rolling Mean'] = daily_la['LA'].rolling(7).mean()
    if norm == True:
        weekly_la_fig = px.line(daily_la,
            x='LA_date',
            y='Weekly Rolling Mean',
            color='campaign',
            labels={'LA_date': 'Day',
                'campaign': 'Campaign',
                'Weekly Rolling Mean': 'LA'},
            title='Weekly LA')
        weekly_la_fig.update_xaxes(
            tickmode='array',
            tickvals = np.arange(0, len(daily_la['LA_date']), 30),
            ticktext=np.arange(0, 13, 1)
        )
        weekly_la_fig.update_layout(
            xaxis_title='Date (Month)'
        )
    else:
        weekly_la_fig = px.line(daily_la,
            x='LA_date',
            y='Weekly Rolling Mean',
            color='campaign',
            labels={'LA_date': 'Date',
                'campaign': 'Campaign',
                'Weekly Rolling Mean': 'LA'},
            title='Weekly LA')
    return weekly_la_fig

def get_monthly_la_fig(daily_la, norm):
    daily_la['Monthly Rolling Mean'] = daily_la['LA'].rolling(30).mean()
    if norm == True:
        monthly_la_fig = px.line(daily_la,
            x='LA_date',
            y='Monthly Rolling Mean',
            color='campaign',
            labels={'LA_date': 'Day',
                'campaign': 'Campaign',
                'Monthly Rolling Mean': 'LA'},
            title='Monthly LA')
        monthly_la_fig.update_xaxes(
            tickmode='array',
            tickvals = np.arange(0, len(daily_la['LA_date']), 30),
            ticktext=np.arange(0, 13, 1)
        )
        monthly_la_fig.update_layout(
            xaxis_title='Date (Month)'
        )
    else:
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

@st.experimental_memo
def get_ra_segments(total_lvls, user_data):
    df = pd.DataFrame(columns = ['segment', 'la', 'perc_la', 'ra', 'rac'])
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
    return res

# --- UI ---
st.title('Annual Campaign Summary')
expander = st.expander('Definitions')
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
        ['LA', 'Learner Acquisition', 'The number of users that have completed at least one FTM level'],
        ['LAC', 'Learner Acquisition Cost', 'The cost (USD) of acquiring one learner'],
        ['RA', 'Reading Acquisition', 'The average percentage of FTM levels completed per learner'],
        ['RAC', 'Reading Acquisition Cost', 'The cost (USD) of acquiring the average amount of reading per learner']
    ],
    columns=['Acronym', 'Name', 'Definition']
)
expander.table(def_df)

ann_camp_data = get_annual_campaign_data()
select_campaigns = st.sidebar.multiselect(
    "Select Annual Campaign",
    ann_camp_data['name'],
    ann_camp_data['name'],#[len(ann_camp_data['name'])-1],
    key = 'campaigns'
)

ann_camp_data = ann_camp_data[ann_camp_data['name'].isin(st.session_state['campaigns'])]
col1, col2 = st.columns(2)
col1.metric('Total LA', millify(ann_camp_data['la'].sum()))
avg_ra = np.average(ann_camp_data['ra'], weights=ann_camp_data['la'])
col2.metric('Avg RA (Weighted)', millify(avg_ra,precision=2))

# SUMMARY TABLE
sum_table = ann_camp_data[['year', 'la', 'ra']].rename(columns={'year': 'Year', 'la': 'LA', 'ra': 'RA'})
sum_table = sum_table.style.format({'LA':'{:n}', 'RA': '{:.3f}'})
st.table(sum_table)

# DAILY LEARNERS ACQUIRED
ftm_users = get_user_data()
users_df = ftm_users[pd.to_datetime(ftm_users['LA_date']).dt.year.between(ann_camp_data['year'].min(), ann_camp_data['year'].max(), inclusive = True)]
users_df['campaign'] = users_df['LA_date'].apply(lambda x: 'FTM_' + str(x.year))
daily_la = users_df.groupby(['campaign', 'LA_date'])['user_pseudo_id'].count().reset_index(name='LA')
st.markdown('***')
col3, col4 = st.columns(2)
radio1 = col3.radio('Start Date Toggle', ('Original', 'Normalized Start'))
radio = col4.radio('Rolling Mean Toggle', ('Daily LA', 'Weekly LA Rolling Mean', 'Monthly LA Rolling Mean'))
norm = False
if radio1 == 'Normalized Start':
    norm = True
    daily_la = get_normalized_start_df(daily_la)
    daily_la = daily_la.rename(columns={'LA_date':'orig_date', 'day': 'LA_date'})
if radio == 'Daily LA':
    la_fig = get_daily_la_fig(daily_la, norm)
elif radio == 'Weekly LA Rolling Mean':
    la_fig = get_weekly_la_fig(daily_la, norm)
elif radio == 'Monthly LA Rolling Mean':
    la_fig = get_monthly_la_fig(daily_la, norm)
st.plotly_chart(la_fig)
st.markdown('***')

# MAP
country_la = users_df.groupby(['country'])['user_pseudo_id'].count().reset_index(name='LA')
country_fig = px.choropleth(country_la,
    locations='country',
    color='LA',
    color_continuous_scale=['blue', 'red', 'yellow'],
    locationmode='country names',
    title='LA by Country')
country_fig.update_layout(geo=dict(bgcolor= 'rgba(0,0,0,0)'))
country_fig.update_geos(fitbounds='locations', visible=False)
st.plotly_chart(country_fig)

# LA BY RA DECILE
ftm_apps = get_apps_data()
ftm_apps[ftm_apps['total_lvls'] == 0] = np.nan
avg_total_levels = np.nanmean(ftm_apps['total_lvls'])
ra_segs = pd.DataFrame()
for campaign in st.session_state['campaigns']:
    temp = get_ra_segments(avg_total_levels, users_df[users_df['campaign'] == campaign])
    temp['campaign'] = campaign
    ra_segs = pd.concat([ra_segs, temp])
ra_segs = ra_segs.sort_values(by=['campaign'])
ra_segs['la_perc'] = round(ra_segs['la_perc'], 2)
if len(st.session_state['campaigns']) == 0:
    ra_segs_fig = px.bar(ra_segs,
        x='seg',
        y='la',
        labels={
            'seg': 'RA Decile',
            'la': 'LA',
            'campaign': 'Campaign'
        },
        text_auto=True,
        title='LA by RA Decile' 
    )
else:
    ra_segs_fig = px.bar(ra_segs,
        x='seg',
        y='la_perc',
        color='campaign',
        barmode='group',
        labels={
            'seg': 'RA Decile',
            'la': 'LA',
            'la_perc': '% LA',
            'campaign': 'Campaign'
        },
        text_auto=True,
        title='LA by RA Decile' )
st.plotly_chart(ra_segs_fig)
st.caption('''The chart above displays LA by *RA Decile*.
    RA Deciles represent the progression of reading acquisition split into ten percentage groups.
    E.g. A learner that has completed 55% of the total FTM levels is included in the 0.5 RA Decile above.''')