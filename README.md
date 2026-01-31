# 💰 Expense Tracker - Bot Telegram + Dashboard

Système complet de suivi de dépenses avec bot Telegram et dashboard temps réel.

## 🎯 Fonctionnalités

### Bot Telegram
- 🎙️ Enregistrement vocal des dépenses
- 🤖 Transcription automatique (Whisper)
- 🧠 Extraction intelligente des informations (Claude)
- ✅ Validation avant enregistrement
- 📊 Statistiques du mois

### Dashboard Streamlit
- 📈 Visualisations en temps réel
- 🎯 Suivi budget vs dépenses réelles
- 💳 Vue par catégorie et par carte
- 📊 Graphiques interactifs
- 💾 Export CSV

## 🏗️ Architecture

```
Note vocale → Telegram Bot → Whisper (transcription) → Claude (extraction) → BigQuery
                                                                                ↓
                                                            Streamlit Dashboard
```

## 📋 Prérequis

1. **Compte GCP** (gratuit)
   - Projet ID: `255826797445`
   - BigQuery activé

2. **API Keys**
   - Telegram Bot Token
   - Anthropic API Key (Claude)
   - OpenAI API Key (Whisper)

3. **Python 3.11+**

## 🚀 Installation

### 1. Clone et setup

```bash
git clone <votre-repo>
cd expense-tracker
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration GCP

#### A. Créer un Service Account

```bash
# Dans GCP Console
1. IAM & Admin > Service Accounts
2. Create Service Account
   - Name: expense-tracker-bot
   - Role: BigQuery Admin
3. Create Key (JSON)
4. Télécharger le fichier → renommer en gcp-credentials.json
```

#### B. Initialiser BigQuery

Le bot créera automatiquement:
- Dataset: `expense_tracker`
- Table: `expenses` avec le schéma:
  ```
  - date (DATE)
  - timestamp (TIMESTAMP)
  - amount (FLOAT)
  - bank_emission (STRING)
  - bank_associated (STRING)
  - comment (STRING)
  - user_id (STRING)
  ```

### 3. Configuration des API Keys

Créer un fichier `.env`:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Anthropic (Claude)
ANTHROPIC_API_KEY=your_anthropic_api_key

# OpenAI (Whisper)
OPENAI_API_KEY=your_openai_api_key
```

#### Comment obtenir les tokens:

