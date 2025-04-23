import pandas as pd
import streamlit as st
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)



def format_currency(value):
    if abs(value) >= 10000000:
        return f'{value / 10000000:.2f} Crs'
    elif abs(value) >= 100000:
        return f"{value / 100000:.2f} L"
    elif abs(value) >= 1000:
        return f"{value / 1000:.2f} K"
    else:
        return f"{value:.2f}"

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import tempfile
import os

def create_simple_investment_report(
            rm_name, selected_month, investment_df,
            smallcase_clients, vested_clients, pms_clients, bonds_clients,FD_clients,output_path=None):
        """Create a simple investment report using ReportLab instead of FPDF"""

        def draw_border(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(2)
            margin = 20
            canvas.rect(margin, margin, doc.width + doc.leftMargin + doc.rightMargin - 2 * margin,
                        doc.height + doc.topMargin + doc.bottomMargin - 2 * margin)
            canvas.restoreState()

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                filename = f"Investment_Report_{rm_name.replace(' ', '_')}_{selected_month.replace(' ', '_')}.pdf"
                output_path = os.path.join(temp_dir, filename)

                doc = SimpleDocTemplate(output_path, pagesize=letter, topMargin=20)
                elements = []
                styles = getSampleStyleSheet()
                title_style = styles['Heading1']
                subtitle_style = styles['Heading2']
                normal_style = styles['Normal']

                # Company Logo (ensure you have the logo image in your working directory)
                logo_path = "Armstrong_logo.png"  # Change path if your logo is in a different location
                if os.path.exists(logo_path):
                    logo = Image(logo_path, width= 7.8 * inch, height=1 * inch)
                    elements.append(logo)
                    elements.append(Spacer(1, 12))
                else:
                    elements.append(Paragraph("Company Logo Missing", normal_style))

                # Report Header
                elements.append(Paragraph("Investment Portfolio Report", title_style))
                elements.append(Paragraph(f"RM: {rm_name} | Month: {selected_month}", subtitle_style))
                elements.append(Spacer(1, 12))

                # Bar Chart
                try:
                    month_data = investment_df[investment_df["Year-Month"] == selected_month]
                    plt.figure(figsize=(8, 4))
                    ax = plt.gca()
                    ax.grid(False)

                    bars = plt.bar(month_data["Product"], month_data["Invested Amount"], width=0.5)
                    plt.xlabel("Products")
                    plt.ylabel("Net Inflow")

                    ylabels = [format_currency(i) for i in ax.get_yticks()]
                    ax.set_yticklabels(ylabels)

                    for bar in bars:
                        yval = bar.get_height()
                        plt.text(bar.get_x() + bar.get_width() / 2, yval + 0.1 * max(month_data["Invested Amount"]),
                                 format_currency(yval), ha='center', va='bottom')

                    plt.tight_layout()
                    chart_path = os.path.join(temp_dir, "chart.png")
                    plt.savefig(chart_path)
                    plt.close()

                    elements.append(Paragraph("Monthly Investment Summary", subtitle_style))
                    elements.append(Spacer(1, 6))
                    elements.append(Image(chart_path, width=400, height=200))
                    elements.append(Spacer(1, 12))

                except Exception as e:
                    elements.append(Paragraph(f"Chart Error: {e}", normal_style))

                # Table rendering function
                def add_table(title, df, columns):
                    elements.append(Paragraph(title, subtitle_style))
                    elements.append(Spacer(1, 6))

                    if df.empty:
                        elements.append(Paragraph("No Transactions", normal_style))
                    else:
                        data = [columns] + df[columns].values.tolist()
                        table = Table(data)
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ]))
                        elements.append(table)

                    elements.append(Spacer(1, 12))

                # Add product-wise tables
                add_table("Smallcase", smallcase_clients, ['Name', 'Invested Amount','PAN','Smallcase Name'])
                add_table("Vested", vested_clients, ['Dwaccountno', 'Invested Amount'])
                add_table("PMS", pms_clients, ['Name', 'Invested Amount', 'Strategy'])
                add_table("FD",FD_clients,['Name','Issue Date','Investment Amount','Channel Partner'])
                add_table("Bonds", bonds_clients, ['Name', 'Invested Amount','PAN', 'Issue Name', 'Type'])

                # Build PDF with page border
                doc.build(elements, onFirstPage=draw_border, onLaterPages=draw_border)

        except Exception as e:
           st.error(f"Error creating PDF report: {e}")
        return output_path
