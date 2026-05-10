import streamlit as st
import pandas as pd
from database import get_db
from utils import fmt_date
from datetime import date, datetime, timedelta


def _ensure_table(db):
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS evenements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            type TEXT DEFAULT 'Réunion',
            date_debut TEXT NOT NULL,
            date_fin TEXT,
            heure_debut TEXT,
            heure_fin TEXT,
            lieu TEXT,
            ville TEXT,
            pays TEXT,
            producteur_id INTEGER,
            producteur_nom TEXT,
            contact_nom TEXT,
            entreprise_nom TEXT,
            objectif TEXT,
            produits TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            archived INTEGER DEFAULT 0
        )""")
        db.commit()
    except Exception:
        pass


TYPES_EVENT = [
    "Salon / foire",
    "Voyage",
    "Réunion client",
    "Réunion producteur",
    "Masterclass / dégustation",
    "Formation",
    "Autre",
]

TYPE_ICON = {
    "Salon / foire":             "🍷",
    "Voyage":                    "✈️",
    "Réunion client":            "🤝",
    "Réunion producteur":        "🏭",
    "Masterclass / dégustation": "🥂",
    "Formation":                 "📚",
    "Autre":                     "📌",
}


def detect_conflicts(db, date_debut, date_fin, exclude_id=None):
    q = """SELECT * FROM evenements WHERE archived=0
           AND date_debut <= ? AND (date_fin >= ? OR (date_fin IS NULL AND date_debut >= ?))"""
    params = [date_fin or date_debut, date_debut, date_debut]
    if exclude_id:
        q += " AND id != ?"; params.append(exclude_id)
    return db.execute(q, params).fetchall()


def generate_ics(events) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Angels Share CRM//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for e in events:
        uid = f"angels-{e['id']}@angelsshare"
        dt_start = e["date_debut"].replace("-", "")
        dt_end   = (e["date_fin"] or e["date_debut"]).replace("-", "")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;VALUE=DATE:{dt_start}",
            f"DTEND;VALUE=DATE:{dt_end}",
            f"SUMMARY:{e['titre']}",
            f"LOCATION:{e['lieu'] or ''} {e['ville'] or ''} {e['pays'] or ''}".strip(),
            f"DESCRIPTION:{(e['objectif'] or e['notes'] or '').replace(chr(10), ' ')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def render():
    st.markdown("## 📅 Calendrier & Salons")
    db = get_db()
    _ensure_table(db)

    pays_list = [p["nom"] for p in db.execute(
        "SELECT nom FROM pays WHERE actif=1 ORDER BY nom").fetchall()]
    producteurs = db.execute(
        "SELECT * FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()

    tab1, tab2, tab3 = st.tabs([
        "📅 Agenda", "➕ Nouvel événement", "✏️ Modifier / Supprimer"
    ])

    # ══ AGENDA ════════════════════════════════════════════════════════════════
    with tab1:
        c1, c2, c3 = st.columns(3)
        f_type    = c1.selectbox("Type", ["Tous"] + TYPES_EVENT, key="cal_ftype")
        f_horizon = c2.selectbox("Période", [
            "À venir (30 jours)", "À venir (90 jours)",
            "Tout l'avenir", "Passés", "Tous"
        ])
        f_prod = c3.selectbox("Producteur", ["Tous"] + [p["nom"] for p in producteurs],
                              key="cal_fprod")

        today = date.today().isoformat()
        q = "SELECT * FROM evenements WHERE archived=0"
        params = []

        if f_type != "Tous":
            q += " AND type=?"; params.append(f_type)
        if f_prod != "Tous":
            q += " AND producteur_nom=?"; params.append(f_prod)
        if f_horizon == "À venir (30 jours)":
            q += " AND date_debut >= ? AND date_debut <= ?"
            params += [today, (date.today() + timedelta(days=30)).isoformat()]
        elif f_horizon == "À venir (90 jours)":
            q += " AND date_debut >= ? AND date_debut <= ?"
            params += [today, (date.today() + timedelta(days=90)).isoformat()]
        elif f_horizon == "Tout l'avenir":
            q += " AND date_debut >= ?"; params.append(today)
        elif f_horizon == "Passés":
            q += " AND date_debut < ?"; params.append(today)

        q += " ORDER BY date_debut"
        events = db.execute(q, params).fetchall()

        # Export ICS
        if events:
            ics_data = generate_ics(events)
            st.download_button(
                "📆 Exporter vers Apple Calendar / Outlook (.ics)",
                data=ics_data.encode("utf-8"),
                file_name="angels_share_agenda.ics",
                mime="text/calendar"
            )

        if not events:
            st.info("Aucun événement trouvé.")
        else:
            # Grouper par mois
            current_month = ""
            for e in events:
                try:
                    dt = datetime.strptime(e["date_debut"], "%Y-%m-%d")
                    month_label = dt.strftime("%B %Y").capitalize()
                except Exception:
                    month_label = e["date_debut"]

                if month_label != current_month:
                    st.markdown(f"### {month_label}")
                    current_month = month_label

                icon = TYPE_ICON.get(e["type"], "📌")
                date_str = fmt_date(e["date_debut"])
                if e["date_fin"] and e["date_fin"] != e["date_debut"]:
                    date_str += f" → {fmt_date(e['date_fin'])}"

                lieu_str = " · ".join(filter(None, [e["lieu"], e["ville"], e["pays"]]))

                with st.container():
                    col_icon, col_info = st.columns([0.5, 9])
                    col_icon.markdown(f"<div style='font-size:1.5rem;'>{icon}</div>",
                                      unsafe_allow_html=True)
                    with col_info:
                        st.markdown(
                            f"**{e['titre']}** — {date_str}  \n"
                            f"<small style='color:#666'>{e['type']}"
                            + (f" · {lieu_str}" if lieu_str else "")
                            + (f" · {e['producteur_nom']}" if e["producteur_nom"] else "")
                            + (f" · {e['contact_nom']}" if e["contact_nom"] else "")
                            + "</small>"
                            + (f"  \n*{e['objectif']}*" if e["objectif"] else ""),
                            unsafe_allow_html=True
                        )
                    st.markdown(
                        "<hr style='margin:6px 0;border:none;border-top:1px solid #eee'>",
                        unsafe_allow_html=True)

    # ══ NOUVEL ÉVÉNEMENT ══════════════════════════════════════════════════════
    with tab2:
        with st.form("form_event", clear_on_submit=True):
            st.markdown("**Informations générales**")
            e1, e2 = st.columns(2)
            titre    = e1.text_input("Titre *", placeholder="Ex: Vinexpo Asia 2026")
            type_evt = e2.selectbox("Type", TYPES_EVENT)

            e3, e4, e5, e6 = st.columns(4)
            date_debut = e3.date_input("Date début *", value=date.today())
            date_fin   = e4.date_input("Date fin", value=None)
            heure_deb  = e5.text_input("Heure début", placeholder="09:00")
            heure_fin  = e6.text_input("Heure fin",   placeholder="18:00")

            st.markdown("**Lieu**")
            l1, l2, l3 = st.columns(3)
            lieu  = l1.text_input("Lieu / Venue", placeholder="Ex: Palais des congrès")
            ville = l2.text_input("Ville",        placeholder="Hong Kong")
            pays  = l3.selectbox("Pays", [""] + pays_list)

            st.markdown("**Liens**")
            r1, r2, r3 = st.columns(3)
            prod_sel = r1.selectbox("Producteur lié", [""] + [p["nom"] for p in producteurs])
            contact  = r2.text_input("Contact / prospect")
            societe  = r3.text_input("Entreprise")

            objectif = st.text_input("Objectif de l'événement",
                placeholder="Ex: Présenter gamme Léda aux importateurs HK")
            produits = st.text_input("Produits / échantillons à apporter")
            notes    = st.text_area("Notes", height=70)

            submitted = st.form_submit_button("💾 Créer l'événement", use_container_width=True)
            if submitted:
                if not titre:
                    st.error("Le titre est obligatoire.")
                else:
                    dd = date_debut.strftime("%Y-%m-%d")
                    df_str = date_fin.strftime("%Y-%m-%d") if date_fin else dd

                    # Détection conflits
                    conflicts = detect_conflicts(db, dd, df_str)
                    if conflicts:
                        st.warning(
                            f"⚠️ Conflit détecté avec : "
                            + ", ".join(c["titre"] for c in conflicts)
                            + " — événement enregistré quand même."
                        )

                    prod_row = next(
                        (p for p in producteurs if p["nom"] == prod_sel), None)
                    db.execute("""INSERT INTO evenements
                        (titre, type, date_debut, date_fin, heure_debut, heure_fin,
                         lieu, ville, pays, producteur_id, producteur_nom,
                         contact_nom, entreprise_nom, objectif, produits, notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (titre, type_evt, dd, df_str, heure_deb, heure_fin,
                         lieu, ville, pays,
                         prod_row["id"] if prod_row else None,
                         prod_sel or None, contact or None,
                         societe or None, objectif, produits, notes))
                    db.commit()
                    st.success(f"✅ Événement **{titre}** créé.")
                    st.rerun()

    # ══ MODIFIER / SUPPRIMER ══════════════════════════════════════════════════
    with tab3:
        all_events = db.execute(
            "SELECT * FROM evenements WHERE archived=0 ORDER BY date_debut DESC"
        ).fetchall()
        if not all_events:
            st.info("Aucun événement.")
        else:
            sel_label = st.selectbox("Événement",
                [f"{fmt_date(e['date_debut'])} — {e['titre']}" for e in all_events])
            idx = [f"{fmt_date(e['date_debut'])} — {e['titre']}"
                   for e in all_events].index(sel_label)
            sel = all_events[idx]

            with st.form("form_edit_event"):
                new_titre = st.text_input("Titre", value=sel["titre"])
                ec1, ec2 = st.columns(2)
                new_obj   = ec1.text_input("Objectif", value=sel["objectif"] or "")
                new_notes = ec2.text_area("Notes", value=sel["notes"] or "", height=80)

                es1, es2 = st.columns(2)
                if es1.form_submit_button("💾 Sauvegarder", use_container_width=True):
                    db.execute(
                        "UPDATE evenements SET titre=?, objectif=?, notes=? WHERE id=?",
                        (new_titre, new_obj, new_notes, sel["id"]))
                    db.commit()
                    st.success("✅ Mis à jour.")
                    st.rerun()
                if es2.form_submit_button("🗑️ Supprimer", use_container_width=True):
                    db.execute("DELETE FROM evenements WHERE id=?", (sel["id"],))
                    db.commit()
                    st.rerun()

    db.close()
