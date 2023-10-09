# -*- coding: utf-8 -*-
# Izzy Bryant
# Last updated Dec 2022
# 01_Campaign_Comparison_Summary.py
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

@st.cache_data
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

@st.cache_data
def get_apps_data():
    apps_sheet_url = st.secrets["ftm_apps_gsheets_url"]
    apps_rows = run_query(f'SELECT app_id, language, bq_property_id, bq_project_id, total_lvls FROM "{apps_sheet_url}"')
    apps_data = pd.DataFrame(columns = ['app_id', 'language', 'bq_property_id', 'bq_project_id', 'total_lvls'],
        data = apps_rows)
    return apps_data

@st.cache_data
def get_campaign_metrics():
    camp_metrics_url = st.secrets["campaign_metrics_gsheets_url"]
    camp_metrics_rows = run_query(f'SELECT * FROM "{camp_metrics_url}"')
    camp_metrics_data = pd.DataFrame(columns = ['campaign_name', 'la', 'lac', 'ra', 'rac'],
                            data = camp_metrics_rows)
    camp_metrics_data = camp_metrics_data.astype({
        'la': 'int',
        'lac': 'float',
        'ra': 'float',
        'rac': 'float'
    })
    return camp_metrics_data

# def get_color_map(camps):
#     res = {}
#     palette = [
#         '#1c83e1', '#00c0f2', '#ff4b4b', 'LightPink', '#29b09d', '#5ce488', '#ff8700'
#     ]
#     for i in range(len(camps)):
#         # res.update({camps[i]: plotly.colors.DEFAULT_PLOTLY_COLORS[i]})
#         res.update({camps[i]: palette[i]})
#     return res

# def color_camps(val):
#     color = cmap[val]
#     return f'background-color: {color}'


# --- UI ---
st.title('Campaign Comparison Summary')
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
        ['LA', 'Learner Acquisition', 'The number of users that have completed at least one FTM level.', 'COUNT(Learners)'],
        ['LAC', 'Learner Acquisition Cost', 'The cost (USD) of acquiring one learner.', 'Total Spend / LA'],
        ['RA', ' Reading Acquisition', 'The  average percentage of FTM levels completed per learner from start date to today.', 'AVG Max Level Reached / Total Levels'],
        ['RAC', 'Reading Acquisition Cost', 'The cost (USD) associated with one learner reaching the average percentage of FTM levels (RA).', 'Total Spend / RA * LA']
    ],
    columns=['Acronym', 'Name', 'Definition', 'Formula']
)
expander.table(def_df)

ftm_campaigns = get_campaign_data()
select_campaigns = st.sidebar.multiselect(
    "Select Campaign(s)",
    ftm_campaigns['Campaign Name'],
    ftm_campaigns['Campaign Name'],
    key = 'campaigns'
)

# GANTT CHART
ftm_campaigns = ftm_campaigns[ftm_campaigns['Campaign Name'].isin(st.session_state['campaigns'])]
ftm_campaigns['Total Cost (USD)'] = round(ftm_campaigns['Total Cost (USD)'],2)
ftm_campaign_metrics = get_campaign_metrics()
ftm_campaign_metrics = ftm_campaign_metrics[ftm_campaign_metrics['campaign_name'].isin(st.session_state['campaigns'])]
gantt_df = pd.merge(ftm_campaigns, ftm_campaign_metrics, how='left', left_on='Campaign Name', right_on='campaign_name')
gantt = px.timeline(gantt_df,
    x_start='Start Date',
    x_end='End Date',
    y='Campaign Name',
    color='Campaign Name',
    hover_data=['Total Cost (USD)', 'la'],
    labels={'Campaign Name': 'Campaign', 'la': 'LA'},
    title='Gantt Chart')
gantt.update_layout(showlegend=False)
st.plotly_chart(gantt)

