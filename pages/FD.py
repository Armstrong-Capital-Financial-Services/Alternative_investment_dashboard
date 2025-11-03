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

def FD_Analysis(display=True):
    with psycopg2.connect(**db_config) as connection:
        FD_client_data_df = fetch_table_data(connection=connection, table_name="FD")
        FD_client_data_df['Maturity Date'] = pd.to_datetime(FD_client_data_df['Maturity Date'],format='mixed')
        FD_client_data_df['Current Status2'] = FD_client_data_df['Maturity Date'].apply( lambda x: 'Mature' if x.date() < date.today() else 'Live')
    active_clients = FD_client_data_df[FD_client_data_df['Current Status2'] == 'Live']
    active_clients['Issue Date']=pd.to_datetime(active_clients['Issue Date'],format='%d-%m-%Y')
    active_clients['YearOnly'] = active_clients['Issue Date'].dt.strftime("%Y")
    active_clients['Month'] = active_clients['Issue Date'].dt.strftime("%B")
    matured_clients = FD_client_data_df[FD_client_data_df['Current Status2']=='Mature']
    FD_client_data_df['Issue Date'] = pd.to_datetime(FD_client_data_df['Issue Date'],format='%d-%m-%Y')
    if display:
        col0,col1,col2=st.columns(3)
        with col0:
            st.metric("Total AUM",format_currency(active_clients['Investment Amount'].sum()),border=True)
        with col1:
            st.metric("Total Active FDs",len(active_clients),border=True)
        with col2:
            st.metric("Total Matured FDs",len(matured_clients),border=True)
        tab1, tab2 = st.tabs(['Active FDs', 'Matured FDs'])
        with tab1:
         col3,col4=st.columns(2)
         with col3.container(border=True):
           fd_distribution_across_providers=active_clients.groupby(['Channel Partner'])['Customer Name'].agg(list).reset_index()
           fd_distribution_across_providers['No of FD'] = fd_distribution_across_providers['Customer Name'].apply(lambda x: len(x))
           fig = go.Figure(data=[go.Pie(
               labels=fd_distribution_across_providers['Channel Partner'],
               values=fd_distribution_across_providers['No of FD'],
               hole=0.3,  # Creates a donut chart
               marker=dict(colors=px.colors.qualitative.Pastel),
               textinfo='percent+label',
               hovertemplate="<b>Channel Partner:</b> %{label}<br><b>Number of FDs:</b> %{value}<br><b>Percentage:</b> %{percent}<extra></extra>"
           )])

           st.subheader("Distribution of FDs across Providers")
           st.plotly_chart(fig)
         with col4.container(border=True):
            aum_distribution_across_providers = active_clients.groupby('Channel Partner')[
                'Investment Amount'].sum().reset_index()
             
            aum_distribution_across_providers = aum_distribution_across_providers.sort_values(
                by='Investment Amount', ascending=True) 
            fig = go.Figure(go.Bar(
                x=aum_distribution_across_providers['Investment Amount'].apply(format_currency),
                y=aum_distribution_across_providers['Channel Partner'],
                orientation='h',hovertemplate="<b>Channel Partner</b>: %{y}<br>" +
                      "<b>Investment Amount</b>: %{x}<extra></extra>"
            ))

            fig.update_layout(
                xaxis_title='Total Investment Amount',
                yaxis_title='Channel Partner',
                yaxis=dict(autorange="reversed")
            )
            fig = fig.update_layout(xaxis=dict(
                title_font=dict(size=12, family='sans serif', color='black'),
                tickfont=dict(size=12, family='sans serif', color='black')),
                yaxis=dict(
                    title_font=dict(size=12, family='sans serif', color='black', ),
                    tickfont=dict(size=12, family='sans serif', color='black', )))
            st.subheader("Distribution of AUM across Providers")


            st.plotly_chart(fig)
         FD_client_data_df["Year"] = FD_client_data_df["Issue Date"].dt.year
         FD_client_data_df["Month"] = FD_client_data_df["Issue Date"].dt.month

         yearly_monthly_counts = FD_client_data_df.groupby(["Year", "Month"]).size().reset_index(name="Record Count")
         yearly_monthly_counts['Year'] = yearly_monthly_counts['Year'].astype(str)
         yearly_monthly_counts['Month'] = pd.to_datetime(yearly_monthly_counts['Month'], format='%m').dt.strftime( "%B")

         with st.container(border=True):
          timeperiod = st.toggle("Custom Time Period",key=1)
          if timeperiod:
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            available_years = sorted(yearly_monthly_counts['Year'].unique())
            available_months = sorted(yearly_monthly_counts['Month'].unique(),
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
                selected_year = st.selectbox("Select Year", available_years,key='selected-year-1')

            def filter_data(df, year, start_month, end_month):
                month_order_dict = {month: index for index, month in enumerate(month_order)}
                year_filtered = df[df['Year'] == year]
                year_filtered['MonthOnly'] = year_filtered['Month']
                month_filtered = year_filtered[
                    (year_filtered['MonthOnly'].map(month_order_dict) >= month_order_dict[start_month]) &
                    (year_filtered['MonthOnly'].map(month_order_dict) <= month_order_dict[selected_end_month])
                    ]
                month_filtered = month_filtered.sort_values(by='MonthOnly', key=lambda x: x.map(month_order_dict))
                return month_filtered

            filtered_data = filter_data(yearly_monthly_counts, selected_year, start_month, selected_end_month)
            fig = go.Figure(
                data=[go.Bar(
                    x=filtered_data['MonthOnly'].astype(str) + "-" + filtered_data['Year'].astype(str),
                    y=filtered_data['Record Count'],
                    hovertemplate='%{y:,.2f}<extra></extra>',
                    text=filtered_data['Record Count']
                )])
            fig.update_layout(
                xaxis_title="Month",
                yaxis_title="New FD Openings",
                yaxis_tickformat=',.0f', xaxis=dict(
                    title_font=dict(size=12, family='sans serif', color='black'),
                    tickfont=dict(size=12, family='sans serif', color='black')),
                yaxis=dict(
                    title_font=dict(size=12, family='sans serif', color='black', ),
                    tickfont=dict(size=12, family='sans serif', color='black', )))
            fig.update_traces(textposition='outside', textfont=dict(
                family="sans serif",
                size=12,
                color='black', weight='bold'))
            st.subheader(f"New FD Openings for {selected_year} "
                         f"({start_month} - {selected_end_month})")
            st.plotly_chart(fig)
          else:
             yearly_monthly_counts=yearly_monthly_counts.tail(10)
             fig = go.Figure(
                 data=[go.Bar(
                     x=yearly_monthly_counts['Month'].astype(str) + "-" + yearly_monthly_counts['Year'].astype(str),
                     y=yearly_monthly_counts['Record Count'],
                     hovertemplate='%{y:,.2f}<extra></extra>',
                     text=yearly_monthly_counts['Record Count']
                 )])
             fig.update_layout(
                 xaxis_title="Month",
                 yaxis_title="New FD Openings",
                 yaxis_tickformat=',.0f', xaxis=dict(
                     title_font=dict(size=12, family='sans serif', color='black'),
                     tickfont=dict(size=12, family='sans serif', color='black')),
                 yaxis=dict(
                     title_font=dict(size=12, family='sans serif', color='black', ),
                     tickfont=dict(size=12, family='sans serif', color='black', )))
             fig.update_traces(textposition='outside', textfont=dict(
                 family="sans serif",
                 size=12,
                 color='black', weight='bold'))
             st.subheader(f"New FD Openings")
             st.plotly_chart(fig)

         with st.container(border=True):
             yearly_monthly_inflow = FD_client_data_df.groupby(["Year", "Month"])['Investment Amount'].agg(list).reset_index()
             yearly_monthly_inflow['Investment Amount']=yearly_monthly_inflow['Investment Amount'].apply(lambda x: sum(x))
             yearly_monthly_inflow['Year'] = yearly_monthly_inflow['Year'].astype(str)
             yearly_monthly_inflow['Month'] = pd.to_datetime(yearly_monthly_inflow['Month'], format='%m').dt.strftime(
                 "%B")
             #yearly_monthly['Cumulative Sum'] = yearly_monthly['Investment Amount'].cumsum()
             month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                            'July', 'August', 'September', 'October', 'November', 'December']

             timeperiod = st.toggle("Custom Time Period", key=11)
             if timeperiod:
                 available_years = sorted(yearly_monthly_inflow['Year'].unique())
                 available_months = sorted(yearly_monthly_inflow['Month'].unique(),
                                           key=lambda x: month_order.index(x))
                 col1, col2, col3 = st.columns(3)

                 with col1:
                     start_month = st.selectbox("Start Month", available_months,
                                                index=0,  # Default to first month
                                                key="start_month_2")
                 with col2:
                     end_month_options = available_months[available_months.index(start_month):]
                     selected_end_month = st.selectbox("End Month", end_month_options,
                                                       index=len(end_month_options) - 1,
                                                       # Default to last available month
                                                       key="end_month_2")
                 with col3:
                     selected_year = st.selectbox("Select Year", available_years,key='selected_year_2')

                 def filter_data(df, year, start_month, end_month):
                     month_order_dict = {month: index for index, month in enumerate(month_order)}
                     year_filtered = df[df['Year'] == year]
                     year_filtered['MonthOnly'] = year_filtered['Month']
                     month_filtered = year_filtered[
                         (year_filtered['MonthOnly'].map(month_order_dict) >= month_order_dict[start_month]) &
                         (year_filtered['MonthOnly'].map(month_order_dict) <= month_order_dict[selected_end_month])
                         ]
                     month_filtered = month_filtered.sort_values(by='MonthOnly', key=lambda x: x.map(month_order_dict))
                     return month_filtered

                 filtered_data = filter_data(yearly_monthly_inflow, selected_year, start_month, selected_end_month)
                 fig = go.Figure(
                     data=[go.Bar(
                         x=filtered_data['MonthOnly'].astype(str),
                         y=filtered_data['Investment Amount'],
                         hovertemplate='%{y:,.2f}<extra></extra>',
                         text=filtered_data['Investment Amount'].apply(format_currency),
                     )])
                 fig.update_layout(
                     xaxis_title="Month",
                     yaxis_title="New FD Openings",
                     yaxis_tickformat=',.0f', xaxis=dict(
                         title_font=dict(size=12, family='sans serif', color='black'),
                         tickfont=dict(size=12, family='sans serif', color='black')),
                     yaxis=dict(
                         title_font=dict(size=12, family='sans serif', color='black', ),
                         tickfont=dict(size=12, family='sans serif', color='black', )))
                 fig.update_traces(textposition='outside', textfont=dict(
                     family="sans serif",
                     size=12,
                     color='black', weight='bold'))

                 st.subheader(f"New FD Openings for {selected_year} "
                              f"({start_month} - {selected_end_month})")
                 st.plotly_chart(fig)
             else:
                 yearly_monthly_inflow = yearly_monthly_inflow.tail(10)
                 fig = go.Figure(
                     data=[go.Bar(
                         x=yearly_monthly_inflow['Month'].astype(str) + "-" + yearly_monthly_inflow['Year'].astype(str),
                         y=yearly_monthly_inflow['Investment Amount'],
                         hovertemplate='%{y:,.2f}<extra></extra>',
                         text=yearly_monthly_inflow['Investment Amount'].apply(format_currency), textposition='outside',
                     )])
                 fig.update_layout(
                     xaxis_title="Month-Year",
                     yaxis_title="New FD Openings",
                     yaxis_tickformat=',.0f', xaxis=dict(
                         title_font=dict(size=12, family='sans serif', color='black'),
                         tickfont=dict(size=12, family='sans serif', color='black')),
                     yaxis=dict(
                         title_font=dict(size=12, family='sans serif', color='black', ),
                         tickfont=dict(size=12, family='sans serif', color='black', )))
                 fig.update_traces(textposition='outside', textfont=dict(
                     family="sans serif",
                     size=12,
                     color='black', weight='bold'))
                 st.subheader("New FD Openings")
                 st.plotly_chart(fig)

         with st.container(border=True):
          opt=st.selectbox("Select type of filter",options=['Monthly Addition of Clients','Top Investors','FDs Near Maturity'])
          if opt=='Monthly Addition of Clients':
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            available_years = sorted(active_clients['YearOnly'].unique())
            active_clients['MonthOnly']=active_clients['Month']
            available_months = sorted(active_clients['MonthOnly'].unique(),
                                      key=lambda x: month_order.index(x))
            col1, col2, col3 = st.columns(3)

            with col1:
                start_month = st.selectbox("Start Month", available_months,
                                           index=0,  # Default to first month
                                           key="start_month_fd2")
            with col2:
                end_month_options = available_months[available_months.index(start_month):]
                selected_end_month = st.selectbox("End Month", end_month_options,
                                                  index=len(end_month_options) - 1,  # Default to last available month
                                                  key="end_month_fd2")
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

            filtered_data = filter_data(active_clients, selected_year, start_month, selected_end_month)
            filtered_data['Issue Date'] = pd.to_datetime( filtered_data['Issue Date'],format ='%d-%m-%Y').dt.strftime('%d-%m-%Y')
            filtered_data['Maturity Date'] = pd.to_datetime( filtered_data['Maturity Date'],format ='%d-%m-%Y').dt.strftime('%d-%m-%Y')  
            filtered_data=filtered_data.iloc[:,:-3]
            st.dataframe(filtered_data,hide_index=True)
          elif opt == 'Top Investors':
            active_clients = active_clients.sort_values(by=['Investment Amount'],ascending=False).head(5)
            active_clients['Issue Date'] = pd.to_datetime(active_clients['Issue Date'],format ='%d-%m-%Y').dt.strftime('%d-%m-%Y')
            active_clients['Maturity Date'] = pd.to_datetime(active_clients['Maturity Date'],format ='%d-%m-%Y').dt.strftime('%d-%m-%Y') 
            st.dataframe(active_clients,hide_index=True)
          elif opt == 'FDs Near Maturity':
            #delta=st.number_input("Enter the months from now ")
            #delta=delta*30
            today = datetime.date.today()
            one_month_from_today = today + datetime.timedelta(days=30)

            active_clients['Maturity Date'] = pd.to_datetime(active_clients['Maturity Date'],format='mixed').dt.date
            near_maturity_df = active_clients[
                (active_clients['Maturity Date'] >= today) & (active_clients['Maturity Date'] <= one_month_from_today)]
            near_maturity_df = near_maturity_df.iloc[:,:-2]
            near_maturity_df['Issue Date'] = pd.to_datetime(near_maturity_df['Issue Date'],format ='%d-%m-%Y').dt.strftime('%d-%m-%Y')
            near_maturity_df['Maturity Date'] = pd.to_datetime(near_maturity_df['Maturity Date'],format ='%d-%m-%Y').dt.strftime('%d-%m-%Y')               
            st.dataframe(near_maturity_df,hide_index=True)
