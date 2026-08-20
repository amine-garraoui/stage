# 🔒 SÉCURITÉ : Guide Complet pour RSI KPI

## 1. EN AUJOURD'HUI (Priorité critique)

### 1.1 Authentification API

**État actuel** : ✅ HTTPBearer + tokens

**À faire** :
```bash
# Générer une clé API sécurisée
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Exemple output: "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890-_"

# Sur Windows, définir la variable d'environnement
$env:API_KEYS = "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890-_"

# Vérifier que c'est bien pris en compte
$env:API_KEYS
```

**Utilisateurs de l'API** doivent envoyer :
```bash
curl -H "Authorization: Bearer AbCdEfGhIjKlMnOpQrStUvWxYz1234567890-_" \
     http://localhost:8000/kpi/2026-06
```

### 1.2 Rate Limiting

**État actuel** : ✅ 20-30 requêtes/minute par IP

**À vérifier** : Si quelqu'un teste 100 fois rapidement, il est bloqué. C'est normal. ✅

---

## 2. COURT TERME (Cette semaine)

### 2.1 Chiffrement des données sensibles

**Fichiers sensibles à protéger** :
- `data/input/*.csv` (noms, emails)
- `data/exports/` (rapports)

**Installer** :
```bash
pip install cryptography
```

**Utiliser** :
```python
from core.encryption import encrypt_file, decrypt_file
from pathlib import Path

# Chiffrer un fichier
encrypt_file(Path("data/input/ASKit - Report.csv"))
# Produit: data/input/ASKit - Report.csv.encrypted

# Déchiffrer (avec clé)
decrypt_file(Path("data/input/ASKit - Report.csv.encrypted"))
```

**Pour votre workflow** :
1. Chiffrez les CSV après import
2. Déchiffrez juste avant traitement
3. Supprimez les fichiers non chiffrés
4. **Sauvegardez la clé** : `.encryption_key` (jamais en Git!)

```bash
# Ajouter à .gitignore
echo ".encryption_key" >> .gitignore
echo ".env.local" >> .gitignore
```

### 2.2 Audit Logging

**Installer** : Déjà dans le code `core/audit.py`

**Utiliser dans api/main.py** :
```python
from core.audit import get_audit_logger

audit = get_audit_logger()

@app.get("/kpi/{mois}")
async def month_kpi(request: Request, mois: str, api_key: str = Depends(verify_api_key)):
    # Log this access
    audit.log_data_access(
        user=api_key[:8] + "...",  # Log partial key for privacy
        mois=mois,
        data_type="KPI"
    )
    # ... rest of endpoint
```

**Résultat** : Fichier `data/audit.log` avec toutes les accessions
```
2026-08-19 10:45:23 | INFO | {"timestamp": "2026-08-19T...", "event_type": "DATA_ACCESS", "user": "AbCdEfGh...", ...}
```

### 2.3 HTTPS/TLS (si l'app est exposée en ligne)

**À faire si** : L'app s'exécute sur un domaine public

**Générer certificat auto-signé** :
```bash
# Sur Windows PowerShell
# Ou utiliser OpenSSL si installé:
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Ensuite, dans api/main.py:
# uvicorn main:app --ssl-keyfile=key.pem --ssl-certfile=cert.pem
```

**En production** : Utiliser Let's Encrypt (certificat gratuit + automatisé)

---

## 3. MEDIUM TERME (Avant soutenance)

### 3.1 Validation d'entrée

**Déjà fait** ✅ dans api/main.py :
```python
def validate_month_format(mois: str) -> str:
    """Validate month parameter format (YYYY-MM)."""
    if not re.match(r"^\d{4}-\d{2}$", mois):
        raise HTTPException(status_code=400, ...)
```

### 3.2 Secrets dans les variables d'environnement

**À éviter** ❌:
```python
API_KEY = "my-secret-key"  # Jamais en dur dans le code!
DB_PASSWORD = "password123"
```

**À faire** ✅ :
```python
import os
API_KEY = os.getenv("API_KEYS")  # Déjà fait! ✅
DB_PASSWORD = os.getenv("DB_PASSWORD")
```

### 3.3 Dépendances à jour

```bash
# Vérifier les vulnérabilités
pip install safety
safety check

# Mettre à jour les packages
pip install --upgrade -r requirements.txt
```

---

## 4. LONG TERME (Avant Go-Live)

### 4.1 Compliance RGPD

**Vérifier avec votre encadrant** :
- [ ] Consentement pour collecter données personnelles ?
- [ ] Droit d'accès / suppression des données ?
- [ ] Anonymisation correcte dans les exports ?

