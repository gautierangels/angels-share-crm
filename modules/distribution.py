import streamlit as st
import pandas as pd
from database import get_db

STATUTS = [
    "Distribué sous votre suivi",
    "Libre / à développer",
    "Déjà ouvert par producteur",
    "Interdit / hors mandat",
    "En discussion",
    "Perdu / arrêté",
    "Non renseigné",
]

STATUT_COLORS = {
    "Distribué sous votre suivi": ("✅", "#27AE60"),
    "Libre / à développer":       ("🔵", "#2E86DE"),
    "Déjà ouvert par producteur": ("🟡", "#F39C12"),
    "Interdit / hors mandat":     ("🔴", "#E74C3C"),
    "En discussion":              ("🟠", "#E67E22"),
    "Perdu / arrêté":             ("⚫", "#555555"),
    "Non renseigné":              ("⚪", "#AAAAAA"),
}


def _migrate(db):
    for sql in [
        "ALTER TABLE distribution ADD COLUMN marque_nom TEXT",
        "ALTER TABLE distribution ADD COLUMN producteur_nom TEXT",
        "ALTER TABLE distribution ADD COLUMN client_actuel TEXT",
        "ALTER TABLE distribution ADD COLUMN exclusivite TEXT",
        "ALTER TABLE distribution ADD COLUMN taux_commission REAL",
        "ALTER TABLE distribution ADD COLUMN archived INTEGER DEFAULT 0",
    ]:
        try:
            db.execute(sql); db.commit()
        except Exception: pass


