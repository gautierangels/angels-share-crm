import streamlit as st
import pandas as pd
import urllib.parse
from database import get_db
from utils import fmt_date
from datetime import date, timedelta

ETAPES = [
    "Nouveau prospect", "Contacté", "Intéressé", "Réunion planifiée",
    "Proposition envoyée", "Négociation", "Recontacter plus tard",
    "Refusé", "Converti",
]
TYPES_ENVOI = [
    "Prospection initiale", "Relance J+10", "Relance J+30",
    "Suivi dégustation", "Envoi tarifs", "Invitation salon", "Autre",
]

# Mapping producteur → compte email expéditeur
EXPEDITEURS = {
    "Maison Léda": "g.salinier@leda-asia.com",
}
EXPEDITEUR_DEFAULT = "gautier@angels-share.net"

def get_expediteur(prods_selec):
    """Retourne l'email expéditeur selon les producteurs sélectionnés.
    Si Maison Léda est le SEUL producteur → compte Léda.
    Sinon → compte Angels' Share."""
    if len(prods_selec) == 1 and prods_selec[0] in EXPEDITEURS:
        return EXPEDITEURS[prods_selec[0]]
    return EXPEDITEUR_DEFAULT


def _nettoyer_emails_invalides(db):
    """Supprime contacts email invalide/tronqué ET doublons ET clients existants."""
    try:
        # 1. Emails invalides ou tronqués
        db.execute("""
            DELETE FROM prospection
            WHERE archived=0
            AND etape='Nouveau prospect'
            AND (
                contact_email IS NULL
                OR TRIM(contact_email) = ''
                OR contact_email NOT LIKE '%@%'
                OR LENGTH(TRIM(contact_email)) < 7
                OR SUBSTR(contact_email, INSTR(contact_email,'@')+1) NOT LIKE '%.%'
                OR LENGTH(SUBSTR(contact_email, INSTR(contact_email,'@')+1)) < 4
            )
        """)

        # 2. Doublons — garder seulement le MIN(id) par email
        db.execute("""
            DELETE FROM prospection
            WHERE archived=0
            AND etape='Nouveau prospect'
            AND id NOT IN (
                SELECT MIN(id) FROM prospection
                WHERE archived=0 AND etape='Nouveau prospect'
                AND contact_email IS NOT NULL AND contact_email != ''
                GROUP BY LOWER(TRIM(contact_email))
            )
            AND contact_email IS NOT NULL AND contact_email != ''
        """)

        # 3. Clients existants — supprimer des prospects si email dans contacts
        try:
            db.execute("""
                DELETE FROM prospection
                WHERE archived=0
                AND etape='Nouveau prospect'
                AND LOWER(TRIM(contact_email)) IN (
                    SELECT LOWER(TRIM(email)) FROM contacts
                    WHERE archived=0 AND email IS NOT NULL AND email != ''
                )
            """)
        except Exception:
            pass

        db.commit()
    except Exception:
        pass


def _ensure_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS prospection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        civilite TEXT DEFAULT '—', prenom TEXT, nom TEXT NOT NULL,
        type TEXT DEFAULT 'Importateur / client',
        pays TEXT, activite TEXT, source TEXT,
        etape TEXT DEFAULT 'Nouveau prospect',
        contact_nom TEXT, contact_email TEXT, contact_mobile TEXT,
        contact_tel_fixe TEXT, contact_poste TEXT,
        contact_whatsapp TEXT, contact_langue TEXT, contact_role_email TEXT,
        producteur_interet TEXT, date_prochain_contact TEXT,
        raison_refus TEXT, notes TEXT, adresse TEXT,
        tel_fixe_societe TEXT, concurrents TEXT, date_fiche_source TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        archived INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS prospection_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id INTEGER REFERENCES prospection(id),
        date_interaction TEXT DEFAULT (datetime('now')),
        type TEXT, contenu TEXT, notes TEXT
    )""")
    db.commit()
    for col, defn in [
        ("source","TEXT"),("contact_tel_fixe","TEXT"),("contact_poste","TEXT"),
        ("contact_whatsapp","TEXT"),("contact_langue","TEXT"),
        ("contact_role_email","TEXT"),("adresse","TEXT"),
        ("tel_fixe_societe","TEXT"),("concurrents","TEXT"),
        ("date_fiche_source","TEXT"),("civilite","TEXT DEFAULT '—'"),
        ("prenom","TEXT"),("activite","TEXT"),
    ]:
        try: db.execute(f"ALTER TABLE prospection ADD COLUMN {col} {defn}"); db.commit()
        except: pass


def _tracer_envoi(db, selections, sujet, type_envoi, expediteur, relance_j):
    """Trace les emails envoyés dans la DB et met à jour l'étape."""
    from datetime import date, timedelta
    relance_date = (date.today() + timedelta(days=int(relance_j))).isoformat()
    today_str    = date.today().strftime("%d/%m/%Y")
    for sel in selections:
        p = sel["prospect"]
        te = sel.get("type_envoi", type_envoi)
        db.execute("""UPDATE prospection SET etape='Contacté',
            date_prochain_contact=?, updated_at=datetime('now') WHERE id=?""",
            (relance_date, p["id"]))
        db.execute("""INSERT INTO prospection_interactions
            (prospect_id, type, contenu, notes) VALUES (?,?,?,?)""",
            (p["id"], "Email",
             f"[{today_str}] {te} — {sujet or '(sans sujet)'}",
             f"Expéditeur: {expediteur} | Rôle: {sel['role']} | Relance: {relance_date}"))
    db.commit()
    return relance_date


