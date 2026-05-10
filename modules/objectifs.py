import streamlit as st
import pandas as pd
from database import get_db
from utils import fmt_money
from datetime import date


def _ensure_table(db):
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS objectifs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            annee INTEGER NOT NULL,
            annee_fiscale INTEGER DEFAULT 0,
            debut_fiscal TEXT,
            fin_fiscal TEXT,
            producteur_id INTEGER REFERENCES producteurs(id),
            producteur_nom TEXT,
            pays TEXT,
            type_produit TEXT,
            client_nom TEXT,
            objectif_ca REAL DEFAULT 0,
            objectif_qualitatif TEXT,
            devise TEXT DEFAULT 'EUR',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        # Migration
        for col, defn in [
            ("annee_fiscale",    "INTEGER DEFAULT 0"),
            ("debut_fiscal",     "TEXT"),
            ("fin_fiscal",       "TEXT"),
            ("type_produit",     "TEXT"),
            ("objectif_qualitatif", "TEXT"),
        ]:
            try:
                db.execute(f"ALTER TABLE objectifs ADD COLUMN {col} {defn}")
            except Exception:
                pass
        db.commit()
    except Exception:
        pass


def get_reel(db, annee, prod_id, pays=None, client=None, type_produit=None):
    q = """SELECT COALESCE(SUM(montant),0) as total FROM commandes
           WHERE producteur_id=? AND archived=0
           AND strftime('%Y', COALESCE(date_enlevement, date_commande))=?"""
    params = [prod_id, str(annee)]
    if pays:
        q += " AND pays=?"; params.append(pays)
    if client:
        q += " AND client_nom=?"; params.append(client)
    return db.execute(q, params).fetchone()["total"] or 0


