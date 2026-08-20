# 🔒 Sécurité - Démarrage Rapide (5 minutes)

## Avant votre soutenance

### 1️⃣ Générer une clé API sécurisée

```powershell
# Ouvrir PowerShell dans le projet
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Output** : `AbCdEfGhIjKlMnOpQrStUvWxYz1234567890-_`

Copier cette clé quelque part (temporaire).

### 2️⃣ Configurer .env.local

```powershell
# Créer .env.local (ne JAMAIS committer)
Copy-Item ".env.example" ".env.local"

# Éditer .env.local et remplacer API_KEYS avec votre clé:
# API_KEYS=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890-_
```

### 3️⃣ Définir la variable d'environnement

```powershell
$env:API_KEYS = "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890-_"
```

### 4️⃣ Vérifier que l'authentification fonctionne

L'API retournera **401 Unauthorized** si vous n'envoyez pas le token :

```powershell
# ❌ Sans clé (doit échouer)
curl http://localhost:8000/kpi/2026-06

# ✅ Avec clé (doit marcher)
curl -H "Authorization: Bearer AbCdEfGhIjKlMnOpQrStUvWxYz1234567890-_" `
     http://localhost:8000/kpi/2026-06
```

### 5️⃣ Vérifier les logs d'audit

Après quelques requêtes API :

```bash
cat data/audit.log
```

Vous verrez :
```json
{"timestamp": "2026-08-19T...", "event_type": "AUTHENTICATION_SUCCESS", "user": "AbCdEfGh...", ...}
{"timestamp": "2026-08-19T...", "event_type": "DATA_ACCESS", "user": "AbCdEfGh...", ...}
```

---

## ✅ Checklist avant de montrer à votre encadrant

- [ ] Clé API générée
- [ ] .env.local créé (pas commité en Git)
- [ ] API demande toujours une clé (test 401)
- [ ] data/audit.log existe et enregistre les accessions
- [ ] Pas de noms/emails dans les PDF/Excel exportés

---

## 🚨 Si quelqu'un demande : « Et si quelqu'un vole votre code ? »

**Réponse** :
1. ✅ Sans la clé API, ils ne peuvent pas faire de requête
2. ✅ Sans `.encryption_key`, ils ne peuvent pas déchiffrer les fichiers  
3. ✅ Les logs d'audit enregistrent TOUS les accès (traçabilité)
4. ✅ Le mot de passe/données sensibles ne sont jamais en logs
5. ✅ HTTPS + TLS en production empêche interception en transit

---

## 🔐 Si vous avez besoin de chiffrer les fichiers CSV

```powershell
# Installer dépendances (si possible)
pip install cryptography

# Chiffrer tous les CSV
python scripts/setup_security.ps1 encrypt
```

Cela crée des fichiers `.csv.encrypted` et supprime les originaux non chiffrés.

---

## 📞 Questions pour votre encadrant

Pendant la soutenance, posez ces questions pour montrer que vous comprendre la sécurité :

1. **« Devrait-on utiliser HTTPS en production ? »**
   - ✅ OUI. Toujours HTTPS sur réseau Sagemcom.

2. **« Comment gérer les secrets en production ? »**
   - ✅ Variables d'environnement OU Azure Key Vault (Sagemcom)

3. **« Faut-il chiffrer les fichiers au repos ? »**
   - ✅ Oui si données très sensibles. Nous avons `core/encryption.py` prêt.

4. **« Comment savoir qui accède aux données ? »**
   - ✅ Audit log dans `data/audit.log`. Chaque accès est enregistré.

---

## 🎯 Résumé pour votre soutenance (30 secondes)

> « Nous avons 3 couches de sécurité :
>
> 1️⃣ **Authentification** : Clé API obligatoire pour tous les endpoints sensibles
>
> 2️⃣ **Audit** : Tous les accès sont enregistrés (qui, quand, quoi)
>
> 3️⃣ **Anonymisation** : Les PDF/Excel n'exposent pas les noms/emails
>
> Pour aller plus loin en production, on peut ajouter HTTPS + TLS et chiffrement au repos. »

---

**Besoin d'aide ?** Regardez [SECURITY.md](SECURITY.md) pour le guide complet.
