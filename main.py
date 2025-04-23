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

def SMALLCASE_Analysis(display=True):
 with psycopg2.connect(**db_config) as connection:
       df=fetch_table_data(connection=connection,table_name="SMALLCASE")
 df['Subscription Start Date'] = pd.to_datetime(df['Subscription Start Date'], errors='coerce')
 df['Subscription End Date'] = pd.to_datetime(df['Subscription End Date'], errors='coerce')
 keywords_to_remove = ['manju', 'ashish']
 import re
 regex = '|'.join(keywords_to_remove)
 df = df[~df['Name'].str.lower().str.contains(regex, na=False, regex=True)]
 df['Networth'] = pd.to_numeric(df['Networth'], errors='coerce')
 df['Networth'] = np.where(df['Current Investment Status'] == 'EXITED', -df['Networth'], df['Networth'])
 df['MonthYear'] = df['Subscription Start Date'].dt.to_period('M')
 new_clients_networth_monthly = df.groupby('MonthYear')['Networth'].sum().reset_index()
 new_clients_networth_monthly.columns = ['Month', 'Total New Client Networth']
 active_clients= df[(df['Current Investment Status']=='INVESTED')& (df['Subscription Status']=='SUBSCRIBED')]
 #st.dataframe(active_clients)
 currenty_not_active_clients = df[(df['Current Investment Status'] == 'INVESTED') & (df['Subscription Status'] == 'UNSUBSCRIBED')]
 active_clients['Subscription Start Date'] = pd.to_datetime(active_clients['Subscription Start Date'])
 existed_clients=df[df['Current Investment Status']=='EXITED']
 active_clients['Networth'] = active_clients['Networth'].astype(float)
 active_clients['MonthYear'] = active_clients['Subscription Start Date'].dt.to_period('M')
 if display:
  col0, col1,col2,col3 = st.columns(4)
  client_smallcases = active_clients.groupby('Name')['Smallcase Name'].agg(list).reset_index()
  client_smallcases['Smallcase Count'] = client_smallcases['Smallcase Name'].apply(len)
  client_smallcases = pd.merge(client_smallcases, active_clients[['Name', 'Subscription Status','Subscription Start Date','Past Subscription Cycles','Subscription Plan']], on='Name', how='left')
  com_networth = df.groupby('Name')['Networth'].sum()
  client_smallcases= pd.merge(client_smallcases,com_networth,on='Name',how='left')
  client_smallcases = client_smallcases.drop_duplicates(subset='Name', keep='first')
  client_smallcases['MonthOnly'] = client_smallcases['Subscription Start Date'].dt.strftime('%B')
  client_smallcases['YearOnly'] = client_smallcases['Subscription Start Date'].dt.strftime('%Y')
  #tab1, tab2 = st.tabs(["Active Clients", "Pending KYC Clients"])
  #with tab1:
  with col0:
      st.metric("Total AUM", format_currency(new_clients_networth_monthly['Total New Client Networth'].sum().round(2)),
                border=True)
  with col1:
      st.metric("Total Active Clients", len(active_clients['Name'].unique()), border=True)
  with col2:
      st.metric("Existing - Not Active Clients", len(currenty_not_active_clients['Name'].unique()), border=True)
  with col3:
      st.metric("Exited Clients", existed_clients['Name'].nunique(), border=True)
#############MONTHLY_NEW_ADDITIONS_VISUALIZATION##############
  col4,col5=st.columns(2)
  with col4:
    with st.container(border=True):
     st.subheader("New Clients Addition Monthly")
     client_smallcases.loc[client_smallcases['Past Subscription Cycles'] == 0, 'MonthYear'] = client_smallcases.loc[
         client_smallcases['Past Subscription Cycles'] == 0, 'Subscription Start Date'].dt.to_period('M')
     new_clients_monthly = client_smallcases.groupby('MonthYear')['Name'].count().reset_index()
     new_clients_monthly['MonthYear'] = new_clients_monthly['MonthYear'].dt.strftime('%B-%Y')
     new_clients_monthly.columns = ['Month', 'New Clients']
     fig = go.Figure(data=[go.Bar(
      x=new_clients_monthly['Month'].astype(str),
      y=new_clients_monthly['New Clients'], hovertemplate='<b>Month:</b> %{x}<br><b>New Clients:</b> %{y}<extra></extra>',text=new_clients_monthly['New Clients'])])
     fig.update_layout( xaxis_title="Month", yaxis_title="New Clients",width=600,height=400,xaxis=dict(
        title_font=dict(size=12, family='sans serif', color='black'),
        tickfont=dict(size=12, family='sans serif', color='black')),
                yaxis=dict(
                            title_font=dict(size=12, family='sans serif', color='black', ),
                            tickfont=dict(size=12, family='sans serif', color='black', ))
                        )
     fig.update_traces(width=0.5,textposition='outside',textfont=dict(
        family="sans serif",
        size=12,
        color='black',weight='bold'))
     st.plotly_chart(fig)
