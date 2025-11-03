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

def VESTED_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
        raw_vested_client_data_df = fetch_table_data(connection=connection, table_name="VESTED")
  raw_vested_client_data_df = raw_vested_client_data_df[raw_vested_client_data_df['RM'] != 'Employee']
  raw_vested_client_data_df = raw_vested_client_data_df.dropna(subset=['Name'])
  raw_vested_client_data_df = raw_vested_client_data_df.dropna(subset=['RC Date'])
  raw_vested_client_data_df['RC Date'] = pd.to_datetime(raw_vested_client_data_df['RC Date'],format='%d-%m-%Y')
  raw_vested_client_data_df['RC Date'] = raw_vested_client_data_df['RC Date'].dt.strftime('%B-%Y')
  raw_vested_client_data_df=raw_vested_client_data_df.fillna(0)
  raw_vested_client_data_df['YearOnly']=raw_vested_client_data_df['RC Date'].str.split('-').str[1]
  raw_vested_client_data_df['MonthOnly']=raw_vested_client_data_df['RC Date'].str.split('-').str[0]
  raw_vested_client_data_df['Invested Amount'] = pd.to_numeric(raw_vested_client_data_df['Invested Amount'])
  raw_vested_client_data_df['Invested Amount'] = raw_vested_client_data_df['Invested Amount'].astype(float)
  raw_vested_client_data_df2=raw_vested_client_data_df[raw_vested_client_data_df['Invested Amount']!=0]
  if display:
    col0, col1,col2,col3= st.columns(4)
    with col0:
        VESTED_total_AUM = raw_vested_client_data_df['Current Value'].astype(float).sum()
        st.metric("Total AUM", f" $ {VESTED_total_AUM:,.2f}", border=True)
    with col1:
        total_vested_clients = len(raw_vested_client_data_df['Name'].unique())
        st.metric("Total Clients", total_vested_clients, border=True)
    with col2:
       total_onboarded_clients = raw_vested_client_data_df[( raw_vested_client_data_df['Invested Amount'] == 0)]['Name'].nunique()
       st.metric("Onboarded Clients",total_onboarded_clients,border=True)
    #with col3:
    #    total_onboarded_clients = raw_vested_client_data_df[(raw_vested_client_data_df['Plan Type'] != 'PREMIUM') & (
    #                raw_vested_client_data_df['Invested Amount'] == 0)]['Name'].nunique()
    #    st.metric("Onboarding Pending Clients", total_onboarded_clients, border=True)
    with col3:
        count = raw_vested_client_data_df['Invested Amount'].dropna().astype(bool).sum()
        st.metric("Total Active Clients", count, border=True)

    col5,col6 = st.columns(2)
    with col5:
        with st.container(border=True):
            st.subheader("New Clients Addition Monthly")

            show_invested = st.toggle("Active Clients")
            if show_invested:
                invested_clients = raw_vested_client_data_df[raw_vested_client_data_df['Invested Amount'] > 0]
                new_clients_monthly = invested_clients.groupby('RC Date')['Name'].count().reset_index()
            else:
                new_clients_monthly = raw_vested_client_data_df.groupby('RC Date')['Name'].count().reset_index()

            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']

            new_clients_monthly['MonthOnly'] = new_clients_monthly['RC Date'].str.split('-').str[0]
            new_clients_monthly['YearOnly'] = new_clients_monthly['RC Date'].str.split('-').str[1]

            month_order_dict = {month: idx for idx, month in enumerate(month_order)}
            new_clients_monthly['MonthNumber'] = new_clients_monthly['MonthOnly'].map(month_order_dict).astype(int)
            new_clients_monthly['YearNumber'] = new_clients_monthly['YearOnly'].astype(int)


            new_clients_monthly = new_clients_monthly.sort_values(['YearNumber', 'MonthNumber'])

            new_clients_monthly = new_clients_monthly.drop(['MonthOnly', 'YearOnly', 'MonthNumber', 'YearNumber'],
                                                           axis=1)

            fig = px.bar(new_clients_monthly, x=new_clients_monthly['RC Date'], y=new_clients_monthly['Name'],
                         text=new_clients_monthly['Name'])

            fig.update_layout(
                xaxis_title="Month",
                yaxis_title="New Clients",
                width=500,
                height=400,
                xaxis=dict(
                    title_font=dict(size=12, family='sans serif', color='black'),
                    tickfont=dict(size=12, family='sans serif', color='black')
                ),
                yaxis=dict(
                    title_font=dict(size=12, family='sans serif', color='black'),
                    tickfont=dict(size=12, family='sans serif', color='black')
                )
            )

            fig.update_traces(
                hovertemplate="<b>Month:</b> %{x}<br><b>New Clients:</b> %{y}<extra></extra>"
            )

            fig.update_traces(
                textposition='outside',
                width=0.4,
                textfont=dict(family="sans serif", size=12, color='black', weight='bold')
            )

            st.plotly_chart(fig)
    with st.container(border=True):
        opt=st.selectbox("Select type of filter",options=['Monthly Addition of Clients','Top Investors'])
        if opt=='Monthly Addition of Clients':
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            available_years = sorted(raw_vested_client_data_df['RC Date'].str.split('-').str[1].unique())
            available_months = sorted(raw_vested_client_data_df['RC Date'].str.split('-').str[0].unique(),
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

            filtered_data = filter_data(raw_vested_client_data_df, selected_year, start_month, selected_end_month)
            filtered_data=filtered_data[filtered_data['Invested Amount'] != 0]
            filtered_data=filtered_data.iloc[:,:-6]
            st.dataframe(filtered_data,hide_index=True)
        elif opt == 'Top Investors':
            filtered_df_invested_amount = raw_vested_client_data_df[raw_vested_client_data_df['Invested Amount'] != 0]
            raw_bonds_client_data_df = filtered_df_invested_amount.sort_values(by=['Invested Amount'],ascending=False).head(5)
            st.dataframe(raw_bonds_client_data_df,hide_index=True)
  return raw_vested_client_data_df2

VESTED_Analysis(display=True)
