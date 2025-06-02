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
     client_smallcases['Subscription Start Date'] = pd.DatetimeIndex(client_smallcases['Subscription Start Date'])
     client_smallcases2=client_smallcases.copy()
     client_smallcases2['Subscription Start Date'] = client_smallcases2['Subscription Start Date'].dt.strftime("%B-%Y")
     client_smallcases2[['MonthOnly', 'YearOnly']] = client_smallcases2[
         'Subscription Start Date'].str.split('-', expand=True)
     monthly_onboarding_clients = (
         df.groupby(pd.Grouper(key='Subscription Start Date', freq='M'))['Name']
         .nunique()
         .reset_index(name='Number of Clients'))
     monthly_onboarding_clients['Month'] = monthly_onboarding_clients['Subscription Start Date'].dt.strftime("%B-%Y")
     fig = go.Figure(data=[
         go.Bar(x=monthly_onboarding_clients['Month'], y=monthly_onboarding_clients['Number of Clients'],
             hovertemplate="<b>Month:</b> %{x}<br><b>New Clients:</b> %{y}<extra></extra>",
             text=monthly_onboarding_clients['Number of Clients'],
             width=0.5 ) ])
     fig.update_layout(
         xaxis_title="Month",
         yaxis_title="Number of Clients", width=700, height=450,
         xaxis=dict(
             title_font=dict(size=14, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')
         ),  yaxis=dict(  title_font=dict(size=14, family='sans serif', color='black'),
             tickfont=dict(size=12, family='sans serif', color='black')))

     fig.update_traces(textposition='outside',textfont=dict( family="sans serif", size=12, color='black',   weight='bold'  ))
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
     fig_subscription_plan_status = go.Figure(data=[go.Pie(labels=subscription_plan_counts.index,
                                            values=subscription_plan_counts.values,
                                            hole=0.3,
                                            hovertemplate='<b>Subscription Type:</b> %{label}<br><b>New Clients:</b> %{value}<extra></extra>',
                                            marker=dict(colors=px.colors.diverging.Temps))])
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
         values=aum_per_smallcase['Percentage of Total AUM'],
         hole=0.3,
         marker=dict(colors=px.colors.diverging.Temps),
         hovertemplate="<b>Smallcase:</b> %{label}<br><b>AUM Share:</b> %{value:.2f}%<br><b>Percentage:</b> %{percent}<extra></extra>"
     )])
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
        opt = st.selectbox("Select type of filter", options=['Monthly Addition of New Clients', 'Top Investors','Active Clients','Exited Clients'])
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
        elif opt == 'Active Clients':
            smallcase_options=active_clients['Smallcase Name'].unique()
            smallcase_sel=st.selectbox("Select a smallcase",options=smallcase_options)
            if smallcase_sel:
                st.dataframe(active_clients[active_clients['Smallcase Name']==smallcase_sel].iloc[:,:-4],hide_index=True)
            else:
                st.dataframe(active_clients.iloc[:, :-4],hide_index=True)
        elif opt == 'Exited Clients':
            st.dataframe(existed_clients.iloc[:, :-4],hide_index=True)


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
           asset_pie_fig = go.Figure(data=[go.Pie(labels=asset_based_distribution_df.index,
                                                  values=asset_based_distribution_df.values,
                                                  hole=0.3,
                                                  marker=dict(colors=px.colors.diverging.Temps))])
           st.plotly_chart(asset_pie_fig)
          else:
              client_data_df = client_data_df[client_data_df['Deal Stage'] == 'Share Certificate Issued']
              asset_based_distribution_df = client_data_df['Asset Name'].value_counts()
              asset_pie_fig = go.Figure(data=[go.Pie(labels=asset_based_distribution_df.index,
                                                     values=asset_based_distribution_df.values,
                                                     hole=0.3,
                                                     marker=dict(colors=px.colors.diverging.Temps))])
              st.plotly_chart(asset_pie_fig)
    with col4:
        with st.container(border=True):
            st.subheader("Client Distribution based on Account Type")
            if asset_toggle:
              accounts_type_based_distribution_df = client_data_df['Accounts Type'].value_counts()
              asset_pie_fig = go.Figure(data=[go.Pie(labels=accounts_type_based_distribution_df.index,
                                           values=accounts_type_based_distribution_df.values,
                                           hole=0.3,
                                           marker=dict(colors=px.colors.diverging.Temps))])
              st.plotly_chart(asset_pie_fig)
            else:
                client_data_df = client_data_df[client_data_df['Deal Stage'] == 'Share Certificate Issued']
                accounts_type_based_distribution_df = client_data_df['Accounts Type'].value_counts()
                asset_pie_fig = go.Figure(data=[go.Pie(labels=accounts_type_based_distribution_df.index,
                                                       values=accounts_type_based_distribution_df.values,
                                                       hole=0.3,
                                                       marker=dict(colors=px.colors.diverging.Temps))])
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
        fig = go.Figure(data=[go.Pie(labels=clients_across_PMS['Strategy'],
                                     values=clients_across_PMS['Name'],
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

def VESTED_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
        raw_vested_client_data_df = fetch_table_data(connection=connection, table_name="VESTED")
  raw_vested_client_data_df = raw_vested_client_data_df[raw_vested_client_data_df['RM'] != 'Employee']
  raw_vested_client_data_df = raw_vested_client_data_df.dropna(subset=['Name'])
  raw_vested_client_data_df['Signupdate'] = pd.to_datetime(raw_vested_client_data_df['Signupdate'],format="%d-%m-%Y")
  raw_vested_client_data_df['Signupdate'] = raw_vested_client_data_df['Signupdate'].dt.strftime('%B-%Y')
  raw_vested_client_data_df=raw_vested_client_data_df.fillna(0)
  raw_vested_client_data_df['YearOnly']=raw_vested_client_data_df['Signupdate'].str.split('-').str[1]
  raw_vested_client_data_df['MonthOnly']=raw_vested_client_data_df['Signupdate'].str.split('-').str[0]
  raw_vested_client_data_df['Invested Amount'] = pd.to_numeric(raw_vested_client_data_df['Invested Amount'])
  raw_vested_client_data_df['Invested Amount'] = raw_vested_client_data_df['Invested Amount'].astype(float)
  raw_vested_client_data_df2=raw_vested_client_data_df[raw_vested_client_data_df['Invested Amount']!=0]
  st.dataframe(raw_vested_client_data_df2)
  if display:
    col0, col1,col2,col3,col4= st.columns(5)
    with col0:
        VESTED_total_AUM = raw_vested_client_data_df2['Equity'].astype(float).sum()
        st.metric("Total AUM", f" $ {VESTED_total_AUM}", border=True)
    with col1:
        total_vested_clients = len(raw_vested_client_data_df2['Name'].unique())
        st.metric("Active Clients", total_vested_clients, border=True)
    with col2:
       total_onboarded_clients = raw_vested_client_data_df[(raw_vested_client_data_df['Subscription'] == 'PREMIUM') & ( raw_vested_client_data_df['Invested Amount'] == 0)]['Name'].nunique()
       st.metric("Onboarded Clients",total_onboarded_clients,border=True)
    with col3:
        total_onboarded_clients = raw_vested_client_data_df2[(raw_vested_client_data_df['Subscription'] != 'PREMIUM') & (
                    raw_vested_client_data_df['Invested Amount'] == 0)]['Name'].nunique()
        st.metric("Onboarding Pending Clients", total_onboarded_clients, border=True)
    with col4:
        count = raw_vested_client_data_df2['Invested Amount'].dropna().astype(bool).sum()
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
            fig = go.Figure(data=[go.Pie(labels=aum_across_PMS['AMC'],
                                                   values=aum_across_PMS['Amount'],
                                                   hole=0.3,
                                                   marker=dict(colors=px.colors.diverging.Temps))])
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
        FD_client_data_df['Maturity Date'] = pd.to_datetime(FD_client_data_df['Maturity Date'],format='mixed')
        FD_client_data_df['Current Status2'] = FD_client_data_df['Maturity Date'].apply(
    lambda x: 'Mature' if x.date() < date.today() else 'Live')
    active_clients = FD_client_data_df[FD_client_data_df['Current Status2'] == 'Live']
    active_clients['Issue Date']=pd.to_datetime(active_clients['Issue Date'],format='mixed')
    active_clients['YearOnly'] = active_clients['Issue Date'].dt.strftime("%Y")
    active_clients['Month'] = active_clients['Issue Date'].dt.strftime("%B")
    matured_clients = FD_client_data_df[FD_client_data_df['Current Status2']=='Mature']
    FD_client_data_df['Issue Date'] = pd.to_datetime(FD_client_data_df['Issue Date'],format='mixed')
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

def BANK_Analysis(display=True):
    with psycopg2.connect(**db_config) as connection:
       df=fetch_table_data(connection=connection,table_name="BANK")

    clients_across_products=df['PRODUCTNAME'].value_counts()
    fig = go.Figure(data=[go.Pie(labels=clients_across_products.index,
                              values=clients_across_products.values,
                              hole=0.3,
                              marker=dict(colors=px.colors.diverging.Temps))])
    col1,col2=st.columns(2)
    with col1:
      with st.container(border=True):
        st.subheader("Distribution of Clients across Products")
        st.plotly_chart(fig)
    df['BOOKING_MONTH'] = pd.DatetimeIndex(df['BOOKING_MONTH'])
    df2=df.copy()
    df2['BOOKING_MONTH']=df2['BOOKING_MONTH'].dt.strftime("%B-%Y")
    df2[['MonthOnly', 'YearOnly']] = df2[
        'BOOKING_MONTH'].str.split('-', expand=True)
    monthly_onboarding_clients = (
           df.groupby(pd.Grouper(key='BOOKING_MONTH', freq='M'))['CUSTOMERNAME']
           .agg(list)
           .reset_index()
           .sort_values('BOOKING_MONTH'))
    monthly_onboarding_clients['Number of Clients'] = monthly_onboarding_clients['CUSTOMERNAME'].apply(len)
    bank_fig = px.bar(monthly_onboarding_clients, x=monthly_onboarding_clients['BOOKING_MONTH'], y=monthly_onboarding_clients['Number of Clients'],
                         text=monthly_onboarding_clients['Number of Clients'])

    bank_fig.update_layout(
           xaxis_title='Month',
           yaxis_title='New Clients',
           width=500,
           height=400,
           xaxis=dict(
               title_font=dict(size=12, family='sans serif', color='black'),
               tickfont=dict(size=12, family='sans serif', color='black')
           ),
           yaxis=dict(
               title_font=dict(size=12, family='sans serif', color='black'),
               tickfont=dict(size=12, family='sans serif', color='black')
           ))
    bank_fig.update_traces(
           hovertemplate="<b>Month:</b> %{x}<br><b>New Clients:</b> %{y}<extra></extra>",
           textposition='outside',textfont=dict(family="sans serif", size=12, color='black', weight='bold'))
    with col2:
        with st.container(border=True):
          st.subheader("Monthly Addition of Clients")
          st.plotly_chart(bank_fig)
    with st.container(border=True):
        opt = st.selectbox("Select type of filter", options=['Monthly Addition of Clients', 'Top Investors'])
        if opt == 'Monthly Addition of Clients':
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            available_years = sorted(df2['YearOnly'].unique())
            available_months = sorted(df2['MonthOnly'].unique(),
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

            filtered_data = filter_data(df2, selected_year, start_month, selected_end_month)
            st.dataframe(filtered_data)


def Geenrate_MIS_Report():   
   @st.cache_data(ttl=7200)
   def fetch_table_data_MIS(table_name):
      try:
         with psycopg2.connect(**db_config) as connection:
           query = f'SELECT * FROM "{table_name}";'
           with connection.cursor() as cursor:
              cursor.execute(query)
              columns = [desc[0] for desc in cursor.description]
              rows = cursor.fetchall()
              return pd.DataFrame(rows, columns=columns)
      except psycopg2.Error as e:
        print(f"Error fetching data from {table_name}: {e}")
        return pd.DataFrame()
   master_data = fetch_table_data_MIS( "Clients_Master_Data")
   master_data = master_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
   Bonds_data = fetch_table_data_MIS("BONDS")
   Bonds_data = Bonds_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
   Bonds_data['Amount'] = Bonds_data['Amount'].astype(float)
   Smallcase_data = fetch_table_data_MIS("SMALLCASE")
   Smallcase_data = Smallcase_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)
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
   FD_data = FD_data.applymap(lambda x: x.lower() if isinstance(x, str) else x)         
   with st.container(border=True):
    col1,col2=st.columns(2)
    with col1:
      RM_name=st.selectbox("Select the RM",options=['rahul m v','mudit','chandan b r','ashish lal','arun mathew','binto sebastian','ratheesh nambiar','khushboo sheth','manju - divya','manju - suhas','manju - chandan','manju - rahul','manju - khushboo','manju - mudit','manju - binto'])
    with col2:
      timeperiod=st.radio("Select the timeframe",['Monthly','Quarterly','Calender Year','Financial Year'],horizontal=True)
      if timeperiod =='Monthly':
         selected_month = st.date_input("Select a Month").strftime('%B-%Y')
      elif timeperiod =='Quarterly':
          def generate_quarter_fy_options(start_year=2023, num_years=5):
              options = []
              for year in range(start_year, start_year + num_years):
                  for quarter in range(1, 5):
                      options.append(f'Q{quarter} - FY{year}')
              return options
          quarter_fy_options = generate_quarter_fy_options(start_year=2023,
                                                           num_years=3)  # Adjust start year and number of years as needed

          selected_quarter_fy = st.selectbox("Select Quarter and Fiscal Year:", quarter_fy_options)
      elif timeperiod =='Calender Year':
          cy_options=['2022','2023','2024','2025']
          selected_calender_year = st.selectbox("Select the Calender Year:",cy_options)
          selected_calender_year = int(selected_calender_year)
      else:
          fy_options = ['FY2020-21','FY2021-22','FY2022-23','FY2023-24','FY2024-25']
          selected_financial_year = st.selectbox("Select the Financial Year",fy_options)
          
   filtered_df = master_data[(master_data['RM Name'] == RM_name)]
   smallcase_clients = Smallcase_data.loc[Smallcase_data['RM'] == RM_name]
   smallcase_clients['Networth'] = pd.to_numeric(smallcase_clients['Networth'], errors='coerce')
   smallcase_clients['Networth'] = np.where(smallcase_clients['Current Investment Status'] == 'EXITED', -smallcase_clients['Networth'], smallcase_clients['Networth'])
   bonds_clients = Bonds_data.loc[Bonds_data['PAN'].isin(filtered_df['PAN Number'])]
   FD_clients = FD_data.loc[FD_data['PAN'].isin(filtered_df['PAN Number'])]
   FD_clients = FD_clients.dropna(subset=['PAN'])
   pms_clients = PMS_data.loc[PMS_data['PAN'].isin(filtered_df['PAN Number'])]
   vested_clients = VESTED_data.loc[VESTED_data['RM'] == RM_name]
   vested_clients['Invested Amount'] = vested_clients['Invested Amount'].fillna(0)
   vested_clients['Invested Amount'] = vested_clients['Invested Amount'].astype(float)
   liquiloans_clients = Liquiloans_data.loc[Liquiloans_data['PAN'].isin(filtered_df['PAN Number'])]
   liquiloans_clients['Current Value (Rs.)'].replace(',', '', regex=True, inplace=True)
   liquiloans_clients['Current Value (Rs.)']=liquiloans_clients['Current Value (Rs.)'].astype(float)     

   date_column_map = {
    "smallcase_clients": "Subscription Start Date",
    "bonds_clients": "Transaction Date",
    "pms_clients": "Date of Investment",
    "vested_clients": "Signupdate",
    "fd_clients": "Issue Date"}
   def get_time_series_data(df, date_col, amount_col=None, source=None, frequency='monthly', month_list=None,cy_list=None,fy_list=None):
    if frequency == 'monthly' and month_list is None:
        raise ValueError("month_list is required for monthly frequency.")

    if date_col not in df.columns:
        if frequency == 'monthly':
            return pd.Series([0] * len(month_list), index=month_list)
        elif frequency == 'calendar_year':
            return pd.Series([0] * len(cy_list), index=cy_list)
        elif frequency == 'financial_year':
            return pd.Series([0] * len(fy_list), index=fy_list)
        else:
            return pd.DataFrame()

    # Date parsing
    if source in ['vested_clients', 'fd_clients']:
        df[date_col] = pd.to_datetime(df[date_col], format='%d-%m-%Y')
    else:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce', format='mixed')

    if frequency == 'monthly':
        df['Year-Month'] = df[date_col].dt.strftime('%B-%Y')
        df_filtered = df[df['Year-Month'].isin(month_list)]
        return df_filtered.groupby('Year-Month')[amount_col].sum().reindex(month_list, fill_value=0)

    elif frequency == 'quarterly':
        df['Fiscal_Quarter'] = pd.PeriodIndex(df[date_col], freq='Q-MAR')
        df['Fiscal_Quarter'] = df['Fiscal_Quarter'].apply(
            lambda x: f"Q{x.quarter} - FY{x.year - 1}" if x.quarter == 4 else f"Q{x.quarter} - FY{x.year}"
        )
        return df.groupby('Fiscal_Quarter')

    elif frequency == 'calendar_year':
        df['Calendar_Year'] = df[date_col].dt.year
        df_filtered = df[df['Calendar_Year'].isin(cy_list)]
        return df_filtered.groupby('Calendar_Year')[amount_col].sum().reindex(cy_list, fill_value=0)

    elif frequency == 'financial_year':
        df['Financial_Year'] = df[date_col].apply(
            lambda x: f"FY{x.year - 1}-{str(x.year)[-2:]}" if x.month <= 3 else f"FY{x.year}-{str(x.year + 1)[-2:]}"
        )
        df_filtered = df[df['Financial_Year'].isin(fy_list)]
        return df_filtered.groupby('Financial_Year')[amount_col].sum().reindex(fy_list, fill_value=0)

    else:
        raise ValueError("frequency must be either 'monthly' or 'quarterly'") 

   if timeperiod == 'Quarterly':
      investment_data_quarterly={  "Vested": get_time_series_data(vested_clients,amount_col='Invested Amount',date_col=date_column_map["vested_clients"],frequency='quarterly',source='vested_clients'),
      "FD": get_time_series_data(FD_clients, amount_col='Investment Amount', date_col=date_column_map['fd_clients'],frequency='quarterly', source='fd_clients'),
      "Smallcase": get_time_series_data(smallcase_clients, amount_col='Networth', date_col=date_column_map["smallcase_clients"],frequency='quarterly', source='smallcase_clients'),
      "PMS": get_time_series_data(pms_clients, amount_col='Invested Amount', date_col=date_column_map["pms_clients"],frequency='quarterly', source='pms_clients'),
      "Bonds": get_time_series_data(bonds_clients, amount_col='Amount', date_col=date_column_map["bonds_clients"], frequency='quarterly',source='bonds_clients'),}    
   elif timeperiod == 'Calender Year':
      cy_list = [(selected_calender_year - i) for i in range(3)]
      investment_data_calender_year={ "Vested": get_time_series_data(vested_clients,amount_col='Invested Amount',date_col=date_column_map["vested_clients"],frequency='calendar_year',source='vested_clients',cy_list=cy_list),
         "FD": get_time_series_data(FD_clients, amount_col='Investment Amount', date_col=date_column_map['fd_clients'],frequency='calendar_year', source='fd_clients',cy_list=cy_list),
         "Smallcase": get_time_series_data(smallcase_clients, amount_col='Networth',  date_col=date_column_map["smallcase_clients"], frequency='calendar_year',  source='smallcase_clients',cy_list=cy_list),
         "PMS": get_time_series_data(pms_clients, amount_col='Invested Amount', date_col=date_column_map["pms_clients"],frequency='calendar_year', source='pms_clients',cy_list=cy_list),
         "Bonds": get_time_series_data(bonds_clients, amount_col='Amount', date_col=date_column_map["bonds_clients"],frequency='calendar_year', source='bonds_clients',cy_list=cy_list)}
      investment_df_cy = pd.DataFrame(investment_data_calender_year).reset_index().melt(id_vars="Calendar_Year", var_name="Product", value_name="Invested Amount")
      investment_df_cy = investment_df_cy.fillna(0)
      investment_df_cy['Calendar_Year'] = pd.Categorical(investment_df_cy['Calendar_Year'], categories=cy_list[::-1], ordered=True)
      investment_df_cy = investment_df_cy.sort_values('Calendar_Year')    
      fig_cy = px.bar(investment_df_cy,x="Product",y="Invested Amount",color="Calendar_Year",barmode="group")
      fig_cy.update_layout(xaxis_title="Products",yaxis_title="Net Inflow",xaxis=dict(
         title_font=dict(size=12, family='sans serif', color='black'),
         tickfont=dict(size=12, family='sans serif', color='black')),yaxis=dict(tickformat=',.0f',
         title_font=dict(size=12, family='sans serif', color='black'),
         tickfont=dict(size=12, family='sans serif', color='black')))
      fig_cy.update_traces(hovertemplate="<b>Product:</b> %{x}<br><b>Amount:</b> %{y:,.0f}<extra></extra>",customdata=investment_df_cy[['Calendar_Year']])
      fig_cy.update_layout(showlegend=True)  # Ensure legend is shown
      fig_cy.update_traces(marker_line_width=1.3, marker_line_color="black",opacity=0.8)
      st.plotly_chart(fig_cy)   
   elif timeperiod == 'Financial Year':
    selected_index = fy_options.index(selected_financial_year)
    fy_list = fy_options[max(0, selected_index - 2):selected_index + 1]
    st.write(fy_list)
    investment_data_financial_year={
    "Vested": get_time_series_data(vested_clients,amount_col='Invested Amount',date_col=date_column_map["vested_clients"],frequency='financial_year',source='vested_clients',fy_list=fy_list),
    "FD": get_time_series_data(FD_clients, amount_col='Investment Amount', date_col=date_column_map['fd_clients'],
                               frequency='financial_year', source='fd_clients',fy_list=fy_list),
    "Smallcase": get_time_series_data(smallcase_clients, amount_col='Networth',
                                      date_col=date_column_map["smallcase_clients"], frequency='financial_year',
                                      source='smallcase_clients',fy_list=fy_list),
    "PMS": get_time_series_data(pms_clients, amount_col='Invested Amount', date_col=date_column_map["pms_clients"],
                                frequency='financial_year', source='pms_clients',fy_list=fy_list),
    "Bonds": get_time_series_data(bonds_clients, amount_col='Amount', date_col=date_column_map["bonds_clients"],
                                  frequency='financial_year', source='bonds_clients',fy_list=fy_list)}
    investment_df_fy = pd.DataFrame(investment_data_financial_year).reset_index().melt(
        id_vars="Financial_Year", var_name="Product", value_name="Invested Amount")
    investment_df_fy = investment_df_fy.fillna(0)
    investment_df_fy['Financial_Year'] = pd.Categorical(investment_df_fy['Financial_Year'], categories=fy_list[::-1],
                                                       ordered=True)
    investment_df_fy = investment_df_fy.sort_values('Financial_Year')
    st.dataframe(investment_df_fy)   
   elif timeperiod == 'Monthly':
     selected_date = pd.to_datetime(selected_month + '-01')
     three_months = [(selected_date - pd.DateOffset(months=i)).strftime('%B-%Y') for i in range(3)]
     investment_data = {   "Smallcase": get_time_series_data(smallcase_clients, amount_col='Networth', date_col=date_column_map["smallcase_clients"], frequency='monthly',month_list=three_months,source='smallcase_clients'),
     "Bonds": get_time_series_data(bonds_clients, amount_col='Amount',date_col= date_column_map["bonds_clients"], frequency='monthly',month_list=three_months, source='bonds_clients'),
     "PMS": get_time_series_data(pms_clients, amount_col='Invested Amount', date_col=date_column_map["pms_clients"],frequency='monthly',month_list=three_months, source='pms_clients'),
     "Vested": get_time_series_data(vested_clients, amount_col='Invested Amount', date_col=date_column_map["vested_clients"],frequency='monthly',month_list=three_months, source='vested_clients'),
     "FD": get_time_series_data(FD_clients, amount_col='Investment Amount',date_col= date_column_map['fd_clients'], frequency='monthly',month_list=three_months,source='fd_clients') }
     investment_df = pd.DataFrame(investment_data).reset_index().melt(id_vars="Year-Month", var_name="Product", value_name="Invested Amount")
     investment_df = investment_df.fillna(0)
     investment_df['Year-Month'] = pd.Categorical(investment_df['Year-Month'], categories=three_months[::-1], ordered=True)
     investment_df = investment_df.sort_values('Year-Month')
     fig = px.bar(investment_df, x=investment_df["Product"], y=investment_df["Invested Amount"], color="Year-Month", barmode="group")
     fig.update_layout( xaxis_title="Products", yaxis_title="Net Inflow", xaxis=dict(
        title_font=dict(size=12, family='sans serif', color='black'),
        tickfont=dict(size=12, family='sans serif', color='black') ), yaxis=dict( tickformat=',.0f', title_font=dict(size=12, family='sans serif', color='black'),
        tickfont=dict(size=12, family='sans serif', color='black')))
     fig.update_traces(  hovertemplate="<b>Product:</b> %{x}<br><b>Amount:</b> %{y}<extra></extra>")
     fig.update_layout(showlegend=True)
     fig.update_traces(marker_line_width=1.3, marker_line_color="black", opacity=0.8)
     st.plotly_chart(fig)
     data=investment_df[investment_df['Year-Month'] == selected_month]    
   def filter_smallcase_clients(smallcase_clients: pd.DataFrame, timeperiod, selected_month = None, selected_quarter_fy = None,selected_cy= None,selected_fy=None) -> pd.DataFrame:
    smallcase_active = smallcase_clients[ (smallcase_clients['Current Investment Status'] == 'invested') & (smallcase_clients['Subscription Status'] == 'subscribed')]
    smallcase_active['Subscription Start Date'] = pd.to_datetime(smallcase_active['Subscription Start Date'], errors='coerce')
    smallcase_active['Month-Year'] = smallcase_active['Subscription Start Date'].dt.strftime('%B-%Y')
    if timeperiod == 'Monthly':
        filtered_smallcase = smallcase_active[smallcase_active['Month-Year'] == selected_month]
    elif timeperiod == 'Quarterly':
        filtered_smallcase = smallcase_active[smallcase_active['Fiscal_Quarter'] == selected_quarter_fy]
    elif timeperiod =='Calender Year':
        filtered_smallcase = smallcase_active[smallcase_active['Calendar_Year'] == selected_cy]
    else:
        filtered_smallcase = smallcase_active[smallcase_active['Financial_Year'] == selected_fy]
    columns_to_select = ['Name', 'Networth', 'PAN', 'Smallcase Name','Subscription Start Date']
    filtered_df_smallcase = filtered_smallcase[columns_to_select].copy()
    filtered_df_smallcase['PAN'] = filtered_df_smallcase['PAN'].str.upper()
    filtered_df_smallcase['Name'] = filtered_df_smallcase['Name'].str.upper()
    filtered_df_smallcase['Smallcase Name'] = filtered_df_smallcase['Smallcase Name'].str.upper()
    filtered_df_smallcase = filtered_df_smallcase.rename(columns={'Name': 'NAME', 'Smallcase Name': 'SMALLCASE NAME','Networth': 'CURRENT VALUE'})
    return filtered_df_smallcase

   with st.container(border=True):
     col1,col2=st.columns(2)
     with col1:
      st.subheader("SMALLCASE")
      if timeperiod == 'Monthly':
         filtered_smallcase_df=filter_smallcase_clients(smallcase_clients,timeperiod=timeperiod,selected_month=selected_month)
      elif timeperiod == 'Quarterly':
         filtered_smallcase_df = filter_smallcase_clients(smallcase_clients,timeperiod= timeperiod, selected_quarter_fy=selected_quarter_fy)
      elif timeperiod == 'Calender Year':
          filtered_smallcase_df = filter_smallcase_clients(smallcase_clients, timeperiod=timeperiod,selected_cy=selected_calender_year)
      else:
          filtered_smallcase_df = filter_smallcase_clients(smallcase_clients, timeperiod=timeperiod, selected_fy=selected_financial_year)
      if len(filtered_smallcase_df) > 0:
         st.dataframe(filtered_smallcase_df, hide_index=True)
         with col2:
              st.metric("Total AUM",format_currency(sum(filtered_smallcase_df['CURRENT VALUE'])),border=True)
      else:
          st.write("No Transactions") 
   def filter_vested_clients(vested_clients: pd.DataFrame, timeperiod, selected_month = None, selected_quarter_fy = None,selected_cy=None,selected_fy=None) -> pd.DataFrame:
    if timeperiod == 'Monthly':
        filtered_df_vested = vested_clients[vested_clients['Year-Month'] == selected_month]
    elif timeperiod == 'Quarterly':
        filtered_df_vested = vested_clients[vested_clients['Fiscal_Quarter'] == selected_quarter_fy]
    elif timeperiod == 'Calender Year':
        filtered_df_vested = vested_clients[vested_clients['Calendar_Year'] == selected_cy]
    else:
        filtered_df_vested = vested_clients[vested_clients['Financial_Year'] == selected_fy]
    columns_to_select_vested = ['Name', 'Dwaccountno', 'Subscription', 'Invested Amount', 'Unrealized P&L']
    filtered_df_vested = filtered_df_vested[columns_to_select_vested].copy()
    filtered_df_vested['Unrealized P&L'] = filtered_df_vested['Unrealized P&L'].fillna(0)
    filtered_df_vested['Name'] = filtered_df_vested['Name'].str.upper()
    filtered_df_vested['Subscription'] = filtered_df_vested['Subscription'].str.upper()
    filtered_df_vested=filtered_df_vested.rename(columns={'Name':'NAME','Dwaccountno':'DWACCOUNTNO','Subscription':'SUBSCRIPTION','Invested Amount':'INVESTED AMOUNT','Unrealized P&L':'UNREALIZED P&L'})
    return filtered_df_vested
   with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("VESTED")
        if timeperiod == 'Monthly':
            filtered_vested_df = filter_vested_clients(vested_clients, timeperiod=timeperiod,
                                                             selected_month=selected_month)
        elif timeperiod =='Quarterly':
            filtered_vested_df = filter_vested_clients(vested_clients, timeperiod=timeperiod,
                                                             selected_quarter_fy=selected_quarter_fy)
        elif timeperiod =='Calender Year':
            filtered_vested_df = filter_vested_clients(vested_clients, timeperiod=timeperiod,selected_cy=selected_calender_year)
        else:
            filtered_vested_df = filter_vested_clients(vested_clients,timeperiod=timeperiod,selected_fy=selected_financial_year)
        if len(filtered_vested_df) > 0:
          st.dataframe(filtered_vested_df,hide_index=True)
          with col2:
            st.metric("Total AUM", format_currency(sum(filtered_vested_df['INVESTED AMOUNT'])), border=True)
        else:
           st.write("No Transactions")   
   def filter_pms_clients(pms_clients: pd.DataFrame, timeperiod, selected_month = None, selected_quarter_fy = None,selected_cy=None,selected_fy=None) -> pd.DataFrame:
    pms_clients['Date of Investment'] = pd.to_datetime(pms_clients['Date of Investment'],
                                                                 errors='coerce')
    if timeperiod == 'Monthly':
       pms_clients = pms_clients[pms_clients['Year-Month'] == selected_month]
    elif timeperiod == 'Quarterly':
       pms_clients = pms_clients[pms_clients['Fiscal_Quarter'] == selected_quarter_fy]
    elif timeperiod == 'Calender Year':
       pms_clients = pms_clients[pms_clients['Calendar_Year'] == selected_cy]
    else:
        pms_clients = pms_clients[pms_clients['Financial_Year'] == selected_fy]
    columns_to_select = ['Name', 'Invested Amount', 'PAN', 'Strategy']
    filtered_df_pms = pms_clients[columns_to_select]
    filtered_df_pms['Name'] =filtered_df_pms['Name'].str.upper()
    filtered_df_pms['PAN'] = filtered_df_pms['PAN'].str.upper()
    filtered_df_pms['Strategy'] = filtered_df_pms['Strategy'].str.upper()
    filtered_df_pms=filtered_df_pms.rename(columns={'Name':'NAME','Invested Amount':'INVESTED AMOUNT','Strategy':'STRATEGY'})
    return filtered_df_pms

   with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("PMS")
        if timeperiod == 'Monthly':
            filtered_pms_df = filter_pms_clients(pms_clients, timeperiod=timeperiod,
                                                       selected_month=selected_month)
        elif timeperiod == 'Quarterly':
            filtered_pms_df = filter_pms_clients(pms_clients, timeperiod=timeperiod,
                                                       selected_quarter_fy=selected_quarter_fy)
        elif timeperiod == 'Calender Year':
            filtered_pms_df = filter_pms_clients(pms_clients, timeperiod=timeperiod,selected_cy=selected_calender_year)
        else:
            filtered_pms_df = filter_pms_clients(pms_clients, timeperiod=timeperiod, selected_fy=selected_financial_year)
        if len(filtered_pms_df) > 0:
           st.dataframe(filtered_pms_df,hide_index=True)
           with col2:
               st.metric("Total AUM",format_currency(sum(filtered_pms_df['INVESTED AMOUNT'])), border=True)
        else:
            st.write("No Transactions")     

   def filter_bonds_clients(bonds_clients: pd.DataFrame, timeperiod, selected_month = None, selected_quarter_fy = None,selected_cy=None,selected_fy=None) -> pd.DataFrame:
    bonds_clients['Transaction Date'] = pd.to_datetime(bonds_clients['Transaction Date'], errors='coerce')
    bonds_clients['Month-Year'] = bonds_clients['Transaction Date'].dt.strftime('%B-%Y')
    if timeperiod == 'Monthly':
        filtered_bonds = bonds_clients[bonds_clients['Month-Year'] == selected_month]
    elif timeperiod == 'Quarterly':
        filtered_bonds = bonds_clients[bonds_clients['Fiscal_Quarter'] == selected_quarter_fy]
    elif timeperiod == 'Calender Year':
        filtered_bonds = bonds_clients[bonds_clients['Calendar_Year'] == selected_cy]
    else:
        filtered_bonds = bonds_clients[bonds_clients['Financial_Year'] == selected_fy]
    columns_to_select = ['Name', 'Amount', 'PAN', 'Issue Name', 'Type']
    filtered_df_bonds = filtered_bonds[columns_to_select]
    filtered_df_bonds['Name'] = filtered_df_bonds['Name'].str.upper()
    filtered_df_bonds['Issue Name'] = filtered_df_bonds['Issue Name'].str.upper()
    filtered_df_bonds['Type'] = filtered_df_bonds['Type'].str.upper()
    filtered_df_bonds['PAN'] = filtered_df_bonds['PAN'].str.upper()
    filtered_df_bonds=filtered_df_bonds.rename(columns={'Name':'NAME', 'Amount':'INVESTED AMOUNT','Issue Name':'ISSUE NAME','Type':'TYPE'})
    return filtered_df_bonds   
   with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("BONDS")
        if timeperiod == 'Monthly':
            filtered_bonds_df = filter_bonds_clients(bonds_clients, timeperiod=timeperiod,
                                                       selected_month=selected_month)
        elif timeperiod == 'Quarterly':
            filtered_bonds_df = filter_bonds_clients(bonds_clients, timeperiod=timeperiod,
                                                       selected_quarter_fy=selected_quarter_fy)
        elif timeperiod == 'Calender Year':
           filtered_bonds_df = filter_bonds_clients(bonds_clients, timeperiod=timeperiod,selected_cy=selected_calender_year)
        else:
            filtered_bonds_df = filter_bonds_clients(bonds_clients, timeperiod=timeperiod,selected_fy=selected_financial_year)
        if len(filtered_bonds_df) > 0:
           st.dataframe(filtered_bonds_df,hide_index=True)
           with col2:
               st.metric("Total AUM",format_currency(sum(filtered_bonds_df['INVESTED AMOUNT'])), border=True)
        else:
            st.write("No Transactions")   
   def filter_fd_clients(FD_clients: pd.DataFrame, timeperiod, selected_month = None, selected_quarter_fy = None,selected_cy=None,selected_fy=None) -> pd.DataFrame:
    FD_clients['Month-Year'] = FD_clients['Issue Date'].dt.strftime('%B-%Y')
    if timeperiod == 'Monthly':
        filtered_FD = FD_clients[FD_clients['Month-Year'] == selected_month]
    elif timeperiod =='Quarterly':
        filtered_FD = FD_clients[FD_clients['Fiscal_Quarter'] == selected_quarter_fy]
    elif timeperiod == 'Calender Year':
        filtered_FD = FD_clients[FD_clients['Calendar_Year'] == selected_cy]
    else:
        filtered_FD = FD_clients[FD_clients['Financial_Year'] == selected_fy]
    columns_to_select = ['Customer Name', 'Issue Date', 'Investment Amount', 'Channel Partner']
    filtered_df_fd = filtered_FD[columns_to_select]
    filtered_df_fd['Customer Name'] = filtered_df_fd['Customer Name'].str.upper()
    filtered_df_fd['Channel Partner'] = filtered_df_fd['Channel Partner'].str.upper()
    filtered_df_fd = filtered_df_fd.rename({'Name':'NAME','Issue Date':'ISSUE DATE','Investment Amount':'INVESTED AMOUNT', 'Channel Partner':'CHANNEL PARTNER'})
    st.dataframe(filtered_df_fd)
    return filtered_df_fd    
   with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("FD")
        if timeperiod == 'Monthly':
            filtered_fd_df = filter_fd_clients(FD_clients, timeperiod=timeperiod,
                                                       selected_month=selected_month)
        elif timeperiod == 'Quarterly':
            filtered_fd_df = filter_fd_clients(FD_clients, timeperiod=timeperiod,
                                                       selected_quarter_fy=selected_quarter_fy)
        elif timeperiod == 'Calender Year':
            filtered_fd_df = filter_fd_clients(FD_clients, timeperiod=timeperiod,selected_cy=selected_calender_year)
        else :
            filtered_fd_df = filter_fd_clients(FD_clients, timeperiod=timeperiod, selected_fy=selected_financial_year)
        if len(filtered_fd_df) > 0:
           st.dataframe(filtered_fd_df,hide_index=True)
           with col2:
               st.metric("Total AUM",format_currency(sum(filtered_fd_df['INVESTED AMOUNT'])), border=True)
        else:
            st.write("No Transactions")
    
   rm_name = RM_name    
   if st.button("Generate Simple PDF Report"):
        with st.spinner("Generating..."):
            # Create a dedicated output path for the PDF
            output_filename = f"Investment_Report_{rm_name.replace(' ', '_')}_{selected_month.replace(' ', '_')}.pdf"
            temp_path = os.path.join(tempfile.gettempdir(), output_filename)
            
            pdf_path = create_simple_investment_report(
                rm_name,
                selected_month,
                investment_df,
                filtered_smallcase_df,
                filtered_vested_df,
                filtered_pms_df,
                filtered_bonds_df,
                filtered_fd_df,
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
    page = st.sidebar.radio("Go to", ["Smallcase", "Fractional Real Estate","Banking Products", "Bonds","Liquiloans","PMS","Vested","FD","AIF","MIS Report"])
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
    elif page == "Banking Products":
        BANK_Analysis(display=True)
    elif page =="MIS Report":
        Geenrate_MIS_Report()

