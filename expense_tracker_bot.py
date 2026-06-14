import os
import json
import logging
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import openai
from google.cloud import bigquery
from google.oauth2 import service_account

# Load environment variables
load_dotenv()

# Configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
BIGQUERY_DATASET = 'expense_tracker'
BIGQUERY_TABLE = 'expenses'

BANKS = ['BNP', 'Boursorama', 'Hello Bank', 'Wise', 'Revolut', 'Ticket Restaurant']

# Initialize clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)


# BigQuery client - credentials loading strategy:
# 1. GCP_CREDENTIALS_JSON env var (raw JSON content) -> for cloud deployment (Render, etc.)
# 2. gcp-credentials.json file -> for local development
# 3. Application Default Credentials -> fallback (GCP environments)
def get_bigquery_client():
    # Option 1: JSON content stored in an environment variable (cloud deployment)
    creds_json = os.getenv('GCP_CREDENTIALS_JSON')
    if creds_json:
        try:
            creds_info = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(creds_info)
            logger.info("BigQuery: using credentials from GCP_CREDENTIALS_JSON env var")
            return bigquery.Client(credentials=credentials, project=GCP_PROJECT_ID)
        except Exception as e:
            logger.error(f"Failed to load GCP_CREDENTIALS_JSON: {e}")
    else:
        logger.warning("GCP_CREDENTIALS_JSON env var is not set or empty")

    # Option 2: local JSON file
    if os.path.exists('gcp-credentials.json'):
        credentials = service_account.Credentials.from_service_account_file(
            'gcp-credentials.json'
        )
        logger.info("BigQuery: using credentials from gcp-credentials.json file")
        return bigquery.Client(credentials=credentials, project=GCP_PROJECT_ID)

    # Option 3: Application Default Credentials
    logger.info("BigQuery: using Application Default Credentials")
    return bigquery.Client(project=GCP_PROJECT_ID)


bq_client = get_bigquery_client()


