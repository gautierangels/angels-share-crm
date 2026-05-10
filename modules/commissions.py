import streamlit as st
import pandas as pd
from database import get_db
from utils import fmt_money, fmt_date, get_echeance, alert_level
from datetime import date
import urllib.parse

REGLES = {
    "Maison Léda": "Éligible dès l'enlèvement — facturée en fin de mois même sans paiement client",
}

COMM_STATUTS = ["À venir", "Dues", "Payé"]


def render():
    st.markdown("## 💰 Commissions")
    db = get_db()

    # Migration statuts
    try:
        db.execute("UPDATE commandes SET comm_statut='À venir' WHERE comm_statut='Non éligible'")
        db.execute("UPDATE commandes SET comm_statut='Dues' WHERE comm_statut='En attente'")
        db.commit()
    except Exception:
        pass

    orders = db.execute("""
        SELECT c.*, p.code as prod_code
        FROM commandes c
        LEFT JOIN producteurs p ON p.id=c.producteur_id
        WHERE c.archived=0 ORDER BY c.created_at DESC
    """).fetchall()

    # KPIs
    total     = sum((o["montant"] or 0) * (o["taux_commission"] or 0) / 100 for o in orders)
    a_venir   = sum((o["montant"] or 0) * (o["taux_commission"] or 0) / 100
                    for o in orders if o["comm_statut"] == "À venir")
    dues      = sum((o["montant"] or 0) * (o["taux_commission"] or 0) / 100
                    for o in orders if o["comm_statut"] == "Dues")
    payees    = sum((o["montant"] or 0) * (o["taux_commission"] or 0) / 100
                    for o in orders if o["comm_statut"] == "Payé")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Portefeuille total", fmt_money(total))
    k2.metric("À venir", fmt_money(a_venir),
              help="Commandes passées, enlèvement non encore effectué")
    k3.metric("Commissions dues", fmt_money(dues),
              delta="⚠️ À encaisser" if dues else None, delta_color="inverse")
    k4.metric("Payées", fmt_money(payees))

    if total > 0:
        pct = int(payees / total * 100)
        st.progress(min(pct / 100, 1.0),
                    text=f"Taux de recouvrement : {pct}%")

    # Règles
    with st.expander("ℹ️ Règles d'éligibilité par producteur"):
        st.markdown("""
| Producteur | Éligibilité | Facturation |
|---|---|---|
| **Maison Léda** | Dès l'enlèvement | **Fin de mois, même sans paiement client** |
| **Famille Fabre** | Après paiement final client | Récapitulatif après le 14 |
| **Autres** | Après paiement final client | Mensuel ou par commande |

**Statuts :**
- 🔜 **À venir** — commande passée, enlèvement non encore effectué
- 💰 **Dues** — enlèvement effectué (ou paiement reçu pour les autres producteurs)
- ✅ **Payé** — commission encaissée
        """)

    st.markdown("---")

    # Alertes
    st.markdown("#### 🚨 Commissions dues — à encaisser")
    today = date.today()
    alert_orders = []
    for o in orders:
        if o["comm_statut"] != "Dues":
            continue
        ech = get_echeance(o["date_enlevement"], o["payment_terms"])
        diff = (ech - today).days if ech else None
        lvl  = alert_level(o["date_enlevement"], o["payment_terms"], o["statut"])
        alert_orders.append((diff or 0, lvl, o, ech))

    alert_orders.sort(key=lambda x: x[0])

    if alert_orders:
        for diff, lvl, o, ech in alert_orders:
            comm_m = (o["montant"] or 0) * (o["taux_commission"] or 0) / 100
            css    = "alerte-rouge" if lvl == "red" else "alerte-orange" if lvl == "orange" else "alerte-bleue"
            icon   = "🔴" if lvl == "red" else "🟠" if lvl == "orange" else "💰"
            diff_label = f"{abs(diff)}j de retard" if diff and diff < 0 else (f"dans {diff}j" if diff else "—")
            st.markdown(
                f'<div class="{css}">'
                f'<b>{icon} {o["proforma"]}</b> — {o["client_nom"]} ({o["pays"]})<br>'
                f'<small>{o["producteur_nom"]} · Éch. '
                f'{ech.strftime("%d/%m/%Y") if ech else "—"} ({diff_label}) · '
                f'Commission : <b>{fmt_money(comm_m)}</b></small>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Brouillon email compta
            prod_ctc = db.execute("""
                SELECT nom, email FROM producteur_contacts
                WHERE producteur_id=? AND role='Comptabilité' LIMIT 1
            """, (o["producteur_id"],)).fetchone()
            if prod_ctc and prod_ctc["email"]:
                subject = f"Vérification commission — {o['client_nom']} — {o['proforma']}"
                body = (
                    f"Bonjour {prod_ctc['nom'].split()[0]},\n\n"
                    f"Pourriez-vous confirmer la commission sur :\n"
                    f"Client : {o['client_nom']} / {o['pays']}\n"
                    f"Proforma : {o['proforma']}\n"
                    f"Montant : {fmt_money(o['montant'], o['devise'])}\n"
                    f"Commission : {fmt_money(comm_m)}\n\n"
                    f"Merci.\nGautier"
                )
                mailto = (f"mailto:{prod_ctc['email']}"
                          f"?subject={urllib.parse.quote(subject)}"
                          f"&body={urllib.parse.quote(body)}")
                st.markdown(
                    f'<a href="{mailto}"><button style="font-size:11px;padding:2px 8px;'
                    f'margin:2px 0 8px;border-radius:4px;border:1px solid #ccc;'
                    f'background:#f8f5f0;cursor:pointer;">📧 Brouillon vérif. compta</button></a>',
                    unsafe_allow_html=True
                )
    else:
        st.success("✅ Aucune commission due en attente.")

    st.markdown("---")

    # Tableau de suivi complet
    st.markdown("#### 📋 Suivi détaillé")
    f_cs = st.selectbox("Filtrer par statut", ["Tous"] + COMM_STATUTS)

    rows = []
    for o in orders:
        if f_cs != "Tous" and o["comm_statut"] != f_cs:
            continue
        ech     = get_echeance(o["date_enlevement"], o["payment_terms"])
        comm_m  = (o["montant"] or 0) * (o["taux_commission"] or 0) / 100
        if o["co_agent"] and o["taux_co_agent"]:
            part_as = comm_m * (1 - o["taux_co_agent"] / 100)
            part_ca = comm_m * o["taux_co_agent"] / 100
            comm_str = f"{fmt_money(part_as)} (AS) + {fmt_money(part_ca)} ({o['co_agent']})"
        else:
            comm_str = fmt_money(comm_m)

        icon_cs = {"À venir": "🔜", "Dues": "💰", "Payé": "✅"}.get(o["comm_statut"], "")
        rows.append({
            "Proforma":   o["proforma"],
            "Producteur": o["producteur_nom"],
            "Client":     o["client_nom"],
            "Pays":       o["pays"],
            "Montant":    fmt_money(o["montant"], o["devise"]),
            "Taux":       f"{o['taux_commission']}%",
            "Commission": comm_str,
            "Échéance":   ech.strftime("%d/%m/%Y") if ech else "—",
            "Statut":     f"{icon_cs} {o['comm_statut']}",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Mise à jour statut — menu enrichi
    st.markdown("##### Mettre à jour le statut commission")
    all_o = db.execute(
        "SELECT * FROM commandes WHERE archived=0 ORDER BY producteur_nom, pays, client_nom"
    ).fetchall()

    def label_commande(o):
        return (f"{o['producteur_nom']} · {o['pays']} · "
                f"{o['client_nom']} · {o['proforma']}")

    labels = [label_commande(o) for o in all_o]
    if labels:
        sel_label = st.selectbox("Commande", labels)
        sel_ord   = all_o[labels.index(sel_label)]

        # Nettoyer les anciennes valeurs (ex: "Facture proforma" -> "À venir")
        cs_val = sel_ord["comm_statut"] or "À venir"
        if cs_val not in COMM_STATUTS:
            cs_val = "À venir"
        new_cs = st.selectbox("Nouveau statut", COMM_STATUTS,
            index=COMM_STATUTS.index(cs_val))

        if st.button("💾 Mettre à jour", key="upd_cs"):
            db.execute("UPDATE commandes SET comm_statut=? WHERE id=?",
                       (new_cs, sel_ord["id"]))
            db.commit()
            st.success(f"✅ {label_commande(sel_ord)} → {new_cs}")
            st.rerun()

    # Récap par producteur
    st.markdown("#### 📊 Par producteur")
    by_prod = {}
    for o in orders:
        k = o["producteur_nom"]
        if k not in by_prod:
            by_prod[k] = {"a_venir": 0, "dues": 0, "payees": 0}
        c = (o["montant"] or 0) * (o["taux_commission"] or 0) / 100
        cs = o["comm_statut"]
        if cs == "À venir": by_prod[k]["a_venir"] += c
        elif cs == "Dues":  by_prod[k]["dues"]    += c
        elif cs == "Payé":  by_prod[k]["payees"]  += c

    if by_prod:
        df_bp = pd.DataFrame([{
            "Producteur":   k,
            "À venir":      fmt_money(v["a_venir"]),
            "Dues":         fmt_money(v["dues"]),
            "Payées":       fmt_money(v["payees"]),
        } for k, v in sorted(by_prod.items())])
        st.dataframe(df_bp, use_container_width=True, hide_index=True)

    db.close()
