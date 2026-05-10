import streamlit as st
import pandas as pd
from database import get_db
from utils import fmt_date, fmt_money, get_echeance, alert_level, DEVISES
from datetime import datetime, date

TAUX_AUTO = {
    "Maison Léda": 8.0,
}

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

def render():
    st.markdown("## 📋 Commandes")
    db = get_db()

    pays_list   = [p["nom"] for p in db.execute("SELECT nom FROM pays WHERE actif=1 ORDER BY nom").fetchall()]
    producteurs = db.execute("SELECT id,nom,code FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()
    entreprises = db.execute("SELECT id,nom,pays_destination FROM entreprises WHERE archived=0 ORDER BY nom").fetchall()

    tab1, tab2, tab3 = st.tabs(["📋 Liste des commandes", "➕ Nouvelle commande", "✏️ Modifier une commande"])

    # ══ LISTE ════════════════════════════════════════════════════════════════
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        f_search = c1.text_input("🔍 Recherche", placeholder="Proforma, client…")
        f_pays   = c2.selectbox("Pays", ["Tous"] + pays_list)
        f_prod   = c3.selectbox("Producteur", ["Tous"] + [p["nom"] for p in producteurs])
        f_stat   = c4.selectbox("Statut", ["Tous", "En cours", "Livré", "Payé", "En retard"])

        q = "SELECT * FROM commandes WHERE archived=0"
        params = []
        if f_search:
            q += " AND (proforma LIKE ? OR client_nom LIKE ? OR producteur_nom LIKE ?)"
            params += [f"%{f_search}%"] * 3
        if f_pays != "Tous":
            q += " AND pays=?"; params.append(f_pays)
        if f_prod != "Tous":
            q += " AND producteur_nom=?"; params.append(f_prod)
        if f_stat != "Tous":
            q += " AND statut=?"; params.append(f_stat)
        q += " ORDER BY created_at DESC"
        orders = db.execute(q, params).fetchall()

        rows = []
        for o in orders:
            ech = get_echeance(o["date_enlevement"], o["payment_terms"])
            lvl = alert_level(o["date_enlevement"], o["payment_terms"], o["statut"])
            flag = {"red": "🔴 ", "orange": "🟠 ", "blue": "", "green": "✅ ", "gray": ""}[lvl]
            comm_eur = (o["montant"] or 0) * (o["taux_commission"] or 0) / 100
            rows.append({
                "Proforma":     o["proforma"],
                "Producteur":   o["producteur_nom"],
                "Client":       o["client_nom"],
                "Pays":         o["pays"],
                "Montant":      fmt_money(o["montant"], o["devise"]),
                "Commission":   fmt_money(comm_eur),
                "Enlèvement":   fmt_date(o["date_enlevement"]),
                "Échéance":     flag + (ech.strftime("%d/%m/%Y") if ech else "—"),
                "Statut":       o["statut"],
                "Comm.":        o["comm_statut"],
            })

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            total = sum(o["montant"] or 0 for o in orders)
            total_c = sum((o["montant"] or 0) * (o["taux_commission"] or 0) / 100 for o in orders)
            st.caption(f"**{len(orders)} commande(s)** · CA : {fmt_money(total)} · Commissions : {fmt_money(total_c)}")
        else:
            st.info("Aucune commande trouvée.")

    # ══ NOUVELLE COMMANDE ════════════════════════════════════════════════════
    with tab2:
        with st.form("form_nouvelle_commande", clear_on_submit=True):
            st.markdown("**📍 Localisation & client**")
            r1a, r1b = st.columns(2)
            pays_sel = r1a.selectbox("Pays de destination *", [""] + pays_list)
            clients_fp = [e["nom"] for e in entreprises
                          if not pays_sel or e["pays_destination"] == pays_sel]
            client_sel = r1b.selectbox(
                "Client *" + (f" ({len(clients_fp)} dans ce pays)" if pays_sel and clients_fp else ""),
                [""] + clients_fp
            )

            st.markdown("**📄 Références**")
            r2a, r2b, r2c, r2d = st.columns(4)
            # Producteurs liés au client sélectionné
            prods_client = []
            if client_sel:
                ent_row = db.execute(
                    "SELECT producteurs_lies FROM entreprises WHERE nom=? AND archived=0",
                    (client_sel,)).fetchone()
                if ent_row and ent_row["producteurs_lies"]:
                    prods_client = [p.strip() for p in ent_row["producteurs_lies"].split("|") if p.strip()]

            all_prod_names = [p["nom"] for p in producteurs]
            if prods_client:
                # Proposer d'abord les producteurs du client, puis les autres
                autres = [p for p in all_prod_names if p not in prods_client]
                prod_options = [""] + prods_client + (["─── Autres ───"] + autres if autres else [])
                st.info(f"💡 Producteurs habituels de **{client_sel}** : {', '.join(prods_client)}")
            else:
                prod_options = [""] + all_prod_names

            prod_sel = r2a.selectbox("Producteur *", prod_options,
                format_func=lambda x: x if x != "─── Autres ───" else "── Autres producteurs ──")
            if prod_sel == "─── Autres ───":
                prod_sel = ""
            proforma   = r2b.text_input("N° Proforma *", placeholder="PF-2026-XXX")
            cmd_client = r2c.text_input("N° Commande client", placeholder="Optionnel")
            date_cmd   = r2d.date_input("Date de commande *", value=date.today())

            # Taux auto selon producteur
            taux_defaut = TAUX_AUTO.get(prod_sel, 0.0) if prod_sel else 0.0

            st.markdown("**💶 Financier**")
            r3a, r3b, r3c, r3d = st.columns(4)
            montant_str = r3a.text_input("Montant *", placeholder="Ex: 18500",
                                          help="Saisissez le montant sans symbole")
            devise  = r3b.selectbox("Devise", DEVISES)
            taux    = r3c.number_input("Commission (%)",
                                        min_value=0.0, max_value=100.0,
                                        value=taux_defaut, step=0.5, format="%.1f",
                                        help="Taux auto : 8% pour Maison Léda")
            terms   = r3d.selectbox("Paiement", [30, 45, 60, 90, 0],
                                    format_func=lambda x: f"{x} jours" if x else "À l'enlèvement")

            if prod_sel in TAUX_AUTO:
                st.info(f"ℹ️ Taux de commission automatique pour **{prod_sel}** : {TAUX_AUTO[prod_sel]}%")

            st.markdown("**🚢 Logistique**")
            r4a, r4b, r4c = st.columns(3)
            enlevement = r4a.date_input("Date d'enlèvement", value=None,
                                         help="Laisser vide si inconnue")
            statut = r4b.selectbox("Statut", ["En cours", "Livré", "Payé", "En retard"])
            facture = r4c.text_input("N° Facture finale", placeholder="Si connu")

            co_agent = st.text_input("Co-agent", placeholder="Ex : Asianet Fine Sourcing")
            taux_co  = 0.0
            if co_agent:
                taux_co = st.number_input("Part co-agent (%)", min_value=0.0,
                                           max_value=100.0, step=0.5)

            notes = st.text_area("Notes", height=70)

            submitted = st.form_submit_button("💾 Enregistrer la commande",
                                               use_container_width=True)
            if submitted:
                errors = []
                if not proforma:   errors.append("N° Proforma obligatoire")
                if not prod_sel:   errors.append("Sélectionnez un producteur")
                if not client_sel: errors.append("Sélectionnez un client")
                if not montant_str.strip(): errors.append("Montant obligatoire")
                if errors:
                    for e in errors: st.error(e)
                else:
                    try:
                        montant = float(montant_str.replace(",", ".").replace(" ", ""))
                    except ValueError:
                        st.error("Montant invalide — saisissez un nombre.")
                        montant = None

                    existing = db.execute("SELECT id FROM commandes WHERE proforma=?",
                                          (proforma,)).fetchone()
                    if existing:
                        st.error(f"❌ Le proforma **{proforma}** existe déjà.")
                    else:
                        prod_row = next((p for p in producteurs if p["nom"] == prod_sel), None)
                        prod_id  = prod_row["id"] if prod_row else None
                        enlev_s  = enlevement.strftime("%Y-%m-%d") if enlevement else None
                        date_cmd_s = date_cmd.strftime("%Y-%m-%d")

                        # Statut commission
                        # Maison Léda : éligible dès l'enlèvement (fin de mois)
                        # Autres : éligible après paiement client
                        if prod_sel == "Maison Léda" and enlev_s:
                            cs = "Dues"
                        elif statut == "Payé":
                            cs = "Dues"
                        elif enlev_s:
                            cs = "À venir"
                        else:
                            cs = "À venir"

                        db.execute("""INSERT INTO commandes
                            (proforma, cmd_client, facture_finale, client_nom, pays,
                             producteur_id, producteur_nom, montant, devise,
                             taux_commission, payment_terms, date_commande,
                             date_enlevement, statut, comm_statut,
                             co_agent, taux_co_agent, notes)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (proforma, cmd_client, facture, client_sel, pays_sel,
                             prod_id, prod_sel, montant, devise, taux,
                             terms, date_cmd_s, enlev_s, statut, cs,
                             co_agent, taux_co, notes))
                        db.commit()

                        # Mettre à jour producteurs_lies sur la fiche client
                        if client_sel and prod_sel:
                            ent_row = db.execute(
                                "SELECT id, producteurs_lies FROM entreprises WHERE nom=? AND archived=0",
                                (client_sel,)).fetchone()
                            if ent_row:
                                existing = [p.strip() for p in (ent_row["producteurs_lies"] or "").split("|") if p.strip()]
                                if prod_sel not in existing:
                                    existing.append(prod_sel)
                                    db.execute("UPDATE entreprises SET producteurs_lies=? WHERE id=?",
                                               ("|".join(existing), ent_row["id"]))
                                    db.commit()
                                    st.info(f"📎 **{prod_sel}** ajouté aux producteurs de **{client_sel}**")

                            # Mettre à jour mandats producteur si nouveau pays
                            prod_row2 = db.execute(
                                "SELECT id FROM producteurs WHERE nom=? AND archived=0",
                                (prod_sel,)).fetchone()
                            if prod_row2 and pays_sel:
                                ex_mandat = db.execute(
                                    "SELECT id FROM producteur_mandats WHERE producteur_id=? AND pays=?",
                                    (prod_row2["id"], pays_sel)).fetchone()
                                if not ex_mandat:
                                    db.execute("""INSERT INTO producteur_mandats
                                        (producteur_id,pays,statut,commission_applicable,notes)
                                        VALUES (?,?,?,?,?)""",
                                        (prod_row2["id"], pays_sel,
                                         "Distribué sous votre suivi", 1,
                                         f"Ajouté auto via commande {proforma}"))
                                    db.commit()

                                # Mettre à jour Distribution automatiquement
                                try:
                                    ex_dist = db.execute(
                                        "SELECT id FROM distribution WHERE producteur_id=? AND pays=? AND produit_id IS NULL",
                                        (prod_row2["id"], pays_sel)).fetchone()
                                    if not ex_dist:
                                        db.execute("""INSERT INTO distribution
                                            (producteur_id, pays, statut,
                                             commission_applicable, client_actuel, notes)
                                            VALUES (?,?,?,?,?,?)""",
                                            (prod_row2["id"], pays_sel,
                                             "Distribué sous votre suivi", 1,
                                             client_sel,
                                             f"Ajouté auto via commande {proforma}"))
                                        db.commit()
                                        st.info(f"🌍 Distribution mise à jour : **{prod_sel}** → **{pays_sel}**")
                                    else:
                                        # Mettre à jour le client actuel si vide
                                        db.execute("""UPDATE distribution SET client_actuel=?
                                            WHERE id=? AND (client_actuel IS NULL OR client_actuel='')""",
                                            (client_sel, ex_dist["id"]))
                                        db.commit()
                                except Exception:
                                    pass

                        st.success(f"✅ Commande **{proforma}** enregistrée — Commission : {cs}")
                        st.balloons()

    # ══ MODIFIER ══════════════════════════════════════════════════════════════
    with tab3:
        all_orders = db.execute(
            "SELECT * FROM commandes WHERE archived=0 ORDER BY created_at DESC"
        ).fetchall()
        if not all_orders:
            st.info("Aucune commande à modifier.")
        else:
            sel_pf = st.selectbox(
                "Choisir une commande",
                [o["proforma"] for o in all_orders],
                format_func=lambda x: next(
                    (f"{o['proforma']} — {o['producteur_nom']} / {o['client_nom']} ({o['pays']})"
                     for o in all_orders if o["proforma"] == x), x
                )
            )
            sel = next((o for o in all_orders if o["proforma"] == sel_pf), None)
            if sel:
                # Double-check documents
                docs_client = None
                if sel["client_nom"]:
                    ent = db.execute(
                        "SELECT docs_requis FROM entreprises WHERE nom=? AND archived=0",
                        (sel["client_nom"],)
                    ).fetchone()
                    if ent and ent["docs_requis"]:
                        docs_list = [d.strip() for d in ent["docs_requis"].split("|") if d.strip()]
                        if docs_list:
                            st.markdown("#### ✅ Double-check documents requis pour ce client")
                            all_checked = True
                            for doc in docs_list:
                                checked = st.checkbox(f"✓ {doc}", key=f"doc_{sel['id']}_{doc}")
                                if not checked:
                                    all_checked = False
                            if all_checked:
                                st.success("✅ Tous les documents sont confirmés.")
                            else:
                                st.warning("⚠️ Certains documents ne sont pas encore confirmés.")
                            st.markdown("---")

                with st.form("form_edit_commande"):
                    e1, e2, e3 = st.columns(3)
                    new_statut = e1.selectbox("Statut",
                        ["En cours", "Livré", "Payé", "En retard"],
                        index=["En cours", "Livré", "Payé", "En retard"].index(sel["statut"])
                              if sel["statut"] in ["En cours", "Livré", "Payé", "En retard"] else 0)

                    # Statuts commission enrichis
                    comm_statuts = ["À venir", "Dues", "Payé"]
                    new_cs = e2.selectbox("Commission",
                        comm_statuts,
                        index=comm_statuts.index(sel["comm_statut"])
                              if sel["comm_statut"] in comm_statuts else 0)
                    new_facture = e3.text_input("N° Facture finale",
                                                value=sel["facture_finale"] or "")

                    enlev_val = None
                    if sel["date_enlevement"]:
                        try:
                            enlev_val = datetime.strptime(
                                sel["date_enlevement"], "%Y-%m-%d").date()
                        except Exception:
                            pass
                    new_enlev = st.date_input("Date d'enlèvement", value=enlev_val)
                    new_notes = st.text_area("Notes", value=sel["notes"] or "",
                                              height=70)

                    # Tarifs envoyés
                    tarifs_envoyes = st.checkbox(
                        "📋 Nouveaux tarifs à jour envoyés au client",
                        value=bool(sel["tarifs_envoyes"] if "tarifs_envoyes" in sel.keys() else 0)
                    )

                    sa, sb = st.columns(2)
                    save = sa.form_submit_button("💾 Sauvegarder",
                                                  use_container_width=True)
                    arch = sb.form_submit_button("🗑️ Archiver",
                                                  use_container_width=True)

                    if save:
                        enlev_s = new_enlev.strftime("%Y-%m-%d") if new_enlev else None

                        # Règles éligibilité commission
                        # Maison Léda : dues dès enlèvement
                        # Autres : dues seulement si enlèvement + payé
                        if sel["producteur_nom"] == "Maison Léda":
                            if enlev_s:
                                new_cs = "Dues"
                            else:
                                new_cs = new_cs  # garder le choix manuel
                        else:
                            if new_statut == "Payé" and enlev_s:
                                new_cs = "Dues"
                            elif enlev_s and new_statut != "Payé":
                                new_cs = "À venir"

                        db.execute("""UPDATE commandes SET statut=?, comm_statut=?,
                            date_enlevement=?, facture_finale=?, notes=? WHERE id=?""",
                            (new_statut, new_cs, enlev_s, new_facture,
                             new_notes, sel["id"]))
                        db.commit()

                        # Alerte si commission devient éligible
                        if new_cs == "Dues" and sel["comm_statut"] != "Dues":
                            st.success(
                                f"✅ Commande mise à jour — "
                                f"💰 Commission maintenant **due** pour {sel['proforma']} !"
                            )
                        else:
                            st.success("✅ Commande mise à jour.")
                        st.rerun()

                    if arch:
                        db.execute("UPDATE commandes SET archived=1 WHERE id=?",
                                   (sel["id"],))
                        db.commit()
                        st.rerun()

    db.close()
