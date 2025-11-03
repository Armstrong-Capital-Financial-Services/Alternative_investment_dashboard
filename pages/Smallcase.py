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
      st.metric("Total AUM", format_currency(active_clients['Networth'].sum().round(2)),
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
  #filtered_data = new_clients_networth_monthly[new_clients_networth_monthly['Total New Client Networth'] != 0]
  #filtered_data = filtered_data.sort_values(by='Month')
  #filtered_data['Month'] = filtered_data['Month'].dt.strftime('%B-%Y')
  #filtered_data['Monthonly'] = filtered_data['Month'].str.split('-').str[0]
  #filtered_data['Year'] = filtered_data['Month'].str.split('-').str[1]
  #ith st.container(border=True):
   #st.subheader("Monthly AUM Inflow")
   #timeperiod = st.toggle("Custom Time Period",key="AUM INFLOW MONTHLY")
   #if timeperiod:
      #month_order = ['January', 'February', 'March', 'April', 'May', 'June',
      #               'July', 'August', 'September', 'October', 'November', 'December']
      #available_years = sorted(filtered_data['Month'].str.split('-').str[1].unique())
      #available_months = sorted(filtered_data['Month'].str.split('-').str[0].unique(),
      #                          key=lambda x: month_order.index(x))
      #col1, col2, col3 = st.columns(3)

      #with col1:
      #    start_month = st.selectbox("Start Month", available_months,
      #                               index=0,  # Default to first month
      #                               key="start_month")
      #with col2:
      #    end_month_options = available_months[available_months.index(start_month):]
      #    selected_end_month = st.selectbox("End Month", end_month_options,
      #                                      index=len(end_month_options) - 1,  # Default to last available month
      #                                      key="end_month")
      #with col3:
          #selected_year = st.selectbox("Select Year", available_years)

      #def filter_data(df, year, start_month, end_month):
          #month_order_dict = {month: index for index, month in enumerate(month_order)}
          #year_filtered = df[df['Year'] == year]
          #year_filtered['MonthOnly'] = year_filtered['Month'].str.split('-').str[0]
          #month_filtered = year_filtered[
          #    (year_filtered['MonthOnly'].map(month_order_dict) >= month_order_dict[start_month]) &
          #    (year_filtered['MonthOnly'].map(month_order_dict) <= month_order_dict[selected_end_month])
          #    ]
          #month_filtered = month_filtered.sort_values(by='MonthOnly', key=lambda x: x.map(month_order_dict))
          #return month_filtered

      #filtered_data = filter_data(filtered_data, selected_year, start_month, selected_end_month)
      #if not filtered_data.empty:
         #num_data_points = len(filtered_data)
         #bar_width = max(0.1, min(0.8, 2.5 / num_data_points))
         #fig = go.Figure(data=[go.Bar( x=filtered_data['MonthOnly'].astype(str), y=filtered_data['Total New Client Networth'],
         #text=filtered_data['Total New Client Networth'].apply(format_currency),width=bar_width)])
         #fig.update_layout( xaxis_title="Month", yaxis_title="Total  Networth", yaxis_tickformat=',.0f',xaxis=dict(
         #    title_font=dict(size=12, family='sans serif', color='black'),
         #    tickfont=dict(size=12, family='sans serif', color='black')),
         #                  yaxis=dict(
         #                      title_font=dict(size=12, family='sans serif', color='black', ),
         #                      tickfont=dict(size=12, family='sans serif', color='black', )))
         #fig.update_traces(width=0.5, textposition='outside', textfont=dict(
         #    family="sans serif",
         #    size=12,
         #    color='black',weight='bold' ))
         #st.plotly_chart(fig)
   #else:
       #fig = go.Figure(data=[go.Bar(x=filtered_data['Month'].astype(str), y=filtered_data['Total New Client Networth'],

       #                             text=filtered_data['Total New Client Networth'].apply(format_currency), )])

       #fig.update_layout(xaxis_title="Month", yaxis_title="Total Networth", yaxis_tickformat=',.0f',xaxis=dict(
       #      title_font=dict(size=12, family='sans serif', color='black'),
       #      tickfont=dict(size=12, family='sans serif', color='black')),
       #                    yaxis=dict(
       #                        title_font=dict(size=12, family='sans serif', color='black', ),
       #                        tickfont=dict(size=12, family='sans serif', color='black', )))
       #fig.update_traces(width=0.5, textposition='outside', textfont=dict(
        #   family="sans serif",
        #   size=12,
        #   color='black',weight='bold' ))

       #st.subheader("Monthly AUM Inflow")
       #st.plotly_chart(fig)

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
              hovertemplate='<b>Month</b>: %{x}<br><b>Cumulative AUM</b>: %{y:,.2f}<extra></extra>',
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
        opt = st.selectbox("Select type of filter", options=['Monthly Addition of New Clients', 'Top Investors','Active Clients','Exited Clients','Subscriptions near expiry'])
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
            active_clients['Subscription Start Date'] = pd.to_datetime(active_clients['Subscription Start Date'],format='mixed').dt.date
            active_clients['Subscription End Date'] = pd.to_datetime(active_clients['Subscription End Date'], format='mixed').dt.date
            if smallcase_sel:
                st.dataframe(active_clients[active_clients['Smallcase Name']==smallcase_sel].iloc[:,:-4],hide_index=True)
            else:
                st.dataframe(active_clients.iloc[:, :-4],hide_index=True)
        elif opt == 'Exited Clients':
            existed_clients['Subscription Start Date'] = pd.to_datetime(existed_clients['Subscription Start Date'],format='mixed').dt.date
            existed_clients['Subscription End Date'] = pd.to_datetime(existed_clients['Subscription End Date'], format='mixed').dt.date
            st.dataframe(existed_clients.iloc[:, :-4],hide_index=True)

        elif opt == 'Subscriptions near expiry':
            today = datetime.date.today()
            one_month_from_today = today + datetime.timedelta(days=30)

            active_clients['Subscription Start Date'] = pd.to_datetime(active_clients['Subscription Start Date'],format='mixed').dt.date

            active_clients['Subscription End Date'] = pd.to_datetime(active_clients['Subscription End Date'], format='mixed').dt.date
            near_maturity_df = active_clients[
                (active_clients['Subscription End Date'] >= today) & (active_clients['Subscription End Date'] <= one_month_from_today)]
            near_maturity_df = near_maturity_df.iloc[:, :-2]
            st.dataframe(near_maturity_df, hide_index=True)

SMALLCASE_Analysis(display=True)
