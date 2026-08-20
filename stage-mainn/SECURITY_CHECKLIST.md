# 🔒 Sécurité - Checklist Avant Soutenance

## A. Configuration (À faire AUJOURD'HUI - 15 min)

### Authentification API
- [ ] Clé API générée : `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] .env.local créé (copié de .env.example)
- [ ] API_KEYS défini dans .env.local
- [ ] Variable d'environnement définie : `$env:API_KEYS = "..."`
- [ ] Test : `curl -H "Authorization: Bearer WRONG_KEY" http://localhost:8000/kpi/2026-06` retourne **401**

### Fichiers sensibles
- [ ] `.env.local` en .gitignore
- [ ] `.encryption_key` en .gitignore
- [ ] Pas de `API_KEYS` en git (vérifier historique)

### Code
- [ ] `core/encryption.py` créé ✅
- [ ] `core/audit.py` créé ✅
- [ ] `api/main.py` intègre audit.log_data_access() et audit.log_export() ✅
- [ ] Imports OK dans api/main.py ✅

---

## B. Validation (À faire AVANT de montrer le code)

### Test basique
- [ ] Dashboard démarre : `run_dashboard.bat` ✅
- [ ] Importer un fichier ASKit ✅
- [ ] Générer un PDF/Excel ✅
- [ ] Vérifier que le PDF ne contient PAS de noms/emails (anonymisé) ✅

### Test API
- [ ] API démarre : `.venv\Scripts\python.exe -m uvicorn api.main:app --reload`
- [ ] `/health` retourne `{"status": "ok"}` sans authentification ✅
- [ ] `/kpi/2026-06` retourne **401** sans clé
- [ ] `/kpi/2026-06` avec clé retourne KPI ✅
- [ ] `data/audit.log` contient au moins 1 ligne ✅

### Tests Pytest
- [ ] `pytest tests/ -q` retourne **50 passed** ✅
- [ ] Aucune erreur ImportError pour `cryptography` (ce n'est pas grave si pas installé, warnings OK)

---

## C. Démonstration (Le jour J - 5 min de démo)

### Points à montrer
1. **Authentification**
   - [ ] Montrer que `/health` est public
   - [ ] Montrer que `/kpi/*` demande une clé
   - [ ] Tester avec curl (bon et mauvais token)

2. **Audit**
   - [ ] Afficher `data/audit.log`
   - [ ] Montrer qu'on voit qui a accédé, quand, quoi

3. **Anonymisation**
   - [ ] Ouvrir un PDF généré
   - [ ] Montrer qu'il y a les chiffres (KPI) mais pas les noms

4. **Code**
   - [ ] Montrer `core/encryption.py` (existe)
   - [ ] Montrer `core/audit.py` (existe)
   - [ ] Montrer `SECURITY.md` et `SECURITY_QUICK_START.md`

### Script de démo (1 min)
```bash
# 1. Montrer que l'API refuse une mauvaise clé
curl http://localhost:8000/kpi/2026-06
# → 401 Unauthorized

# 2. Montrer que l'API accepte la bonne clé
curl -H "Authorization: Bearer <votre-clé>" http://localhost:8000/kpi/2026-06
# → {"kpi": {...}, "comparison": {...}, "anomalies": {...}}

# 3. Montrer les logs d'audit
cat data/audit.log | tail -3
```

---

## D. Questions attendues de l'encadrant

### Q: « Comment vous gérez les secrets ? »
**Réponse** :
> Variables d'environnement, jamais en dur. En production, Azure Key Vault ou AWS Secrets Manager.
> Fichier `.env.local` en `.gitignore` → ne sera jamais commité.

### Q: « Et si quelqu'un accède au serveur ? »
**Réponse** :
> 3 couches :
> 1. Clé API obligatoire (401 si absent ou invalide)
> 2. Logs d'audit (traçabilité complète : qui a accédé, quand, quoi)
> 3. HTTPS/TLS en production (chiffrement en transit)
> Optionnel : chiffrement au repos avec `core/encryption.py`

### Q: « Comment on sait qui accède aux données ? »
**Réponse** :
> Audit log dans `data/audit.log`. Chaque accès API est enregistré en JSON avec :
> - Timestamp
> - Utilisateur (clé tronquée : "AbCdEfGh...")
> - Type d'événement (DATA_ACCESS, EXPORT, AUTH_SUCCESS/FAILURE)
> - Détails (mois accédé, format d'export, etc.)

### Q: « Les PII sont anonymisées ? »
**Réponse** :
> Oui, dans `core/anonymisation.py`. On supprime :
> - Noms
> - Emails
> - Téléphones
> - Commentaires
> 
> Les rapports contiennent SEULEMENT des données agrégées (KPI par site/sujet, pas par personne).

### Q: « Manque quelque chose pour la production ? »
**Réponse** :
> Court terme : HTTPS/TLS (certificat SSL)
> Long terme : Azure AD/Entra (authentification d'entreprise), chiffrement au repos, SIEM
> Nous avons déjà la foundation (auth + audit + anonymisation)

---

## E. Installations recommandées (si le temps)

```bash
# Installer les dépendances de sécurité
pip install cryptography python-dotenv safety

# Vérifier vulnérabilités
safety check
# Doit retourner zéro critique/haute

# Compiler tous les fichiers Python (vérifier syntaxe)
python -m py_compile core/encryption.py core/audit.py api/main.py
```

---

## F. Ressources pour briller

### Si encadrant pose question technique
- OWASP Top 10 : Injection SQL, CSRF, XSS
- Bearer tokens : RFC 6750
- Rate limiting : Comment slowapi protège des attaques par bruteforce
- Fernet encryption : Symmetric key cryptography (cryptography.io)

### Docs importantes
1. [SECURITY.md](SECURITY.md) — guide complet
2. [SECURITY_QUICK_START.md](SECURITY_QUICK_START.md) — quick start
3. [.env.example](.env.example) — template de config
4. [core/encryption.py](core/encryption.py) — code chiffrement
5. [core/audit.py](core/audit.py) — code audit

---

## G. Statut Final

| Élément | Statut | Notes |
|---------|--------|-------|
| Authentification API | ✅ | HTTPBearer + tokens |
| Audit logging | ✅ | `data/audit.log` |
| Anonymisation | ✅ | PII supprimées |
| Validation input | ✅ | Regex sur mois |
| Rate limiting | ✅ | slowapi (20-30/min) |
| HTTPS/TLS | ⏳ | En production seulement |
| Chiffrement au repos | ⏳ | Optionnel, code prêt |
| SIEM/Alertes | ⏳ | À implémenter Sagemcom |

---

## H. Avant de quitter ce fichier

- [ ] Tout coché ? → Vous êtes prêt ✅
- [ ] Manque l'authentification ? → Générer clé + configurer .env.local
- [ ] Manque les logs d'audit ? → Ils seront créés après première requête API
- [ ] Peur de l'API ? → Lancer `run_api.bat` et tester avec curl

**Bon courage pour votre soutenance ! 🚀**
