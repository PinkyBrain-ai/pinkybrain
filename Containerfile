# Configuration de conteneur pour UnityBrain & BugBrain v3.0
# Utilise l'image Python 3.12-slim comme base

FROM python:3.12-slim

# Définir les variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installer Ollama (runtime de modèles)
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Copier le projet
WORKDIR /app
COPY . /app/

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Installer le projet
RUN pip install -e .

# Télécharger les modèles par défaut (optionnel)
RUN ollama pull SmolLM2:1.7b || true

# Créer un utilisateur non-root
RUN useradd -m -u 1000 unitybrain && \
    chown -R unitybrain:unitybrain /app

USER unitybrain

# Exposer les ports
EXPOSE 8080 9999

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Commande par défaut
CMD ["python", "-m", "src.unitybrain_v3_final"]