import streamlit as st
import pandas as pd
from database import get_db
from utils import fmt_date, fmt_money
from datetime import date


# ── Migrations ────────────────────────────────────────────────────────────────
def _migrate(db):
    for col, defn in [
        ("contrat_signe",  "INTEGER DEFAULT 0"),
        ("date_contrat",   "TEXT"),
        ("prenom",         "TEXT"),
        ("civilite",       "TEXT"),
        ("tel_general",    "TEXT"),
        ("adresse_ligne1", "TEXT"),
        ("adresse_ligne2", "TEXT"),
        ("code_postal",    "TEXT"),
        ("ville",          "TEXT"),
        ("pays_adresse",   "TEXT"),
        ("tarifs_envoyes", "INTEGER DEFAULT 0"),
    ]:
        try: db.execute(f"ALTER TABLE producteurs ADD COLUMN {col} {defn}"); db.commit()
        except: pass
    for col, defn in [
        ("prenom","TEXT"),("civilite","TEXT"),("date_naissance","TEXT"),
        ("adresse_ligne1","TEXT"),("adresse_ligne2","TEXT"),
        ("code_postal","TEXT"),("ville","TEXT"),("pays_adresse","TEXT"),
    ]:
        try: db.execute(f"ALTER TABLE producteur_contacts ADD COLUMN {col} {defn}"); db.commit()
        except: pass
    for col, defn in [
        ("marque_nom","TEXT"),("producteur_nom","TEXT"),("client_actuel","TEXT"),
        ("exclusivite","TEXT"),("taux_commission","REAL"),("archived","INTEGER DEFAULT 0"),
        ("statut","TEXT"),("commission_applicable","INTEGER DEFAULT 1"),("notes","TEXT"),
        ("pays","TEXT"),
    ]:
        try: db.execute(f"ALTER TABLE distribution ADD COLUMN {col} {defn}"); db.commit()
        except: pass


STATUTS_PROD = ["Actif", "En négociation", "En pause", "Archivé"]
STATUTS_DIST = [
    "Distribué sous votre suivi",
    "Non distribué — à prospecter",
    "En attente de réponse",
    "Refusé",
    "Anciennement distribué",
]


