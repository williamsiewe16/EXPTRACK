# Utiliser une image Python officielle
FROM python:3.11-slim

# Créer le dossier de l'app
WORKDIR /app

# Copier les fichiers
COPY . /app

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Définir la commande pour lancer l'app
CMD ["python", "expense_tracker_bot_mini.py"]
