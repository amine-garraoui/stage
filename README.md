# Automatisation des KPI support IT - RSI Sagemcom

Projet Python professionnel pour automatiser les KPI ASKit du support IT.

## Fonctionnalites

- ingestion CSV, CSV.GZ, XLSX et XLS ;
- nettoyage des exports ASKit tickets, satisfaction et employes ;
- KPI mensuels: ouverts, fermes, ouverts-et-fermes meme mois, delai moyen, satisfaction ;
- repartitions par site et sujet ;
- detection d'anomalies sur delai moyen et satisfaction ;
- comparaison mois N vs mois N-1 ;
- dashboard Streamlit ;
- API REST FastAPI avec Swagger ;
- export PDF et Excel ;
- tests unitaires pytest.

## Structure

```text
api/          API FastAPI
core/         ingestion, transformation, KPI, anomalies
dashboard/    interface Streamlit
reports/      exports PDF et Excel
scripts/      generation automatique mensuelle
tests/        tests unitaires
data/exports/ rapports generes
```

## Installation

```powershell
cd "C:\Users\MSI\Downloads\JFoenix-master\ticket stage"
python -m pip install -r requirements.txt
```

## Configuration

Les chemins des fichiers ASKit sont dans `config.yaml`.

Par defaut, le projet cherche les fichiers dans:

```text
data/input/
```

## Lancer le dashboard

```powershell
python -m streamlit run app.py
```

Adresse habituelle:

```text
http://localhost:8501
```

## Lancer l'API

```powershell
python -m uvicorn api.main:app --reload
```

Swagger:

```text
http://localhost:8000/docs
```

Endpoints utiles:

```text
GET /months
GET /kpi/{mois}
GET /kpi/{mois}/par-site
GET /kpi/{mois}/sujets
GET /satisfaction/{mois}
GET /export/{mois}
```

Exemple:

```text
http://localhost:8000/kpi/2026-06
```

## Generer un rapport

```powershell
python scripts/generate_monthly_report.py --month 2026-06
```

Les fichiers sont crees dans:

```text
data/exports/
```

## Tests

```powershell
python -m pytest
```

## Formules KPI

Les KPI sont calcules uniquement depuis les colonnes des fichiers ASKit.

| KPI | Formule | Colonne source |
| --- | --- | --- |
| Demandes ouvertes | Compter les tickets dont le mois de date d'ouverture correspond au mois selectionne | `Enregistre le` |
| Tickets fermes | Compter les tickets dont le mois de date de resolution correspond au mois selectionne | `Date de resolution` |
| Ouverts et fermes meme mois | Compter les tickets dont mois ouverture = mois resolution = mois selectionne | `Enregistre le`, `Date de resolution` |
| Tickets par site | Grouper les tickets ouverts du mois par site puis compter | `Beneficiaire : Localisation` |
| Sujets ouverts | Grouper les tickets ouverts du mois par sujet puis compter et trier | `Sujet` |
| Delai moyen | Moyenne du delai brut des tickets fermes du mois, converti HH:MM vers minutes puis heures | `Delai de resolution (min)` |
| Satisfaction | Moyennes des reponses enquete du mois | `Satisfaction de traitement`, `Communication des operateurs`, `Satisfaction du temps de traitement` |
| Taux participation | Nombre de reponses enquete du mois / demandes ouvertes du mois x 100 | fichier enquete + tickets ouverts |

Si une colonne attendue est absente, le dashboard affiche `Donnee indisponible`.

## Deploiement vers un PC Sagemcom

Copier tout le dossier `ticket stage` vers le Desktop du PC cible, puis adapter
ou remplacer les fichiers dans `data/input/`.

Commande de lancement apres copie:

```powershell
cd "C:\Users\[UTILISATEUR]\Desktop\ticket stage"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Des fichiers `.bat` sont aussi disponibles pour simplifier:

```text
install.bat
run_dashboard.bat
run_api.bat
generate_report.bat
```