def init_bigquery():
    """Initialize BigQuery dataset and table if they don't exist"""
    dataset_id = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}"
    
    # Create dataset if not exists
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "EU"
    try:
        bq_client.create_dataset(dataset, exists_ok=True)
        logger.info(f"Dataset {dataset_id} created or already exists")
    except Exception as e:
        logger.error(f"Error creating dataset: {e}")
    
    # Create table if not exists
    table_id = f"{dataset_id}.{BIGQUERY_TABLE}"
    schema = [
        bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("amount", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("bank_emission", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("bank_associated", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("comment", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
    ]
    
    table = bigquery.Table(table_id, schema=schema)
    try:
        bq_client.create_table(table, exists_ok=True)
        logger.info(f"Table {table_id} created or already exists")
    except Exception as e:
        logger.error(f"Error creating table: {e}")


def transcribe_audio(audio_file_path: str) -> str:
    """Transcribe audio using OpenAI Whisper API"""
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="fr"
            )
        return transcript.text
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return None


def extract_expense_info(transcription: str) -> dict:
    """Extract expense information from transcription using ChatGPT"""
    prompt = f"""Tu es un assistant qui extrait les informations de dépenses depuis une transcription audio.

Transcription: "{transcription}"

Extrait les informations suivantes:
- Date de la dépense (format YYYY-MM-DD): si mentionnée dans la transcription (ex: "hier", "lundi dernier", "le 15 janvier"), sinon null
- Montant (en euros, nombre décimal)
- Banque d'émission (la carte utilisée): doit être une parmi: {', '.join(BANKS)}
- Banque associée (la catégorie de dépense): doit être une parmi: {', '.join(BANKS)}
- Commentaire (description de la dépense)

L'audio est sous la forme:
"[Date optionnelle] J'ai dépensé [montant] euros avec [banque émission], dépense associée à [banque catégorie] pour [commentaire]"
Exemples:
• "J'ai dépensé 15 euros avec Boursorama, dépense associée à BNP pour kebab"
• "Hier j'ai dépensé 50 euros avec Wise, dépense associée à Revolut pour restaurant"
• "Le 28 janvier j'ai dépensé 30 euros avec Hello Bank, dépense associée à BNP pour courses"

IMPORTANT: Si une seule banque est mentionnée dans la transcription, utilise-la pour BOTH bank_emission ET bank_associated.

Date du jour pour référence: {datetime.now().strftime('%Y-%m-%d')} ({datetime.now().strftime('%A %d %B %Y')})

Réponds UNIQUEMENT avec un JSON valide dans ce format exact:
{{
    "date": "2025-01-30",
    "amount": 15.50,
    "bank_emission": "Boursorama",
    "bank_associated": "BNP",
    "comment": "kebab"
}}

Si la date n'est pas mentionnée, mets null pour date.
Si une autre information est manquante ou ambiguë, mets null pour cette valeur.
N'ajoute AUCUN texte avant ou après le JSON."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Plus économique que gpt-4
            messages=[
                {"role": "system", "content": "Tu es un assistant qui extrait des informations structurées de transcriptions. Tu réponds uniquement en JSON valide."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        expense_data = json.loads(response_text)
        print(expense_data)
        
        # Smart fallback: if only one bank is provided, use it for both fields
        bank_emission = expense_data.get('bank_emission')
        bank_associated = expense_data.get('bank_associated')
        
        if bank_emission and not bank_associated:
            expense_data['bank_associated'] = bank_emission
            logger.info(f"Only bank_emission provided, using it for bank_associated too: {bank_emission}")
        elif bank_associated and not bank_emission:
            expense_data['bank_emission'] = bank_associated
            logger.info(f"Only bank_associated provided, using it for bank_emission too: {bank_associated}")
        
        return expense_data
    except Exception as e:
        logger.error(f"Error extracting expense info: {e}")
        return None


def save_to_bigquery(user_id: str, expense_data: dict) -> bool:
    """Save expense to BigQuery"""
    try:
        table_id = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"
        
        now = datetime.now()
        
        # Use extracted date if provided, otherwise use today's date
        if expense_data.get('date'):
            try:
                expense_date = datetime.strptime(expense_data['date'], '%Y-%m-%d').date()
            except:
                # If date parsing fails, use today
                expense_date = now.date()
        else:
            expense_date = now.date()
        
        row = {
            "date": expense_date.isoformat(),
            "timestamp": now.isoformat(),
            "amount": float(expense_data['amount']),
            "bank_emission": expense_data['bank_emission'],
            "bank_associated": expense_data['bank_associated'],
            "comment": expense_data.get('comment', ''),
            "user_id": str(user_id),
        }
        
        errors = bq_client.insert_rows_json(table_id, [row])
        
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
            return False
        
        logger.info(f"Expense saved to BigQuery: {row}")
        return True
    except Exception as e:
        logger.error(f"Error saving to BigQuery: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_message = """🎯 **Expense Tracker Bot**

Bienvenue ! Envoie-moi une note vocale avec ta dépense et je m'occupe du reste.

**Format attendu:**
"[Date optionnelle] J'ai dépensé [montant] euros avec [banque émission], dépense associée à [banque catégorie] pour [commentaire]"

**Exemples:**
• "J'ai dépensé 15 euros avec Boursorama, dépense associée à BNP pour kebab"
• "Hier j'ai dépensé 50 euros avec Wise, dépense associée à Revolut pour restaurant"
• "Le 28 janvier j'ai dépensé 30 euros avec Hello Bank, dépense associée à BNP pour courses"

**Banques disponibles:**
• BNP
• Boursorama
• Hello Bank
• Wise
• Revolut
• Ticket Restaurant

**Commandes:**
/start - Afficher ce message
/stats - Voir tes statistiques du mois
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages"""
    user_id = update.effective_user.id
    
    # Send processing message
    processing_msg = await update.message.reply_text("🎧 Transcription en cours...")
    
    voice_path = None
    try:
        # Download voice file to temporary directory
        voice_file = await update.message.voice.get_file()
        
        # Create temp file with proper extension
        temp_fd, voice_path = tempfile.mkstemp(suffix='.ogg', prefix=f'voice_{user_id}_')
        os.close(temp_fd)  # Close the file descriptor, we'll use the path
        
        await voice_file.download_to_drive(voice_path)
        
        # Transcribe
        await processing_msg.edit_text("🎧 Transcription terminée, extraction des infos...")
        transcription = transcribe_audio(voice_path)
        
        if not transcription:
            await processing_msg.edit_text("❌ Erreur lors de la transcription. Réessaye.")
            return
        
        # Extract expense info
        expense_data = extract_expense_info(transcription)
        
        if not expense_data:
            await processing_msg.edit_text("❌ Impossible d'extraire les informations. Réessaye.")
            return
        
        # Check if all required fields are present
        missing_fields = []
        if not expense_data.get('amount'):
            missing_fields.append('montant')
        if not expense_data.get('bank_emission'):
            missing_fields.append('banque émission')
        if not expense_data.get('bank_associated'):
            missing_fields.append('banque associée')
        
        if missing_fields:
            await processing_msg.edit_text(
                f"❌ Informations manquantes: {', '.join(missing_fields)}\n\n"
                f"Transcription: \"{transcription}\"\n\n"
                "Réessaye en étant plus précis."
            )
            return
        
        # Store in context for confirmation
        context.user_data['pending_expense'] = expense_data
        context.user_data['transcription'] = transcription
        
        # Create confirmation message
        confirmation_text = f"""✅ **Informations extraites:**

📅 **Date:** {expense_data.get('date') or 'Aujourd\'hui (non précisée)'}
💰 **Montant:** {expense_data['amount']}€
💳 **Carte utilisée:** {expense_data['bank_emission']}
🏦 **Catégorie:** {expense_data['bank_associated']}
📝 **Commentaire:** {expense_data.get('comment', 'N/A')}

📝 *Transcription:* "{transcription}"

Confirmes-tu ces informations ?"""
        
        # Create confirmation buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmer", callback_data="confirm"),
                InlineKeyboardButton("❌ Annuler", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await processing_msg.edit_text(f"❌ Erreur: {str(e)}")
    
    finally:
        # Clean up voice file
        if voice_path and os.path.exists(voice_path):
            try:
                os.remove(voice_path)
                logger.info(f"Cleaned up voice file: {voice_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up voice file: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "confirm":
        expense_data = context.user_data.get('pending_expense')
        
        if not expense_data:
            await query.edit_message_text("❌ Aucune dépense en attente.")
            return
        
        # Save to BigQuery
        success = save_to_bigquery(user_id, expense_data)
        
        if success:
            # Determine which date was used
            if expense_data.get('date'):
                date_msg = f"📅 {expense_data['date']}"
            else:
                date_msg = f"📅 {datetime.now().strftime('%Y-%m-%d')} (aujourd'hui)"
            
            await query.edit_message_text(
                f"✅ **Dépense enregistrée !**\n\n"
                f"{date_msg}\n"
                f"💰 {expense_data['amount']}€ - {expense_data['bank_emission']} → {expense_data['bank_associated']}\n"
                f"📝 {expense_data.get('comment', 'N/A')}",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Erreur lors de l'enregistrement. Réessaye.")
        
        # Clear pending data
        context.user_data.pop('pending_expense', None)
        context.user_data.pop('transcription', None)
        
    elif query.data == "cancel":
        await query.edit_message_text("❌ Dépense annulée.")
        context.user_data.pop('pending_expense', None)
        context.user_data.pop('transcription', None)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show monthly statistics"""
    user_id = update.effective_user.id
    
    try:
        # Query BigQuery for current month stats
        query = f"""
        SELECT 
            bank_associated,
            SUM(amount) as total
        FROM `{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE user_id = '{user_id}'
            AND DATE_TRUNC(date, MONTH) = DATE_TRUNC(CURRENT_DATE(), MONTH)
        GROUP BY bank_associated
        ORDER BY total DESC
        """
        
        query_job = bq_client.query(query)
        results = query_job.result()
        
        stats_text = "📊 **Dépenses du mois:**\n\n"
        total = 0
        
        for row in results:
            stats_text += f"🏦 **{row.bank_associated}:** {row.total:.2f}€\n"
            total += row.total
        
        if total == 0:
            stats_text = "📊 Aucune dépense enregistrée ce mois-ci."
        else:
            stats_text += f"\n💰 **Total:** {total:.2f}€"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await update.message.reply_text(f"❌ Erreur: {str(e)}")


def start_keep_alive_server():
    """Start a minimal HTTP server in a background thread.

    Render's Web Services require an open port. A Telegram bot in polling mode
    doesn't open one, so this tiny server binds to the port Render provides
    (via the PORT env var) just to satisfy the platform's health check.
    """
    port = int(os.getenv('PORT', '10000'))

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is running')

        def log_message(self, format, *args):
            # Silence default HTTP logging to keep bot logs clean
            pass

    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Keep-alive HTTP server started on port {port}")


def main():
    """Start the bot"""
    # Start keep-alive server (for Render Web Service port binding)
    start_keep_alive_server()

    # Initialize BigQuery
    init_bigquery()
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Start bot
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
