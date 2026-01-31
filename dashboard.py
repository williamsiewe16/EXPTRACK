import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime, timedelta
import calendar
import dotenv
import os
import json

# Load environment variables
dotenv.load_dotenv()

# Page config
st.set_page_config(
    page_title="Expense Tracker Dashboard",
    page_icon="💰",
    layout="wide"
)

# Configuration
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
BIGQUERY_DATASET = 'expense_tracker'
BIGQUERY_TABLE = 'expenses'

BANKS = ['BNP', 'Boursorama', 'Hello Bank', 'Wise', 'Revolut']

# Initialize BigQuery client
@st.cache_resource
def get_bigquery_client():
    try:
        if os.getenv("ENVIRONMENT") == "PROD":
            print("Environnement PROD détecté, configuration des identifiants GCP.")
            # récupérer la clé stockée dans les secrets
            key_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

            # créer un fichier temporaire pour le SDK
            key_file = "/tmp/sa_key.json"
            with open(key_file, "w") as f:
                f.write(key_json)
            
            credentials = service_account.Credentials.from_service_account_file(key_file)
    
            print(key_json)
            print("Identifiants GCP configurés.")
            return bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)  
        else:
            print("Environnement DEV détecté, ")
            credentials = service_account.Credentials.from_service_account_file(
                'gcp-credentials.json'
            )
            return bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)  
    except:
        print("Erreur lors de la configuration des identifiants GCP.")

bq_client = get_bigquery_client()


@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_expenses(start_date, end_date, user_filter=None):
    """Load expenses from BigQuery"""
    query = f"""
    SELECT 
        date,
        timestamp,
        amount,
        bank_emission,
        bank_associated,
        comment,
        user_id
    FROM `{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
    WHERE date BETWEEN @start_date AND @end_date
    """
    
    if user_filter:
        query += " AND user_id = @user_id"
    
    query += " ORDER BY timestamp DESC"
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        ]
    )
    
    if user_filter:
        job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("user_id", "STRING", user_filter)
        )
    
    df = bq_client.query(query, job_config=job_config).to_dataframe()
    return df


def get_monthly_budget():
    """Get monthly budget limits for each bank/category"""
    # This will be stored in session state and can be edited
    if 'budgets' not in st.session_state:
        st.session_state.budgets = {
            'BNP': 100,
            'Boursorama': 100,
            'Hello Bank': 180,
            'Wise': 490,
            'Revolut': 28.5,
            'Ticket Restaurant': 190
        }
    return st.session_state.budgets