# LEADERBOARD
st.markdown('***')
st.subheader('Top 10 Leaderboard')
col1, col2 = st.columns(2)
top_df = ftm_campaign_metrics.rename(columns={'campaign_name': 'Campaign', 'la': 'LA', 'ra': 'RA', 'rac': 'RAC', 'lac': 'LAC'})
# cmap = get_color_map(st.session_state['campaigns'])
top_la = top_df.sort_values(by=['LA'], ascending=False).reset_index()
top_la.index = top_la.index + 1
col1.write('Highest LA')
col1.table(top_la[['Campaign', 'LA']].head(10))#.style.applymap(color_camps, subset=['Campaign']))
top_ra = top_df.sort_values(by=['RA'], ascending=False).reset_index()
top_ra.index = top_ra.index + 1
col2.write('Highest RA')
col2.table(top_ra[['Campaign', 'RA']].head(10))#.style.applymap(color_camps, subset=['Campaign']))
top_lac = top_df.sort_values(by=['LAC'], ascending=True).reset_index()
top_lac.index = top_lac.index + 1
col1.write('Lowest LAC')
col1.table(top_lac[['Campaign', 'LAC']].head(10))#.style.applymap(color_camps, subset=['Campaign']))
top_rac = top_df.sort_values(by=['RAC'], ascending=True).reset_index()
top_rac.index = top_rac.index + 1
col2.write('Lowest RAC')
col2.table(top_rac[['Campaign', 'RAC']].head(10))#.style.applymap(color_camps, subset=['Campaign']))
st.markdown('***')

# LEARNER & READING ACQUISITION COST
st.subheader('Reach & Impact')
st.markdown('*Which campaigns have the greatest reach and learning impact?*')
ftm_campaign_metrics['camp_age'] = [(ftm_campaigns.loc[ftm_campaigns['Campaign Name'] == c, 'End Date'].item() - ftm_campaigns.loc[ftm_campaigns['Campaign Name'] == c, 'Start Date'].item()).days for c in ftm_campaign_metrics['campaign_name']]
ftm_campaign_metrics['ra'] = round(ftm_campaign_metrics['ra'],3)
ftm_campaign_metrics['rac'] = round(ftm_campaign_metrics['rac'],3)
ftm_campaign_metrics['lac'] = round(ftm_campaign_metrics['lac'],3)
lavsra = px.scatter(ftm_campaign_metrics,
    x='ra',
    y='la',
    color='campaign_name',
    size='camp_age',
    labels={
        'ra': 'RA',
        'la': 'LA',
        'camp_age': 'Campaign Age (Days)',
        'campaign_name': 'Campaign'
    },
    title='LA vs RA' 
)
lavsra.add_shape(type='rect', xref='x domain', yref='y domain',
    x0=0.5, x1=1, y0=0.5, y1=1, line=dict(color='LightGreen', width=3))
st.plotly_chart(lavsra)
st.markdown('***')

st.subheader('Cost Analysis')
st.markdown('*Which campaigns are the most cost effective?*')
lacvsrac = px.scatter(ftm_campaign_metrics,
    x='lac',
    y='rac',
    color='campaign_name',
    size='camp_age',
    labels={
        'lac': 'LAC',
        'rac': 'RAC',
        'camp_age': 'Campaign Age (Days)',
        'campaign_name': 'Campaign'
    },
    title='LAC vs RAC'    
)
lacvsrac.add_shape(type='rect', xref='x domain', yref='y domain',
    x0=0, x1=0.5, y0=0, y1=0.5, line=dict(color='LightGreen', width=3))
st.plotly_chart(lacvsrac)
st.markdown('*Which campaigns are the most cost effective at reaching learners at scale?*')
lavslac = px.scatter(ftm_campaign_metrics,
    x='la',
    y='lac',
    color='campaign_name',
    size='camp_age',
    labels={
        'la': 'LA',
        'lac': 'LAC',
        'camp_age': 'Campaign Age (Days)',
        'campaign_name': 'Campaign'
    },
    title='LA vs LAC'    
)
lavslac.add_shape(type='rect', xref='x domain', yref='y domain',
    x0=0.5, x1=1, y0=0, y1=0.5, line=dict(color='LightGreen', width=3))
st.plotly_chart(lavslac)
