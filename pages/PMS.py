from enum import unique
import psycopg2
import pandas as pd
import plotly.express as px
import streamlit
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from rich.jupyter import display
from streamlit import table
from datetime import date
import datetime
from psycopg2 import sql
from supabase import create_client
from pdf_generator_fixed import create_simple_investment_report


def format_currency(value):
    if abs(value) >= 10000000:
        return f'{value/10000000:.2f} Crs'
    elif abs(value) >= 100000:
        return f"{value / 100000:.2f} L"
    elif abs(value) >= 1000:
        return f"{value / 1000:.2f} K"
    else:
        return f"{value:.2f}"

db_config = {
    "user": st.secrets["DB"]["USER"],
    "password": st.secrets["DB"]["PASSWORD"],
    "host": st.secrets["DB"]["HOST"],
    "port": st.secrets["DB"]["PORT"],
    "dbname": st.secrets["DB"]["NAME"]
}

def fetch_table_data(connection, table_name):
    """Fetch data from a PostgreSQL table and return as a Pandas DataFrame."""
    try:
        query = f'SELECT * FROM "{table_name}";'
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=columns)
    except psycopg2.Error as e:
        print(f"Error fetching data from {table_name}: {e}")
        return pd.DataFrame()

def PMS_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
         raw_pms_client_data_df = fetch_table_data(connection=connection,table_name="PMS")
  if display:
    col0,col1=st.columns(2)
    with col1:
      st.metric("Total Active Clients",len(raw_pms_client_data_df['Name'].unique()),border=True)

    with col0:
      PMS_total_AUM = raw_pms_client_data_df['Invested Amount'].sum()
      st.metric("Total AUM",format_currency(PMS_total_AUM),border=True)
    col2,col3=st.columns(2)
    with col2:
      with st.container(border=True):
        raw_pms_client_data_df['Invested Amount']  =   raw_pms_client_data_df['Invested Amount'].astype(float)
        raw_pms_client_data_df = raw_pms_client_data_df[raw_pms_client_data_df['Invested Amount'] > 0]
        clients_across_PMS = raw_pms_client_data_df.groupby('Strategy')[['Name','Invested Amount']].agg(list).reset_index()
        clients_across_PMS['Num_Clients'] = clients_across_PMS['Name'].apply(len)
        fig = go.Figure(data=[go.Pie(labels=clients_across_PMS['Strategy'],
                                     values=clients_across_PMS['Num_Clients'],
                                     hole=0.3,
                                     marker=dict(colors=px.colors.diverging.Temps),
                                     hovertemplate="<b>Strategy:</b> %{label}<br><b>Clients:</b> %{value}<br><b>Percentage:</b> %{percent}<extra></extra>"
                                     )])

        st.subheader('Distribution of Clients Across Strategies')
        st.plotly_chart(fig)
    with col3:
      with st.container(border=True):
        aum_across_PMS = raw_pms_client_data_df.groupby('Strategy')['Invested Amount'].sum().reset_index()
        fig = go.Figure(data=[go.Pie(labels=aum_across_PMS['Strategy'],
                                     values=aum_across_PMS['Invested Amount'],
                                     hole=0.3,
                                     marker=dict(colors=px.colors.diverging.Temps))])
        st.subheader('Distribution of AUM Across Strategies')
        st.plotly_chart(fig)
    with st.container(border=True):
        st.dataframe(raw_pms_client_data_df)
  raw_pms_client_data_df['MonthOnly'] = pd.to_datetime(raw_pms_client_data_df['Date of Investment']).dt.strftime("%B")
  raw_pms_client_data_df['YearOnly'] = pd.to_datetime(raw_pms_client_data_df['Date of Investment']).dt.strftime("%Y")
  return raw_pms_client_data_df
