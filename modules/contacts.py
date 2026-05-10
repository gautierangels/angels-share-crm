import streamlit as st
import pandas as pd
from database import get_db

DOCS_POSSIBLES = [
    "Facture commerciale (Commercial Invoice)",
    "Certificat d'origine EUR.1",
    "Certificat d'origine Form A",
    "Certificat d'origine CO",
    "Packing List",
    "Bill of Lading (BL)",
    "Airway Bill (AWB)",
    "Certificat d'analyse (phtalates)",
    "Certificat d'analyse (SO2)",
    "Certificat sanitaire",
    "Certificat phytosanitaire",
    "DAE / Excise document",
    "Certificat d'exportation",
    "Licence d'importation client",
    "Certificat CITES",
    "Fiche technique produit",
    "Étiquettes approuvées",
    "Attestation d'assurance",
]

CIVILITES = ["—", "M.", "Mme", "Dr", "Prof."]


def _migrate(db):
    for table, col, defn in [
        ("entreprises", "groupe_id",           "INTEGER"),
        ("entreprises", "numero_tva",          "TEXT"),
        ("entreprises", "registre_commerce",   "TEXT"),
        ("entreprises", "livraison_nom",        "TEXT"),
        ("entreprises", "livraison_adresse",    "TEXT"),
        ("entreprises", "livraison_pays",       "TEXT"),
        ("entreprises", "livraison_contact",    "TEXT"),
        ("entreprises", "facturation_nom",      "TEXT"),
        ("entreprises", "facturation_adresse",  "TEXT"),
        ("entreprises", "facturation_pays",     "TEXT"),
        ("entreprises", "facturation_contact",  "TEXT"),
        ("entreprises", "docs_requis",          "TEXT"),
        ("entreprises", "tarifs_envoyes",       "INTEGER DEFAULT 0"),
        ("entreprises", "producteurs_lies",     "TEXT"),
        ("contacts",    "prenom",               "TEXT"),
        ("contacts",    "civilite",             "TEXT"),
        ("contacts",    "date_naissance",       "TEXT"),
        ("contacts",    "conjoint",             "TEXT"),
        ("contacts",    "enfants",              "TEXT"),
        ("contacts",    "prefs_vins",           "TEXT"),
        ("contacts",    "prefs_cuisine",        "TEXT"),
        ("contacts",    "loisirs",              "TEXT"),
        ("contacts",    "infos_perso",          "TEXT"),
        ("contacts",    "prefs_pro",            "TEXT"),
    ]:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
            db.commit()
        except Exception:
            pass


def _get_prods_lies(ent):
    """Retourne la liste des producteurs liés à une entreprise."""
    raw = ent["producteurs_lies"] or ""
    return [p.strip() for p in raw.split("|") if p.strip()]


def _set_prods_lies(db, ent_id, prods_list):
    db.execute("UPDATE entreprises SET producteurs_lies=? WHERE id=?",
               ("|".join(prods_list), ent_id))
    db.commit()