###### Active Client Distribution by Investment Status & Active Client Distribution by Subscription Plan  #######
  #with col4:
  #  with st.container(border=True):
  #    st.subheader("Active Client Distribution by Investment Status")
  #    investment_status_counts = client_smallcases['Subscription Status'].value_counts()
  #    fig_investment_status = px.pie( investment_status_counts, names=investment_status_counts.index,
  #  values=investment_status_counts.values,
  #  hover_data={'Count': investment_status_counts.values})

  #    fig_investment_status.update_traces(
  #  textinfo='percent+label',   hovertemplate='<b>%{label}</b><br>Count: %{customdata[0]}')

  #    st.plotly_chart(fig_investment_status)
  #  with st.expander(" "):
  #     dfs=[]
  #     for status, count in client_smallcases['Subscription Status'].value_counts().items():
  #         clients_with_status = client_smallcases[client_smallcases['Subscription Status'] == status]['Name'].unique()
  #         dfs.append(clients_with_status)
  #     option=st.selectbox("",options=['Subscribed','Not Subscribed'])
  #     if option == 'Subscribed':
  #             st.write(dfs[0])
  #     if option == 'Not Subscribed':
  #             st.write(dfs[1])

  with col5:
   with st.container(border=True):
     st.subheader("Clients Distribution by Subscription Plan")
     subscription_plan_counts = client_smallcases['Subscription Plan'].value_counts()

     fig_subscription_plan_status = go.Figure(data=[go.Pie(
         labels=subscription_plan_counts.index,
         values=subscription_plan_counts.values,
         textinfo='percent+label',
         hovertemplate='<b>Subscription Type:</b> %{label}<br><b>New Clients:</b> %{value}<extra></extra>'
     )])
     fig_subscription_plan_status.update_layout(
         width=600,
         height=400,
     )

     st.plotly_chart(fig_subscription_plan_status)
     #dfs2 = []
     #for plan, count in client_smallcases['Subscription Plan'].value_counts().items():
     #  clients_with_plan = client_smallcases[client_smallcases['Subscription Plan'] == plan]['Name'].unique()
     #  dfs2.append(clients_with_plan)
     #option2 = st.selectbox("", options=['Semi-Annually', 'Quarterly'])
     #if option2 == 'Semi-Annually':
     #  st.write(dfs2[0])
     #if option2 == 'Quarterly':
     #   st.write(dfs2[1])