**À votre code fait déjà** ✅ :
```python
# Dans core/anonymisation.py
drop_columns = ["nom", "prenom", "email", "telephone", "comment"]
```

### 4.2 Disaster Recovery

**Backup** :
```bash
# Automatiser un backup quotidien
# Créer scripts/backup.ps1

param($SourceDir = "data", $BackupDir = "backups")

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupPath = Join-Path $BackupDir "backup_$timestamp"

Copy-Item -Path $SourceDir -Destination $backupPath -Recurse -Force

# Chiffrer les backups
python -c "from core.encryption import encrypt_file; encrypt_file('$backupPath')"
```

### 4.3 Monitoring & Alertes

**Pour la production** :
- Surveiller le fichier `data/audit.log` (chercher authentifications échouées)
- Alerter si > 10 tentatives échouées/minute
- Archiver les logs mensuels

---

## 5. CHECKLIST DE SÉCURITÉ AVANT GO-LIVE

### Avant de montrer à votre encadrant

- [ ] **Authentification**
  - [ ] Clé API générée et stockée en .env.local
  - [ ] Tous les endpoints sensibles protégés
  - [ ] /health public uniquement

- [ ] **Chiffrement**
  - [ ] `cryptography` installé
  - [ ] Fichiers sensibles chiffrés
  - [ ] Clé `.encryption_key` en `.gitignore`

- [ ] **Audit**
  - [ ] `core/audit.py` en place
  - [ ] Logs générés dans `data/audit.log`
  - [ ] Pas de mots de passe en logs

- [ ] **Anonymisation**
  - [ ] PDF/Excel ne contiennent pas noms/emails/téléphones
  - [ ] Validation : ouvrir PDF, vérifier qu'on voit que chiffres, pas PII

- [ ] **Git**
  - [ ] `.env.local` en `.gitignore` ✅
  - [ ] `.encryption_key` en `.gitignore` ✅
  - [ ] Pas de passwords en commits (vérifier historique)

- [ ] **Dépendances**
  - [ ] `pip install safety && safety check` ← pas d'alertes
  - [ ] Requirements.txt à jour

### Avant la production Sagemcom

- [ ] **HTTPS obligatoire**
- [ ] **Certificat SSL/TLS valide**
- [ ] **Firewall : bloque tout sauf ports 443 (HTTPS), 22 (SSH admin)**
- [ ] **Reverse proxy** (ex: nginx) devant FastAPI
- [ ] **Logs centralisés** (ex: Syslog, ELK stack)
- [ ] **Backup quotidien chiffré**
- [ ] **SIEM** (Security Information & Event Management) pour alertes
- [ ] **Audit de sécurité externe** (si budget)

---

## 6. COMMANDES POUR SÉCURISER MAINTENANT

```bash
# 1. Installer dépendances de sécurité
pip install cryptography python-dotenv

# 2. Générer clé API
python -c "import secrets; print('API_KEY=' + secrets.token_urlsafe(32))"

# 3. Créer .env.local (jamais committer!)
# Copier .env.example vers .env.local et remplir

# 4. Vérifier vulnérabilités dépendances
pip install safety
safety check

# 5. Test de la sécurité API
curl -H "Authorization: Bearer WRONG_KEY" http://localhost:8000/kpi/2026-06
# Doit répondre: {"detail":"Invalid API key"}

# 6. Chiffrer fichiers sensibles
python -c "
from core.encryption import encrypt_file
from pathlib import Path
for f in Path('data/input').glob('*.csv'):
    encrypt_file(f)
    print(f'Encrypted: {f}')
"

# 7. Vérifier audit.log est créé
ls data/audit.log
```

---

## 7. RESSOURCES POUR EN SAVOIR PLUS

- [OWASP Top 10 Vulnerabilities](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Cryptography.io](https://cryptography.io/en/latest/)
- [RGPD - Cnil.fr](https://www.cnil.fr/fr/comprendre-le-rgpd)

---

## 8. CONTACTS ET ESCALADE

**Si attaque suspectée** :
1. Arrêter l'application immédiatement
2. Sauvegarder les logs audit (`data/audit.log`)
3. Notifier infosec Sagemcom
4. Ne pas nettoyer les traces

**Questions pour votre encadrant** :
- Avez-vous une équipe de sécurité ?
- Quelles sont les exigences de conformité ?
- Comment sont gérés les secrets en production ?
- Existe-t-il un WAF (Web Application Firewall) ?

---

**Statut** : Ce guide couvre 80% des besoins. Les 20% restants dépendent de votre infra Sagemcom spécifique.

**Prochaine étape** : Demander à votre encadrant de valider ce plan avant la soutenance.