def render():
    st.markdown("## 🎯 Objectifs & Suivi CA")
    db = get_db()
    _ensure_table(db)

    producteurs = db.execute(
        "SELECT * FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()
    pays_list = [p["nom"] for p in db.execute(
        "SELECT nom FROM pays WHERE actif=1 ORDER BY nom").fetchall()]

    annee = st.number_input("Année de référence", min_value=2020, max_value=2035,
                             value=date.today().year, key="obj_annee")

    tab1, tab2, tab3 = st.tabs([
        "📊 Tableau de suivi",
        "➕ Définir un objectif",
        "📈 Analyse graphique",
    ])

    # ══ TABLEAU DE SUIVI ══════════════════════════════════════════════════════
    with tab1:
        objectifs = db.execute(
            "SELECT * FROM objectifs WHERE annee=? ORDER BY producteur_nom, pays, type_produit",
            (int(annee),)
        ).fetchall()

        if not objectifs:
            st.info(f"Aucun objectif défini pour {int(annee)}.")
        else:
            rows = []
            total_obj = 0
            total_reel = 0

            for o in objectifs:
                # Objectif qualitatif pur (sans CA)
                if o["objectif_qualitatif"] and not o["objectif_ca"]:
                    rows.append({
                        "Producteur":  o["producteur_nom"],
                        "Pays":        o["pays"] or "Tous",
                        "Type produit": o["type_produit"] or "Tous",
                        "Client":      o["client_nom"] or "Tous",
                        "Objectif CA": "—",
                        "Réalisé":     "—",
                        "Atteinte":    "—",
                        "Qualitatif":  f"🎯 {o['objectif_qualitatif']}",
                        "Période":     f"Fiscal" if o["annee_fiscale"] else "Civile",
                    })
                    continue

                reel = get_reel(db, annee, o["producteur_id"],
                                o["pays"] or None, o["client_nom"] or None)
                obj  = o["objectif_ca"] or 0
                pct  = int(reel / obj * 100) if obj > 0 else 0
                barre = "█" * min(int(pct/10),10) + "░" * max(0,10-int(pct/10))
                total_obj  += obj
                total_reel += reel

                rows.append({
                    "Producteur":   o["producteur_nom"],
                    "Pays":         o["pays"] or "Tous",
                    "Type produit": o["type_produit"] or "Tous",
                    "Client":       o["client_nom"] or "Tous",
                    "Objectif CA":  fmt_money(obj, o["devise"]),
                    "Réalisé":      fmt_money(reel, o["devise"]),
                    "Atteinte":     f"{pct}% {barre}",
                    "Qualitatif":   o["objectif_qualitatif"] or "—",
                    "Période":      "Fiscal" if o["annee_fiscale"] else "Civile",
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if total_obj > 0:
                pct_g = int(total_reel / total_obj * 100)
                k1,k2,k3,k4 = st.columns(4)
                k1.metric("Objectif global",  fmt_money(total_obj))
                k2.metric("Réalisé global",   fmt_money(total_reel))
                k3.metric("Taux d'atteinte",  f"{pct_g}%")
                k4.metric("Écart",            fmt_money(total_reel - total_obj))
                st.progress(min(pct_g/100, 1.0), text=f"Avancement {int(annee)} : {pct_g}%")

            # Supprimer
            with st.expander("🗑️ Supprimer un objectif"):
                labels = [
                    f"{o['producteur_nom']} / {o['pays'] or 'Tous pays'} / "
                    f"{o['type_produit'] or 'Tous types'} / {o['client_nom'] or 'Tous clients'}"
                    for o in objectifs
                ]
                sel = st.selectbox("Objectif", labels)
                if st.button("Supprimer"):
                    idx = labels.index(sel)
                    db.execute("DELETE FROM objectifs WHERE id=?", (objectifs[idx]["id"],))
                    db.commit(); st.rerun()

    # ══ DÉFINIR UN OBJECTIF ═══════════════════════════════════════════════════
    with tab2:
        with st.form("form_objectif", clear_on_submit=True):
            st.markdown("**Producteur & période**")
            o1,o2,o3 = st.columns(3)
            annee_obj = o1.number_input("Année *", min_value=2020, max_value=2035,
                                         value=date.today().year, key="obj_annee2")
            prod_sel  = o2.selectbox("Producteur *",
                [""] + [p["nom"] for p in producteurs])
            devise    = o3.selectbox("Devise", ["EUR","USD","HKD"])

            # Année fiscale
            annee_fiscale = st.checkbox("Année fiscale (différente de l'année civile)")
            if annee_fiscale:
                af1,af2 = st.columns(2)
                debut_fiscal = af1.text_input("Début année fiscale", placeholder="Ex: 01/03/2026")
                fin_fiscal   = af2.text_input("Fin année fiscale",   placeholder="Ex: 28/02/2027")
                st.caption("Exemple Maison Léda : 1er Mars → fin Février")
            else:
                debut_fiscal = fin_fiscal = ""

            st.markdown("**Granularité** *(laisser vide pour objectif global)*")
            g1,g2,g3 = st.columns(3)
            pays_sel    = g1.selectbox("Pays", ["Tous pays"] + pays_list)
            type_prod   = g2.selectbox("Type de produit",
                ["Tous types"] + ["Armagnac","Cognac","Vin rouge","Vin blanc",
                 "Vin rosé","Champagne","Crémant","Whisky","Autre spiritueux"])
            client_sel  = g3.text_input("Client spécifique", placeholder="Laisser vide = tous")

            st.markdown("**Objectif**")
            ob1,ob2 = st.columns(2)
            obj_ca  = ob1.number_input("Objectif CA (0 si qualitatif uniquement)",
                                        min_value=0.0, step=1000.0)
            obj_qual= ob2.text_input("Objectif qualitatif",
                placeholder="Ex: Vendre du Chambertin Trapet à IWS Thaïlande")

            notes = st.text_area("Notes complémentaires", height=60)

            if st.form_submit_button("💾 Enregistrer l'objectif", use_container_width=True):
                if not prod_sel:
                    st.error("Sélectionnez un producteur.")
                elif not obj_ca and not obj_qual:
                    st.error("Renseignez un objectif CA ou un objectif qualitatif.")
                else:
                    prod_row = next((p for p in producteurs if p["nom"] == prod_sel), None)
                    db.execute("""INSERT INTO objectifs
                        (annee, annee_fiscale, debut_fiscal, fin_fiscal,
                         producteur_id, producteur_nom, pays, type_produit,
                         client_nom, objectif_ca, objectif_qualitatif, devise, notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (int(annee_obj), int(annee_fiscale), debut_fiscal, fin_fiscal,
                         prod_row["id"] if prod_row else None, prod_sel,
                         None if pays_sel == "Tous pays" else pays_sel,
                         None if type_prod == "Tous types" else type_prod,
                         client_sel.strip() or None,
                         obj_ca, obj_qual or None, devise, notes))
                    db.commit()
                    st.success(f"✅ Objectif enregistré pour {prod_sel}.")
                    st.rerun()

    # ══ ANALYSE ═══════════════════════════════════════════════════════════════
    with tab3:
        st.markdown(f"#### CA par producteur — {int(annee)}")
        rows_ca = []
        for prod in producteurs:
            reel = get_reel(db, annee, prod["id"])
            obj_row = db.execute(
                "SELECT COALESCE(SUM(objectif_ca),0) as total FROM objectifs "
                "WHERE annee=? AND producteur_id=? AND pays IS NULL AND type_produit IS NULL",
                (int(annee), prod["id"])
            ).fetchone()
            obj = obj_row["total"] or 0
            if reel > 0 or obj > 0:
                rows_ca.append({"Producteur": prod["nom"],
                                 "CA réalisé": reel, "Objectif": obj})
        if rows_ca:
            st.bar_chart(pd.DataFrame(rows_ca).set_index("Producteur"))

        st.markdown(f"#### CA par pays — {int(annee)}")
        pays_ca = db.execute("""
            SELECT pays, SUM(montant) as total FROM commandes WHERE archived=0
            AND strftime('%Y', COALESCE(date_enlevement, date_commande))=?
            GROUP BY pays ORDER BY total DESC
        """, (str(int(annee)),)).fetchall()
        if pays_ca:
            st.bar_chart(pd.DataFrame([{"Pays": r["pays"], "CA (EUR)": r["total"]}
                                        for r in pays_ca]).set_index("Pays"))

    db.close()