**Telegram Bot:**
1. Parler à [@BotFather](https://t.me/botfather)
2. `/newbot`
3. Suivre les instructions
4. Copier le token

**Anthropic API:**
1. Aller sur [console.anthropic.com](https://console.anthropic.com)
2. Créer un compte
3. API Keys → Create Key
4. Tier gratuit disponible

**OpenAI API:**
1. Aller sur [platform.openai.com](https://platform.openai.com)
2. API Keys → Create new secret key
3. Whisper coûte ~$0.006/minute (ultra cheap)

### 4. Lancer le bot

```bash
python expense_tracker_bot.py
```

Le bot:
- ✅ Initialise BigQuery (dataset + table)
- ✅ Se connecte à Telegram
- ✅ Attend vos notes vocales

### 5. Lancer le dashboard

```bash
streamlit run dashboard.py
```

Le dashboard s'ouvre sur `http://localhost:8501`

## 📱 Utilisation du Bot

### Format de note vocale

**Exemple:**
> "J'ai dépensé 15 euros avec Boursorama, dépense associée à BNP pour kebab"

**Template:**
> "J'ai dépensé [MONTANT] euros avec [CARTE], dépense associée à [CATÉGORIE] pour [COMMENTAIRE]"

### Banques/Catégories disponibles
- BNP
- Boursorama
- Hello Bank
- Wise
- Revolut

### Commandes

- `/start` - Message de bienvenue
- `/stats` - Statistiques du mois

## 🎨 Dashboard

### Fonctionnalités

1. **Vue d'ensemble**
   - Total dépenses
   - Nombre de transactions
   - Dépense moyenne

2. **Par catégorie**
   - Montant dépensé
   - Budget restant
   - Barre de progression
   - Code couleur (🟢🟠🔴)

3. **Graphiques**
   - Répartition par catégorie (pie chart)
   - Cartes utilisées (bar chart)
   - Évolution quotidienne (line chart)
   - Budget vs Réel (grouped bar chart)

4. **Configuration**
   - Définir les seuils mensuels
   - Filtres de date
   - Export CSV

## 💰 Coûts (estimés pour usage personnel)

| Service | Coût mensuel |
|---------|--------------|
| BigQuery | 0€ (sous quotas gratuits) |
| Whisper API | ~0.50€ (30 notes vocales/jour) |
| Claude API | 0€ (tier gratuit) ou ~1€ |
| Telegram | 0€ |
| Streamlit Cloud | 0€ |
| **TOTAL** | **~0-2€/mois** |

## 🚀 Déploiement (Production)

### Bot Telegram

**Option 1: Render.com (gratuit)**
```bash
1. Créer compte sur render.com
2. New → Web Service
3. Connecter repo GitHub
4. Build Command: pip install -r requirements.txt
5. Start Command: python expense_tracker_bot.py
6. Ajouter variables d'environnement
7. Ajouter gcp-credentials.json en secret file
```

**Option 2: Railway (gratuit)**
```bash
1. railway.app
2. New Project → Deploy from GitHub
3. Variables → Ajouter les API keys
4. Settings → Add gcp-credentials.json
```

### Dashboard

**Streamlit Cloud (gratuit)**
```bash
1. share.streamlit.io
2. New app → Connecter repo
3. Main file: dashboard.py
4. Secrets → Ajouter gcp-credentials.json
5. Deploy
```

## 🔒 Sécurité

1. **Ne jamais commit:**
   - `.env`
   - `gcp-credentials.json`
   - API keys

2. **Ajouter au `.gitignore`:**
```
.env
gcp-credentials.json
*.pyc
__pycache__/
venv/
```

3. **Variables d'environnement:**
   - Utiliser les secrets des plateformes de déploiement
   - Ne jamais hardcoder les tokens

## 🐛 Troubleshooting

### Bot ne répond pas
```bash
# Vérifier les logs
python expense_tracker_bot.py

# Tester la connexion
curl https://api.telegram.org/bot<TOKEN>/getMe
```

### Erreur BigQuery
```bash
# Vérifier les credentials
gcloud auth application-default login

# Vérifier les permissions du service account
# BigQuery Admin requis
```

### Dashboard n'affiche pas les données
```bash
# Vérifier la connexion BigQuery
# Vérifier que le dataset/table existent
# Vérifier les dates filtrées
```

## 📊 Structure du projet

```
expense-tracker/
├── expense_tracker_bot.py         # Bot Telegram
├── expense_tracker_bot_mini.py    # Bot Telegram
├── dashboard.py                   # Dashboard Streamlit
├── requirements.txt               # Dépendances
├── gcp-credentials.json           # Credentials GCP (ne pas commit)
├── .env                           # Variables d'env (ne pas commit)
├── .gitignore                     # Fichiers à ignorer
└── README.md                      # Ce fichier
```

## 🎯 Améliorations futures

- [ ] Multi-utilisateurs avec authentification
- [ ] Notifications budget dépassé
- [ ] Export PDF rapports mensuels
- [ ] Analyse prédictive des dépenses
- [ ] Support photos de reçus (OCR)
- [ ] Intégration banques (via APIs)
- [ ] Application mobile native

## 📝 Notes

- Les données sont stockées dans la région EU (BigQuery)
- La transcription Whisper supporte le français
- Claude extrait intelligemment les infos même si le format varie
- Le dashboard se rafraîchit toutes les 60 secondes

## 🆘 Support

Pour toute question:
1. Vérifier les logs
2. Consulter la documentation des APIs
3. Tester avec `/start` sur le bot

## 📄 Licence

MIT License - Libre d'utilisation

---