def _envoyer_smtp(db, selections, sujet, corps, smtp_user, smtp_pass,
                   smtp_server, smtp_port, smtp_ssl, type_envoi, expediteur, relance_j):
    """Envoie les emails via SMTP et trace dans la DB."""
    import smtplib, ssl as ssl_lib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import streamlit as st

    envoyes = 0
    erreurs = []

    try:
        # Connexion SMTP
        context = ssl_lib.create_default_context()
        if smtp_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()

        server.login(smtp_user, smtp_pass)

        progress = st.progress(0, text="Envoi en cours…")

        for i, sel in enumerate(selections):
            p  = sel["prospect"]
            em = p["contact_email"] or ""
            if not em: continue

            # Personnaliser le corps avec le prénom si disponible
            prenom = p["contact_nom"] or p["nom"] or ""
            corps_perso = corps
            if prenom:
                # Remplacer "Dear," par "Dear Prenom,"
                corps_perso = corps_perso.replace("Dear,", f"Dear {prenom.split()[0]},")
                corps_perso = corps_perso.replace("Bonjour,", f"Bonjour {prenom.split()[0]},")

            # Créer le message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = sujet
            msg["From"]    = smtp_user
            msg["To"]      = em
            msg.attach(MIMEText(corps_perso, "plain", "utf-8"))

            try:
                server.sendmail(smtp_user, em, msg.as_string())
                envoyes += 1
            except Exception as e:
                erreurs.append(f"{em}: {e}")

            progress.progress((i+1)/len(selections),
                              text=f"Envoi {i+1}/{len(selections)} — {em}")

        server.quit()
        progress.empty()

        # Tracer dans DB
        relance_date = _tracer_envoi(db, selections, sujet, type_envoi,
                                      expediteur, relance_j)

        st.success(f"✅ **{envoyes} email(s) envoyés** · Relance le **{relance_date}**")
        if erreurs:
            st.warning(f"⚠️ {len(erreurs)} erreur(s) : {'; '.join(erreurs[:3])}")

    except smtplib.SMTPAuthenticationError:
        st.error("❌ Authentification SMTP échouée — vérifiez votre email et mot de passe.")
    except Exception as e:
        st.error(f"❌ Erreur SMTP : {e}")


