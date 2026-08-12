# Architecture - Automatisation KPI RSI

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

## Principes

- Le coeur metier est dans `core/`, reutilisable sans Streamlit.
- L'API et le dashboard utilisent les memes fonctions KPI.
- Les chemins et seuils sont centralises dans `config.yaml`.
- Les exports PDF/Excel sont generes dans `data/exports/`.
- Les tests unitaires couvrent transformation, KPI et anomalies.
