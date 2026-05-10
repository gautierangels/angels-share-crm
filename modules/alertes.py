import streamlit as st
import pandas as pd
import urllib.parse
from database import get_db
from utils import fmt_date, fmt_money, get_echeance
from datetime import date, timedelta, datetime

LANGUES_RELANCE = {
    "Anglais":  "EN",
    "Français": "FR",
    "Chinois":  "ZH",
    "Japonais": "EN",  # fallback anglais
    "Coréen":   "EN",
    "Khmer":    "EN",
    "Thaï":     "EN",
    "Autre":    "EN",
}

RELANCE_CLIENT = {
    "EN": {
        "subject": "Payment Reminder — Invoice {ref} — Due {due}",
        "body": """Dear {prenom} {nom},

I hope this message finds you well.

I am writing to kindly remind you that the payment for the following invoice is due on {due}:

  • Supplier: {producteur}
  • Invoice / Reference: {ref}
  • Amount: {montant}
  • Due date: {due}

Could you please confirm that payment has been arranged, or let us know the expected transfer date?

Please do not hesitate to contact me if you have any questions.

Many thanks in advance for your prompt attention to this matter.

Kind regards,
Gautier Salinier
Angels' Share Marketing Limited"""
    },
    "FR": {
        "subject": "Rappel de paiement — Facture {ref} — Échéance {due}",
        "body": """Bonjour {prenom} {nom},

J'espère que vous allez bien.

Je me permets de vous rappeler que le paiement de la facture suivante arrive à échéance le {due} :

  • Fournisseur : {producteur}
  • Référence : {ref}
  • Montant : {montant}
  • Échéance : {due}

Pourriez-vous confirmer que le virement a bien été initié, ou nous indiquer la date de règlement prévue ?

N'hésitez pas à me contacter pour toute question.

Avec mes remerciements anticipés,
Gautier Salinier
Angels' Share Marketing Limited"""
    },
    "ZH": {
        "subject": "付款提醒 — 发票 {ref} — 到期日 {due}",
        "body": """您好 {prenom} {nom}，

希望您一切安好。

谨此提醒，以下发票的付款将于 {due} 到期：

  • 供应商：{producteur}
  • 发票编号：{ref}
  • 金额：{montant}
  • 到期日：{due}

请问款项是否已安排汇出？如有任何问题，欢迎随时联系。

谢谢您的配合。

此致
Gautier Salinier
Angels' Share Marketing Limited"""
    }
}

VERIF_PRODUCTEUR = {
    "subject": "Vérification paiement — {client} ({pays}) — {ref} — Échéance {due}",
    "body": """Bonjour {prenom_prod},

J'espère que vous allez bien.

Je vous contacte au sujet de la facture suivante dont l'échéance approche :

  • Client : {client} ({pays})
  • Référence : {ref}
  • Montant : {montant}
  • Date d'enlèvement : {enlevement}
  • Échéance de paiement : {due}

Avez-vous déjà reçu le règlement de votre client pour cette livraison ?
Dans le cas contraire, pourriez-vous surveiller un éventuel virement entrant et m'en informer dès réception ?

Si le paiement a déjà été effectué, merci de me le confirmer afin que je puisse mettre à jour nos dossiers.

Merci beaucoup et bonne journée,
Gautier Salinier
Angels' Share Marketing Limited"""
}


def make_mailto(to_list, cc_list, bcc_list, subject, body):
    to  = ",".join(to_list)
    cc  = ",".join(cc_list)
    bcc = ",".join(bcc_list)
    url = f"mailto:{urllib.parse.quote(to)}"
    url += f"?subject={urllib.parse.quote(subject)}"
    if cc:  url += f"&cc={urllib.parse.quote(cc)}"
    if bcc: url += f"&bcc={urllib.parse.quote(bcc)}"
    url += f"&body={urllib.parse.quote(body)}"
    return url