############AUM INFLOW MONTHLY##########
  filtered_data = new_clients_networth_monthly[new_clients_networth_monthly['Total New Client Networth'] != 0]
  filtered_data = filtered_data.sort_values(by='Month')
  filtered_data['Month'] = filtered_data['Month'].dt.strftime('%B-%Y')
  filtered_data['Monthonly'] = filtered_data['Month'].str.split('-').str[0]
  filtered_data['Year'] = filtered_data['Month'].str.split('-').str[1]
  with st.container(border=True):
   st.subheader("Monthly AUM Inflow")
   timeperiod = st.toggle("Custom Time Period",key="AUM INFLOW MONTHLY")
   if timeperiod:
      month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December']
      available_years = sorted(filtered_data['Month'].str.split('-').str[1].unique())
      available_months = sorted(filtered_data['Month'].str.split('-').str[0].unique(),
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
          year_filtered = df[df['Year'] == year]
          year_filtered['MonthOnly'] = year_filtered['Month'].str.split('-').str[0]
          month_filtered = year_filtered[
              (year_filtered['MonthOnly'].map(month_order_dict) >= month_order_dict[start_month]) &
              (year_filtered['MonthOnly'].map(month_order_dict) <= month_order_dict[selected_end_month])
              ]
          month_filtered = month_filtered.sort_values(by='MonthOnly', key=lambda x: x.map(month_order_dict))
          return month_filtered

      filtered_data = filter_data(filtered_data, selected_year, start_month, selected_end_month)
      if not filtered_data.empty:
         num_data_points = len(filtered_data)
         bar_width = max(0.1, min(0.8, 2.5 / num_data_points))
         fig = go.Figure(data=[go.Bar( x=filtered_data['MonthOnly'].astype(str), y=filtered_data['Total New Client Networth'],
         text=filtered_data['Total New Client Networth'].apply(format_currency),width=bar_width)])
         fig.update_layout( xaxis_title="Month", yaxis_title="Total  Networth", yaxis_tickformat=',.0f',xaxis=dict(
             title_font=dict(size=12, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')),
                           yaxis=dict(
                               title_font=dict(size=12, family='sans serif', color='black', ),
                               tickfont=dict(size=12, family='sans serif', color='black', )))
         fig.update_traces(width=0.5, textposition='outside', textfont=dict(
             family="sans serif",
             size=12,
             color='black',weight='bold' ))
         st.plotly_chart(fig)
   else:
       fig = go.Figure(data=[go.Bar(x=filtered_data['Month'].astype(str), y=filtered_data['Total New Client Networth'],

                                    text=filtered_data['Total New Client Networth'].apply(format_currency), )])

       fig.update_layout(xaxis_title="Month", yaxis_title="Total Networth", yaxis_tickformat=',.0f',xaxis=dict(
             title_font=dict(size=12, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')),
                           yaxis=dict(
                               title_font=dict(size=12, family='sans serif', color='black', ),
                               tickfont=dict(size=12, family='sans serif', color='black', )))
       fig.update_traces(width=0.5, textposition='outside', textfont=dict(
           family="sans serif",
           size=12,
           color='black',weight='bold' ))

       st.subheader("Monthly AUM Inflow")
       st.plotly_chart(fig)

########CUMMULATIVE_AUM_GROWTH######
  with st.container(border=True):
      new_clients_networth_monthly['Cumulative AUM'] = new_clients_networth_monthly[
          'Total New Client Networth'].cumsum()
      new_clients_networth_monthly['Month'] = new_clients_networth_monthly['Month'].dt.strftime("%B-%Y")
      new_clients_networth_monthly['Year'] = new_clients_networth_monthly['Month'].str.split('-').str[1]

      timeperiod=st.toggle("Custom Time Period")
      if timeperiod:
        month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December']
        available_years = sorted(new_clients_networth_monthly['Year'].unique())
        available_months = sorted(new_clients_networth_monthly['Month'].str.split('-').str[0].unique(),
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
          year_filtered = df[df['Year'] == year]
          year_filtered['MonthOnly'] = year_filtered['Month'].str.split('-').str[0]
          month_filtered = year_filtered[
              (year_filtered['MonthOnly'].map(month_order_dict) >= month_order_dict[start_month]) &
              (year_filtered['MonthOnly'].map(month_order_dict) <= month_order_dict[selected_end_month])
              ]
          month_filtered = month_filtered.sort_values(by='MonthOnly', key=lambda x: x.map(month_order_dict))
          return month_filtered

        filtered_data = filter_data(new_clients_networth_monthly, selected_year, start_month, selected_end_month)
        fig = go.Figure(
          data=[go.Scatter(
              x=filtered_data['MonthOnly'].astype(str),
              y=filtered_data['Cumulative AUM'],
              fill='tozeroy',
              hovertemplate='%{y:,.2f}<extra></extra>',
              text=filtered_data['Cumulative AUM'].apply(format_currency)
          )] )
        fig.update_layout(
          xaxis_title="Month",
          yaxis_title="Cumulative AUM",
          yaxis_tickformat=',.0f',xaxis=dict(
             title_font=dict(size=12, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')),
                           yaxis=dict(
                               title_font=dict(size=12, family='sans serif', color='black', ),
                               tickfont=dict(size=12, family='sans serif', color='black', )))
        st.subheader(f"Cumulative AUM Growth for {selected_year} "
                   f"({start_month} - {selected_end_month})")
        st.plotly_chart(fig)
      else:
          fig = go.Figure(
              data=[go.Scatter(
                  x=new_clients_networth_monthly['Month'].astype(str),
                  y=new_clients_networth_monthly['Cumulative AUM'],
                  fill='tozeroy',
                  hovertemplate='%{y:,.2f}<extra></extra>',
                  text=new_clients_networth_monthly['Cumulative AUM']
              )])
          fig.update_layout(
              xaxis_title="Month",
              yaxis_title="Cumulative AUM",
              yaxis_tickformat=',.0f',xaxis=dict(
             title_font=dict(size=12, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')),
                           yaxis=dict(
                               title_font=dict(size=12, family='sans serif', color='black', ),
                               tickfont=dict(size=12, family='sans serif', color='black', )))
          st.subheader(f"Cumulative AUM")
          st.plotly_chart(fig)

  #########AUM_Distribution_across_smallcase########
  col6,col7 = st.columns(2)
  with col6:
    with st.container(border=True):
     exploded_df = client_smallcases.explode('Smallcase Name')
     aum_per_smallcase = exploded_df.groupby('Smallcase Name')['Networth'].sum().reset_index()
     total_aum = client_smallcases['Networth'].sum()
     aum_per_smallcase['Percentage of Total AUM'] = (aum_per_smallcase['Networth'] / total_aum) * 100
     fig_pie = go.Figure(data=[go.Pie(
         labels=aum_per_smallcase['Smallcase Name'],
         values=aum_per_smallcase['Percentage of Total AUM'])])
     st.subheader("Distribution of AUM across Smallcases")
     st.plotly_chart(fig_pie)

  with col7:
    with st.container(border=True):
        clients_per_smallcase = exploded_df.groupby('Smallcase Name')['Name'].unique().reset_index()
        st.subheader("Client Distribution Across Smallcases")
        clients_per_smallcase['Name'] = clients_per_smallcase['Name'].apply(lambda x: len(x))
        clients_per_smallcase = clients_per_smallcase.sort_values(by='Name', ascending=True)
        fig = go.Figure(data=[go.Bar(y=clients_per_smallcase['Smallcase Name'], x=clients_per_smallcase['Name'],
                                     text=clients_per_smallcase['Name'], textposition='outside', orientation='h',
                                     width=0.5,
                                     hovertemplate='<b>Smallcase Name:</b> %{y}<br><b>No of Clients:</b> %{x}<extra></extra>')])

        fig.update_layout(
            xaxis_title="Number of Clients",
            yaxis_title="Smallcase Name",xaxis=dict(
             title_font=dict(size=12, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')),
                           yaxis=dict(
                               title_font=dict(size=12, family='sans serif', color='black', ),
                               tickfont=dict(size=12, family='sans serif', color='black', )))
        st.plotly_chart(fig)
  with st.container(border=True):
        opt = st.selectbox("Select type of filter", options=['Monthly Addition of New Clients', 'Top Investors'])
        if opt == 'Monthly Addition of New Clients':
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            available_years = sorted(client_smallcases['YearOnly'].unique())
            available_months = sorted(client_smallcases['MonthOnly'].unique(),
                                      key=lambda x: month_order.index(x))
            col1, col2, col3 = st.columns(3)

            with col1:
                start_month = st.selectbox("Start Month", available_months,
                                           index=0,  # Default to first month
                                           key="start_month_smallcase")
            with col2:
                end_month_options = available_months[available_months.index(start_month):]
                selected_end_month = st.selectbox("End Month", end_month_options,
                                                  index=len(end_month_options) - 1,  # Default to last available month
                                                  key="end_month_smallcase")
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
                month_filtered = month_filtered[month_filtered['Past Subscription Cycles'] == 0]
                return month_filtered

            filtered_data = filter_data(client_smallcases, selected_year, start_month, selected_end_month)
            filtered_data = filtered_data.iloc[:,:-3]
            st.dataframe(filtered_data, hide_index=True)
        elif opt == 'Top Investors':
            raw_bonds_client_data_df = client_smallcases.sort_values(by=['Networth'], ascending=False).head(5)
            raw_bonds_client_data_df=raw_bonds_client_data_df.iloc[:,:-3]
            st.dataframe(raw_bonds_client_data_df, hide_index=True)


#with tab2:
#  onboarding_required= df1[df1['Subscription Status']=='REQUESTED_ACCESS']
#  streamlit.write(f"total pending onboarding {len(onboarding_required)}")
#  streamlit.dataframe(onboarding_required)
#  text_search = st.text_input("Search detials by client name or other details", value="")
#  m1 = onboarding_required["Name"].str.contains(text_search)
#  m2 = onboarding_required["Phone Number"].str.contains(text_search)
#  m3 = onboarding_required['PAN'].str.contains(text_search)
#  df_search = onboarding_required[m1 | m2 | m3]
#  if text_search:
#      st.write(df_search)

def RIETS_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
        client_data_df = fetch_table_data(connection=connection, table_name="FRACTIONAL_REAL_ESTATE")
  client_data_df['Date of investment '] = client_data_df['Date of investment'].replace('Nil', np.nan)
  client_data_df['Date of investment '] = pd.to_datetime(client_data_df['Date of investment '],format='mixed')
  client_data_df['YearOnly'] = client_data_df['Date of investment '].dt.strftime('%Y')
  client_data_df['MonthOnly'] = client_data_df['Date of investment '].dt.strftime('%B')
  if display:
    no_active_clients = client_data_df[(client_data_df['Deal Stage'] == 'Share Certificate Issued')]
    other_clients = client_data_df[client_data_df['Deal Stage'] != 'Share Certificate Issued']
    col0,col1,col2=st.columns(3)
    with col0:
        aum = client_data_df[
            (client_data_df['Deal Stage'] == 'Share Certificate Issued') & (client_data_df['Investment Value'] != 0)]
        st.metric("Total AUM", format_currency(aum['Investment Value'].sum()), border=True)
    with col1:
        st.metric("Total Active Clients", len(no_active_clients['Name'].unique()), border=True)
    with col2:
        st.metric("Total inactive Clients", len(other_clients['Name'].unique()), border=True)


    col3,col4=st.columns(2)
    with col3:
        with st.container(border=True):
          st.subheader("Client Distribution based on Assets")
          asset_toggle=st.toggle("All Clients",key=0)
          if asset_toggle:
           asset_based_distribution_df = client_data_df['Asset Name'].value_counts()
           asset_pie_fig = px.pie(asset_based_distribution_df, values=asset_based_distribution_df.values,
                               names=asset_based_distribution_df.index)
           st.plotly_chart(asset_pie_fig)
          else:
              client_data_df = client_data_df[client_data_df['Deal Stage'] == 'Share Certificate Issued']
              asset_based_distribution_df = client_data_df['Asset Name'].value_counts()
              asset_pie_fig = px.pie(asset_based_distribution_df, values=asset_based_distribution_df.values,
                                     names=asset_based_distribution_df.index)  # Improved
              st.plotly_chart(asset_pie_fig)
    with col4:
        with st.container(border=True):
            st.subheader("Client Distribution based on Account Type")
            if asset_toggle:
              accounts_type_based_distribution_df = client_data_df['Accounts Type'].value_counts()
              asset_pie_fig = px.pie(accounts_type_based_distribution_df, values=accounts_type_based_distribution_df.values,
                                   names=accounts_type_based_distribution_df.index)  # Improved
              st.plotly_chart(asset_pie_fig)
            else:
                client_data_df = client_data_df[client_data_df['Deal Stage'] == 'Share Certificate Issued']
                accounts_type_based_distribution_df = client_data_df['Accounts Type'].value_counts()
                asset_pie_fig = px.pie(accounts_type_based_distribution_df,
                                       values=accounts_type_based_distribution_df.values,
                                       names=accounts_type_based_distribution_df.index)  # Improved
                st.plotly_chart(asset_pie_fig)

    col5,col6=st.columns(2)
    with col5:
            accounts_type_based_distribution_df = client_data_df['Deal Stage'].value_counts()
            asset_pie_fig = px.pie(accounts_type_based_distribution_df,
                                   values=accounts_type_based_distribution_df.values,
                                   names=accounts_type_based_distribution_df.index)
            with st.container(border=True):
                st.subheader("Client Distribution based on Deal Stage")
                st.plotly_chart(asset_pie_fig)
    with col6:
        with st.container(border=True):
            st.subheader("Client Distribution based on Rental Income Type")
            accounts_type_based_distribution_df = client_data_df['Intrest Income type'].value_counts()
            asset_pie_fig = px.pie(accounts_type_based_distribution_df, values=accounts_type_based_distribution_df.values,
                                   names=accounts_type_based_distribution_df.index)  # Improved
            st.plotly_chart(asset_pie_fig)


    client_data_df = client_data_df.sort_values(['Date of investment '])
    client_data_df['Cummulative AUM'] = client_data_df['Investment Value'].cumsum(skipna=True)
    fig = go.Figure(data=[go.Scatter(
            x=client_data_df['Date of investment '].sort_values(ascending=True),
            y=client_data_df['Cummulative AUM'],
            fill='tozeroy',
            text=client_data_df['Cummulative AUM'],
            hoverinfo='text+x+y',
            mode='lines+markers' )])
    fig.update_layout(
        yaxis=dict(
            tickformat=',.0f',
            title_font=dict(size=12, family='sans serif', color='black'),
            tickfont=dict(size=12, family='sans serif', color='black')
        ),
        xaxis=dict(
            title_font=dict(size=12, family='sans serif', color='black'),
            tickfont=dict(size=12, family='sans serif', color='black')
        )
    )
    with st.container(border=True):
          st.subheader("Cummulative AUM Growth")
          st.plotly_chart(fig)
    with st.container(border=True):
        opt = st.selectbox("Select type of filter", options=['Monthly Addition of New Clients', 'Top Investors'])
        if opt == 'Monthly Addition of New Clients':
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            available_years = sorted(client_data_df['YearOnly'].unique())
            available_months = sorted(client_data_df['MonthOnly'].unique(),
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

            filtered_data = filter_data(client_data_df, selected_year, start_month, selected_end_month)
            filtered_data = filtered_data.iloc[:, :-3]
            st.dataframe(filtered_data, hide_index=True)
        elif opt == 'Top Investors':
            raw_bonds_client_data_df = client_data_df.sort_values(by=['Investment Value'], ascending=False).head(5)
            raw_bonds_client_data_df = raw_bonds_client_data_df.iloc[:, :-3]
            st.dataframe(raw_bonds_client_data_df, hide_index=True)
  return client_data_df


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
        clients_across_PMS = raw_pms_client_data_df.groupby('Strategy')['Name'].nunique().reset_index()
        fig = go.Figure(data=[go.Pie(labels=clients_across_PMS['Strategy'], values=clients_across_PMS['Name'],
                                     hovertemplate='<b>Strategy:</b> %{label}<br><b>Clients:</b> %{value}<br><b>Percentage:</b> %{percent}<extra></extra>')])

        st.subheader('Distribution of Clients Across Strategies')
        st.plotly_chart(fig)
    with col3:
      with st.container(border=True):
        aum_across_PMS = raw_pms_client_data_df.groupby('Strategy')['Invested Amount'].sum().reset_index()
        fig = go.Figure(data=[go.Pie(labels=aum_across_PMS['Strategy'], values=aum_across_PMS['Invested Amount'],
                                     hovertemplate='<b>Strategy:</b> %{label}<br><b>Amount:</b> %{value}<br><b>Percentage:</b> %{percent}<extra></extra>')])
        st.subheader('Distribution of AUM Across Strategies')
        st.plotly_chart(fig)
    with st.container(border=True):
        st.dataframe(raw_pms_client_data_df)
  raw_pms_client_data_df['MonthOnly'] = pd.to_datetime(raw_pms_client_data_df['Date of Investment']).dt.strftime("%B")
  raw_pms_client_data_df['YearOnly'] = pd.to_datetime(raw_pms_client_data_df['Date of Investment']).dt.strftime("%Y")
  return raw_pms_client_data_df

def VESTED_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
        raw_vested_client_data_df = fetch_table_data(connection=connection, table_name="VESTED")
  raw_vested_client_data_df = raw_vested_client_data_df[raw_vested_client_data_df['RM'] != 'Employee']
  raw_vested_client_data_df['Signupdate'] = pd.to_datetime(raw_vested_client_data_df['Signupdate'],format="mixed")
  raw_vested_client_data_df['Signupdate'] = raw_vested_client_data_df['Signupdate'].dt.strftime('%B-%Y')
  raw_vested_client_data_df=raw_vested_client_data_df.fillna(0)
  raw_vested_client_data_df['YearOnly']=raw_vested_client_data_df['Signupdate'].str.split('-').str[1]
  raw_vested_client_data_df['MonthOnly']=raw_vested_client_data_df['Signupdate'].str.split('-').str[0]
  raw_vested_client_data_df['Invested Amount'] = raw_vested_client_data_df['Invested Amount'].astype(str).str.replace('$', '', regex=False).astype(float)
  raw_vested_client_data_df2=raw_vested_client_data_df[raw_vested_client_data_df['Invested Amount']!=0]
  if display:
    col0, col1,col2,col3,col4= st.columns(5)
    with col0:
        VESTED_total_AUM = raw_vested_client_data_df['Invested Amount'].sum()
        st.metric("Total AUM", f" $ {VESTED_total_AUM}", border=True)
    with col1:
        total_vested_clients = len(raw_vested_client_data_df['Name'].unique())
        st.metric("Total Clients", total_vested_clients, border=True)
    with col2:
       total_onboarded_clients = raw_vested_client_data_df[(raw_vested_client_data_df['Subscription'] == 'PREMIUM') & ( raw_vested_client_data_df['Invested Amount'] == 0)]['Name'].nunique()
       st.metric("Onboarded Clients",total_onboarded_clients,border=True)
    with col3:
        total_onboarded_clients = raw_vested_client_data_df[(raw_vested_client_data_df['Subscription'] != 'PREMIUM') & (
                    raw_vested_client_data_df['Invested Amount'] == 0)]['Name'].nunique()
        st.metric("Onboarding Pending Clients", total_onboarded_clients, border=True)
    with col4:
        count = raw_vested_client_data_df['Invested Amount'].dropna().astype(bool).sum()
        st.metric("Total Active Clients", count, border=True)

    col5,col6 = st.columns(2)
    with col5:
        with st.container(border=True):
            st.subheader("New Clients Addition Monthly")

            show_invested = st.toggle("Active Clients")
            if show_invested:
                invested_clients = raw_vested_client_data_df[raw_vested_client_data_df['Invested Amount'] > 0]
                new_clients_monthly = invested_clients.groupby('Signupdate')['Name'].count().reset_index()
            else:
                new_clients_monthly = raw_vested_client_data_df.groupby('Signupdate')['Name'].count().reset_index()

            new_clients_monthly = new_clients_monthly.sort_values('Signupdate', ascending=False)

            fig = px.bar(new_clients_monthly, x=new_clients_monthly['Signupdate'], y=new_clients_monthly['Name'],
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
            available_years = sorted(raw_vested_client_data_df['Signupdate'].str.split('-').str[1].unique())
            available_months = sorted(raw_vested_client_data_df['Signupdate'].str.split('-').str[0].unique(),
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


def Liquiloans(display=True):
  with psycopg2.connect(**db_config) as connection:
    raw_liquiloans_client_data_df= fetch_table_data(connection=connection, table_name="liquiloans")
    condition1 = raw_liquiloans_client_data_df['Current Value (Rs.)'] != '0'
    condition2 = raw_liquiloans_client_data_df['Current Value (Rs.)'].notna()
    active_liquiloans_clients = raw_liquiloans_client_data_df[condition1 & condition2]
  if display:
    tab1,tab2 = st.tabs(['Active Clients','Past Clients'])
    with tab1:
      col0,col1=st.columns(2)
      with col0:
        st.metric("Total Active Clients",len(active_liquiloans_clients['Lender Name']),border=True)
      with col1:
        active_liquiloans_clients.replace(',', '', regex=True, inplace=True)
        active_liquiloans_clients['Current Value (Rs.)'] = pd.to_numeric(active_liquiloans_clients['Current Value (Rs.)'],errors='coerce')
        st.metric("Total AUM",format_currency(active_liquiloans_clients['Current Value (Rs.)'].sum()), border=True)
      with st.container(border=True):
          raw_bonds_client_data_df = active_liquiloans_clients.sort_values(by=['Current Value (Rs.)'],
                                                                           ascending=False).head(5)
          st.subheader("Top Investors")
          st.dataframe(raw_bonds_client_data_df, hide_index=True)
    with tab2:
        st.dataframe(raw_liquiloans_client_data_df[raw_liquiloans_client_data_df['Current Value (Rs.)']=='0'])
  return active_liquiloans_clients
def BONDS_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
        raw_bonds_client_data_df = fetch_table_data(connection=connection, table_name="BONDS")
  raw_bonds_client_data_df['Amount'] = pd.to_numeric(raw_bonds_client_data_df['Amount'])
  raw_bonds_client_data_df['Transaction Date'] = pd.to_datetime(raw_bonds_client_data_df['Transaction Date'])
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
            fig = go.Figure(data=[go.Pie(labels=aum_across_PMS['AMC'], values=aum_across_PMS['Amount'], hovertemplate='<b>AMC:</b> %{label}<br><b>Amount:</b> %{value}<br>,<b>Percentage:</b> %{percent}<extra></extra>')])
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

def FD_Analysis(display=True):
    with psycopg2.connect(**db_config) as connection:
        FD_client_data_df = fetch_table_data(connection=connection, table_name="FD")
    active_clients = FD_client_data_df[FD_client_data_df['Current Status'].isin(["Open", "Live","LIVE"])]
    active_clients['Issue Date']=pd.to_datetime(active_clients['Issue Date'],format='mixed')
    active_clients['YearOnly'] = active_clients['Issue Date'].dt.strftime("%Y")
    active_clients['Month'] = active_clients['Issue Date'].dt.strftime("%B")
    matured_clients = FD_client_data_df[FD_client_data_df['Current Status'].isin(["CLOSED", "mature"])]
    FD_client_data_df['Issue Date'] = pd.to_datetime(FD_client_data_df['Issue Date'])
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
           fig = go.Figure(data=[go.Pie(labels=fd_distribution_across_providers['Channel Partner'], textinfo='percent',
                                     values=fd_distribution_across_providers['No of FD'],hovertemplate='<b>Channel Partner:</b> %{label}<br><b>No of FD:</b> %{value}<br>,<b>Percentage:</b> %{percent}<extra></extra>')])

           st.subheader("Distribution of FDs across Providers")
           st.plotly_chart(fig)
         with col4.container(border=True):
            aum_distribution_across_providers = active_clients.groupby('Channel Partner')[
                'Investment Amount'].sum().reset_index()

            # Create the bar chart
            fig = go.Figure(go.Bar(
                x=aum_distribution_across_providers['Investment Amount'],
                y=aum_distribution_across_providers['Channel Partner'],
                orientation='h'
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
                selected_year = st.selectbox("Select Year", available_years)

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
                    x=filtered_data['MonthOnly'].astype(str),
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
                     x=yearly_monthly_counts['Month'].astype(str),
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
                                                key="start_month")
                 with col2:
                     end_month_options = available_months[available_months.index(start_month):]
                     selected_end_month = st.selectbox("End Month", end_month_options,
                                                       index=len(end_month_options) - 1,
                                                       # Default to last available month
                                                       key="end_month")
                 with col3:
                     selected_year = st.selectbox("Select Year", available_years)

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
            filtered_data=filtered_data.iloc[:,:-3]
            st.dataframe(filtered_data,hide_index=True)
          elif opt == 'Top Investors':
            active_clients = active_clients.sort_values(by=['Investment Amount'],ascending=False).head(5)
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
            st.dataframe(near_maturity_df,hide_index=True)




def Geenrate_MIS_Report():
    def fetch_table_data_MIS(table_name):
      """Fetch data from a PostgreSQL table and return as a Pandas DataFrame."""
      try:
        with psycopg2.connect(**db_config) as connection:
         query = f'SELECT * FROM "{table_name}";'  # Handling table names with special characters
         with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]  # Get column names
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=columns)
      except psycopg2.Error as e:
        print(f"Error fetching data from {table_name}: {e}")
        return pd.DataFrame()  # Return empty DataFrame if an error occurs

    master_data = fetch_table_data_MIS( "Clients_Master_Data")
    master_data = master_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
    Bonds_data = fetch_table_data_MIS("BONDS")
    Bonds_data = Bonds_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
    Bonds_data['Amount'] = Bonds_data['Amount'].astype(float)
    Smallcase_data = fetch_table_data_MIS("SMALLCASE")
    Smallcase_data = Smallcase_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
    #st.dataframe(Smallcase_data)
    PMS_data = fetch_table_data_MIS("PMS")
    PMS_data = PMS_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
    VESTED_data = fetch_table_data_MIS("VESTED")
    VESTED_data = VESTED_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
    VESTED_data['Aum'] = VESTED_data['Aum'].str.replace(',', '',regex=False).astype(float)
    Liquiloans_data = fetch_table_data_MIS("liquiloans")
    Liquiloans_data = Liquiloans_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
    Liqui_data = fetch_table_data_MIS("FRACTIONAL_REAL_ESTATE")
    Liquiloans_data = Liquiloans_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)

    FD_data = fetch_table_data_MIS("FD")
    #st.dataframe(FD_data)
    RM_name=st.selectbox("Select the RM",options=['rahul m v'])
    filtered_df = master_data[(master_data['RM Name'] == 'rahul m v')]
    #st.write(filtered_df)
    smallcase_clients = Smallcase_data.loc[Smallcase_data['PAN'].isin(filtered_df['PAN Number'])]
    #smallcase_clients = Smallcase_data.loc[Smallcase_data['RM'] == 'chandan']
    bonds_clients = Bonds_data.loc[Bonds_data['PAN'].isin(filtered_df['PAN Number'])]
    FD_clients = FD_data.loc[FD_data['PAN'].isin(filtered_df['PAN Number'])]
    pms_clients = PMS_data.loc[PMS_data['PAN'].isin(filtered_df['PAN Number'])]
    vested_clients = VESTED_data.loc[VESTED_data['RM'].isin(filtered_df['RM Name'])]
    vested_clients['Invested Amount'] = vested_clients['Invested Amount'].fillna(0)
    vested_clients['Invested Amount'] = vested_clients['Invested Amount'].astype(str).str.replace('$', '', regex=False).astype(float)
    liquiloans_clients = Liquiloans_data.loc[Liquiloans_data['PAN'].isin(filtered_df['PAN Number'])]
    liquiloans_clients['Current Value (Rs.)'].replace(',', '', regex=True, inplace=True)
    liquiloans_clients['Current Value (Rs.)']=liquiloans_clients['Current Value (Rs.)'].astype(float)
    smallcase_clients['Networth'] = pd.to_numeric(smallcase_clients['Networth'], errors='coerce')
    smallcase_clients['Networth'] = np.where(smallcase_clients['Current Investment Status'] == 'EXITED', -smallcase_clients['Networth'], smallcase_clients['Networth'])

    # User selects a month
    selected_month = st.date_input("Select a Month").strftime('%B-%Y')
    # Dictionary mapping for investment date columns
    date_column_map = {
    "smallcase_clients": "Subscription Start Date",
    "bonds_clients": "Transaction Date",
    "pms_clients": "Date of Investment",
    "vested_clients": "Fadate",
    "fd_clients": "Issue Date"}

    # Function to filter and aggregate investments for last 3 months
    def get_monthly_data(df, amount_col, date_col):
      if date_col not in df.columns:
          return pd.Series([0, 0, 0], index=three_months)  # Return zero if column missing
      df[date_col] = pd.to_datetime(df[date_col], errors='coerce', format='mixed')  # Convert date column
      df['Year-Month'] = df[date_col].dt.strftime('%B-%Y')
      df_filtered = df[df['Year-Month'].isin(three_months)]
      return df_filtered.groupby(['Year-Month'])[amount_col].sum().reindex(three_months, fill_value=0)

    # Define last three months from selected month
    selected_date = pd.to_datetime(selected_month + '-01')
    three_months = [(selected_date - pd.DateOffset(months=i)).strftime('%B-%Y') for i in range(3)]

    # Fetch investment amounts for each product using correct date column
    investment_data = {
    "Smallcase": get_monthly_data(smallcase_clients, 'Networth', date_column_map["smallcase_clients"]),
    "Bonds": get_monthly_data(bonds_clients, 'Amount', date_column_map["bonds_clients"]),
    "PMS": get_monthly_data(pms_clients, 'Invested Amount', date_column_map["pms_clients"]),
    "Vested": get_monthly_data(vested_clients, 'Aum', date_column_map["vested_clients"]),
    "FD":get_monthly_data(FD_clients,'Investment Amount',date_column_map['fd_clients'])}

    # Convert to DataFrame
    investment_df = pd.DataFrame(investment_data).reset_index().melt(id_vars="Year-Month", var_name="Product",
                                                                 value_name="Invested Amount")
    investment_df = investment_df.fillna(0)

    investment_df['Year-Month'] = pd.Categorical(investment_df['Year-Month'], categories=three_months[::-1], ordered=True)
    investment_df = investment_df.sort_values('Year-Month')

    # Plot Stacked Bar Chart
    fig = px.bar(investment_df, x=investment_df["Product"], y=investment_df["Invested Amount"], color="Year-Month", barmode="group")
    fig.update_layout(
    xaxis_title="Products",
    yaxis_title="Net Inflow",
    xaxis=dict(
        title_font=dict(size=12, family='sans serif', color='black'),
        tickfont=dict(size=12, family='sans serif', color='black')
    ),
    yaxis=dict( tickformat=',.0f',
        title_font=dict(size=12, family='sans serif', color='black'),
        tickfont=dict(size=12, family='sans serif', color='black')
    ))
    fig.update_traces(
    hovertemplate="<b>Product:</b> %{x}<br><b>Amount:</b> %{y}<extra></extra>")

    # Set showlegend to True to ensure the legend shows all months
    fig.update_layout(showlegend=True)

    # Explicitly show zero values
    fig.update_traces(marker_line_width=1.3, marker_line_color="black", opacity=0.8)

    st.plotly_chart(fig)

    Smallcase_Active= smallcase_clients[(smallcase_clients['Current Investment Status']=='invested')& (smallcase_clients['Subscription Status']=='subscribed')]
    Smallcase_Active['Subscription Start Date'] = pd.to_datetime(Smallcase_Active['Subscription Start Date'], errors='coerce')
    Smallcase_Active['Month-Year'] = Smallcase_Active['Subscription Start Date'].dt.strftime('%B-%Y')
    filtered_smallcase = Smallcase_Active[Smallcase_Active['Month-Year'] == selected_month]
    with st.container(border=True):
      col1,col2=st.columns(2)
      with col1:
       st.subheader("SMALLCASE")
       columns_to_select = ['Name','Networth','PAN','Smallcase Name']
       filtered_df_smallcase = filtered_smallcase[columns_to_select]
       filtered_df_smallcase.rename(columns={'Networth': 'Invested Amount'}, inplace=True)
       if len(filtered_df) > 0:
          st.dataframe(filtered_df_smallcase,hide_index=True)
          with col2:
              st.metric("Total AUM",format_currency(sum(filtered_df_smallcase['Invested Amount'])),border=True)
       else:
           st.write("No Transactions")

    with st.container(border=True):
      col1, col2 = st.columns(2)
      with col1:
        st.subheader("VESTED")
      vested_clients=vested_clients[vested_clients['Invested Amount'] != 0]
      if len(vested_clients) > 0:
         st.dataframe(vested_clients)
         with col2:
            st.metric("Total AUM", format_currency(sum(vested_clients['Invested Amount'])), border=True)
      else:
         st.write("No Transactions")

    with st.container(border=True):
      pms_clients['Date of Investment'] = pd.to_datetime(pms_clients['Date of Investment'],
                                                                 errors='coerce')
      pms_clients = pms_clients[pms_clients['Year-Month'] == selected_month]
      columns_to_select = ['Name', 'Invested Amount','PAN','Strategy']
      filtered_df = pms_clients[columns_to_select]
      col1, col2 = st.columns(2)
      with col1:
        st.subheader("PMS")
      if len(filtered_df) > 0:
          st.dataframe(filtered_df,hide_index=True)
          with col2:
              st.metric("Total AUM",format_currency(sum(filtered_df['Invested Amount'])), border=True)
      else:
          st.write("No Transactions")

    # Filter Bonds Data
    bonds_clients['Transaction Date'] = pd.to_datetime(bonds_clients['Transaction Date'], errors='coerce')
    bonds_clients['Month-Year'] = bonds_clients['Transaction Date'].dt.strftime('%B-%Y')
    filtered_bonds = bonds_clients[bonds_clients['Month-Year'] == selected_month]
    with st.container(border=True):
        columns_to_select = ['Name', 'Amount','PAN','Issue Name','Type']
        bond_filtered_df = filtered_bonds[columns_to_select]
        col1, col2 = st.columns(2)
        with col1:
          st.subheader("Bonds")
        if len(filtered_df) > 0:
            st.dataframe(bond_filtered_df,hide_index=True)
            bond_filtered_df.rename(columns={'Amount': 'Invested Amount'}, inplace=True)
            with col2:
              st.metric("Total AUM",format_currency(sum(bond_filtered_df['Invested Amount'])), border=True)
        else:
           st.write("No Transactions")


    FD_clients['Transaction Date'] = pd.to_datetime(FD_clients['Issue Date'], errors='coerce')
    FD_clients['Month-Year'] = FD_clients['Issue Date'].dt.strftime('%B-%Y')
    filtered_FD = FD_clients[FD_clients['Month-Year'] == selected_month]
    with st.container(border=True):
        columns_to_select = ['Customer Name', 'Issue Date','Investment Amount','Channel Partner']
        filtered_FD = filtered_FD[columns_to_select]
        col1, col2 = st.columns(2)
        with col1:
          st.subheader("FD")
        if len(filtered_FD) > 0:
          st.dataframe(filtered_FD,hide_index=True)
          filtered_FD.rename(columns={'Customer Name': 'Name'}, inplace=True)
          with col2:
              st.metric("Total AUM",format_currency(sum(filtered_FD['Investment Amount'])), border=True)
        else:
          st.write("No Transactions")
            
    rm_name = 'RAHUL MV'    
    if st.button("Generate Simple PDF Report"):
        with st.spinner("Generating..."):
            # Create a dedicated output path for the PDF
            output_filename = f"Investment_Report_{rm_name.replace(' ', '_')}_{selected_month.replace(' ', '_')}.pdf"
            temp_path = os.path.join(tempfile.gettempdir(), output_filename)
            
            pdf_path = create_simple_investment_report(
                rm_name,
                selected_month,
                investment_df,
                filtered_df_smallcase,
                vested_clients,
                pms_clients,
                bond_filtered_df,
                filtered_FD,
                output_path=temp_path
            )
            
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_data = f.read()
                
                st.download_button(
                    label="Download Report",
                    data=pdf_data,
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf"
                )
            else:
                st.error("Failed to generate PDF report.")

def AIF_Analysis(display=True):
  if display:
    col0,col1=st.columns(2)
    with col0:
      st.metric("Total Active Clients",0,border=True)

    with col1:
      st.metric("Total AUM",0,border=True)




if __name__ == "__main__":
    page = st.sidebar.radio("Go to", ["Smallcase", "Fractional Real Estate", "Bonds","Liquiloans","PMS","Vested","FD","AIF","MIS Report"])
    if page == "Bonds":
        BONDS_Analysis()
    elif page == "PMS":
        PMS_Analysis(display=True)
    elif page == "Vested":
        VESTED_Analysis(display=True)
    elif page == "Liquiloans":
        Liquiloans()
    elif page == "Fractional Real Estate":
        RIETS_Analysis(display=True)
    elif page == "Smallcase":
        SMALLCASE_Analysis(display=True)
    elif page == "FD":
        FD_Analysis()
    elif page == "AIF":
        AIF_Analysis()
    elif page =="MIS Report":
        Geenrate_MIS_Report()

