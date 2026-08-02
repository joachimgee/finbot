# 🔐 Configuration Secrets GitHub

## 📍 Accès aux secrets

Allez sur : https://github.com/joachimgee/finbot/settings/secrets/actions

## ✅ Secrets à ajouter (6 au total)

### 1. APCA_API_KEY_ID
```
PKMB6OKRPTX7RBYOYHFY2FVDF2
```

### 2. APCA_API_SECRET_KEY
```
8Cz4jtsvCCm2p3LkjeEvGzAjB4YC8zzcnRkrZYpMPRxc
```

### 3. APCA_API_BASE_URL
```
https://paper-api.alpaca.markets
```

### 4. FMP_API_KEY
```
jJq5c4prWZALILljWhjgq08u2LV320lE
```

### 5. ALPHAVANTAGE_API_KEY
```
TGQCY9LANIUPJ4IL
```

### 6. NEWSAPI_KEY
```
c264bd241a2447bb94c32ba44377eda1
```

---

## 🚀 Après avoir ajouté les secrets

### Test manuel immédiat :
1. Allez sur : https://github.com/joachimgee/finbot/actions
2. Cliquez sur "Daily Professional Analysis Global 12K"
3. Cliquez sur "Run workflow" → "Run workflow"
4. Attendez 3-4 heures
5. Téléchargez l'artefact : `professional-analysis-global-12k-XXX`

### Exécution automatique :
- **Quand** : Chaque matin à **09:30 ET** (ouverture marchés US)
- **Jours** : Lundi-Vendredi seulement (pas le week-end)
- **Durée** : 3-4 heures
- **Résultat** : Fichier CSV avec top 200 symboles + 300+ facteurs

### Télécharger les résultats :
1. Allez sur : https://github.com/joachimgee/finbot/actions
2. Cliquez sur l'exécution la plus récente
3. En bas : "Artifacts" → Téléchargez `professional-analysis-global-12k-XXX`

---

## 📊 Ce qui sera analysé chaque matin

- **12,000 symboles** du monde entier (US, Europe, Asie, Amériques)
- **300+ facteurs** par symbole :
  - 100+ facteurs alpha (9 catégories)
  - 114 facteurs ML
  - 25+ indicateurs techniques
  - 47+ ratios fondamentaux
  - Sentiment FinBERT
- **Top 200** positions sélectionnées
- **IC-Weighted** scoring (Information Coefficient)
- **365 jours** de données historiques

---

## ⚙️ Configuration actuelle

| Paramètre | Valeur |
|-----------|--------|
| Limite symboles | 12,000 global |
| Top positions | 200 |
| Période historique | 365 jours |
| Niveau risque | medium-high |
| Pondération | ic-weighted |
| Horaire | 09:30 ET (14:30 UTC) |
| Jours actifs | Lundi-Vendredi |
| Timeout | 4 heures max |
| Rétention artefacts | 30 jours |

---

## 🔍 Monitoring

### Voir l'exécution en cours :
https://github.com/joachimgee/finbot/actions

### Voir les logs en temps réel :
1. Cliquez sur l'exécution en cours
2. Cliquez sur "analyze" → "Run Global 12K Analysis"
3. Logs défilent en direct

### Status badge :
Chaque exécution crée un fichier `analysis_status.txt` avec :
- Nombre de symboles analysés
- Date/heure de l'analyse

---

## 🛠️ Dépannage

### Si l'analyse échoue :
1. Vérifiez que tous les 6 secrets sont bien configurés
2. Vérifiez que les clés API sont valides
3. Regardez les logs pour identifier l'erreur
4. Relancez manuellement via "Run workflow"

### Si le workflow ne se lance pas automatiquement :
- Les workflows GitHub Actions ont parfois 5-10 min de délai
- Vérifiez que le workflow est bien activé (pas désactivé)
- Les workflows ne tournent pas sur les repos archivés

### Si vous voulez changer l'horaire :
Éditez `.github/workflows/daily_professional_analysis_global_12k.yml` :
```yaml
- cron: '30 14 * * 1-5'  # 09:30 ET
```

Exemples :
- `'00 13 * * 1-5'` → 08:00 ET (pré-market)
- `'00 21 * * 1-5'` → 16:00 ET (clôture)

---

## 💡 Avantages GitHub Actions vs PC local

✅ **Toujours actif** : Tourne même si votre PC est éteint  
✅ **Gratuit** : 2,000 min/mois inclus (une analyse = ~180-240 min)  
✅ **Fiable** : Infrastructure professionnelle  
✅ **Historique** : Tous les résultats archivés 30 jours  
✅ **Notifications** : Email si échec  
✅ **Logs complets** : Toute la trace d'exécution  

---

## 📧 Notifications

Par défaut, GitHub vous envoie un email si le workflow échoue.

Pour configurer d'autres notifications :
https://github.com/settings/notifications

---

**✅ CONFIGURATION TERMINÉE**

Une fois les secrets ajoutés, le système est **100% autonome** :
- Analyse **chaque matin à 09:30 ET**
- **Aucune action requise** de votre part
- Résultats disponibles dans "Actions" → "Artifacts"