def main():
    st.title("💰 Expense Tracker Dashboard")
    st.markdown("---")
    
    # Sidebar for filters and budgets
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Date filter
        st.subheader("📅 Période")
        date_option = st.radio(
            "Sélectionner:",
            ["Mois en cours", "Mois dernier", "Personnalisé"]
        )
        
        today = datetime.now().date()
        
        if date_option == "Mois en cours":
            start_date = today.replace(day=1)
            end_date = today
        elif date_option == "Mois dernier":
            first_day_current = today.replace(day=1)
            last_day_previous = first_day_current - timedelta(days=1)
            start_date = last_day_previous.replace(day=1)
            end_date = last_day_previous
        else:
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Du", value=today.replace(day=1))
            with col2:
                end_date = st.date_input("Au", value=today)
        
        st.markdown("---")
        
        # Budget settings
        st.subheader("🎯 Seuils mensuels")
        budgets = get_monthly_budget()
        
        for bank in BANKS:
            budgets[bank] = st.number_input(
                f"{bank}",
                min_value=0.0,
                value=float(budgets[bank]),
                step=50.0,
                key=f"budget_{bank}"
            )
        
        if st.button("💾 Sauvegarder les seuils"):
            st.session_state.budgets = budgets
            st.success("Seuils sauvegardés !")
        
        st.markdown("---")
        st.info("🔄 Les données se rafraîchissent automatiquement toutes les 60 secondes")
    
    # Load data
    try:
        df = load_expenses(start_date, end_date)
        
        if df.empty:
            st.warning("Aucune dépense enregistrée pour cette période.")
            return
        
        # Summary metrics
        st.header("📊 Vue d'ensemble")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_expenses = df['amount'].sum()
            st.metric("Total dépenses", f"{total_expenses:.2f} €")
        
        with col2:
            num_transactions = len(df)
            st.metric("Nombre de transactions", num_transactions)
        
        with col3:
            avg_expense = df['amount'].mean()
            st.metric("Dépense moyenne", f"{avg_expense:.2f} €")
        
        st.markdown("---")
        
        # By category (bank_associated)
        st.header("💳 Dépenses par catégorie")
        
        category_summary = df.groupby('bank_associated')['amount'].sum().reset_index()
        category_summary = category_summary.sort_values('amount', ascending=False)
        
        # Create columns for each category
        cols = st.columns(len(BANKS))
        
        for idx, bank in enumerate(BANKS):
            with cols[idx]:
                spent = category_summary[category_summary['bank_associated'] == bank]['amount'].sum()
                budget = budgets[bank]
                
                # Calculate progress
                if budget > 0:
                    progress = (spent / budget) * 100
                    remaining = budget - spent
                    
                    # Color coding
                    if progress >= 100:
                        color = "🔴"
                        status = "Dépassé"
                    elif progress >= 80:
                        color = "🟠"
                        status = "Attention"
                    else:
                        color = "🟢"
                        status = "OK"
                    
                    st.metric(
                        f"{color} {bank}",
                        f"{spent:.2f} €",
                        f"{remaining:.2f} € restant"
                    )
                    st.progress(min(progress / 100, 1.0))
                    st.caption(f"Budget: {budget:.2f} € ({progress:.1f}%)")
                else:
                    st.metric(f"💰 {bank}", f"{spent:.2f} €")
                    st.caption("Pas de seuil défini")
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Répartition par catégorie")
            fig_pie = px.pie(
                category_summary,
                values='amount',
                names='bank_associated',
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            st.subheader("💳 Cartes utilisées")
            emission_summary = df.groupby('bank_emission')['amount'].sum().reset_index()
            fig_bar = px.bar(
                emission_summary,
                x='bank_emission',
                y='amount',
                color='bank_emission',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_bar.update_layout(showlegend=False, xaxis_title="", yaxis_title="Montant (€)")
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Daily expenses trend
        st.subheader("📈 Évolution quotidienne")
        daily_expenses = df.groupby('date')['amount'].sum().reset_index()
        daily_expenses = daily_expenses.sort_values('date')
        
        fig_line = px.line(
            daily_expenses,
            x='date',
            y='amount',
            markers=True,
            line_shape='spline'
        )
        fig_line.update_layout(xaxis_title="Date", yaxis_title="Montant (€)")
        fig_line.update_traces(line_color='#667eea', marker=dict(size=8))
        st.plotly_chart(fig_line, use_container_width=True)
        
        st.markdown("---")
        
        # Budget vs Actual comparison
        st.subheader("🎯 Budget vs Réel")
        
        budget_comparison = []
        for bank in BANKS:
            spent = category_summary[category_summary['bank_associated'] == bank]['amount'].sum()
            budget = budgets[bank]
            budget_comparison.append({
                'Catégorie': bank,
                'Budget': budget,
                'Dépensé': spent,
                'Écart': budget - spent
            })
        
        budget_df = pd.DataFrame(budget_comparison)
        
        fig_budget = go.Figure()
        
        fig_budget.add_trace(go.Bar(
            name='Budget',
            x=budget_df['Catégorie'],
            y=budget_df['Budget'],
            marker_color='lightblue'
        ))
        
        fig_budget.add_trace(go.Bar(
            name='Dépensé',
            x=budget_df['Catégorie'],
            y=budget_df['Dépensé'],
            marker_color='coral'
        ))
        
        fig_budget.update_layout(barmode='group', xaxis_title="", yaxis_title="Montant (€)")
        st.plotly_chart(fig_budget, use_container_width=True)
        
        st.markdown("---")
        
        # Recent transactions
        st.subheader("📝 Dernières transactions")
        
        recent_df = df.head(20)[['date', 'amount', 'bank_emission', 'bank_associated', 'comment']].copy()
        recent_df.columns = ['Date', 'Montant (€)', 'Carte', 'Catégorie', 'Commentaire']
        
        st.dataframe(
            recent_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download data
        st.markdown("---")
        st.subheader("💾 Export des données")
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger CSV",
            data=csv,
            file_name=f'expenses_{start_date}_{end_date}.csv',
            mime='text/csv',
        )
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des données: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    #print(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    #print(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    main()