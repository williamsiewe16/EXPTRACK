# 🚀 Quick Start Guide

## Étape 1: Créer le virtualenv

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Étape 2: Obtenir les API Keys

### Telegram Bot
1. Ouvrir Telegram
2. Chercher `@BotFather`
3. Envoyer `/newbot`
4. Choisir un nom et un username
5. Copier le token

### Anthropic (Claude)
1. Aller sur https://console.anthropic.com
2. Sign up (gratuit)
3. API Keys → Create Key
4. Copier la clé

### OpenAI (Whisper)
1. Aller sur https://platform.openai.com
2. Sign up
3. API Keys → Create new secret key
4. Copier la clé

## Étape 3: Configuration GCP

### Créer le Service Account
1. Aller sur https://console.cloud.google.com
2. Sélectionner projet `255826797445`
3. Menu → IAM & Admin → Service Accounts
4. Create Service Account
   - Name: `expense-tracker`
   - Role: `BigQuery Admin`
5. Actions → Manage Keys → Add Key → Create new key → JSON
6. Télécharger et renommer en `gcp-credentials.json`
7. Placer dans le dossier du projet

## Étape 4: Configurer les variables

Copier `.env.example` vers `.env`:
```bash
cp .env.example .env
```

Éditer `.env` et remplacer:
```
TELEGRAM_BOT_TOKEN=le_token_de_botfather
ANTHROPIC_API_KEY=la_cle_anthropic
OPENAI_API_KEY=la_cle_openai
```

## Étape 5: Lancer le bot

```bash
python expense_tracker_bot.py
```

Si tout fonctionne, vous verrez:
```
INFO - Dataset ... created or already exists
INFO - Table ... created or already exists
INFO - Bot starting...
```

## Étape 6: Tester le bot

1. Ouvrir Telegram
2. Chercher votre bot (username donné par BotFather)
3. Envoyer `/start`
4. Envoyer une note vocale:
   > "J'ai dépensé 15 euros avec Boursorama, dépense associée à BNP pour kebab"

## Étape 7: Lancer le dashboard

Terminal 2:
```bash
source venv/bin/activate  # Windows: venv\Scripts\activate
streamlit run dashboard.py
```

Dashboard disponible sur: http://localhost:8501

## Étape 8: Configurer les seuils

Dans le dashboard (sidebar):
1. Entrer les montants pour chaque catégorie
2. Cliquer "Sauvegarder les seuils"

## ✅ Checklist

- [ ] Virtualenv créé et activé
- [ ] Dépendances installées
- [ ] Telegram bot token obtenu
- [ ] Anthropic API key obtenue
- [ ] OpenAI API key obtenue
- [ ] Service Account GCP créé
- [ ] gcp-credentials.json téléchargé
- [ ] .env configuré
- [ ] Bot lancé sans erreur
- [ ] Bot répond sur Telegram
- [ ] Dashboard accessible
- [ ] Seuils configurés

## 🆘 Problèmes courants

### "No module named 'telegram'"
```bash
pip install -r requirements.txt
```

### "Could not find gcp-credentials.json"
Vérifier que le fichier est bien dans le dossier du projet

### Bot ne répond pas
Vérifier le token dans .env et relancer le bot

### Erreur BigQuery permissions
Vérifier que le Service Account a bien le rôle "BigQuery Admin"

## 💡 Conseils

- Garder le bot en cours d'exécution pour recevoir les messages
- Rafraîchir le dashboard (F5) pour voir les nouvelles dépenses
- Exporter régulièrement les données en CSV (backup)
- Tester d'abord avec de petites notes vocales claires

## 📊 Utilisation quotidienne

1. **Faire une dépense** → Envoyer note vocale au bot
2. **Vérifier** → Confirmer les infos extraites
3. **Suivre** → Ouvrir le dashboard pour voir l'évolution
4. **Ajuster** → Modifier les seuils si nécessaire

---

**Tout fonctionne ? Bravo ! 🎉**

Prochaines étapes: Déployer en production (voir README.md)