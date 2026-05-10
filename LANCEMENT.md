# 🍷 Angels' Share CRM — Guide de lancement

## 1. Installation (une seule fois)

Ouvrez le **Terminal** sur votre Mac et exécutez ces commandes une par une :

```bash
# Installer les dépendances Python
pip3 install streamlit pandas pillow openpyxl
```

Si pip3 n'est pas reconnu, essayez :
```bash
python3 -m pip install streamlit pandas pillow openpyxl
```

---

## 2. Lancer l'application

```bash
cd ~/Desktop/angels_share
streamlit run app.py
```

L'application s'ouvre automatiquement dans votre navigateur à l'adresse :
**http://localhost:8501**

---

## 3. Connexion

| Identifiant | Mot de passe |
|-------------|--------------|
| `gautier`   | `angels2026` |

> ⚠️ Changez le mot de passe dans `database.py` avant le premier lancement si vous le souhaitez.

---

## 4. Vos données

La base de données est stockée ici :
```
/Users/gautiersalinier/Documents/Angels Share Marketing Limited/Angels' Share Management/angels_share.db
```

Ce dossier est synchronisé par **iCloud** automatiquement si votre dossier Documents est dans iCloud Drive.

---

## 5. Accès depuis votre iPhone (Wi-Fi local)

1. Votre Mac et votre iPhone doivent être sur le **même réseau Wi-Fi**
2. Trouvez l'IP locale de votre Mac :
   - Préférences Système → Réseau → notez l'adresse (ex: `192.168.1.42`)
3. Sur votre iPhone, ouvrez Safari et tapez :
   **http://192.168.1.42:8501**

---

## 6. Accès depuis votre iPhone (réseau mobile — hors bureau)

**Recommandation : Railway (déploiement cloud)**

Une fois l'app terminée, nous déploierons sur Railway (~5$/mois) pour un accès permanent depuis n'importe où, même Mac éteint.

Instructions de déploiement fournies séparément.

---

## 7. Structure des fichiers

```
angels_share/
├── app.py              ← Point d'entrée principal
├── database.py         ← Base de données SQLite + migrations
├── utils.py            ← Fonctions partagées
├── requirements.txt    ← Dépendances Python
├── assets/
│   └── logo.jpg        ← Votre logo Angels' Share
├── modules/
│   ├── dashboard.py    ← Tableau de bord
│   ├── commandes.py    ← Gestion des commandes
│   ├── commissions.py  ← Suivi des commissions
│   ├── producteurs.py  ← Fiches producteurs
│   ├── contacts.py     ← Contacts & entreprises
│   ├── actions.py      ← Actions & to-do
│   └── frais.py        ← Notes de frais
└── .streamlit/
    └── config.toml     ← Configuration (port, thème)
```

---

## 8. Modules à venir (prochaines sessions)

- [ ] Module Distribution (matrice pays × produits)
- [ ] Objectifs & suivi CA
- [ ] Export Excel / PDF
- [ ] Rapports producteurs
- [ ] Calendrier & salons
- [ ] Prospection pipeline
- [ ] Déploiement Railway (accès mobile permanent)