def render():
    st.markdown("## 🏢 Contacts & Entreprises")
    db = get_db()
    _migrate(db)

    pays_list = [p["nom"] for p in db.execute(
        "SELECT nom FROM pays WHERE actif=1 ORDER BY nom").fetchall()]
    all_producteurs = [p["nom"] for p in db.execute(
        "SELECT nom FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()]

    tab1, tab2, tab3 = st.tabs([
        "🏢 Entreprises",
        "👤 Contacts individuels",
        "➕ Nouveau contact",
    ])

    # ══ ENTREPRISES ══════════════════════════════════════════════════════════
    with tab1:
        with st.expander("➕ Nouvelle entreprise"):
            with st.form("form_nouvelle_entreprise", clear_on_submit=True):
                st.markdown("**Identification**")
                e1, e2, e3 = st.columns(3)
                e_nom      = e1.text_input("Nom du client / groupe *")
                e_type     = e2.selectbox("Type", ["Client actif","Prospect",
                    "Ancien client","Co-agent","Prestataire"])
                e_activite = e3.selectbox("Activité", ["Importateur","Distributeur",
                    "Retail","Horeca","Duty Free","E-commerce","Agent","Autre"])
                e4, e5 = st.columns(2)
                e_pays_d = e4.selectbox("Pays marché *", [""] + pays_list)
                e_statut = e5.selectbox("Statut", ["Actif","Nouveau","En discussion",
                    "Refusé","À recontacter","Inactif"])

                st.markdown("---")
                st.markdown("**Renseignez les deux sociétés si elles sont différentes**")

                col_l, col_f = st.columns(2)

                with col_l:
                    st.markdown(
                        '<div style="background:#E8F4FD;border-radius:8px;padding:10px 14px;'
                        'border-left:4px solid #2E86DE;margin-bottom:12px;font-weight:600;">'
                        '📦 Société de destination / livraison</div>',
                        unsafe_allow_html=True)
                    l_nom  = st.text_input("Nom de la société",
                        placeholder="Ex: Cambodia Wines Co.", key="new_lnom")
                    l_adr  = st.text_area("Adresse complète", height=90,
                        placeholder="Numéro, rue\nVille, code postal", key="new_ladr")
                    l_pays = st.text_input("Pays", placeholder="Ex: Cambodge", key="new_lpays")
                    l_ctc  = st.text_input("Contact logistique", key="new_lctc")

                with col_f:
                    st.markdown(
                        '<div style="background:#FFF4E6;border-radius:8px;padding:10px 14px;'
                        'border-left:4px solid #E67E22;margin-bottom:12px;font-weight:600;">'
                        '🧾 Société de facturation</div>',
                        unsafe_allow_html=True)
                    # Case "idem"
                    idem = st.checkbox("✅ Identique à la société de destination",
                                       key="new_idem")
                    if idem:
                        st.info("Les informations de facturation seront copiées depuis la livraison.")
                        f_nom = f_adr = f_pays = f_ctc = ""
                    else:
                        f_nom  = st.text_input("Nom de la société",
                            placeholder="Ex: Indian Ocean Trading Ltd", key="new_fnom")
                        f_adr  = st.text_area("Adresse complète", height=90,
                            placeholder="Numéro, rue\nVille, code postal", key="new_fadr")
                        f_pays = st.text_input("Pays", placeholder="Ex: Maurice", key="new_fpays")
                        f_ctc  = st.text_input("Contact finance", key="new_fctc")

                st.markdown("---")
                st.markdown("**🤝 Producteurs travaillés**")
                prods_sel = st.multiselect(
                    "Producteurs avec lesquels cet importateur travaille",
                    all_producteurs, key="new_prods")

                st.markdown("**Documents & tarifs**")
                docs_sel  = st.multiselect("Documents requis", DOCS_POSSIBLES, key="new_docs")
                tarifs_ok = st.checkbox("✅ Nouveaux tarifs envoyés", key="new_tarifs")
                ef1, ef2  = st.columns(2)
                e_tva     = ef1.text_input("N° TVA / Tax ID")
                e_rc      = ef2.text_input("Registre de commerce")
                e_notes   = st.text_area("Notes", height=70)

                if st.form_submit_button("💾 Créer", use_container_width=True):
                    if not e_nom:
                        st.error("Le nom est obligatoire.")
                    else:
                        # Si idem coché, copie livraison → facturation
                        fn  = l_nom  if idem else f_nom
                        fa  = l_adr  if idem else f_adr
                        fp  = l_pays if idem else f_pays
                        fc  = l_ctc  if idem else f_ctc
                        db.execute("""INSERT INTO entreprises
                            (nom,type,pays_destination,activite,statut,
                             livraison_nom,livraison_adresse,livraison_pays,livraison_contact,
                             facturation_nom,facturation_adresse,facturation_pays,facturation_contact,
                             numero_tva,registre_commerce,docs_requis,tarifs_envoyes,
                             producteurs_lies,notes)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (e_nom,e_type,e_pays_d,e_activite,e_statut,
                             l_nom,l_adr,l_pays,l_ctc,
                             fn,fa,fp,fc,
                             e_tva,e_rc,
                             "|".join(docs_sel),int(tarifs_ok),
                             "|".join(prods_sel),e_notes))
                        db.commit()
                        st.success(f"✅ {e_nom} créée.")
                        st.rerun()

        # Filtres
        c1, c2, c3 = st.columns(3)
        f_pays = c1.selectbox("Filtrer par pays", ["Tous"] + pays_list, key="ctc_pays")
        f_type = c2.selectbox("Type", ["Tous","Client actif","Prospect",
            "Ancien client","Co-agent","Prestataire"], key="ctc_type")
        f_nom  = c3.text_input("Recherche", placeholder="Nom...", key="ctc_nom")
        q = "SELECT * FROM entreprises WHERE archived=0 AND (groupe_id IS NULL OR groupe_id=0)"
        params = []
        if f_pays != "Tous":
            q += " AND pays_destination=?"; params.append(f_pays)
        if f_type != "Tous":
            q += " AND type=?"; params.append(f_type)
        if f_nom:
            q += " AND (nom LIKE ? OR livraison_nom LIKE ? OR facturation_nom LIKE ?)"
            params += [f"%{f_nom}%"]*3
        q += " ORDER BY nom"
        # Limite pour la performance — pagination
        PAGE_SIZE = 50
        if "ctc_page" not in st.session_state: st.session_state.ctc_page = 0
        # Reset page si filtre change
        filtre_key = f"{f_pays}_{f_type}_{f_nom}"
        if st.session_state.get("ctc_filtre_key") != filtre_key:
            st.session_state.ctc_page = 0
            st.session_state.ctc_filtre_key = filtre_key

        all_ents = db.execute(q, params).fetchall()
        total = len(all_ents)
        page = st.session_state.ctc_page
        entreprises = all_ents[page*PAGE_SIZE:(page+1)*PAGE_SIZE]

        if total > PAGE_SIZE:
            nb_pages = (total-1)//PAGE_SIZE + 1
            pc1, pc2, pc3 = st.columns([1,2,1])
            if pc1.button("◀ Précédent", disabled=page==0, key="ctc_prev"):
                st.session_state.ctc_page -= 1; st.rerun()
            pc2.caption(f"Page {page+1}/{nb_pages} — {total} entreprises")
            if pc3.button("Suivant ▶", disabled=page>=nb_pages-1, key="ctc_next"):
                st.session_state.ctc_page += 1; st.rerun()

        if not entreprises:
            st.info("Aucune entreprise enregistrée.")

        type_emoji = {"Client actif":"✅","Prospect":"🔵","Ancien client":"⚪",
                      "Co-agent":"🤝","Prestataire":"🔧"}

        for ent in entreprises:
            em   = type_emoji.get(ent["type"],"")
            liv  = ent["livraison_nom"]  or ent["livraison_pays"]  or ""
            fact = ent["facturation_nom"] or ent["facturation_pays"] or ""
            sous = ""
            if liv and fact and liv != fact: sous = f" | 📦 {liv} / 🧾 {fact}"
            elif liv: sous = f" | {liv}"
            tarifs_flag = " · 📋✅" if ent["tarifs_envoyes"] else ""

            with st.expander(
                f"{em} **{ent['nom']}** — {ent['pays_destination'] or '—'} "
                f"· {ent['type']}{sous}{tarifs_flag}"
            ):
                d1, d2, d3 = st.columns(3)
                d1.markdown(f"**Activité :** {ent['activite'] or '—'}")
                d2.markdown(f"**Statut :** {ent['statut'] or '—'}")
                d3.markdown(f"TVA : `{ent['numero_tva'] or '—'}` · RC : `{ent['registre_commerce'] or '—'}`")
                if ent["notes"]: st.info(ent["notes"])

                # Tarifs
                tarifs_val = bool(ent["tarifs_envoyes"])
                new_tarif = st.checkbox("📋 Nouveaux tarifs à jour envoyés",
                                        value=tarifs_val, key=f"tarifs_{ent['id']}")
                if new_tarif != tarifs_val:
                    db.execute("UPDATE entreprises SET tarifs_envoyes=? WHERE id=?",
                               (int(new_tarif), ent["id"]))
                    db.commit()

                st.markdown("---")

                # ── Producteurs liés ──────────────────────────────────────
                st.markdown("**🤝 Producteurs travaillés par cet importateur**")
                prods_actuels = _get_prods_lies(ent)
                with st.form(f"f_prods_{ent['id']}"):
                    new_prods = st.multiselect(
                        "Producteurs",
                        all_producteurs,
                        default=[p for p in prods_actuels if p in all_producteurs],
                        key=f"prods_sel_{ent['id']}"
                    )
                    if st.form_submit_button("💾 Sauvegarder"):
                        _set_prods_lies(db, ent["id"], new_prods)
                        st.success("✅ Producteurs mis à jour.")
                        st.rerun()

                st.markdown("---")

                # ── Documents requis ──────────────────────────────────────
                st.markdown("**📄 Documents requis**")
                docs_actuels = [d.strip() for d in (ent["docs_requis"] or "").split("|") if d.strip()]

                # Afficher les documents déjà renseignés (même hors liste standard)
                if docs_actuels:
                    for doc in docs_actuels:
                        st.markdown(f"✅ {doc}")

                # Permettre de modifier via multiselect
                # Fusionner docs existants + liste standard sans doublons
                docs_complets = DOCS_POSSIBLES + [d for d in docs_actuels if d not in DOCS_POSSIBLES]

                with st.form(f"f_docs_{ent['id']}"):
                    docs_sel = st.multiselect("Modifier les documents requis",
                        docs_complets,
                        default=[d for d in docs_actuels if d in docs_complets],
                        key=f"docs_sel_{ent['id']}")
                    if st.form_submit_button("💾 Sauvegarder"):
                        db.execute("UPDATE entreprises SET docs_requis=? WHERE id=?",
                                   ("|".join(docs_sel), ent["id"]))
                        db.commit()
                        st.success("Documents mis à jour.")
                        st.rerun()

                st.markdown("---")

                # ── Adresses ──────────────────────────────────────────────
                col_l, col_f = st.columns(2)
                with col_l:
                    st.markdown(
                        '<div style="background:#E8F4FD;border-radius:8px;padding:10px 14px;'
                        'border-left:4px solid #2E86DE;margin-bottom:8px;">'
                        '<b>📦 Destination / Livraison</b></div>',
                        unsafe_allow_html=True)
                    if ent["livraison_nom"]:     st.markdown(f"**{ent['livraison_nom']}**")
                    if ent["livraison_adresse"]: st.markdown(ent["livraison_adresse"])
                    if ent["livraison_pays"]:    st.markdown(f"🌍 {ent['livraison_pays']}")
                    if ent["livraison_contact"]: st.markdown(f"👤 {ent['livraison_contact']}")
                    if not any([ent["livraison_nom"],ent["livraison_adresse"],ent["livraison_pays"]]):
                        st.caption("Non renseigné")

                with col_f:
                    # Détecter si idem
                    is_idem = (
                        ent["livraison_nom"] and
                        ent["facturation_nom"] == ent["livraison_nom"] and
                        ent["facturation_adresse"] == ent["livraison_adresse"] and
                        ent["facturation_pays"] == ent["livraison_pays"]
                    )
                    idem_label = " *(idem livraison)*" if is_idem else ""
                    st.markdown(
                        f'<div style="background:#FFF4E6;border-radius:8px;padding:10px 14px;'
                        f'border-left:4px solid #E67E22;margin-bottom:8px;">'
                        f'<b>🧾 Facturation{idem_label}</b></div>',
                        unsafe_allow_html=True)
                    if is_idem:
                        st.caption("Identique à la société de destination")
                    else:
                        if ent["facturation_nom"]:     st.markdown(f"**{ent['facturation_nom']}**")
                        if ent["facturation_adresse"]: st.markdown(ent["facturation_adresse"])
                        if ent["facturation_pays"]:    st.markdown(f"🌍 {ent['facturation_pays']}")
                        if ent["facturation_contact"]: st.markdown(f"👤 {ent['facturation_contact']}")
                        if not any([ent["facturation_nom"],ent["facturation_adresse"],ent["facturation_pays"]]):
                            st.caption("Non renseigné")

                st.markdown("---")

                # ── Contacts ──────────────────────────────────────────────
                st.markdown("**👤 Contacts**")
                ctcs = db.execute(
                    "SELECT * FROM contacts WHERE entreprise_id=? AND archived=0 ORDER BY nom",
                    (ent["id"],)).fetchall()
                if ctcs:
                    for c in ctcs:
                        civ = f"{c['civilite']} " if c["civilite"] and c["civilite"] != "—" else ""
                        prn = c["prenom"] or ""
                        nom_c = c["nom"] or ""
                        ci, cd = st.columns([9,1])
                        with ci:
                            nom_full = f"{civ}{prn} {nom_c}".strip()
                            # WhatsApp link
                            wa_num = (c["mobile"] or "").replace(" ","").replace("-","")
                            wa_link = f'<a href="https://wa.me/{wa_num}">📱 WA</a>' if wa_num else f"📱 {c['mobile'] or '—'}"
                            st.markdown(
                                f"**{nom_full}** — {c['position'] or '—'}  \n"
                                f"📧 {c['email'] or '—'} · {wa_link} · "
                                f"💬 WeChat: {c['wechat'] or '—'} · {c['langue']}",
                                unsafe_allow_html=True)
                        with cd:
                            if st.button("🗑️", key=f"del_ctc_{c['id']}"):
                                db.execute("DELETE FROM contacts WHERE id=?", (c["id"],))
                                db.commit(); st.rerun()
                        st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid #eee'>",
                                    unsafe_allow_html=True)
                else:
                    st.caption("Aucun contact rattaché.")

                with st.form(f"f_add_ctc_{ent['id']}", clear_on_submit=True):
                    st.caption("➕ Ajouter un contact")
                    cc1,cc2,cc3,cc4 = st.columns(4)
                    c_civ    = cc1.selectbox("Civilité", CIVILITES, key=f"acc_{ent['id']}")
                    c_prenom = cc2.text_input("Prénom",  key=f"acpr_{ent['id']}")
                    c_nom    = cc3.text_input("Nom *",   key=f"acn_{ent['id']}")
                    c_pos    = cc4.text_input("Poste",   key=f"acp_{ent['id']}")
                    cc5,cc6,cc7 = st.columns(3)
                    c_email  = cc5.text_input("Email",   key=f"ace_{ent['id']}")
                    c_mob    = cc6.text_input("Mobile",  key=f"acm_{ent['id']}")
                    c_wc     = cc7.text_input("WeChat",  key=f"acw_{ent['id']}")
                    cc8,cc9,cc10 = st.columns(3)
                    c_ddn    = cc8.text_input("Date naissance (JJ/MM/AAAA)", key=f"acdn_{ent['id']}")
                    c_lang   = cc9.selectbox("Langue",
                        ["Anglais","Français","Chinois","Japonais","Coréen","Khmer","Thaï","Autre"],
                        key=f"acl_{ent['id']}")
                    c_role   = cc10.selectbox("Rôle email",["To","CC","BCC"],key=f"acr_{ent['id']}")
                    if st.form_submit_button("Ajouter"):
                        if c_nom:
                            db.execute("""INSERT INTO contacts
                                (entreprise_id,civilite,prenom,nom,position,
                                 email,mobile,wechat,date_naissance,langue,email_role)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                                (ent["id"],c_civ,c_prenom,c_nom,c_pos,
                                 c_email,c_mob,c_wc,c_ddn,c_lang,c_role))
                            db.commit(); st.rerun()
                        else: st.error("Le nom est obligatoire.")

                # ── Modifier ──────────────────────────────────────────────
                st.markdown("---")
                with st.expander("✏️ Modifier cette entreprise"):
                    with st.form(f"f_edit_ent_{ent['id']}"):
                        types_l   = ["Client actif","Prospect","Ancien client","Co-agent","Prestataire"]
                        statuts_l = ["Actif","Nouveau","En discussion","Refusé","À recontacter","Inactif"]
                        x1,x2,x3 = st.columns(3)
                        new_nom    = x1.text_input("Nom", value=ent["nom"], key=f"en_{ent['id']}")
                        new_type   = x2.selectbox("Type", types_l,
                            index=types_l.index(ent["type"]) if ent["type"] in types_l else 0,
                            key=f"et_{ent['id']}")
                        new_statut = x3.selectbox("Statut", statuts_l,
                            index=statuts_l.index(ent["statut"]) if ent["statut"] in statuts_l else 0,
                            key=f"es_{ent['id']}")
                        new_pays = st.selectbox("Pays marché", [""] + pays_list,
                            index=([""] + pays_list).index(ent["pays_destination"])
                                  if ent["pays_destination"] in pays_list else 0,
                            key=f"ep_{ent['id']}")

                        ml, mf = st.columns(2)
                        with ml:
                            st.markdown("**📦 Livraison**")
                            new_lnom  = st.text_input("Nom société", value=ent["livraison_nom"] or "",  key=f"ln_{ent['id']}")
                            new_ladr  = st.text_area("Adresse",      value=ent["livraison_adresse"] or "",height=70,key=f"la_{ent['id']}")
                            new_lpays = st.text_input("Pays",        value=ent["livraison_pays"] or "",  key=f"lp_{ent['id']}")
                            new_lctc  = st.text_input("Contact",     value=ent["livraison_contact"] or "",key=f"lc_{ent['id']}")
                        with mf:
                            st.markdown("**🧾 Facturation**")
                            edit_idem = st.checkbox("✅ Identique à livraison",
                                                     value=bool(is_idem),
                                                     key=f"edit_idem_{ent['id']}")
                            if edit_idem:
                                st.info("Facturation = Livraison (sera copié à la sauvegarde)")
                                new_fnom = new_fadr = new_fpays = new_fctc = ""
                            else:
                                new_fnom  = st.text_input("Nom société", value=ent["facturation_nom"] or "",  key=f"fn_{ent['id']}")
                                new_fadr  = st.text_area("Adresse",      value=ent["facturation_adresse"] or "",height=70,key=f"fa_{ent['id']}")
                                new_fpays = st.text_input("Pays",        value=ent["facturation_pays"] or "",  key=f"fp_{ent['id']}")
                                new_fctc  = st.text_input("Contact",     value=ent["facturation_contact"] or "",key=f"fc_{ent['id']}")

                        new_notes = st.text_area("Notes", value=ent["notes"] or "", height=60, key=f"no_{ent['id']}")
                        s1,s2 = st.columns(2)
                        if s1.form_submit_button("💾 Sauvegarder", use_container_width=True):
                            fn  = new_lnom  if edit_idem else new_fnom
                            fa  = new_ladr  if edit_idem else new_fadr
                            fp  = new_lpays if edit_idem else new_fpays
                            fc  = new_lctc  if edit_idem else new_fctc
                            db.execute("""UPDATE entreprises SET
                                nom=?,type=?,statut=?,pays_destination=?,
                                livraison_nom=?,livraison_adresse=?,livraison_pays=?,livraison_contact=?,
                                facturation_nom=?,facturation_adresse=?,facturation_pays=?,facturation_contact=?,
                                notes=? WHERE id=?""",
                                (new_nom,new_type,new_statut,new_pays,
                                 new_lnom,new_ladr,new_lpays,new_lctc,
                                 fn,fa,fp,fc,
                                 new_notes,ent["id"]))
                            db.commit(); st.success("✅ Mis à jour."); st.rerun()
                        if s2.form_submit_button("🗑️ Supprimer définitivement", use_container_width=True):
                            db.execute("UPDATE contacts SET entreprise_id=NULL WHERE entreprise_id=?", (ent["id"],))
                            db.execute("DELETE FROM entreprises WHERE id=?", (ent["id"],))
                            db.commit(); st.rerun()

    # ══ CONTACTS INDIVIDUELS ══════════════════════════════════════════════════
    with tab2:
        f_search = st.text_input("🔍 Rechercher", placeholder="Nom, prénom, email…")
        q_c = """SELECT c.*, e.nom as entreprise_nom, e.pays_destination
                 FROM contacts c LEFT JOIN entreprises e ON e.id=c.entreprise_id
                 WHERE c.archived=0"""
        params_c = []
        if f_search:
            q_c += " AND (c.nom LIKE ? OR c.prenom LIKE ? OR c.email LIKE ? OR e.nom LIKE ?)"
            params_c += [f"%{f_search}%"]*4
        q_c += " ORDER BY c.nom"
        all_ctc = db.execute(q_c, params_c).fetchall()

        if not all_ctc:
            st.info("Aucun contact enregistré.")
        else:
            st.caption(f"{len(all_ctc)} contact(s)")
            for c in all_ctc:
                civ = f"{c['civilite']} " if c["civilite"] and c["civilite"] != "—" else ""
                prn = c["prenom"] or ""
                nom_c = c["nom"] or ""
                ent_str  = c["entreprise_nom"] or "*(indépendant)*"
                pays_str = f" — {c['pays_destination']}" if c["pays_destination"] else ""
                with st.expander(f"**{civ}{prn} {nom_c}** @ {ent_str}{pays_str}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📋 Informations professionnelles**")
                        st.markdown(
                            f"Poste : {c['position'] or '—'}  \n"
                            f"📧 {c['email'] or '—'}  \n"
                            f"📱 {c['mobile'] or '—'}  \n"
                            f"💬 WeChat : {c['wechat'] or '—'}  \n"
                            f"Langue : {c['langue']}  \n"
                            f"Rôle email : {c['email_role']}"
                        )
                        if c["date_naissance"]:
                            st.markdown(f"🎂 {c['date_naissance']}")
                    with col2:
                        st.markdown("**🧠 Profil personnel**")
                        if c["conjoint"]:      st.markdown(f"💑 {c['conjoint']}")
                        if c["enfants"]:       st.markdown(f"👨‍👩‍👧 {c['enfants']}")
                        if c["prefs_vins"]:    st.markdown(f"🍷 {c['prefs_vins']}")
                        if c["prefs_cuisine"]: st.markdown(f"🍽️ {c['prefs_cuisine']}")
                        if c["loisirs"]:       st.markdown(f"⛳ {c['loisirs']}")
                        if c["prefs_pro"]:     st.markdown(f"💼 {c['prefs_pro']}")
                        if c["infos_perso"]:   st.info(c["infos_perso"])

                    st.markdown("---")
                    with st.expander("✏️ Modifier ce contact"):
                        with st.form(f"f_edit_ctc_{c['id']}"):
                            ec1,ec2,ec3,ec4 = st.columns(4)
                            new_civ    = ec1.selectbox("Civilité", CIVILITES,
                                index=CIVILITES.index(c["civilite"]) if c["civilite"] in CIVILITES else 0,
                                key=f"eciv_{c['id']}")
                            new_prenom = ec2.text_input("Prénom", value=prn, key=f"epr_{c['id']}")
                            new_nom    = ec3.text_input("Nom *",  value=nom_c, key=f"enm_{c['id']}")
                            new_ddn    = ec4.text_input("Date naissance",
                                value=c["date_naissance"] or "",
                                placeholder="JJ/MM/AAAA", key=f"eddn_{c['id']}")
                            ec5,ec6,ec7 = st.columns(3)
                            new_pos   = ec5.text_input("Poste",  value=c["position"] or "", key=f"epos_{c['id']}")
                            new_email = ec6.text_input("Email",  value=c["email"] or "",    key=f"eem_{c['id']}")
                            new_mob   = ec7.text_input("Mobile", value=c["mobile"] or "",   key=f"emob_{c['id']}")
                            ec8,ec9 = st.columns(2)
                            new_wc   = ec8.text_input("WeChat", value=c["wechat"] or "",   key=f"ewc_{c['id']}")
                            langues_l = ["Anglais","Français","Chinois","Japonais","Coréen","Khmer","Thaï","Autre"]
                            lang_val = c["langue"] if c["langue"] in langues_l else "Anglais"
                            new_lang = ec9.selectbox("Langue", langues_l,
                                index=langues_l.index(lang_val),
                                key=f"elng_{c['id']}")
                            st.markdown("**🧠 Profil**")
                            ep1,ep2 = st.columns(2)
                            new_cj   = ep1.text_input("Conjoint(e)", value=c["conjoint"] or "",    key=f"ecj_{c['id']}")
                            new_enf  = ep2.text_input("Enfants",     value=c["enfants"] or "",     key=f"eenf_{c['id']}")
                            ep3,ep4  = st.columns(2)
                            new_vins = ep3.text_input("Préf. vins",  value=c["prefs_vins"] or "",  key=f"evins_{c['id']}")
                            new_cuis = ep4.text_input("Préf. cuisine",value=c["prefs_cuisine"] or "",key=f"ecuis_{c['id']}")
                            new_lois = st.text_input("Loisirs",       value=c["loisirs"] or "",    key=f"elois_{c['id']}")
                            new_pro  = st.text_area("Notes pro",      value=c["prefs_pro"] or "",  height=60,key=f"epro_{c['id']}")
                            new_perso= st.text_area("Notes perso",    value=c["infos_perso"] or "",height=60,key=f"eperso_{c['id']}")
                            es1,es2  = st.columns(2)
                            if es1.form_submit_button("💾 Sauvegarder", use_container_width=True):
                                db.execute("""UPDATE contacts SET
                                    civilite=?,prenom=?,nom=?,date_naissance=?,position=?,
                                    email=?,mobile=?,wechat=?,langue=?,
                                    conjoint=?,enfants=?,prefs_vins=?,prefs_cuisine=?,
                                    loisirs=?,prefs_pro=?,infos_perso=? WHERE id=?""",
                                    (new_civ,new_prenom,new_nom,new_ddn,new_pos,
                                     new_email,new_mob,new_wc,new_lang,
                                     new_cj,new_enf,new_vins,new_cuis,
                                     new_lois,new_pro,new_perso,c["id"]))
                                db.commit(); st.success("✅ Mis à jour."); st.rerun()
                            if es2.form_submit_button("🗑️ Supprimer", use_container_width=True):
                                db.execute("DELETE FROM contacts WHERE id=?", (c["id"],))
                                db.commit(); st.rerun()

    # ══ NOUVEAU CONTACT ════════════════════════════════════════════════════════
    with tab3:
        with st.form("form_nouveau_contact", clear_on_submit=True):
            n1,n2,n3,n4 = st.columns(4)
            c_civ    = n1.selectbox("Civilité", CIVILITES)
            c_prenom = n2.text_input("Prénom")
            c_nom    = n3.text_input("Nom *")
            c_ddn    = n4.text_input("Date naissance (JJ/MM/AAAA)")
            n5,n6,n7 = st.columns(3)
            c_pos    = n5.text_input("Poste")
            c_email  = n6.text_input("Email")
            c_mob    = n7.text_input("Mobile / WhatsApp")
            n8,n9,n10 = st.columns(3)
            c_wc     = n8.text_input("WeChat ID")
            c_lang   = n9.selectbox("Langue",
                ["Anglais","Français","Chinois","Japonais","Coréen","Khmer","Thaï","Autre"])
            c_role   = n10.selectbox("Rôle email", ["To","CC","BCC"])
            all_ents = db.execute(
                "SELECT id,nom,pays_destination FROM entreprises WHERE archived=0 ORDER BY nom"
            ).fetchall()
            ent_options = ["— Aucune —"] + [
                f"{e['nom']} ({e['pays_destination'] or '—'})" for e in all_ents]
            ent_sel = st.selectbox("Rattacher à une entreprise (optionnel)", ent_options)
            c_notes = st.text_input("Notes")

            if st.form_submit_button("💾 Créer", use_container_width=True):
                if not c_nom:
                    st.error("Le nom est obligatoire.")
                else:
                    ent_id = None
                    if ent_sel != "— Aucune —":
                        idx = ent_options.index(ent_sel) - 1
                        ent_id = all_ents[idx]["id"]
                    db.execute("""INSERT INTO contacts
                        (entreprise_id,civilite,prenom,nom,position,
                         email,mobile,wechat,date_naissance,langue,email_role,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ent_id,c_civ,c_prenom,c_nom,c_pos,
                         c_email,c_mob,c_wc,c_ddn,c_lang,c_role,c_notes))
                    db.commit()
                    st.success(f"✅ {c_civ} {c_prenom} {c_nom} créé.")
                    st.rerun()

    db.close()
