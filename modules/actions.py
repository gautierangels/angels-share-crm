import streamlit as st
import pandas as pd
from database import get_db
from utils import fmt_date
from datetime import date


def render():
    st.markdown("## ✅ Actions & To-do")
    db = get_db()

    tab1, tab2 = st.tabs(["📋 Liste des actions", "➕ Nouvelle action"])

    with tab1:
        c1, c2, c3 = st.columns(3)
        f_prio   = c1.selectbox("Priorité", ["Toutes", "Urgente", "Haute", "Normale", "Basse"])
        f_statut = c2.selectbox("Statut",   ["En cours", "Tous", "À faire", "En cours", "En attente", "Fait"])
        f_entite = c3.selectbox("Type",     ["Tous", "Commande", "Client", "Prospect", "Producteur", "Salon / voyage", "Général"])

        q = "SELECT * FROM actions WHERE 1=1"
        params = []
        if f_statut == "En cours":
            q += " AND statut != 'Fait'"
        elif f_statut != "Tous":
            q += " AND statut=?"; params.append(f_statut)
        if f_prio != "Toutes":
            q += " AND priorite=?"; params.append(f_prio)
        if f_entite != "Tous":
            q += " AND entite_type=?"; params.append(f_entite)
        q += " ORDER BY CASE priorite WHEN 'Urgente' THEN 0 WHEN 'Haute' THEN 1 WHEN 'Normale' THEN 2 ELSE 3 END, due_date NULLS LAST"
        actions = db.execute(q, params).fetchall()

        prio_icon = {"Urgente": "🔴", "Haute": "🟠", "Normale": "🔵", "Basse": "⚪"}
        today = date.today()

        for a in actions:
            icon    = prio_icon.get(a["priorite"], "⚪")
            overdue = a["due_date"] and a["due_date"] < today.isoformat() and a["statut"] != "Fait"

            with st.container():
                col_check, col_info, col_act = st.columns([0.5, 6, 2])

                with col_info:
                    titre_style = "color:#c0392b;font-weight:600;" if overdue else ""
                    due_str = f" · 📅 {fmt_date(a['due_date'])}" if a["due_date"] else ""
                    st.markdown(
                        f"<div style='{titre_style}'>{icon} <b>{a['titre']}</b></div>"
                        f"<small style='color:#888'>{a['entite_type'] or ''}  ·  {a['priorite']}{due_str}  ·  {a['statut']}</small>"
                        + (f"<br><small style='color:#555'>{a['notes']}</small>" if a["notes"] else ""),
                        unsafe_allow_html=True
                    )

                with col_act:
                    if a["statut"] != "Fait":
                        if st.button("✅ Fait", key=f"done_{a['id']}", help="Marquer comme terminé"):
                            db.execute("UPDATE actions SET statut='Fait' WHERE id=?", (a["id"],))
                            db.commit()
                            st.rerun()
                    if st.button("🗑️", key=f"del_{a['id']}", help="Supprimer"):
                        db.execute("DELETE FROM actions WHERE id=?", (a["id"],))
                        db.commit()
                        st.rerun()

                st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid #eee'>",
                            unsafe_allow_html=True)

        if not actions:
            st.success("🎉 Aucune action en cours — bien joué !")

    with tab2:
        with st.form("form_action", clear_on_submit=True):
            titre = st.text_input("Titre de l'action *", placeholder="Ex: Relancer Dragon Cellar…")
            a1, a2, a3, a4 = st.columns(4)
            entite  = a1.selectbox("Type d'entité", ["Général", "Commande", "Client", "Prospect",
                                                      "Producteur", "Salon / voyage"])
            prio    = a2.selectbox("Priorité", ["Normale", "Urgente", "Haute", "Basse"])
            statut  = a3.selectbox("Statut",   ["À faire", "En cours", "En attente"])
            due     = a4.date_input("Échéance", value=None)
            notes   = st.text_area("Notes", height=80)

            if st.form_submit_button("💾 Créer l'action", use_container_width=True):
                if not titre:
                    st.error("Le titre est obligatoire.")
                else:
                    due_s = due.strftime("%Y-%m-%d") if due else None
                    db.execute(
                        "INSERT INTO actions (titre,entite_type,priorite,statut,due_date,notes) VALUES (?,?,?,?,?,?)",
                        (titre, entite, prio, statut, due_s, notes)
                    )
                    db.commit()
                    st.success("✅ Action créée.")
                    st.rerun()

    db.close()
