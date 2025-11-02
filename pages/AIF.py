def AIF_Analysis(display=True):
  with psycopg2.connect(**db_config) as connection:
       aif_df=fetch_table_data(connection=connection,table_name="AIF")
  if display:
    col0,col1=st.columns(2)
    with col0:
      st.metric("Total Active Clients",len(aif_df),border=True)

    with col1:
      st.metric("Total AUM",aif_df['Current Value'].sum(),border=True)
