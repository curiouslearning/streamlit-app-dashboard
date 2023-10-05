# streamlit-app-repo

## Overview
This repo contains all files related to the [Curious Learning FTM Metrics Streamlit Dashboard](https://cl-ftm-dash.streamlit.app/). The dashboard is mainly used for internal strategic purposes by members of Curious Learning's staff and board. It serves to provide insight into the reach and educational effectiveness of the Feed the Monster app. Key metrics of interest include Learner Acquisition (LA), Reading Acquisition (RA), Learner Acquisition Cost (LAC), and Reading Acquisition Cost (RAC). Definitions of those metrics can be found at the top of each page in the Streamlit app. 

## Contributers
Izzy Bryant and Tinsley Galyean

## Pages
There are currently five subpages in the dashboard, each of which have a separate python file. *Summary.py* is the entrypoint file, the four others are located in the pages folder.
1. Summary.py (Annual Summary across all apps and geos)
2. Campaign_Comparison_Summary.py (High-level comparison of multiple campaigns' reach and cost effectiveness)
3. Campaign_Details.py (Detailed metrics & related visualizations for a single campaign)
4. Campaign_Comparison_Details.py (Comparitive view of detailed metrics & related visualizations for multiple campaigns)
5. Manual Analysis.py (Define your own dimensions for analysis of key metrics)