def render():
    st.markdown("## 🔔 Alertes & Relances")
    db = get_db()

    today = date.today()

    # Récupérer toutes les commandes non payées avec date d'enlèvement
    orders = db.execute("""
        SELECT c.*, p.nom as prod_nom_full, p.code as prod_code
        FROM commandes c
        LEFT JOIN producteurs p ON p.id = c.producteur_id
        WHERE c.archived=0 AND c.statut != 'Payé'
        AND c.date_enlevement IS NOT NULL
        ORDER BY c.date_enlevement
    """).fetchall()

    # Catégoriser
    en_retard, urgentes, a_venir_4j, a_venir_plus = [], [], [], []

    for o in orders:
        ech = get_echeance(o["date_enlevement"], o["payment_terms"])
        if not ech:
            continue
        diff = (ech - today).days
        if diff < 0:
            en_retard.append((diff, o, ech))
        elif diff <= 4:
            urgentes.append((diff, o, ech))
        elif diff <= 14:
            a_venir_4j.append((diff, o, ech))
        else:
            a_venir_plus.append((diff, o, ech))

    # ── KPIs ─────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔴 En retard",     len(en_retard),  delta="urgent" if en_retard else None, delta_color="inverse")
    k2.metric("🟠 Dans 4 jours",  len(urgentes),   delta="à traiter" if urgentes else None, delta_color="inverse")
    k3.metric("🔵 Dans 14 jours", len(a_venir_4j))
    k4.metric("⚪ Au-delà",       len(a_venir_plus))

    st.markdown("---")

    def render_alerte(diff, o, ech, niveau):
        """Affiche une alerte avec brouillons email."""
        ref = o["facture_finale"] or o["proforma"]
        montant_str = fmt_money(o["montant"], o["devise"])
        due_str = ech.strftime("%d/%m/%Y")
        enl_str = fmt_date(o["date_enlevement"])
        diff_label = f"{abs(diff)}j de retard" if diff < 0 else f"dans {diff}j"

        css = {"rouge": "#FFF0F0;border-left:4px solid #C0392B",
               "orange": "#FFF8F0;border-left:4px solid #E67E22",
               "bleu": "#F0F4FF;border-left:4px solid #2E86DE"}[niveau]
        icon = {"rouge": "🔴", "orange": "🟠", "bleu": "🔵"}[niveau]

        st.markdown(
            f'<div style="background:{css};padding:10px 14px;border-radius:8px;margin:6px 0;">'
            f'<b>{icon} {o["proforma"]}</b> — {o["client_nom"]} ({o["pays"]})<br>'
            f'<small><b>{o["producteur_nom"]}</b> · Ref: {ref} · {montant_str} · '
            f'Éch: {due_str} ({diff_label})</small></div>',
            unsafe_allow_html=True
        )

        with st.expander(f"📧 Brouillons email — {o['proforma']}"):
            col_prod, col_client = st.columns(2)

            # ── Email au PRODUCTEUR (toujours en français) ─────────────────
            with col_prod:
                st.markdown("**📧 Email au producteur** *(vérification paiement reçu)*")

                # Contact comptabilité du producteur
                ctc_prod = db.execute("""
                    SELECT * FROM producteur_contacts
                    WHERE producteur_id=? AND role='Comptabilité'
                    LIMIT 1
                """, (o["producteur_id"],)).fetchone()
                ctc_prod_principal = db.execute("""
                    SELECT * FROM producteur_contacts
                    WHERE producteur_id=? AND role='Contact principal'
                    LIMIT 1
                """, (o["producteur_id"],)).fetchone()

                prenom_prod = ""
                email_prod_to = []
                email_prod_cc = []

                if ctc_prod:
                    prenom_prod = ctc_prod["prenom"] or ctc_prod["nom"] or ""
                    if ctc_prod["email"]:
                        email_prod_to.append(ctc_prod["email"])
                if ctc_prod_principal and ctc_prod_principal["email"]:
                    email_prod_cc.append(ctc_prod_principal["email"])

                subj_prod = VERIF_PRODUCTEUR["subject"].format(
                    client=o["client_nom"], pays=o["pays"],
                    ref=ref, due=due_str)
                body_prod = VERIF_PRODUCTEUR["body"].format(
                    prenom_prod=prenom_prod or "Madame, Monsieur",
                    client=o["client_nom"], pays=o["pays"],
                    ref=ref, montant=montant_str,
                    enlevement=enl_str, due=due_str)

                # Afficher les destinataires
                if email_prod_to:
                    st.caption(f"À : {', '.join(email_prod_to)}")
                if email_prod_cc:
                    st.caption(f"CC : {', '.join(email_prod_cc)}")
                else:
                    st.caption("⚠️ Aucun email comptabilité enregistré pour ce producteur")

                st.text_area("Corps du message", value=body_prod, height=200,
                             key=f"body_prod_{o['id']}")

                mailto_prod = make_mailto(email_prod_to, email_prod_cc, [], subj_prod, body_prod)
                st.markdown(
                    f'<a href="{mailto_prod}"><button style="background:#1A6EA5;color:white;'
                    f'border:none;padding:8px 16px;border-radius:6px;cursor:pointer;width:100%;">'
                    f'📧 Ouvrir dans Outlook (Producteur)</button></a>',
                    unsafe_allow_html=True)

            # ── Email au CLIENT ───────────────────────────────────────────
            with col_client:
                st.markdown("**📧 Email au client** *(relance paiement)*")

                # Contacts de l'entreprise cliente
                ent = db.execute(
                    "SELECT * FROM entreprises WHERE nom=? AND archived=0",
                    (o["client_nom"],)).fetchone()

                ctcs_client = []
                if ent:
                    ctcs_client = db.execute(
                        "SELECT * FROM contacts WHERE entreprise_id=? AND archived=0",
                        (ent["id"],)).fetchall()

                # Sélectionner destinataires
                if ctcs_client:
                    st.caption("Sélectionnez les destinataires :")
                    to_emails, cc_emails, bcc_emails = [], [], []
                    prenom_client = nom_client = ""
                    langue_client = "Anglais"

                    for c in ctcs_client:
                        civ = f"{c['civilite']} " if c["civilite"] and c["civilite"] != "—" else ""
                        prn = c["prenom"] or ""
                        nom = c["nom"] or ""
                        nom_display = f"{civ}{prn} {nom}".strip()
                        role_defaut = c["email_role"] or "To"

                        col_chk, col_role = st.columns([3, 1])
                        checked = col_chk.checkbox(
                            f"{nom_display} — {c['position'] or '—'} ({c['email'] or 'pas d email'})",
                            value=(role_defaut == "To"),
                            key=f"chk_client_{o['id']}_{c['id']}")
                        role_sel = col_role.selectbox("Rôle", ["To","CC","BCC"],
                            index=["To","CC","BCC"].index(role_defaut) if role_defaut in ["To","CC","BCC"] else 0,
                            key=f"role_client_{o['id']}_{c['id']}")

                        if checked and c["email"]:
                            if role_sel == "To":
                                to_emails.append(c["email"])
                                if not prenom_client:
                                    prenom_client = prn
                                    nom_client = nom
                                    langue_client = c["langue"] or "Anglais"
                            elif role_sel == "CC":
                                cc_emails.append(c["email"])
                            else:
                                bcc_emails.append(c["email"])
                else:
                    st.caption("⚠️ Aucun contact enregistré pour ce client")
                    to_emails = cc_emails = bcc_emails = []
                    prenom_client = nom_client = ""
                    langue_client = "Anglais"

                # Langue de relance
                lang_code = LANGUES_RELANCE.get(langue_client, "EN")
                tmpl = RELANCE_CLIENT[lang_code]

                subj_client = tmpl["subject"].format(ref=ref, due=due_str)
                body_client = tmpl["body"].format(
                    prenom=prenom_client or "",
                    nom=nom_client or o["client_nom"],
                    producteur=o["producteur_nom"],
                    ref=ref, montant=montant_str, due=due_str)

                st.text_area("Corps du message", value=body_client, height=200,
                             key=f"body_client_{o['id']}")

                if to_emails or cc_emails:
                    mailto_client = make_mailto(to_emails, cc_emails, bcc_emails,
                                               subj_client, body_client)
                    st.markdown(
                        f'<a href="{mailto_client}"><button style="background:#C0392B;color:white;'
                        f'border:none;padding:8px 16px;border-radius:6px;cursor:pointer;width:100%;">'
                        f'📧 Ouvrir dans Outlook (Client)</button></a>',
                        unsafe_allow_html=True)
                else:
                    st.warning("Sélectionnez au moins un destinataire.")

            # Bouton marquer comme traité
            if st.button(f"✅ Marquer comme suivi", key=f"suivi_{o['id']}"):
                from modules.actions import render as _
                db.execute("""INSERT INTO actions
                    (titre,entite_type,entite_nom,priorite,statut,notes)
                    VALUES (?,?,?,?,?,?)""",
                    (f"Relance envoyée — {o['proforma']} / {o['client_nom']}",
                     "Commande", o["proforma"], "Haute", "Fait",
                     f"Relance échéance {due_str}"))
                db.commit()
                st.success("Action de suivi enregistrée.")

    # ── AFFICHAGE PAR CATÉGORIE ───────────────────────────────────────────────
    if en_retard:
        st.markdown("### 🔴 Paiements en retard")
        for diff, o, ech in sorted(en_retard, key=lambda x: x[0]):
            render_alerte(diff, o, ech, "rouge")

    if urgentes:
        st.markdown("### 🟠 Échéances dans 4 jours ou moins")
        for diff, o, ech in sorted(urgentes, key=lambda x: x[0]):
            render_alerte(diff, o, ech, "orange")

    if a_venir_4j:
        st.markdown("### 🔵 Échéances dans les 14 jours")
        for diff, o, ech in sorted(a_venir_4j, key=lambda x: x[0]):
            render_alerte(diff, o, ech, "bleu")

    if not en_retard and not urgentes and not a_venir_4j:
        st.success("✅ Aucune échéance urgente en ce moment.")

    if a_venir_plus:
        with st.expander(f"⚪ {len(a_venir_plus)} échéance(s) à venir (> 14 jours)"):
            rows = []
            for diff, o, ech in sorted(a_venir_plus, key=lambda x: x[0]):
                rows.append({
                    "Proforma":    o["proforma"],
                    "Client":      o["client_nom"],
                    "Pays":        o["pays"],
                    "Producteur":  o["producteur_nom"],
                    "Montant":     fmt_money(o["montant"], o["devise"]),
                    "Échéance":    ech.strftime("%d/%m/%Y"),
                    "Dans":        f"{diff}j",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    db.close()
