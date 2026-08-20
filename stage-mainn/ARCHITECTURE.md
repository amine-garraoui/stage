# Architecture - Automatisation KPI RSI

## Vue d'ensemble

```mermaid
flowchart LR
        sources[(Sources ASKit)] --> ingestion[core/ingestion.py]
        ingestion --> transform[core/transformation.py]
        transform --> analytics[core/kpi.py<br/>core/anomalies.py<br/>core/insights.py]
        config[(config.yaml)] --> ingestion
        config --> analytics
        analytics --> api[FastAPI<br/>api/main.py]
        analytics --> dashboard[Streamlit<br/>dashboard/app.py]
        analytics --> reports[Exports<br/>PDF / Excel]
        api --> apiuser[Clients API]
        dashboard --> browser[Navigateur]
        reports --> exports[(data/exports)]
```

```text
Sources ASKit
  - Tickets
  - Enquete satisfaction
  - Referentiel employes
        |
        v
core/ingestion.py
  Lecture CSV, CSV.GZ, Excel
        |
        v
core/transformation.py
  Standardisation colonnes, dates, statuts, jointures
        |
        v
core/kpi.py + core/anomalies.py
  KPI, tendances mensuelles, anomalies
        |
        +-------------------+
        |                   |
        v                   v
api/main.py           dashboard/app.py
FastAPI + Swagger     Streamlit
        |
        v
reports/pdf.py + reports/excel.py
Exports mensuels
```

## Flux DevOps local

```mermaid
flowchart TD
                checkout[Cloner le dépôt] --> install[install.bat]
                install --> venv[Créer .venv]
                venv --> dependencies[Installer requirements.txt]
                dependencies --> tests[pytest<br/>50 tests]
                tests -->|OK| package[Construire l'image Docker]
                tests -->|Echec| fix[Corriger le code]
                fix --> tests
                package --> image[Image Python 3.12 slim]
                image --> runtime[Conteneur sous utilisateur non-root]
                runtime --> health[Healthcheck Streamlit :8501]
                health --> dashboard[Dashboard disponible]
```

## Déploiement Docker

```mermaid
sequenceDiagram
                participant Dev as Développeur
                participant Docker as Docker Engine
                participant App as Conteneur RSI KPI
                participant User as Utilisateur

                Dev->>Docker: docker build -t rsi-kpi .
                Docker->>Docker: Installer requirements.txt
                Docker->>App: Copier le code et créer appuser
                Dev->>Docker: docker run -p 8501:8501 rsi-kpi
                Docker->>App: Démarrer Streamlit sur 0.0.0.0:8501
                App-->>Docker: /_stcore/health
                User->>App: Ouvrir le dashboard
                App->>App: Lire les sources et calculer les KPI
                App-->>User: KPI, anomalies et exports
```

## Commandes opérationnelles

```text
Installation      : install.bat
Dashboard local   : run_dashboard.bat
API locale        : run_api.bat
Rapport mensuel   : generate_report.bat
Tests             : .venv\Scripts\python.exe -m pytest -q
Docker             : docker build -t rsi-kpi .
```

## État DevOps

- Le conteneur utilise Python 3.12 slim et un utilisateur Linux non-root.
- Le dashboard possède un healthcheck Docker sur le port 8501.
- Les scripts Windows utilisent le virtualenv `.venv` du projet.
- Les secrets API doivent être fournis via la variable d'environnement `API_KEYS`.
- Aucun pipeline CI/CD n'est encore présent dans le dépôt ; les tests doivent donc être exécutés avant chaque build ou déploiement.

## Principes

- Le coeur metier est dans `core/`, reutilisable sans Streamlit.
- L'API et le dashboard utilisent les memes fonctions KPI.
- Les chemins et seuils sont centralises dans `config.yaml`.
- Les exports PDF/Excel sont generes dans `data/exports/`.
- Les tests unitaires couvrent transformation, KPI et anomalies.
