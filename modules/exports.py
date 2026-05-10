import streamlit as st
import pandas as pd
import io
from database import get_db
from utils import fmt_date, fmt_money
from datetime import date


def render():
    st.markdown("## 📤 Exports")
    db = get_db()

    st.markdown("Exportez toutes vos données en Excel. Chaque onglet correspond à un jeu de données.")

    col1, col2 = st.columns(2)
    date_debut = col1.date_input("Période — du", value=date(date.today().year, 1, 1))
    date_fin   = col2.date_input("Période — au", value=date.today())
    dd = date_debut.strftime("%Y-%m-%d")
    df_str = date_fin.strftime("%Y-%m-%d")

    st.markdown("---")

    # ── Export complet toutes données ─────────────────────────────────────────
    if st.button("📊 Générer l'export complet (tous modules)", type="primary",
                 use_container_width=True):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:

            # Commandes
            commandes = db.execute("""
                SELECT proforma, client_nom, pays, producteur_nom,
                       montant, devise, taux_commission,
                       ROUND(montant * taux_commission / 100, 2) as commission_eur,
                       payment_terms, date_commande, date_enlevement,
                       statut, comm_statut, co_agent, notes
                FROM commandes WHERE archived=0
                AND date_commande BETWEEN ? AND ?
                ORDER BY date_commande DESC
            """, (dd, df_str)).fetchall()
            if commandes:
                pd.DataFrame([dict(r) for r in commandes]).rename(columns={
                    "proforma": "Proforma", "client_nom": "Client",
                    "pays": "Pays", "producteur_nom": "Producteur",
                    "montant": "Montant", "devise": "Devise",
                    "taux_commission": "Taux comm. %",
                    "commission_eur": "Commission EUR",
                    "payment_terms": "Paiement (jours)",
                    "date_commande": "Date commande",
                    "date_enlevement": "Date enlèvement",
                    "statut": "Statut", "comm_statut": "Statut commission",
                    "co_agent": "Co-agent", "notes": "Notes",
                }).to_excel(writer, sheet_name="Commandes", index=False)

            # Commissions
            comm_data = db.execute("""
                SELECT proforma, producteur_nom, client_nom, pays,
                       montant, taux_commission,
                       ROUND(montant * taux_commission / 100, 2) as commission,
                       date_enlevement, payment_terms, comm_statut, co_agent, taux_co_agent
                FROM commandes WHERE archived=0
                ORDER BY comm_statut, producteur_nom
            """).fetchall()
            if comm_data:
                pd.DataFrame([dict(r) for r in comm_data]).rename(columns={
                    "proforma": "Proforma", "producteur_nom": "Producteur",
                    "client_nom": "Client", "pays": "Pays",
                    "montant": "Montant", "taux_commission": "Taux %",
                    "commission": "Commission EUR",
                    "date_enlevement": "Date enlèvement",
                    "payment_terms": "Paiement (j)",
                    "comm_statut": "Statut commission",
                    "co_agent": "Co-agent", "taux_co_agent": "Part co-agent %",
                }).to_excel(writer, sheet_name="Commissions", index=False)

            # Contacts
            contacts = db.execute("""
                SELECT c.nom, c.position, e.nom as entreprise, e.pays_destination as pays,
                       c.email, c.mobile, c.wechat, c.langue, c.email_role, c.notes
                FROM contacts c
                LEFT JOIN entreprises e ON e.id=c.entreprise_id
                WHERE c.archived=0 ORDER BY c.nom
            """).fetchall()
            if contacts:
                pd.DataFrame([dict(r) for r in contacts]).rename(columns={
                    "nom": "Nom", "position": "Poste", "entreprise": "Entreprise",
                    "pays": "Pays", "email": "Email", "mobile": "Mobile",
                    "wechat": "WeChat", "langue": "Langue",
                    "email_role": "Rôle email", "notes": "Notes",
                }).to_excel(writer, sheet_name="Contacts", index=False)

            # Producteurs
            prods = db.execute("""
                SELECT p.nom, p.code, p.region, p.statut,
                       p.adresse_ligne1, p.code_postal, p.ville, p.pays_adresse,
                       p.website, p.notes,
                       COUNT(DISTINCT c.id) as nb_commandes,
                       COALESCE(SUM(c.montant),0) as ca_total
                FROM producteurs p
                LEFT JOIN commandes c ON c.producteur_id=p.id AND c.archived=0
                WHERE p.archived=0
                GROUP BY p.id ORDER BY p.nom
            """).fetchall()
            if prods:
                pd.DataFrame([dict(r) for r in prods]).rename(columns={
                    "nom": "Producteur", "code": "Code", "region": "Région",
                    "statut": "Statut", "adresse_ligne1": "Adresse",
                    "code_postal": "CP", "ville": "Ville", "pays_adresse": "Pays",
                    "website": "Site web", "notes": "Notes",
                    "nb_commandes": "Nb commandes", "ca_total": "CA total",
                }).to_excel(writer, sheet_name="Producteurs", index=False)

            # Frais
            frais = db.execute("""
                SELECT date_frais, description, categorie, moyen_paiement,
                       montant, devise, cat_comptable, notes
                FROM frais
                WHERE date_frais BETWEEN ? AND ?
                ORDER BY date_frais DESC
            """, (dd, df_str)).fetchall()
            if frais:
                pd.DataFrame([dict(r) for r in frais]).rename(columns={
                    "date_frais": "Date", "description": "Description",
                    "categorie": "Catégorie", "moyen_paiement": "Moyen paiement",
                    "montant": "Montant", "devise": "Devise",
                    "cat_comptable": "Type comptable", "notes": "Notes",
                }).to_excel(writer, sheet_name="Frais", index=False)

            # Actions
            actions = db.execute("""
                SELECT titre, entite_type, entite_nom, priorite, statut, due_date, notes
                FROM actions ORDER BY
                    CASE priorite WHEN 'Urgente' THEN 0 WHEN 'Haute' THEN 1
                    WHEN 'Normale' THEN 2 ELSE 3 END
            """).fetchall()
            if actions:
                pd.DataFrame([dict(r) for r in actions]).rename(columns={
                    "titre": "Action", "entite_type": "Type entité",
                    "entite_nom": "Entité", "priorite": "Priorité",
                    "statut": "Statut", "due_date": "Échéance", "notes": "Notes",
                }).to_excel(writer, sheet_name="Actions", index=False)

            # Distribution
            dist = db.execute("""
                SELECT p.nom as producteur, p.code, d.pays, d.produit_nom,
                       d.statut, d.commission_applicable, d.client_actuel, d.notes
                FROM distribution d
                JOIN producteurs p ON p.id=d.producteur_id
                WHERE p.archived=0 ORDER BY p.nom, d.pays
            """).fetchall() if _table_exists(db, "distribution") else []
            if dist:
                pd.DataFrame([dict(r) for r in dist]).rename(columns={
                    "producteur": "Producteur", "code": "Code", "pays": "Pays",
                    "produit_nom": "Produit", "statut": "Statut distribution",
                    "commission_applicable": "Commission",
                    "client_actuel": "Client actuel", "notes": "Notes",
                }).to_excel(writer, sheet_name="Distribution", index=False)

            # Prospection
            pros = db.execute("""
                SELECT nom, type, pays, activite, etape, contact_nom,
                       contact_email, producteur_interet,
                       date_prochain_contact, notes
                FROM prospection WHERE archived=0 ORDER BY etape, nom
            """).fetchall() if _table_exists(db, "prospection") else []
            if pros:
                pd.DataFrame([dict(r) for r in pros]).rename(columns={
                    "nom": "Prospect", "type": "Type", "pays": "Pays",
                    "activite": "Activité", "etape": "Étape",
                    "contact_nom": "Contact", "contact_email": "Email",
                    "producteur_interet": "Producteur intérêt",
                    "date_prochain_contact": "Prochain contact", "notes": "Notes",
                }).to_excel(writer, sheet_name="Prospection", index=False)

            # Factures commissions
            facts = db.execute("""
                SELECT invoice_number, producteur_nom, date_facture,
                       montant_total, devise, contact_att, fichier
                FROM commission_invoices ORDER BY date_facture DESC
            """).fetchall() if _table_exists(db, "commission_invoices") else []
            if facts:
                pd.DataFrame([dict(r) for r in facts]).rename(columns={
                    "invoice_number": "N° Facture", "producteur_nom": "Producteur",
                    "date_facture": "Date", "montant_total": "Montant",
                    "devise": "Devise", "contact_att": "Att",
                    "fichier": "Fichier",
                }).to_excel(writer, sheet_name="Factures comm.", index=False)

        filename = f"angels_share_export_{date.today().strftime('%Y%m%d')}.xlsx"
        st.download_button(
            "⬇️ Télécharger l'export Excel complet",
            data=buf.getvalue(),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.success(f"✅ Export généré — {filename}")

    st.markdown("---")
    st.markdown("#### Exports individuels")

    # Exports rapides individuels
    exports = [
        ("📋 Commandes uniquement",     _export_commandes),
        ("💰 Commissions uniquement",   _export_commissions),
        ("🏢 Contacts uniquement",      _export_contacts),
        ("🧾 Frais uniquement",         _export_frais),
    ]
    cols = st.columns(4)
    for i, (label, fn) in enumerate(exports):
        with cols[i]:
            buf = fn(db, dd, df_str)
            st.download_button(label, data=buf,
                file_name=f"angels_{label.split()[1].lower()}_{date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
    db.close()


def _table_exists(db, name):
    r = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return r is not None


def _export_commandes(db, dd, df_str):
    rows = db.execute("""
        SELECT proforma, client_nom, pays, producteur_nom, montant, devise,
               taux_commission, ROUND(montant*taux_commission/100,2) as commission,
               date_enlevement, statut, comm_statut, notes
        FROM commandes WHERE archived=0 AND date_commande BETWEEN ? AND ?
        ORDER BY date_commande DESC
    """, (dd, df_str)).fetchall()
    buf = io.BytesIO()
    pd.DataFrame([dict(r) for r in rows]).to_excel(buf, index=False)
    return buf.getvalue()


def _export_commissions(db, dd, df_str):
    rows = db.execute("""
        SELECT proforma, producteur_nom, client_nom, pays, montant,
               taux_commission, ROUND(montant*taux_commission/100,2) as commission,
               comm_statut, date_enlevement
        FROM commandes WHERE archived=0 ORDER BY comm_statut, producteur_nom
    """).fetchall()
    buf = io.BytesIO()
    pd.DataFrame([dict(r) for r in rows]).to_excel(buf, index=False)
    return buf.getvalue()


def _export_contacts(db, dd, df_str):
    rows = db.execute("""
        SELECT c.nom, c.position, e.nom as entreprise, e.pays_destination,
               c.email, c.mobile, c.wechat, c.langue
        FROM contacts c LEFT JOIN entreprises e ON e.id=c.entreprise_id
        WHERE c.archived=0 ORDER BY c.nom
    """).fetchall()
    buf = io.BytesIO()
    pd.DataFrame([dict(r) for r in rows]).to_excel(buf, index=False)
    return buf.getvalue()


def _export_frais(db, dd, df_str):
    rows = db.execute("""
        SELECT date_frais, description, categorie, moyen_paiement,
               montant, devise, cat_comptable
        FROM frais WHERE date_frais BETWEEN ? AND ?
        ORDER BY date_frais DESC
    """, (dd, df_str)).fetchall()
    buf = io.BytesIO()
    pd.DataFrame([dict(r) for r in rows]).to_excel(buf, index=False)
    return buf.getvalue()