def render():
    st.markdown("## 🍇 Producteurs")
    db = get_db()
    _migrate(db)

    producteurs = db.execute(
        "SELECT * FROM producteurs WHERE archived=0 ORDER BY nom"
    ).fetchall()
    pays_list = [p["nom"] for p in db.execute(
        "SELECT nom FROM pays WHERE actif=1 ORDER BY nom").fetchall()]

    tab1, tab2 = st.tabs(["🍇 Fiches producteurs", "➕ Nouveau producteur"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — FICHES PRODUCTEURS (vue unifiée)
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        if not producteurs:
            st.info("Aucun producteur enregistré.")
        else:
            # Sélecteur producteur
            prod_noms = [p["nom"] for p in producteurs]
            sel_nom = st.selectbox(
                "Choisir un producteur",
                ["— Sélectionner —"] + prod_noms,
                key="prod_sel"
            )
            if sel_nom == "— Sélectionner —":
                # Vue liste compacte
                for p in producteurs:
                    contrat = "✅" if p["contrat_signe"] else "⬜"
                    st.markdown(
                        f"**{p['nom']}** {contrat} · {p['region'] or '—'} · {p['statut'] or '—'}"
                    )
                st.stop()

            prod = next(p for p in producteurs if p["nom"] == sel_nom)

            # ── BANDEAU INFOS + CONTRAT ───────────────────────────────────────
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Région", prod["nom"] or "—")
            c2.metric("Statut", prod["statut"] or "—")
            contrat_val = bool(prod["contrat_signe"]) if "contrat_signe" in prod.keys() else False
            c3.metric("Contrat agent", "✅ Signé" if contrat_val else "⬜ Non signé")
            date_ctr = prod["date_contrat"] if "date_contrat" in prod.keys() else None
            c4.metric("Date contrat", fmt_date(date_ctr) if date_ctr else "—")

            st.markdown("---")

            # ── 4 SOUS-ONGLETS : Infos / Produits / Mandats+Distrib / Contacts ──
            s1, s2, s3, s4 = st.tabs([
                "📋 Infos générales",
                "🍾 Produits & Marques",
                "🌍 Mandats & Distribution",
                "👤 Contacts producteur",
            ])

            # ── S1 : INFOS GÉNÉRALES ─────────────────────────────────────────
            with s1:
                with st.form(f"f_edit_{prod['id']}"):
                    st.markdown("**Identité & coordonnées**")
                    ep1, ep2, ep3 = st.columns(3)
                    new_nom    = ep1.text_input("Nom", value=prod["nom"], key=f"en_{prod['id']}")
                    new_region = ep2.text_input("Région", value=prod["region"] or "", key=f"er_{prod['id']}")
                    new_web    = ep3.text_input("Site web", value=prod["website"] or "", key=f"ew_{prod['id']}")

                    ea1, ea2, ea3 = st.columns(3)
                    new_statut  = ea1.selectbox("Statut", STATUTS_PROD,
                        index=STATUTS_PROD.index(prod["statut"]) if prod["statut"] in STATUTS_PROD else 0,
                        key=f"es_{prod['id']}")
                    new_tel     = ea2.text_input("Tél général",
                        value=prod["tel_general"] if "tel_general" in prod.keys() else "",
                        key=f"et_{prod['id']}")
                    new_web2    = ea3.text_input("Email général", key=f"em_{prod['id']}")

                    eb1, eb2 = st.columns(2)
                    new_adr1 = eb1.text_input("Adresse ligne 1",
                        value=prod["adresse_ligne1"] if "adresse_ligne1" in prod.keys() else "",
                        key=f"ea1_{prod['id']}")
                    new_adr2 = eb2.text_input("Adresse ligne 2",
                        value=prod["adresse_ligne2"] if "adresse_ligne2" in prod.keys() else "",
                        key=f"ea2_{prod['id']}")

                    ec1, ec2, ec3 = st.columns(3)
                    new_cp    = ec1.text_input("Code postal",
                        value=prod["code_postal"] if "code_postal" in prod.keys() else "",
                        key=f"ecp_{prod['id']}")
                    new_ville = ec2.text_input("Ville",
                        value=prod["ville"] if "ville" in prod.keys() else "",
                        key=f"ev_{prod['id']}")
                    new_pays_adr = ec3.text_input("Pays",
                        value=prod["pays_adresse"] if "pays_adresse" in prod.keys() else "",
                        key=f"epa_{prod['id']}")

                    st.markdown("**Contrat d'agent**")
                    ctr1, ctr2, _ = st.columns([1,1,2])
                    new_contrat = ctr1.checkbox("✅ Contrat signé",
                        value=contrat_val, key=f"ectr_{prod['id']}")
                    new_date_ctr = ctr2.date_input("Date signature", value=None,
                        key=f"edctr_{prod['id']}") if new_contrat else None

                    new_notes = st.text_area("Notes internes",
                        value=prod["notes"] or "", height=80, key=f"enotes_{prod['id']}")

                    s_save, s_arch = st.columns(2)
                    if s_save.form_submit_button("💾 Sauvegarder", use_container_width=True, type="primary"):
                        dc_str = new_date_ctr.strftime("%Y-%m-%d") if new_date_ctr else None
                        db.execute("""UPDATE producteurs SET
                            nom=?, region=?, website=?, statut=?, tel_general=?,
                            adresse_ligne1=?, adresse_ligne2=?, code_postal=?,
                            ville=?, pays_adresse=?,
                            contrat_signe=?, date_contrat=?, notes=?
                            WHERE id=?""",
                            (new_nom, new_region, new_web, new_statut, new_tel,
                             new_adr1, new_adr2, new_cp, new_ville, new_pays_adr,
                             int(new_contrat), dc_str, new_notes, prod["id"]))
                        db.commit()
                        st.success("✅ Producteur mis à jour.")
                        st.rerun()
                    if s_arch.form_submit_button("🗑️ Archiver ce producteur", use_container_width=True):
                        # Vérifier dépendances
                        nb = db.execute(
                            "SELECT COUNT(*) FROM commandes WHERE producteur_id=? AND archived=0",
                            (prod["id"],)).fetchone()[0]
                        if nb > 0:
                            st.error(f"❌ Impossible — {nb} commande(s) active(s) liée(s).")
                        else:
                            for tbl in ["producteur_contacts","produits","producteur_mandats","distribution"]:
                                try: db.execute(f"UPDATE {tbl} SET archived=1 WHERE producteur_id=?", (prod["id"],))
                                except: pass
                            db.execute("UPDATE producteurs SET archived=1 WHERE id=?", (prod["id"],))
                            db.commit()
                            st.success("✅ Archivé."); st.rerun()

            # ── S2 : PRODUITS & MARQUES ──────────────────────────────────────
            with s2:
                produits = db.execute(
                    "SELECT * FROM produits WHERE producteur_id=? ORDER BY nom",
                    (prod["id"],)).fetchall()

                if produits:
                    # Tableau éditable inline
                    st.markdown("**Modifier directement dans le tableau :**")
                    df_prod = pd.DataFrame([{
                        "id":   p["id"],
                        "Nom / Marque": p["nom"] or "",
                        "Type": p["type_produit"] or "",
                        "Style": p["style"] or "",
                        "Statut": p["statut"] or "Actif",
                        "Notes": p["notes"] or "",
                    } for p in produits])

                    edited = st.data_editor(
                        df_prod[["Nom / Marque","Type","Style","Statut","Notes"]],
                        column_config={
                            "Nom / Marque": st.column_config.TextColumn(width="large"),
                            "Type":   st.column_config.TextColumn(width="medium"),
                            "Style":  st.column_config.TextColumn(width="medium"),
                            "Statut": st.column_config.SelectboxColumn(
                                options=["Actif","Arrêté","Bientôt disponible"], width="medium"),
                            "Notes":  st.column_config.TextColumn(width="large"),
                        },
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        key=f"edit_produits_{prod['id']}"
                    )

                    if st.button("💾 Sauvegarder les modifications", key=f"save_prod_{prod['id']}"):
                        for i, row in edited.iterrows():
                            pid = df_prod.iloc[i]["id"]
                            db.execute("""UPDATE produits SET nom=?, type_produit=?,
                                style=?, statut=?, notes=? WHERE id=?""",
                                (row["Nom / Marque"], row["Type"], row["Style"],
                                 row["Statut"], row["Notes"], pid))
                        db.commit()
                        st.success("✅ Produits mis à jour.")
                        st.rerun()

                    # Supprimer une marque
                    with st.expander("🗑️ Supprimer une marque"):
                        opts_del = [p["nom"] for p in produits]
                        to_del = st.selectbox("Marque à supprimer", opts_del, key=f"del_prod_{prod['id']}")
                        if st.button("Supprimer", key=f"btn_del_prod_{prod['id']}"):
                            pid_del = next(p["id"] for p in produits if p["nom"]==to_del)
                            db.execute("DELETE FROM produits WHERE id=?", (pid_del,))
                            db.commit(); st.rerun()
                else:
                    st.info("Aucune marque / produit enregistré.")

                # Ajouter nouvelle marque
                st.markdown("---")
                with st.form(f"f_add_prod_{prod['id']}", clear_on_submit=True):
                    st.markdown("**➕ Ajouter une marque / domaine**")
                    ap1, ap2, ap3 = st.columns(3)
                    p_nom  = ap1.text_input("Nom *", key=f"pn_{prod['id']}")
                    p_type = ap2.text_input("Type", placeholder="AOC, IGP, Cognac…", key=f"pt_{prod['id']}")
                    p_style= ap3.text_input("Style", placeholder="Rouge, Blanc, Effervescent…", key=f"ps_{prod['id']}")
                    if st.form_submit_button("➕ Ajouter", use_container_width=True):
                        if p_nom:
                            db.execute("INSERT INTO produits (producteur_id, nom, type_produit, style) VALUES (?,?,?,?)",
                                       (prod["id"], p_nom, p_type, p_style))
                            db.commit(); st.success(f"✅ {p_nom} ajouté."); st.rerun()

            # ── S3 : MANDATS & DISTRIBUTION (vue croisée) ────────────────────
            with s3:
                st.markdown("### 🌍 Vue croisée Mandats ↔ Distribution")
                st.caption("Mandats = pays où vous êtes agent | Distribution = qui distribue quoi et où")

                # Charger les deux tables en même temps
                mandats = db.execute(
                    "SELECT * FROM producteur_mandats WHERE producteur_id=? ORDER BY pays",
                    (prod["id"],)).fetchall()
                distrib = db.execute(
                    """SELECT d.* FROM distribution d
                       WHERE (d.producteur_id=? OR d.producteur_nom=?)
                       AND (d.archived=0 OR d.archived IS NULL)
                       ORDER BY d.pays, d.marque_nom""",
                    (prod["id"], prod["nom"])).fetchall()

                # Construire vue consolidée par pays
                all_pays = sorted(set(
                    [m["pays"] for m in mandats] +
                    [d["pays"] for d in distrib if d["pays"]]
                ))

                if not all_pays:
                    st.info("Aucun mandat ni distribution enregistrés.")
                else:
                    for pays in all_pays:
                        mandat_pays = next((m for m in mandats if m["pays"]==pays), None)
                        distrib_pays = [d for d in distrib if d["pays"]==pays]

                        # En-tête pays
                        m_icon = "✅" if mandat_pays and mandat_pays["statut"]=="Agent exclusif" else \
                                 "🤝" if mandat_pays else "⚪"
                        m_label = mandat_pays["statut"] if mandat_pays else "Pas de mandat"
                        nb_distrib = len(distrib_pays)

                        with st.expander(
                            f"{m_icon} **{pays}** — {m_label}"
                            + (f" · {nb_distrib} distribution(s)" if nb_distrib else "")
                        ):
                            col_m, col_d = st.columns(2)

                            # Mandat
                            with col_m:
                                st.markdown("**📋 Mandat**")
                                with st.form(f"f_mandat_{prod['id']}_{pays}"):
                                    statuts_m = ["Agent exclusif","Agent non exclusif",
                                                 "Représentation directe","Pas de mandat"]
                                    idx_m = statuts_m.index(mandat_pays["statut"]) \
                                            if mandat_pays and mandat_pays["statut"] in statuts_m else 3
                                    new_m_stat = st.selectbox("Statut mandat", statuts_m,
                                        index=idx_m, key=f"ms_{prod['id']}_{pays}")
                                    new_m_comm = st.checkbox("Commission applicable",
                                        value=bool(mandat_pays["commission_applicable"]) if mandat_pays else True,
                                        key=f"mc_{prod['id']}_{pays}")
                                    new_m_notes = st.text_input("Notes mandat",
                                        value=mandat_pays["notes"] or "" if mandat_pays else "",
                                        key=f"mn_{prod['id']}_{pays}")
                                    if st.form_submit_button("💾 Mandat", use_container_width=True):
                                        if mandat_pays:
                                            db.execute("""UPDATE producteur_mandats SET
                                                statut=?, commission_applicable=?, notes=?
                                                WHERE id=?""",
                                                (new_m_stat, int(new_m_comm), new_m_notes, mandat_pays["id"]))
                                        else:
                                            db.execute("""INSERT INTO producteur_mandats
                                                (producteur_id, pays, statut, commission_applicable, notes)
                                                VALUES (?,?,?,?,?)""",
                                                (prod["id"], pays, new_m_stat, int(new_m_comm), new_m_notes))
                                        db.commit(); st.success("✅"); st.rerun()

                            # Distribution
                            with col_d:
                                st.markdown("**📦 Distribution**")
                                if distrib_pays:
                                    for d in distrib_pays:
                                        marque = d["marque_nom"] or "(Toutes marques)"
                                        client = d["client_actuel"] or "—"
                                        statut_d = d["statut"] or "—"
                                        st.markdown(
                                            f"**{marque}** → {client}  \n"
                                            f"<small>{statut_d}</small>",
                                            unsafe_allow_html=True)
                                        with st.form(f"f_dist_{d['id']}"):
                                            dd1, dd2 = st.columns(2)
                                            new_ds = dd1.selectbox("Statut", STATUTS_DIST,
                                                index=STATUTS_DIST.index(statut_d) if statut_d in STATUTS_DIST else 0,
                                                key=f"ds_{d['id']}")
                                            new_dc = dd2.text_input("Client actuel",
                                                value=client if client!="—" else "",
                                                key=f"dc_{d['id']}")
                                            if st.form_submit_button("💾", use_container_width=True):
                                                db.execute("""UPDATE distribution SET
                                                    statut=?, client_actuel=? WHERE id=?""",
                                                    (new_ds, new_dc, d["id"]))
                                                db.commit(); st.success("✅"); st.rerun()
                                        st.markdown("---")
                                else:
                                    st.caption("Aucune distribution enregistrée pour ce pays.")

                                # Ajouter distribution
                                marques_prod = [p["nom"] for p in db.execute(
                                    "SELECT nom FROM produits WHERE producteur_id=? ORDER BY nom",
                                    (prod["id"],)).fetchall()]
                                with st.form(f"f_add_dist_{prod['id']}_{pays}"):
                                    new_marque_d = st.selectbox("Marque",
                                        ["(Toutes marques)"] + marques_prod,
                                        key=f"add_dm_{prod['id']}_{pays}")
                                    new_client_d = st.text_input("Client distributeur",
                                        key=f"add_dc_{prod['id']}_{pays}")
                                    new_stat_d   = st.selectbox("Statut", STATUTS_DIST,
                                        key=f"add_ds_{prod['id']}_{pays}")
                                    if st.form_submit_button("➕ Ajouter distribution", use_container_width=True):
                                        marque_val = new_marque_d if new_marque_d != "(Toutes marques)" else None
                                        db.execute("""INSERT INTO distribution
                                            (producteur_id, producteur_nom, marque_nom, pays,
                                             statut, client_actuel)
                                            VALUES (?,?,?,?,?,?)""",
                                            (prod["id"], prod["nom"], marque_val, pays,
                                             new_stat_d, new_client_d))
                                        db.commit(); st.success("✅ Distribution ajoutée."); st.rerun()

                # Ajouter un nouveau pays
                st.markdown("---")
                with st.form(f"f_add_pays_{prod['id']}", clear_on_submit=True):
                    st.markdown("**➕ Ajouter un pays (mandat ou distribution)**")
                    np1, np2 = st.columns(2)
                    new_pays  = np1.selectbox("Pays", [""] + pays_list, key=f"npays_{prod['id']}")
                    new_type  = np2.selectbox("Type", ["Mandat + Distribution","Mandat seul","Distribution seule"],
                                             key=f"ntype_{prod['id']}")
                    if st.form_submit_button("➕ Ajouter", use_container_width=True):
                        if new_pays:
                            if "Mandat" in new_type:
                                db.execute("""INSERT OR IGNORE INTO producteur_mandats
                                    (producteur_id, pays, statut, commission_applicable)
                                    VALUES (?,?,?,1)""",
                                    (prod["id"], new_pays, "Agent non exclusif"))
                            if "Distribution" in new_type:
                                db.execute("""INSERT INTO distribution
                                    (producteur_id, producteur_nom, pays, statut)
                                    VALUES (?,?,?,?)""",
                                    (prod["id"], prod["nom"], new_pays, "Non distribué — à prospecter"))
                            db.commit(); st.success(f"✅ {new_pays} ajouté."); st.rerun()

            # ── S4 : CONTACTS PRODUCTEUR ─────────────────────────────────────
            with s4:
                contacts_prod = db.execute(
                    "SELECT * FROM producteur_contacts WHERE producteur_id=? ORDER BY id",
                    (prod["id"],)).fetchall()

                if contacts_prod:
                    df_ctc = pd.DataFrame([{
                        "id":      c["id"],
                        "Civilité": c["civilite"] if "civilite" in c.keys() else "—",
                        "Prénom":  c["prenom"] if "prenom" in c.keys() else "",
                        "Nom":     c["nom"] or "",
                        "Rôle":    c["role"] or "",
                        "Email":   c["email"] or "",
                        "Tél":     c["tel"] or "",
                        "Mobile":  c["mobile"] or "",
                    } for c in contacts_prod])

                    edited_ctc = st.data_editor(
                        df_ctc[["Civilité","Prénom","Nom","Rôle","Email","Tél","Mobile"]],
                        column_config={
                            "Civilité": st.column_config.SelectboxColumn(
                                options=["—","M.","Mme","Dr"], width="small"),
                            "Prénom":  st.column_config.TextColumn(width="medium"),
                            "Nom":     st.column_config.TextColumn(width="medium"),
                            "Rôle":    st.column_config.TextColumn(width="medium"),
                            "Email":   st.column_config.TextColumn(width="large"),
                            "Tél":     st.column_config.TextColumn(width="medium"),
                            "Mobile":  st.column_config.TextColumn(width="medium"),
                        },
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        key=f"edit_ctc_{prod['id']}"
                    )

                    if st.button("💾 Sauvegarder contacts", key=f"save_ctc_{prod['id']}"):
                        for i, row in edited_ctc.iterrows():
                            cid = df_ctc.iloc[i]["id"]
                            db.execute("""UPDATE producteur_contacts SET
                                civilite=?, prenom=?, nom=?, role=?,
                                email=?, tel=?, mobile=? WHERE id=?""",
                                (row["Civilité"], row["Prénom"], row["Nom"], row["Rôle"],
                                 row["Email"], row["Tél"], row["Mobile"], cid))
                        db.commit(); st.success("✅ Contacts mis à jour."); st.rerun()
                else:
                    st.info("Aucun contact enregistré.")

                st.markdown("---")
                with st.form(f"f_add_ctc_{prod['id']}", clear_on_submit=True):
                    st.markdown("**➕ Ajouter un contact**")
                    cc1,cc2,cc3,cc4 = st.columns(4)
                    c_civ    = cc1.selectbox("Civilité", ["—","M.","Mme","Dr"], key=f"cciv_{prod['id']}")
                    c_prenom = cc2.text_input("Prénom", key=f"cp_{prod['id']}")
                    c_nom    = cc3.text_input("Nom *",  key=f"cn_{prod['id']}")
                    c_role   = cc4.text_input("Rôle",   key=f"cr_{prod['id']}")
                    cd1,cd2,cd3 = st.columns(3)
                    c_email  = cd1.text_input("Email",  key=f"ce_{prod['id']}")
                    c_tel    = cd2.text_input("Tél",    key=f"ct_{prod['id']}")
                    c_mob    = cd3.text_input("Mobile", key=f"cm_{prod['id']}")
                    if st.form_submit_button("➕ Ajouter", use_container_width=True):
                        if c_nom:
                            db.execute("""INSERT INTO producteur_contacts
                                (producteur_id, civilite, prenom, nom, role, email, tel, mobile)
                                VALUES (?,?,?,?,?,?,?,?)""",
                                (prod["id"], c_civ, c_prenom, c_nom, c_role, c_email, c_tel, c_mob))
                            db.commit(); st.success(f"✅ {c_nom} ajouté."); st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — NOUVEAU PRODUCTEUR
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        with st.form("form_nouveau_producteur", clear_on_submit=True):
            st.markdown("**Nouveau producteur**")
            n1, n2, n3 = st.columns(3)
            p_nom    = n1.text_input("Nom du producteur *")
            p_code   = n2.text_input("Code (ex: LEDA)")
            p_region = n3.text_input("Région", placeholder="Ex: Bordeaux, Cognac…")
            n4, n5 = st.columns(2)
            p_statut = n4.selectbox("Statut", STATUTS_PROD)
            p_web    = n5.text_input("Site internet")
            p_notes  = st.text_area("Notes", height=60)
            if st.form_submit_button("💾 Créer le producteur", use_container_width=True):
                if not p_nom or not p_code:
                    st.error("Nom et code sont obligatoires.")
                else:
                    existing = db.execute(
                        "SELECT id FROM producteurs WHERE code=?", (p_code,)).fetchone()
                    if existing:
                        st.error(f"❌ Code **{p_code}** déjà utilisé.")
                    else:
                        db.execute("""INSERT INTO producteurs
                            (nom, code, region, statut, website, notes)
                            VALUES (?,?,?,?,?,?)""",
                            (p_nom, p_code, p_region, p_statut, p_web, p_notes))
                        db.commit()
                        st.success(f"✅ **{p_nom}** créé.")
                        st.rerun()

    db.close()
