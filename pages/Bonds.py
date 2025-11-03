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
st.set_page_config(layout="wide")
SUPABASE_URL = st.secrets["supabase"]["URL"]
SUPABASE_KEY = st.secrets["supabase"]["KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
import tempfile
import os

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








def BONDS_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
        raw_bonds_client_data_df = fetch_table_data(connection=connection, table_name="BONDS")
  raw_bonds_client_data_df['Amount'] = pd.to_numeric(raw_bonds_client_data_df['Amount'])
  raw_bonds_client_data_df['Transaction Date'] = pd.to_datetime(raw_bonds_client_data_df['Transaction Date'],format="%d-%m-%Y")
  raw_bonds_client_data_df['Transaction Date'] = raw_bonds_client_data_df['Transaction Date'].dt.strftime("%B-%Y")
  raw_bonds_client_data_df['MonthOnly'] = raw_bonds_client_data_df['Transaction Date'].str.split('-').str[0]
  raw_bonds_client_data_df['YearOnly'] = raw_bonds_client_data_df['Transaction Date'].str.split('-').str[1]
  if display:
    col0,col1=st.columns(2)
    with col0:
        st.metric("Total AUM", format_currency(raw_bonds_client_data_df['Amount'].sum()), border=True)
    with col1:
        st.metric("Total Active CLients", len(raw_bonds_client_data_df['Name'].unique()), border=True)
    raw_bonds_client_data_df['AMC'] = ''
    raw_bonds_client_data_df.loc[
        raw_bonds_client_data_df['Issue Name'] == 'IIFL SECURITIES LIMITED', 'AMC'
    ] = 'IIFL'
    raw_bonds_client_data_df.loc[
        raw_bonds_client_data_df['Issue Name'] == 'IREDA BONDS', 'AMC'
    ] = 'SUNRISE GUILT'
    raw_bonds_client_data_df.loc[
        raw_bonds_client_data_df['Issue Name'] == 'PFC Bond', 'AMC'
    ] = 'RELIGARE'
    raw_bonds_client_data_df.loc[
        raw_bonds_client_data_df['Issue Name'] == 'REC Bond', 'AMC'
    ] = 'RELIGARE'

    col2, col3 = st.columns(2)
    with col2:
        with st.container(border=True):
            clients_across_PMS = raw_bonds_client_data_df.groupby('AMC')['Name'].nunique().reset_index()
            clients_across_PMS = clients_across_PMS.sort_values(by=['Name'])
            fig = go.Figure(data=[go.Bar(y=clients_across_PMS['AMC'], x=clients_across_PMS['Name'], orientation='h',
                                         hovertemplate='<b>AMC:</b> %{y}<br><b>Clients:</b> %{x}<extra></extra>')])
            fig.update_layout(
                xaxis_title="Number of Clients",
                yaxis_title="AMC",xaxis=dict(
             title_font=dict(size=12, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')),
                           yaxis=dict(
                               title_font=dict(size=12, family='sans serif', color='black', ),
                               tickfont=dict(size=12, family='sans serif', color='black', ))
            )
            st.subheader('Distribution of Clients Across Providers')
            st.plotly_chart(fig)
    with col3:
        with st.container(border=True):
            aum_across_PMS = raw_bonds_client_data_df.groupby('AMC')['Amount'].sum().reset_index()
            fig = go.Figure(data=[go.Pie(
                labels=aum_across_PMS['AMC'],
                values=aum_across_PMS['Amount'],
                hole=0.3,
                marker=dict(colors=px.colors.diverging.Temps),
                hovertemplate=(
                    "<b>AMC</b>: %{label}<br>"  # Displays the AMC label
                    "<b>Percentage</b>: %{percent}<extra></extra>"  # Displays the percentage, removes extra trace info
                )
            )])
            st.subheader('Distribution of AUM Across Strategies')
            st.plotly_chart(fig)

    with st.container(border=True):
        opt=st.selectbox("Select type of filter",options=['Monthly Addition of Clients','Top Investors'])
        if opt=='Monthly Addition of Clients':
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            available_years = sorted(raw_bonds_client_data_df['YearOnly'].unique())
            available_months = sorted(raw_bonds_client_data_df['MonthOnly'].str.split('-').str[0].unique(),
                                      key=lambda x: month_order.index(x))
            col1, col2, col3 = st.columns(3)

            with col1:
                start_month = st.selectbox("Start Month", available_months,
                                           index=0,  # Default to first month
                                           key="start_month")
            with col2:
                end_month_options = available_months[available_months.index(start_month):]
                selected_end_month = st.selectbox("End Month", end_month_options,
                                                  index=len(end_month_options) - 1,  # Default to last available month
                                                  key="end_month")
            with col3:
                selected_year = st.selectbox("Select Year", available_years)
            def filter_data(df, year, start_month, end_month):
                month_order_dict = {month: index for index, month in enumerate(month_order)}
                year_filtered = df[df['YearOnly'] == year]
                month_filtered = year_filtered[
                    (year_filtered['MonthOnly'].map(month_order_dict) >= month_order_dict[start_month]) &
                    (year_filtered['MonthOnly'].map(month_order_dict) <= month_order_dict[selected_end_month])
                    ]
                month_filtered = month_filtered.sort_values(by='MonthOnly', key=lambda x: x.map(month_order_dict))
                return month_filtered

            filtered_data = filter_data(raw_bonds_client_data_df, selected_year, start_month, selected_end_month)
            filtered_data=filtered_data.iloc[:,:-5]
            st.dataframe(filtered_data,hide_index=True)
        elif opt == 'Top Investors':
            raw_bonds_client_data_df = raw_bonds_client_data_df.sort_values(by=['Amount'],ascending=False).head(5)
            raw_bonds_client_data_df=raw_bonds_client_data_df.iloc[:,:-5]
            st.dataframe(raw_bonds_client_data_df,hide_index=True)
  return raw_bonds_client_data_df

BONDS_Analysis(display=True)