def render():
    st.markdown("## 🌍 Distribution")
    db = get_db()
    _migrate(db)

    pays_list = [p["nom"] for p in db.execute(
        "SELECT nom FROM pays WHERE actif=1 ORDER BY nom").fetchall()]
    producteurs = db.execute(
        "SELECT * FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()

    if not producteurs:
        st.info("Aucun producteur enregistré.")
        db.close()
        return

    tab1, tab2, tab3 = st.tabs([
        "📊 Vue par producteur",
        "🌍 Vue par pays",
        "✏️ Gérer la distribution",
    ])

    # ══ VUE PAR PRODUCTEUR ═══════════════════════════════════════════════════
    with tab1:
        prod_names = [p["nom"] for p in producteurs]
        sel_prod = st.selectbox("Producteur",
            ["— Sélectionner —"] + prod_names, key="dist_sel_prod")
        if sel_prod == "— Sélectionner —":
            st.info("Sélectionnez un producteur.")
        else:
            prod_row = next(p for p in producteurs if p["nom"] == sel_prod)

            vue = st.radio("Niveau d'affichage",
                           ["Par marque (vue rapide)", "Par produit (vue détaillée)"],
                           horizontal=True)

            # Légende
            st.markdown("**Légende :**")
            leg_cols = st.columns(len(STATUT_COLORS))
            for i, (stat, (icon, color)) in enumerate(STATUT_COLORS.items()):
                leg_cols[i].markdown(
                    f'<span style="background:{color};color:white;padding:2px 8px;'
                    f'border-radius:4px;font-size:0.75rem;">{icon} {stat}</span>',
                    unsafe_allow_html=True)
            st.markdown("---")

            # Récupérer toutes les entrées distribution pour ce producteur
            dist_rows = db.execute("""
                SELECT d.*, c.nb as nb_cmdes
                FROM distribution d
                LEFT JOIN (
                    SELECT pays, producteur_id, COUNT(*) as nb
                    FROM commandes WHERE archived=0
                    GROUP BY pays, producteur_id
                ) c ON c.pays=d.pays AND c.producteur_id=d.producteur_id
                WHERE d.producteur_id=? OR d.producteur_nom=?
            """, (prod_row["id"], sel_prod)).fetchall()

            # Construire index : pays → {marque → [rows]}
            from collections import defaultdict
            pays_marque = defaultdict(lambda: defaultdict(list))
            for r in dist_rows:
                marque = r["marque_nom"] or "(Toutes marques)"
                pays_marque[r["pays"]][marque].append(r)

            # Ajouter les pays sans entrée distribution
            all_pays_in_dist = set(pays_marque.keys())

            st.markdown(f"### {sel_prod} — {vue.split('(')[0].strip()}")

            if vue == "Par marque (vue rapide)":
                # Vue consolidée : un ligne par pays, statut le plus pertinent
                rows_display = []
                for pays in sorted(all_pays_in_dist):
                    marques_data = pays_marque[pays]
                    # Consolider : liste des marques distribuées
                    marques_dist = []
                    clients_dist = []
                    statut_global = "Non renseigné"
                    nb_cmdes = 0

                    for marque, entries in marques_data.items():
                        for e in entries:
                            if e["statut"] == "Distribué sous votre suivi":
                                statut_global = "Distribué sous votre suivi"
                                if marque != "(Toutes marques)" and marque not in marques_dist:
                                    marques_dist.append(marque)
                                if e["client_actuel"] and e["client_actuel"] not in clients_dist:
                                    clients_dist.append(e["client_actuel"])
                            nb_cmdes += (e["nb_cmdes"] or 0)

                    if statut_global == "Non renseigné":
                        # Prendre le premier statut trouvé
                        for marque, entries in marques_data.items():
                            if entries:
                                statut_global = entries[0]["statut"] or "Non renseigné"
                                break

                    icon, color = STATUT_COLORS.get(statut_global, ("⚪", "#AAAAAA"))
                    marques_str = " · ".join(marques_dist) if marques_dist else "—"
                    clients_str = " · ".join(clients_dist) if clients_dist else "—"
                    comm = "✅" if any(e["commission_applicable"] for m in marques_data.values() for e in m) else "❌"

                    rows_display.append({
                        "Pays":         pays,
                        "Statut":       f"{icon} {statut_global}",
                        "Marques distribuées": marques_str,
                        "Client(s) actuel(s)": clients_str,
                        "Commission":   comm,
                        "Cmdes actives": nb_cmdes if nb_cmdes else "—",
                    })

                if rows_display:
                    df = pd.DataFrame(rows_display)
                    st.dataframe(df, use_container_width=True, hide_index=True,
                                 column_config={
                                     "Statut": st.column_config.TextColumn(width="medium"),
                                     "Marques distribuées": st.column_config.TextColumn(width="large"),
                                     "Client(s) actuel(s)": st.column_config.TextColumn(width="large"),
                                 })
                    st.caption(f"{len(rows_display)} pays · "
                               f"{sum(1 for r in rows_display if '✅' in r['Statut'])} sous votre suivi")
                else:
                    st.info("Aucune entrée de distribution pour ce producteur.")

            else:  # Vue par produit
                # Récupérer les marques/produits du catalogue
                marques_catalogue = db.execute("""
                    SELECT DISTINCT nom FROM produits
                    WHERE producteur_id=? ORDER BY nom
                """, (prod_row["id"],)).fetchall()
                marques_noms = [m["nom"] for m in marques_catalogue]

                # Ajouter les marques de distribution non dans le catalogue
                for pays, marques_data in pays_marque.items():
                    for marque in marques_data.keys():
                        if marque != "(Toutes marques)" and marque not in marques_noms:
                            marques_noms.append(marque)
                marques_noms = sorted(set(marques_noms))

                if not marques_noms:
                    st.info("Aucun produit enregistré pour ce producteur.")
                else:
                    # Construire la matrice pays × marque
                    # Index rapide : (pays, marque) → statut
                    dist_index = {}
                    client_index = {}
                    for pays, marques_data in pays_marque.items():
                        for marque, entries in marques_data.items():
                            key = (pays, marque)
                            for e in entries:
                                if e["statut"] == "Distribué sous votre suivi":
                                    dist_index[key] = e["statut"]
                                    if e["client_actuel"]:
                                        client_index[key] = e["client_actuel"]
                                    break
                                elif key not in dist_index:
                                    dist_index[key] = e["statut"] or "Non renseigné"

                    # Construire index multi-clients : (pays, marque) → [clients]
                    multi_client_index = {}
                    for pays, marques_data in pays_marque.items():
                        for marque, entries in marques_data.items():
                            key = (pays, marque)
                            clients = [e["client_actuel"] for e in entries
                                       if e["client_actuel"] and e["statut"] == "Distribué sous votre suivi"]
                            if clients:
                                multi_client_index[key] = clients

                    # Construire DataFrame
                    all_pays_sorted = sorted(all_pays_in_dist)
                    table_data = []
                    for pays in all_pays_sorted:
                        row = {"Pays": pays}
                        for marque in marques_noms:
                            key_exact = (pays, marque)
                            key_all   = (pays, "(Toutes marques)")
                            statut = dist_index.get(key_exact) or dist_index.get(key_all) or "Non renseigné"
                            icon, _ = STATUT_COLORS.get(statut, ("⚪","#AAAAAA"))
                            # Récupérer TOUS les clients
                            clients = multi_client_index.get(key_exact) or multi_client_index.get(key_all) or []
                            if clients and statut == "Distribué sous votre suivi":
                                row[marque] = "✅ " + " · ".join(clients)
                            else:
                                row[marque] = icon
                        table_data.append(row)

                    if table_data:
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        # Légende compacte sous le tableau
                        st.caption("✅ Distribué · 🔵 Libre · 🟡 Déjà ouvert · 🔴 Interdit · 🟠 En discussion · ⚫ Perdu · ⚪ Non renseigné")

    # ══ VUE PAR PAYS ══════════════════════════════════════════════════════════
    with tab2:
        sel_pays = st.selectbox("Pays", [""] + pays_list)
        if not sel_pays:
            st.info("Sélectionnez un pays pour voir sa distribution.")
        else:
            dist_pays = db.execute("""
                SELECT * FROM distribution
                WHERE pays=? ORDER BY producteur_nom, marque_nom
            """, (sel_pays,)).fetchall()

            # Aussi chercher via commandes
            cmdes_pays = db.execute("""
                SELECT DISTINCT producteur_nom, client_nom
                FROM commandes WHERE pays=? AND archived=0
            """, (sel_pays,)).fetchall()

            st.markdown(f"### Distribution — {sel_pays}")

            if dist_pays:
                rows = []
                for d in dist_pays:
                    icon, _ = STATUT_COLORS.get(d["statut"] or "Non renseigné", ("⚪",""))
                    rows.append({
                        "Producteur":  d["producteur_nom"] or "—",
                        "Marque":      d["marque_nom"] or "(Toutes marques)",
                        "Statut":      f"{icon} {d['statut'] or 'Non renseigné'}",
                        "Client":      d["client_actuel"] or "—",
                        "Exclusivité": d["exclusivite"] or "—",
                        "Commission":  "✅" if d["commission_applicable"] else "❌",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info(f"Aucune entrée de distribution pour {sel_pays}.")

            if cmdes_pays:
                st.markdown("**Commandes actives dans ce pays :**")
                for c in cmdes_pays:
                    st.markdown(f"• {c['producteur_nom']} → {c['client_nom']}")

    # ══ GÉRER LA DISTRIBUTION ══════════════════════════════════════════════════
    with tab3:
        st.markdown("#### Ajouter / modifier une entrée")

        with st.form("f_add_dist", clear_on_submit=True):
            d1, d2, d3 = st.columns(3)
            d_prod  = d1.selectbox("Producteur *",
                ["— Sélectionner —"] + [p["nom"] for p in producteurs])
            d_pays  = d2.selectbox("Pays *", [""] + pays_list)
            d_stat  = d3.selectbox("Statut *", STATUTS)

            # Marques du producteur sélectionné
            marques_prod = []
            if d_prod:
                prod_r = next((p for p in producteurs if p["nom"] == d_prod), None)
                if prod_r:
                    marques_prod = [m["nom"] for m in db.execute(
                        "SELECT nom FROM produits WHERE producteur_id=? ORDER BY nom",
                        (prod_r["id"],)).fetchall()]

            d4, d5 = st.columns(2)
            mode_marque = d4.radio("Marque / Domaine",
                ["Choisir existante", "Saisir manuellement"],
                horizontal=True, key="dist_mode_marque")
            if mode_marque == "Choisir existante":
                d_marque = d4.selectbox("Marque",
                    ["(Toutes marques)"] + marques_prod, key="dist_marque_sel")
                d_nouvelle_marque = ""
            else:
                d_nouvelle_marque = d4.text_input(
                    "Nouvelle marque / domaine *",
                    placeholder="Ex: Château La Rose Nouvelle",
                    key="dist_marque_new")
                d_marque = d_nouvelle_marque
                if d_nouvelle_marque:
                    d4.caption("✅ Sera ajoutée définitivement au catalogue du producteur.")
            d_client = d5.text_input("Client actuel")

            d6, d7 = st.columns(2)
            d_exclu = d6.text_input("Exclusivité géographique",
                placeholder="Ex: National / Duty Free / Nord Chine")
            d_comm  = d7.checkbox("Commission applicable", value=True)
            d_notes = st.text_input("Notes")

            if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                if not d_prod or d_prod == "— Sélectionner —" or not d_pays:
                    st.error("Producteur et pays sont obligatoires.")
                else:
                    prod_r = next((p for p in producteurs if p["nom"] == d_prod), None)
                    prod_id = prod_r["id"] if prod_r else None
                    marque_val = d_marque if d_marque not in ("(Toutes marques)", "") else None

                    # Enregistrer nouvelle marque dans produits si saisie manuellement
                    if marque_val and prod_id and marque_val not in marques_prod:
                        exist = db.execute(
                            "SELECT id FROM produits WHERE producteur_id=? AND nom=?",
                            (prod_id, marque_val)).fetchone()
                        if not exist:
                            db.execute(
                                "INSERT INTO produits (producteur_id, nom) VALUES (?,?)",
                                (prod_id, marque_val))
                            db.commit()

                    ex = db.execute("""
                        SELECT id FROM distribution
                        WHERE (producteur_id=? OR producteur_nom=?)
                        AND pays=?
                        AND (marque_nom=? OR (marque_nom IS NULL AND ? IS NULL))
                        AND (client_actuel=? OR client_actuel IS NULL OR client_actuel='')
                    """, (prod_id, d_prod, d_pays,
                          marque_val, marque_val,
                          d_client)).fetchone()

                    if ex:
                        db.execute("""UPDATE distribution SET
                            statut=?, client_actuel=?, exclusivite=?,
                            commission_applicable=?, notes=? WHERE id=?""",
                            (d_stat, d_client, d_exclu, int(d_comm), d_notes, ex["id"]))
                        st.success("✅ Mis à jour.")
                    else:
                        db.execute("""INSERT INTO distribution
                            (producteur_id, producteur_nom, marque_nom, pays,
                             statut, client_actuel, exclusivite,
                             commission_applicable, notes)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                            (prod_id, d_prod, marque_val, d_pays,
                             d_stat, d_client, d_exclu, int(d_comm), d_notes))
                        st.success("✅ Entrée créée.")
                    db.commit()
                    st.rerun()

        # Liste des entrées avec suppression
        st.markdown("#### Entrées existantes")
        f_prod_d = st.selectbox("Filtrer par producteur",
                                ["Tous"] + [p["nom"] for p in producteurs],
                                key="f_prod_dist")
        q = "SELECT * FROM distribution WHERE 1=1"
        params = []
        if f_prod_d != "Tous":
            q += " AND (producteur_nom=? OR producteur_id=(SELECT id FROM producteurs WHERE nom=? LIMIT 1))"
            params += [f_prod_d, f_prod_d]
        q += " ORDER BY producteur_nom, pays, marque_nom"
        all_dist = db.execute(q, params).fetchall()

        if all_dist:
            for d in all_dist:
                icon, _ = STATUT_COLORS.get(d["statut"] or "Non renseigné", ("⚪",""))
                with st.expander(
                    f"{icon} **{d['producteur_nom']}** · "
                    f"{d['marque_nom'] or '(Toutes marques)'} · "
                    f"**{d['pays']}** — {d['statut']}"
                ):
                    st.markdown(
                        f"Client actuel : **{d['client_actuel'] or '—'}** · "
                        f"Exclusivité : {d['exclusivite'] or '—'}"
                    )
                    # Formulaire de modification
                    with st.form(f"edit_dist_{d['id']}"):
                        ec1, ec2, ec3 = st.columns(3)
                        new_statut = ec1.selectbox("Statut", STATUTS,
                            index=STATUTS.index(d["statut"]) if d["statut"] in STATUTS else 0,
                            key=f"eds_{d['id']}")
                        new_client = ec2.text_input("Client actuel",
                            value=d["client_actuel"] or "", key=f"edc_{d['id']}")
                        new_exclu  = ec3.text_input("Exclusivité",
                            value=d["exclusivite"] or "", key=f"ede_{d['id']}")
                        new_notes  = st.text_input("Notes",
                            value=d["notes"] or "", key=f"edn_{d['id']}")

                        # Marque — modifiable
                        marques_prod_e = [m["nom"] for m in db.execute(
                            "SELECT nom FROM produits WHERE producteur_id=? ORDER BY nom",
                            (d["producteur_id"],)).fetchall()] if d["producteur_id"] else []
                        marque_actuelle = d["marque_nom"] or "(Toutes marques)"
                        opts_marque = ["(Toutes marques)"] + marques_prod_e
                        idx_marque = opts_marque.index(marque_actuelle) if marque_actuelle in opts_marque else 0
                        new_marque = st.selectbox("Marque / Domaine", opts_marque,
                            index=idx_marque, key=f"edm_{d['id']}")
                        # Option saisir manuellement
                        new_marque_libre = st.text_input(
                            "Ou saisir une nouvelle marque",
                            placeholder="Laisser vide pour utiliser la sélection ci-dessus",
                            key=f"edml_{d['id']}")

                        ef1, ef2, ef3 = st.columns(3)
                        if ef1.form_submit_button("💾 Modifier", use_container_width=True):
                            marque_val = (new_marque_libre.strip() if new_marque_libre.strip()
                                          else (new_marque if new_marque != "(Toutes marques)" else None))
                            # Ajouter nouvelle marque au catalogue si nécessaire
                            if new_marque_libre.strip() and d["producteur_id"]:
                                ex_m = db.execute(
                                    "SELECT id FROM produits WHERE producteur_id=? AND nom=?",
                                    (d["producteur_id"], new_marque_libre.strip())).fetchone()
                                if not ex_m:
                                    db.execute(
                                        "INSERT INTO produits (producteur_id, nom) VALUES (?,?)",
                                        (d["producteur_id"], new_marque_libre.strip()))
                            db.execute("""UPDATE distribution SET
                                statut=?, client_actuel=?, exclusivite=?,
                                marque_nom=?, notes=? WHERE id=?""",
                                (new_statut, new_client, new_exclu,
                                 marque_val, new_notes, d["id"]))
                            db.commit()
                            st.success("✅ Mis à jour.")
                            st.rerun()
                        if ef2.form_submit_button("🗑️ Supprimer", use_container_width=True):
                            db.execute("DELETE FROM distribution WHERE id=?", (d["id"],))
                            db.commit()
                            st.rerun()
        else:
            st.info("Aucune entrée.")

    db.close()
