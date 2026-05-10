import streamlit as st
import pandas as pd
from database import get_db
from utils import fmt_date
from datetime import date


TYPES_INTERACTION = [
    "Email", "Appel téléphonique", "WhatsApp", "WeChat",
    "Réunion", "Dégustation", "Formation / masterclass",
    "Visite client", "Relance paiement", "Autre",
]


def _ensure_table(db):
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_interaction TEXT DEFAULT (datetime('now')),
            type TEXT,
            entite_type TEXT,
            entite_id INTEGER,
            entite_nom TEXT,
            description TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        db.commit()
    except Exception:
        pass


def render():
    st.markdown("## 💬 Interactions")
    db = get_db()
    _ensure_table(db)

    producteurs = db.execute(
        "SELECT id, nom FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()
    entreprises = db.execute(
        "SELECT id, nom FROM entreprises WHERE archived=0 ORDER BY nom").fetchall()

    tab1, tab2 = st.tabs(["📋 Historique", "➕ Nouvelle interaction"])

    # ══ HISTORIQUE ════════════════════════════════════════════════════════════
    with tab1:
        c1, c2, c3 = st.columns(3)
        f_type   = c1.selectbox("Type", ["Tous"] + TYPES_INTERACTION, key="int_ftype")
        f_entite = c2.selectbox("Entité", ["Toutes", "Producteur", "Client",
                                            "Prospect", "Commande"], key="int_fent")
        f_search = c3.text_input("Recherche", placeholder="Nom, description…")

        q = "SELECT * FROM interactions WHERE 1=1"
        params = []
        if f_type != "Tous":
            q += " AND type=?"; params.append(f_type)
        if f_entite != "Toutes":
            q += " AND entite_type=?"; params.append(f_entite)
        if f_search:
            q += " AND (entite_nom LIKE ? OR description LIKE ?)"
            params += [f"%{f_search}%", f"%{f_search}%"]
        q += " ORDER BY date_interaction DESC LIMIT 200"

        interactions = db.execute(q, params).fetchall()

        if not interactions:
            st.info("Aucune interaction enregistrée.")
        else:
            st.caption(f"{len(interactions)} interaction(s)")
            type_icon = {
                "Email": "📧", "Appel téléphonique": "📞",
                "WhatsApp": "💬", "WeChat": "🟢",
                "Réunion": "🤝", "Dégustation": "🥂",
                "Formation / masterclass": "📚",
                "Visite client": "🏢", "Relance paiement": "💰",
                "Autre": "📌",
            }
            for i in interactions:
                icon = type_icon.get(i["type"], "📌")
                col_info, col_del = st.columns([10, 1])
                with col_info:
                    st.markdown(
                        f"{icon} **{i['type']}** — "
                        f"{i['entite_nom'] or '—'} "
                        f"<small style='color:#888'>({i['entite_type'] or '—'})</small>  \n"
                        f"{i['description'] or '—'}  \n"
                        f"<small style='color:#aaa'>{fmt_date(i['date_interaction'][:10])}"
                        + (f" · {i['notes']}" if i["notes"] else "")
                        + "</small>",
                        unsafe_allow_html=True
                    )
                with col_del:
                    if st.button("🗑️", key=f"del_int_{i['id']}"):
                        db.execute("DELETE FROM interactions WHERE id=?", (i["id"],))
                        db.commit()
                        st.rerun()
                st.markdown(
                    "<hr style='margin:4px 0;border:none;border-top:1px solid #eee'>",
                    unsafe_allow_html=True)

    # ══ NOUVELLE INTERACTION ══════════════════════════════════════════════════
    with tab2:
        with st.form("form_interaction", clear_on_submit=True):
            i1, i2 = st.columns(2)
            type_sel = i1.selectbox("Type d'interaction *", TYPES_INTERACTION)
            date_sel = i2.date_input("Date *", value=date.today())

            i3, i4 = st.columns(2)
            entite_type = i3.selectbox("Type d'entité", [
                "Producteur", "Client", "Prospect", "Commande", "Général"
            ])

            entite_options = {"Producteur": producteurs, "Client": entreprises}
            if entite_type in entite_options:
                noms = [e["nom"] for e in entite_options[entite_type]]
                entite_nom = i4.selectbox("Entité", [""] + noms)
            else:
                entite_nom = i4.text_input("Entité / référence")

            description = st.text_area("Description *", height=100,
                placeholder="Résumé de l'échange, points discutés, suite à donner…")
            notes = st.text_input("Notes complémentaires")

            if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                if not description:
                    st.error("La description est obligatoire.")
                else:
                    db.execute("""INSERT INTO interactions
                        (date_interaction, type, entite_type, entite_nom, description, notes)
                        VALUES (?,?,?,?,?,?)""",
                        (date_sel.strftime("%Y-%m-%d"), type_sel,
                         entite_type, entite_nom, description, notes))
                    db.commit()
                    st.success("✅ Interaction enregistrée.")
                    st.rerun()

    db.close()