def render():
    st.markdown("## 🔍 Prospection")
    db = get_db()
    db.execute("PRAGMA busy_timeout=5000")  # 5s timeout si DB occupée
    _ensure_tables(db)
    _nettoyer_emails_invalides(db)

    pays_list = [p["nom"] for p in db.execute(
        "SELECT nom FROM pays WHERE actif=1 ORDER BY nom").fetchall()]
    producteurs_list = [p["nom"] for p in db.execute(
        "SELECT nom FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()]

    tab1, tab2, tab3, tab4 = st.tabs([
        "📨 Campagne email", "🗂️ Pipeline", "➕ Nouveau prospect", "📊 Statistiques"
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — CAMPAGNE EMAIL (architecture légère)
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown("### 📨 Campagne de prospection")

        # ── ÉTAPE 1 : Filtres ─────────────────────────────────────────────────
        st.markdown("#### 1. Choisir un pays et filtrer")
        fc1, fc2, fc3 = st.columns(3)
        sel_pays  = fc1.selectbox("🌍 Pays *", ["— Choisir —"] + pays_list, key="camp_pays")
        sel_etape = fc2.selectbox("Étape", ["— Toutes —"] + ETAPES, key="camp_etape")
        sel_src   = fc3.text_input("Source", placeholder="Business France…", key="camp_src")

        if sel_pays == "— Choisir —":
            st.info("👆 Commencez par choisir un pays.")
            db.close(); return

        # ── Charger noms ET domaines des clients existants pour exclusion ────
        noms_clients   = set()
        domaines_clients = set()
        emails_clients = set()
        try:
            # Noms d'entreprises clientes
            for row in db.execute(
                "SELECT LOWER(TRIM(nom)) as nom FROM entreprises WHERE archived=0"
            ).fetchall():
                if row["nom"]: noms_clients.add(row["nom"])

            # Emails individuels des contacts clients
            for row in db.execute(
                "SELECT LOWER(TRIM(email)) as email FROM contacts WHERE archived=0 AND email LIKE '%@%'"
            ).fetchall():
                if row["email"]:
                    emails_clients.add(row["email"])
                    domaine = row["email"].split("@")[-1].lower().strip()
                    if domaine and "." in domaine:
                        domaines_clients.add(domaine)

            # Email général des entreprises
            for row in db.execute(
                "SELECT LOWER(TRIM(email_general)) as email FROM entreprises WHERE archived=0 AND email_general LIKE '%@%'"
            ).fetchall():
                if row["email"]:
                    emails_clients.add(row["email"])
                    domaine = row["email"].split("@")[-1].lower().strip()
                    if domaine and "." in domaine and domaine not in (
                        "gmail.com","yahoo.com","hotmail.com","outlook.com",
                        "icloud.com","me.com","qq.com","163.com","126.com"
                    ):
                        domaines_clients.add(domaine)
        except Exception:
            pass

        # ── Charger TOUS les prospects du pays ───────────────────────────────
        q = "SELECT * FROM prospection WHERE archived=0 AND pays=?"
        params = [sel_pays]
        if sel_etape != "— Toutes —": q += " AND etape=?"; params.append(sel_etape)
        if sel_src: q += " AND source LIKE ?"; params.append(f"%{sel_src}%")
        q += " ORDER BY nom"
        tous_raw = db.execute(q, params).fetchall()
        # Dédupliquer + exclure toute entreprise déjà cliente
        emails_vus = set()
        tous = []
        for p in tous_raw:
            email = str(p["contact_email"] or "").strip().lower()
            nom_prospect = str(p["nom"] or "").strip().lower()

            # 1. Email invalide ou tronqué → ignorer
            if not email or "@" not in email or len(email) < 7:
                continue
            domaine = email.split("@")[-1].strip()
            if "." not in domaine or len(domaine) < 4:
                continue

            # 2. Doublon email → ignorer
            if email in emails_vus:
                continue

            # 3. Email déjà client → toute l'entreprise exclue
            if email in emails_clients:
                continue

            # 4. Domaine email = domaine d'un client (même société) → exclure
            generiques = {"gmail.com","yahoo.com","hotmail.com","outlook.com",
                          "icloud.com","me.com","qq.com","163.com","126.com",
                          "yahoo.fr","hotmail.fr","sina.com","sohu.com"}
            if domaine not in generiques and domaine in domaines_clients:
                continue

            # 5. Nom entreprise identique à un client → exclure
            if nom_prospect and nom_prospect in noms_clients:
                continue

            emails_vus.add(email)
            tous.append(p)

        if not tous:
            st.warning(f"Aucun prospect trouvé en **{sel_pays}**.")
            db.close(); return

        # ── Découpage alphabétique si > 50 ───────────────────────────────────
        TRANCHE = 50
        if len(tous) > TRANCHE:
            # Construire les tranches A-Z
            tranches = {}
            for p in tous:
                lettre = (p["nom"] or "?")[0].upper()
                lettre = lettre if lettre.isalpha() else "#"
                tranches[lettre] = tranches.get(lettre, []) + [p]

            # Regrouper en blocs de ~50
            blocs = []
            bloc_courant = []
            lettres_bloc = []
            for lettre in sorted(tranches.keys()):
                if len(bloc_courant) + len(tranches[lettre]) > TRANCHE and bloc_courant:
                    blocs.append((lettres_bloc, bloc_courant))
                    bloc_courant = []
                    lettres_bloc = []
                bloc_courant += tranches[lettre]
                lettres_bloc.append(lettre)
            if bloc_courant:
                blocs.append((lettres_bloc, bloc_courant))

            # Labels lisibles : "A → D (32)", "E → K (48)"…
            labels = []
            for lettres, plist in blocs:
                if len(lettres) == 1:
                    labels.append(f"{lettres[0]}  ({len(plist)})")
                else:
                    labels.append(f"{lettres[0]} → {lettres[-1]}  ({len(plist)})")

            st.info(f"**{len(tous)} contacts** en {sel_pays} — choisissez une tranche :")
            sel_label = st.radio("Tranche alphabétique", labels,
                                  horizontal=True, key="tranche_alpha")
            idx_bloc = labels.index(sel_label)
            prospects = blocs[idx_bloc][1]
            st.success(f"**{len(prospects)} contact(s)** affichés · {sel_label.split('(')[0].strip()}")
        else:
            prospects = tous
            st.success(f"**{len(prospects)} contact(s)** en {sel_pays}")

        # ── ÉTAPE 2 : Paramètres ──────────────────────────────────────────────
        st.markdown("#### 2. Producteurs & paramètres")
        if producteurs_list:
            cols_p = st.columns(min(4, len(producteurs_list)))
            prods_selec = [p for i,p in enumerate(producteurs_list)
                           if cols_p[i%len(cols_p)].checkbox(p, key=f"p_{i}")]
        else:
            prods_selec = []

        # Expéditeur automatique selon producteurs
        expediteur = get_expediteur(prods_selec) if prods_selec else EXPEDITEUR_DEFAULT
        if prods_selec:
            if expediteur == EXPEDITEUR_DEFAULT:
                st.info(f"📤 Expéditeur : **{expediteur}** (compte Angels' Share)")
            else:
                st.success(f"📤 Expéditeur : **{expediteur}** (compte Maison Léda)")

        ep1, ep2, ep3 = st.columns(3)
        type_envoi  = ep1.selectbox("Type d'envoi", TYPES_ENVOI, key="type_envoi")
        camp_langue = ep2.selectbox("Langue", [
            "Anglais","Français","Chinois","Japonais","Coréen","Bahasa Indonesia"
        ], key="camp_lng")
        relance_j   = ep3.number_input("Relance auto (jours)", 1, 30, 10, key="camp_relance")

        # ── ÉTAPE 3 : Sélection contacts ──────────────────────────────────────
        st.markdown("#### 3. Sélectionner les contacts")

        # Boutons tout/rien
        bc1, bc2, _ = st.columns([1, 1, 4])
        if bc1.button("✅ Tout cocher", key="btn_all"):
            for p in prospects:
                st.session_state[f"chk_{p['id']}"] = True
        if bc2.button("⬜ Tout décocher", key="btn_none"):
            for p in prospects:
                st.session_state[f"chk_{p['id']}"] = False

        # Table header
        h0,h1,h2,h3,h4,h5 = st.columns([0.4, 2.2, 1.8, 1.2, 1.4, 1.8])
        for col, txt in zip([h1,h2,h3,h4,h5],["Entreprise","Contact · Poste","Rôle","Type","Email"]):
            col.markdown(f"<small><b>{txt}</b></small>", unsafe_allow_html=True)
        st.divider()

        # Checkboxes simples — léger et fiable
        selections = []
        for p in prospects:
            c0,c1,c2,c3,c4,c5,c6,c7 = st.columns([0.4, 1.8, 1.6, 0.9, 1.6, 1.6, 0.3, 0.3])

            checked = c0.checkbox("", key=f"chk_{p['id']}",
                                  value=st.session_state.get(f"chk_{p['id']}", False))

            nom_ent  = p["nom"] or "—"
            pays_ent = p["pays"] or ""
            c1.markdown(f"**{nom_ent}**  \n<small style='color:#888'>{pays_ent}</small>",
                        unsafe_allow_html=True)

            nom_ctc = p["contact_nom"] or "—"
            poste   = p["contact_poste"] or ""
            c2.markdown(f"<small>{nom_ctc}</small>  \n<small style='color:#888'>{poste}</small>",
                        unsafe_allow_html=True)

            nb_same_ent = sum(1 for x in prospects if x["nom"] == p["nom"])
            role_defaut = "CC" if (nb_same_ent > 1 and p["contact_role_email"] == "CC") else "To"
            role = c3.selectbox("", ["To","CC"], key=f"role_{p['id']}",
                                index=0 if role_defaut=="To" else 1,
                                label_visibility="collapsed")

            type_ctc = c4.selectbox("", TYPES_ENVOI, key=f"type_{p['id']}",
                                    label_visibility="collapsed")

            email = p["contact_email"] or "—"
            c5.markdown(f"<small style='color:#555'>{email}</small>",
                        unsafe_allow_html=True)

            # Boutons ✏️ et 🗑️ en bout de ligne
            if c6.button("✏️", key=f"edit_{p['id']}", help="Modifier ce contact"):
                st.session_state[f"edit_open_{p['id']}"] = True
            if c7.button("🗑️", key=f"del_{p['id']}", help="Supprimer ce contact"):
                st.session_state[f"del_confirm_{p['id']}"] = True

            # Popup modification
            if st.session_state.get(f"edit_open_{p['id']}"):
                with st.expander(f"✏️ Modifier — {nom_ctc} ({nom_ent})", expanded=True):
                    with st.form(f"form_edit_{p['id']}"):
                        fe1,fe2 = st.columns(2)
                        new_email_m = fe1.text_input("Email", value=p["contact_email"] or "", key=f"em_{p['id']}")
                        new_nom_m   = fe2.text_input("Nom", value=p["contact_nom"] or "", key=f"nm_{p['id']}")
                        fe3,fe4 = st.columns(2)
                        new_poste_m = fe3.text_input("Poste", value=p["contact_poste"] or "", key=f"pm_{p['id']}")
                        new_mob_m   = fe4.text_input("Mobile", value=p["contact_mobile"] or "", key=f"mm_{p['id']}")
                        new_notes_m = st.text_area("Notes", value=p["notes"] or "", height=50, key=f"no_{p['id']}")
                        fs1,fs2 = st.columns(2)
                        if fs1.form_submit_button("💾 Sauvegarder", use_container_width=True):
                            try:
                                db.execute("PRAGMA busy_timeout=5000")
                                db.execute("""UPDATE prospection SET
                                    contact_email=?,contact_nom=?,contact_poste=?,
                                    contact_mobile=?,notes=?,updated_at=datetime('now')
                                    WHERE id=?""",
                                    (new_email_m,new_nom_m,new_poste_m,new_mob_m,new_notes_m,p["id"]))
                                db.commit()
                                st.session_state[f"edit_open_{p['id']}"] = False
                                st.success("✅ Modifié."); st.rerun()
                            except Exception as e:
                                st.error(f"Erreur modification : {e}. Relancez l'app et réessayez.")
                        if fs2.form_submit_button("Annuler", use_container_width=True):
                            st.session_state[f"edit_open_{p['id']}"] = False
                            st.rerun()

            # Confirmation suppression
            if st.session_state.get(f"del_confirm_{p['id']}"):
                st.warning(f"⚠️ Supprimer **{nom_ctc}** ({email}) ? Cette action est irréversible.")
                cd1,cd2,cd3 = st.columns([1,1,4])
                if cd1.button("✅ Confirmer", key=f"del_ok_{p['id']}"):
                    try:
                        db.execute("PRAGMA busy_timeout=5000")
                        db.execute("DELETE FROM prospection WHERE id=?", (p["id"],))
                        db.commit()
                        st.session_state[f"del_confirm_{p['id']}"] = False
                        st.success("✅ Supprimé."); st.rerun()
                    except Exception as e:
                        st.error(f"Erreur suppression : {e}. Relancez l'app et réessayez.")
                if cd2.button("Annuler", key=f"del_no_{p['id']}"):
                    st.session_state[f"del_confirm_{p['id']}"] = False
                    st.rerun()

            if checked:
                selections.append({"prospect": p, "role": role, "type_envoi": type_ctc})

        n_sel = len(selections)
        st.divider()
        st.caption(f"**{n_sel}/{len(prospects)}** contact(s) sélectionné(s) · "
                   f"{sum(1 for s in selections if s['role']=='To')} To · "
                   f"{sum(1 for s in selections if s['role']=='CC')} CC")

        # ── ÉTAPE 4 : Email ───────────────────────────────────────────────────
        st.markdown("#### 4. Rédiger l'email")
        st.caption("💡 Cliquez sur un lien Outlook ci-dessous — il ouvrira un email pré-rempli avec votre texte.")

        sujet = st.text_input("📌 Sujet de l'email", placeholder="Ex: Découvrez nos nouvelles références…", key="camp_sujet")
        corps = st.text_area("✉️ Corps de l'email", height=200, key="camp_corps",
                             placeholder="Bonjour,\n\nJe me permets de vous contacter…\n\n(Votre signature sera ajoutée automatiquement dans Outlook)")

        # ── ÉTAPE 5 : Préparer l'envoi ───────────────────────────────────────
        st.markdown("#### 5. Préparer l'envoi")

        if n_sel == 0:
            st.info("👆 Cochez au moins un contact ci-dessus.")
        else:
            # Alerte distribution
            try:
                distrib = db.execute("""
                    SELECT producteur_nom, marque_nom, client_actuel
                    FROM distribution
                    WHERE pays=? AND (archived=0 OR archived IS NULL)
                    AND client_actuel IS NOT NULL AND client_actuel!=''
                """, (sel_pays,)).fetchall()
                if distrib:
                    par_prod = {}
                    for d in distrib:
                        prod = d["producteur_nom"] or "—"
                        if prod not in par_prod:
                            par_prod[prod] = {"client": d["client_actuel"], "marques": []}
                        if d["marque_nom"]: par_prod[prod]["marques"].append(d["marque_nom"])
                    with st.expander(f"⚠️ {len(par_prod)} producteur(s) déjà présent(s) en {sel_pays}"):
                        for prod, info in par_prod.items():
                            m = f" ({', '.join(info['marques'][:2])})" if info["marques"] else ""
                            st.markdown(f"- **{prod}**{m} → **{info['client']}**")
            except Exception:
                pass

            # ── Choix du mode d'envoi ─────────────────────────────────────────
            mode_envoi = st.radio(
                "Mode d'envoi",
                ["📧 Lien Outlook (manuel, un par un)",
                 "🚀 Publipostage SMTP (automatique, tous d'un coup)"],
                horizontal=True, key="mode_envoi"
            )

            if mode_envoi == "📧 Lien Outlook (manuel, un par un)":
                sujet_enc = urllib.parse.quote(sujet or "Prospection Angels' Share", safe="")
                corps_enc = urllib.parse.quote(corps or "", safe="")
                st.caption("Cliquez sur chaque lien pour ouvrir Outlook avec l'email pré-rempli.")
                for sel in selections:
                    p  = sel["prospect"]
                    em = p["contact_email"] or ""
                    if not em: continue
                    nom   = p["contact_nom"] or p["nom"] or "—"
                    ent   = p["nom"] or "—"
                    badge = "**To**" if sel["role"]=="To" else "CC"
                    mailto = f"mailto:{em}?subject={sujet_enc}&body={corps_enc}"
                    st.markdown(f"[📧 {nom} — {ent}]({mailto}) → {badge}")

                if st.button("✅ Marquer comme envoyés", key="btn_mark_sent"):
                    _tracer_envoi(db, selections, sujet, type_envoi, expediteur, relance_j)
                    st.success(f"✅ {n_sel} prospect(s) → **Contacté** · Relance le **{fmt_date((date.today()+timedelta(days=int(relance_j))).isoformat())}**")
                    st.rerun()

            else:
                # ── Configuration SMTP ────────────────────────────────────────
                st.markdown("**⚙️ Configuration SMTP**")
                smtp_col1, smtp_col2, smtp_col3 = st.columns(3)
                smtp_server = smtp_col1.text_input("Serveur SMTP",
                    value=st.session_state.get("smtp_server", ""),
                    placeholder="ex: mail.votredomaine.com",
                    key="smtp_server_input")
                smtp_port = smtp_col2.number_input("Port",
                    value=st.session_state.get("smtp_port", 465),
                    min_value=1, max_value=9999, key="smtp_port_input")
                smtp_ssl  = smtp_col3.checkbox("SSL",
                    value=st.session_state.get("smtp_ssl", True),
                    key="smtp_ssl_input")

                smtp_col4, smtp_col5 = st.columns(2)
                smtp_user = smtp_col4.text_input("Email expéditeur",
                    value=expediteur, key="smtp_user_input")
                smtp_pass = smtp_col5.text_input("Mot de passe",
                    type="password", key="smtp_pass_input",
                    help="Non stocké — en mémoire uniquement pendant la session")

                if smtp_server and smtp_pass:
                    st.session_state["smtp_server"] = smtp_server
                    st.session_state["smtp_port"]   = smtp_port
                    st.session_state["smtp_ssl"]    = smtp_ssl

                    if st.button(f"🚀 Envoyer {n_sel} email(s) maintenant",
                                 type="primary", use_container_width=True,
                                 key="btn_smtp_send"):
                        if not sujet:
                            st.error("⚠️ Le sujet est obligatoire.")
                        elif not corps:
                            st.error("⚠️ Le corps de l'email est obligatoire.")
                        else:
                            _envoyer_smtp(db, selections, sujet, corps,
                                          smtp_user, smtp_pass, smtp_server,
                                          int(smtp_port), smtp_ssl,
                                          type_envoi, expediteur, relance_j)
                else:
                    st.info("Renseignez le serveur SMTP et votre mot de passe pour activer l'envoi.")


        # ── Notes entreprises ─────────────────────────────────────────────────
        avec_notes = [p for p in prospects if p["notes"] and len(p["notes"]) > 10]
        if avec_notes:
            with st.expander(f"ℹ️ Fiches entreprises ({len(avec_notes)} avec notes)"):
                for p in avec_notes:
                    st.markdown(f"**{p['nom']}**")
                    st.caption(p["notes"][:300])
                    if p["concurrents"]:
                        st.caption(f"🏷️ {p['concurrents']}")
                    st.divider()

        # (Modifier/Supprimer intégré dans chaque ligne — voir ci-dessus)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — PIPELINE (édition inline)
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("### 🗂️ Pipeline — édition directe dans le tableau")
        st.caption("Modifiez l'étape, les notes ou la date de relance directement dans le tableau, puis cliquez **Sauvegarder**.")

        c1, c2, c3 = st.columns(3)
        fp = c1.selectbox("Pays",  ["Tous"] + pays_list, key="pip_pays")
        fe = c2.selectbox("Étape", ["Toutes"] + ETAPES,  key="pip_etape")
        fn = c3.text_input("Recherche", key="pip_nom")

        q = "SELECT * FROM prospection WHERE archived=0"
        params = []
        if fp != "Tous":   q += " AND pays=?";  params.append(fp)
        if fe != "Toutes": q += " AND etape=?"; params.append(fe)
        if fn:             q += " AND (nom LIKE ? OR contact_nom LIKE ?)"; params += [f"%{fn}%"]*2
        q += " ORDER BY pays, nom LIMIT 150"
        pip_list = db.execute(q, params).fetchall()

        if not pip_list:
            st.info("Aucun prospect trouvé.")
        else:
            st.caption(f"{len(pip_list)} prospect(s)")

            # Construire DataFrame éditable
            rows = []
            for p in pip_list:
                retard = ""
                if p["date_prochain_contact"] and p["date_prochain_contact"] < date.today().isoformat():
                    retard = " 🔴"
                rows.append({
                    "_id":               p["id"],
                    "Entreprise":        p["nom"] or "—",
                    "Contact":           p["contact_nom"] or "—",
                    "Pays":              p["pays"] or "—",
                    "Étape":             p["etape"] or "Nouveau prospect",
                    "Prochain contact":  p["date_prochain_contact"] or "",
                    "Notes":             p["notes"] or "",
                    "Email":             p["contact_email"] or "—",
                })
            df_pip = pd.DataFrame(rows)

            edited_pip = st.data_editor(
                df_pip[["Entreprise","Contact","Pays","Étape","Prochain contact","Notes","Email"]],
                column_config={
                    "Entreprise":       st.column_config.TextColumn(width="large"),
                    "Contact":          st.column_config.TextColumn(width="medium"),
                    "Pays":             st.column_config.TextColumn(width="small"),
                    "Étape":            st.column_config.SelectboxColumn(
                                            options=ETAPES, width="medium"),
                    "Prochain contact": st.column_config.TextColumn(
                                            help="Format YYYY-MM-DD", width="small"),
                    "Notes":            st.column_config.TextColumn(width="large"),
                    "Email":            st.column_config.TextColumn(width="medium"),
                },
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                key="pip_editor"
            )

            sv1, sv2 = st.columns(2)
            if sv1.button("💾 Sauvegarder les modifications", type="primary",
                          use_container_width=True, key="pip_save"):
                nb_changes = 0
                for i, row in edited_pip.iterrows():
                    pid   = df_pip.iloc[i]["_id"]
                    orig  = pip_list[i]
                    etape = row["Étape"]
                    notes = row["Notes"]
                    rc    = str(row["Prochain contact"]) if row["Prochain contact"] else None
                    # Détecter changements
                    if (etape != orig["etape"] or notes != (orig["notes"] or "")
                            or rc != orig["date_prochain_contact"]):
                        db.execute("""UPDATE prospection SET etape=?, notes=?,
                            date_prochain_contact=?, updated_at=datetime('now') WHERE id=?""",
                            (etape, notes, rc, pid))
                        # Logger changement d'étape
                        if etape != orig["etape"]:
                            db.execute("""INSERT INTO prospection_interactions
                                (prospect_id, type, contenu) VALUES (?,?,?)""",
                                (pid, "Changement étape",
                                 f"{orig['etape']} → {etape}"))
                        nb_changes += 1
                db.commit()
                if nb_changes:
                    st.success(f"✅ {nb_changes} prospect(s) mis à jour.")
                    st.rerun()
                else:
                    st.info("Aucun changement détecté.")

            # Ajouter interaction / archiver sur un prospect spécifique
            with st.expander("📝 Ajouter une interaction ou archiver un prospect"):
                noms_pip = [f"{p['contact_nom'] or '—'} — {p['nom']} ({p['pays'] or '—'})"
                            for p in pip_list]
                idx_sel = st.selectbox("Prospect", range(len(noms_pip)),
                                       format_func=lambda i: noms_pip[i], key="pip_sel_inter")
                p_sel = pip_list[idx_sel]

                col_i, col_a = st.columns(2)
                with col_i:
                    st.markdown("**📋 Ajouter une interaction**")
                    with st.form("pip_inter_form"):
                        int_type = st.selectbox("Type", [
                            "Email","Appel","WhatsApp","WeChat",
                            "Réunion","Dégustation","Salon","Réponse reçue","Autre"
                        ], key="pip_int_type")
                        int_cont = st.text_input("Résumé", key="pip_int_cont")
                        if st.form_submit_button("➕ Ajouter", use_container_width=True):
                            if int_cont:
                                db.execute("""INSERT INTO prospection_interactions
                                    (prospect_id, type, contenu) VALUES (?,?,?)""",
                                    (p_sel["id"], int_type, int_cont))
                                db.commit(); st.success("✅"); st.rerun()

                with col_a:
                    st.markdown("**📋 Historique**")
                    inters = db.execute(
                        """SELECT * FROM prospection_interactions
                           WHERE prospect_id=? ORDER BY date_interaction DESC LIMIT 5""",
                        (p_sel["id"],)).fetchall()
                    for i in inters:
                        st.markdown(f"- `{i['date_interaction'][:10]}` **{i['type']}** — {i['contenu']}")
                    if not inters:
                        st.caption("Aucune interaction.")

                if st.button("🗑️ Archiver ce prospect", key="pip_arch"):
                    db.execute("UPDATE prospection SET archived=1 WHERE id=?", (p_sel["id"],))
                    db.commit(); st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — NOUVEAU PROSPECT
    # ══════════════════════════════════════════════════════════════════════════
    with tab3:
        with st.form("form_nouveau", clear_on_submit=True):
            n0,n1,n2,n3,n4 = st.columns(5)
            p_civ    = n0.selectbox("Civilité", ["—","M.","Mme","Dr"])
            p_prenom = n1.text_input("Prénom")
            p_nom    = n2.text_input("Société *")
            p_type   = n3.selectbox("Type", ["Importateur / client","Producteur à représenter"])
            p_pays   = n4.selectbox("Pays", [""] + pays_list)
            c1,c2,c3,c4 = st.columns(4)
            p_cnom   = c1.text_input("Nom contact")
            p_cemail = c2.text_input("Email")
            p_cmob   = c3.text_input("Mobile")
            p_cposte = c4.text_input("Poste")
            s1,s2    = st.columns(2)
            p_etape  = s1.selectbox("Étape", ETAPES)
            p_rc     = s2.date_input("Prochain contact", value=None)
            p_source = st.text_input("Source")
            p_notes  = st.text_area("Notes", height=80)
            if st.form_submit_button("💾 Créer", use_container_width=True):
                if not p_nom:
                    st.error("Nom obligatoire.")
                else:
                    rc_str = p_rc.strftime("%Y-%m-%d") if p_rc else None
                    db.execute("""INSERT INTO prospection
                        (civilite,prenom,nom,type,pays,source,etape,
                         contact_nom,contact_email,contact_mobile,contact_poste,
                         date_prochain_contact,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (p_civ,p_prenom,p_nom,p_type,p_pays,p_source,p_etape,
                         p_cnom,p_cemail,p_cmob,p_cposte,rc_str,p_notes))
                    db.commit(); st.success(f"✅ **{p_nom}** créé."); st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — STATISTIQUES
    # ══════════════════════════════════════════════════════════════════════════
    with tab4:
        all_p = db.execute("SELECT etape, pays FROM prospection WHERE archived=0").fetchall()
        by_etape = {}
        for p in all_p: by_etape[p["etape"]] = by_etape.get(p["etape"],0)+1
        if by_etape:
            st.bar_chart(pd.DataFrame(
                [{"Étape":e,"N":n} for e,n in by_etape.items()]).set_index("Étape"))
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total", len(all_p))
        m2.metric("Contactés",   sum(1 for p in all_p if p["etape"]=="Contacté"))
        m3.metric("Convertis",   sum(1 for p in all_p if p["etape"]=="Converti"))
        m4.metric("Refusés",     sum(1 for p in all_p if p["etape"]=="Refusé"))

        # Relances en retard
        retard = db.execute("""SELECT nom, pays, date_prochain_contact FROM prospection
            WHERE archived=0 AND date_prochain_contact < date('now')
            AND etape NOT IN ('Converti','Refusé') ORDER BY date_prochain_contact""").fetchall()
        if retard:
            st.markdown(f"#### 🔴 {len(retard)} relance(s) en retard")
            for r in retard:
                st.markdown(f"- **{r['nom']}** ({r['pays'] or '—'}) · {fmt_date(r['date_prochain_contact'])}")

    db.close()
