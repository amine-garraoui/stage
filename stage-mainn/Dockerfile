# Image officielle Python légère et à jour
FROM python:3.12-slim

# Empêcher la création de fichiers .pyc et forcer l'affichage immédiat des logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Définir le répertoire de travail
WORKDIR /app

# Sécurité: Créer un utilisateur non-root dédié avec des privilèges restreints
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copier et installer uniquement les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'application et attribuer la propriété à l'utilisateur non-root
COPY --chown=appuser:appgroup . .

# Créer les dossiers de données avec les bons droits
RUN mkdir -p data/input data/exports logs && chown -R appuser:appgroup /app

# Sécurité: Passer sous l'utilisateur non-root
USER appuser

# Exposer le port Streamlit
EXPOSE 8501

# Contrôle de santé (Healthcheck)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Lancer Streamlit avec les protections réseau renforcées
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.enableCORS=true", \
     "--server.enableXsrfProtection=true", \
     "--server.maxUploadSize=200"]
