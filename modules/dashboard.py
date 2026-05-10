import streamlit as st
import pandas as pd
import urllib.parse
import re
from database import get_db
from utils import fmt_money, fmt_date, get_echeance
from datetime import date, datetime, timedelta

# ── Config email par producteur ───────────────────────────────────────────────
EMAIL_CONFIG = {
    "Maison Léda":     {"from": "",  "signature": "Maison Léda - Gautier"},
    "Famille Baldès":  {"from": "",  "signature": "Famille Baldès - Gautier"},
    "Cognac Lhéraud":  {"from": "",  "signature": "Cognac Lhéraud - Gautier"},
    "_default":        {"from": "",  "signature": "Angels' Share - Gautier"},
}

def email_cfg(prod):
    return EMAIL_CONFIG.get(prod, EMAIL_CONFIG["_default"])

def relance_body(prenom, langue, prod, type_msg="inactif"):
    sig = email_cfg(prod)["signature"]
    p   = prenom or "Madame, Monsieur"

    msgs = {
        "inactif": {
            "Français": (
                f"Bonjour {p},\n\nJ'espère que vous allez bien et que vos affaires se portent bien.\n\n"
                f"Je me permets de vous contacter pour prendre de vos nouvelles et savoir si vous avez "
                f"des besoins en vins et spiritueux pour les prochaines semaines.\n\n"
                f"Je serais ravi de vous proposer nos dernières nouveautés et de discuter "
                f"de ce que je peux faire pour vous.\n\n"
                f"Au plaisir d'échanger avec vous,\n--\n[Signature : {sig}]"
            ),
            "Chinois": (
                f"您好 {p}，\n\n希望您一切安好，生意兴隆。\n\n"
                f"特此联系，想了解您近况如何，以及是否有葡萄酒或烈酒方面的采购需求。\n\n"
                f"期待与您交流，\n--\n[Signature : {sig}]"
            ),
            "_": (
                f"Dear {p},\n\nI hope this message finds you well.\n\n"
                f"I wanted to reach out to catch up and find out if you have any upcoming "
                f"needs in wines and spirits.\n\n"
                f"I would love to share our latest offerings with you.\n\n"
                f"Looking forward to hearing from you,\n--\n[Signature : {sig}]"
            ),
        },
        "appel": {
            "Français": (
                f"Bonjour {p},\n\nSeriez-vous disponible pour un appel téléphonique "
                f"dans les prochains jours ?\n\n"
                f"Dites-moi quel moment vous conviendrait le mieux.\n\n"
                f"Cordialement,\n--\n[Signature : {sig}]"
            ),
            "Chinois": (
                f"您好 {p}，\n\n请问您近期是否方便安排一次电话沟通？\n\n"
                f"请告知您方便的时间。\n\n此致，\n--\n[Signature : {sig}]"
            ),
            "_": (
                f"Dear {p},\n\nWould you be available for a quick call in the coming days?\n\n"
                f"Please let me know what time works best for you.\n\n"
                f"Best regards,\n--\n[Signature : {sig}]"
            ),
        },
        "visio": {
            "Français": (
                f"Bonjour {p},\n\nSeriez-vous disponible pour une réunion en visioconférence "
                f"dans les prochains jours ?\n\n"
                f"Dites-moi quel créneau vous conviendrait et je vous ferai parvenir "
                f"une invitation Teams/Zoom.\n\n"
                f"Au plaisir de vous retrouver,\n--\n[Signature : {sig}]"
            ),
            "Chinois": (
                f"您好 {p}，\n\n请问您近期是否方便安排一次视频会议？\n\n"
                f"请告知您方便的时间，我将发送会议邀请。\n\n"
                f"期待与您线上见面，\n--\n[Signature : {sig}]"
            ),
            "_": (
                f"Dear {p},\n\nWould you be available for a video call in the coming days?\n\n"
                f"Let me know your preferred time and I will send a Teams/Zoom invite.\n\n"
                f"Looking forward to connecting,\n--\n[Signature : {sig}]"
            ),
        },
    }
    lang_key = langue if langue in ("Français", "Chinois") else "_"
    return msgs.get(type_msg, msgs["inactif"]).get(lang_key, msgs[type_msg]["_"])


def make_mailto(email, subj, body):
    to = urllib.parse.quote(email or "")
    return (f"mailto:{to}"
            f"?subject={urllib.parse.quote(subj)}"
            f"&body={urllib.parse.quote(body)}")


def btn(label, href, color):
    return (f'<a href="{href}" target="_blank">'
            f'<button style="width:100%;background:{color};color:white;border:none;'
            f'padding:5px 4px;border-radius:6px;font-size:0.7rem;cursor:pointer;'
            f'white-space:nowrap;">{label}</button></a>')


def _jours_label(n):
    if n < 0:   return f"🔴 {abs(n)}j de retard"
    if n == 0:  return "🔴 Aujourd'hui"
    if n <= 4:  return f"🟠 dans {n}j"
    if n <= 14: return f"🔵 dans {n}j"
    return f"⚪ dans {n}j"


def render():
    db    = get_db()
    today = date.today()
    MOIS  = ["","Janvier","Février","Mars","Avril","Mai","Juin",
              "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
    JOURS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

    st.markdown("""<style>
    .kpi-card{background:linear-gradient(135deg,#1C1C1C,#2a2a2a);border-radius:12px;
        padding:16px 20px;border-left:4px solid #C9A84C;margin-bottom:8px;}
    .kpi-val{font-size:1.6rem;font-weight:700;color:#F5E6A0;}
    .kpi-lbl{font-size:0.72rem;color:#9A8060;letter-spacing:.05em;text-transform:uppercase;}
    .al{border-radius:8px;padding:10px 14px;margin:4px 0;border-left:4px solid #C0392B;background:#FFF0F0;}
    .al.or{border-left-color:#E67E22;background:#FFF8F0;}
    .al.bl{border-left-color:#2E86DE;background:#F0F6FF;}
    .al.gr{border-left-color:#27AE60;background:#F0FFF4;}
    .sec{font-size:.95rem;font-weight:700;color:#2A1F0E;border-bottom:2px solid #C9A84C;
        padding-bottom:3px;margin:14px 0 8px 0;}
    .from-hint{font-size:.72rem;color:#888;margin:2px 0 4px 0;font-style:italic;}
    </style>""", unsafe_allow_html=True)

    st.markdown(
        f'<h2 style="color:#2A1F0E;margin-bottom:0;">📊 Tableau de bord</h2>'
        f'<p style="color:#8B7355;font-size:.85rem;margin-top:2px;">'
        f'{JOURS[today.weekday()]} {today.day} {MOIS[today.month]} {today.year}</p>',
        unsafe_allow_html=True)

    # ── Données ───────────────────────────────────────────────────────────────
    orders = db.execute("SELECT * FROM commandes WHERE archived=0").fetchall()
    annee  = today.year

    ca_mois  = sum(o["montant"] or 0 for o in orders
                   if (o["date_commande"] or "")[:7] == today.strftime("%Y-%m"))
    ca_annee = sum(o["montant"] or 0 for o in orders
                   if (o["date_commande"] or "")[:4] == str(annee))
    c_dues   = sum((o["montant"] or 0)*(o["taux_commission"] or 0)/100
                   for o in orders if o["comm_statut"] == "Dues")
    c_avenir = sum((o["montant"] or 0)*(o["taux_commission"] or 0)/100
                   for o in orders if o["comm_statut"] == "À venir")

    urgentes = []
    for o in orders:
        if o["statut"] == "Payé": continue
        ech  = get_echeance(o["date_enlevement"], o["payment_terms"])
        if not ech: continue
        diff = (ech - today).days
        if diff <= 14:
            urgentes.append((diff, o, ech))
    urgentes.sort(key=lambda x: x[0])

    # Éligibles facturation commission
    elig = []
    for o in orders:
        if o["comm_statut"] != "Dues": continue
        if o["producteur_nom"] == "Maison Léda":
            if o["date_enlevement"]: elig.append(o)
        else:
            if o["statut"] == "Payé" and o["date_enlevement"]: elig.append(o)

    # Clients inactifs
    inactifs = []
    for ent in db.execute(
        "SELECT * FROM entreprises WHERE archived=0 AND type='Client actif'"
    ).fetchall():
        last = db.execute(
            "SELECT MAX(date_commande) as lc FROM commandes WHERE client_nom=? AND archived=0",
            (ent["nom"],)).fetchone()
        lc = last["lc"] if last else None
        if lc:
            try:
                ld   = datetime.strptime(lc[:10], "%Y-%m-%d").date()
                diff = (today - ld).days
                if diff > 90: inactifs.append((diff, ent, ld))
            except Exception: pass
        else:
            inactifs.append((9999, ent, None))
    inactifs.sort(key=lambda x: -x[0])

    # ── KPIs ──────────────────────────────────────────────────────────────────
    cols = st.columns(5)
    for col, val, lbl in [
        (cols[0], fmt_money(ca_mois),   f"CA {MOIS[today.month]}"),
        (cols[1], fmt_money(ca_annee),  f"CA {annee}"),
        (cols[2], fmt_money(c_dues),    "Commissions dues"),
        (cols[3], fmt_money(c_avenir),  "Commissions à venir"),
        (cols[4], str(len(urgentes)),   "Échéances urgentes"),
    ]:
        col.markdown(
            f'<div class="kpi-card"><div class="kpi-lbl">{lbl}</div>'
            f'<div class="kpi-val">{val}</div></div>',
            unsafe_allow_html=True)

    st.markdown("---")
    left, right = st.columns(2)

    # ── COLONNE GAUCHE ────────────────────────────────────────────────────────
    with left:
        # Échéances
        st.markdown('<div class="sec">⏰ Échéances paiement</div>', unsafe_allow_html=True)
        if urgentes:
            for diff, o, ech in urgentes[:6]:
                css = "al" if diff < 0 else "al or" if diff <= 4 else "al bl"
                comm = (o["montant"] or 0)*(o["taux_commission"] or 0)/100
                st.markdown(
                    f'<div class="{css}"><b>{_jours_label(diff)}</b> — {o["proforma"]}<br>'
                    f'<small>{o["client_nom"]} ({o["pays"]}) · {o["producteur_nom"]} · '
                    f'{fmt_money(o["montant"],o["devise"])} · Comm: {fmt_money(comm)}</small></div>',
                    unsafe_allow_html=True)
        else:
            st.markdown('<div class="al gr">✅ Aucune échéance urgente</div>', unsafe_allow_html=True)

        # Factures commission
        st.markdown('<div class="sec">📄 Factures commission à émettre</div>', unsafe_allow_html=True)
        leda_e  = [o for o in elig if o["producteur_nom"] == "Maison Léda"]
        other_e = [o for o in elig if o["producteur_nom"] != "Maison Léda"]

        if leda_e:
            total_l = sum((o["montant"] or 0)*(o["taux_commission"] or 0)/100 for o in leda_e)
            sig_l   = email_cfg("Maison Léda")["signature"]
            st.markdown(
                f'<div class="al or"><b>🏰 Maison Léda</b> — Récap fin de mois<br>'
                f'<small>{len(leda_e)} commande(s) · Commission : <b>{fmt_money(total_l)}</b><br>'
                f'<span class="from-hint">📤 Expéditeur à choisir manuellement — Signature : {sig_l}</span>'
                f'</small></div>', unsafe_allow_html=True)
            if st.button("📄 Générer facture récap. Léda"):
                st.session_state["page"] = "factures"
                st.rerun()

        for o in other_e[:4]:
            comm = (o["montant"] or 0)*(o["taux_commission"] or 0)/100
            sig  = email_cfg(o["producteur_nom"])["signature"]
            st.markdown(
                f'<div class="al bl"><b>{o["producteur_nom"]}</b> — {o["proforma"]}<br>'
                f'<small>{o["client_nom"]} ({o["pays"]}) · Commission : <b>{fmt_money(comm)}</b> · '
                f'Enlevé: {fmt_date(o["date_enlevement"])}<br>'
                f'<span class="from-hint">📤 Expéditeur à choisir manuellement — Signature : {sig}</span>'
                f'</small></div>', unsafe_allow_html=True)

        if not elig:
            st.markdown('<div class="al gr">✅ Aucune facture en attente</div>', unsafe_allow_html=True)

    # ── COLONNE DROITE ────────────────────────────────────────────────────────
    with right:
        st.markdown('<div class="sec">😴 Clients à relancer</div>', unsafe_allow_html=True)

        if inactifs:
            for diff, ent, last_d in inactifs[:5]:
                last_str = last_d.strftime("%d/%m/%Y") if last_d else "Jamais commandé"
                diff_str = f"{diff}j sans commande" if diff < 9999 else "Jamais commandé"
                css = "al" if diff > 180 else "al or"

                try:
                    prods_lies = ent["producteurs_lies"] or "—"
                except (IndexError, KeyError):
                    prods_lies = "—"
                st.markdown(
                    f'<div class="{css}"><b>{ent["nom"]}</b> — {ent["pays_destination"] or "—"}<br>'
                    f'<small>⏱ {diff_str} · Dernière: {last_str}<br>'
                    f'🤝 {prods_lies}</small></div>',
                    unsafe_allow_html=True)

                # Contact principal
                ctc = db.execute("""
                    SELECT * FROM contacts WHERE entreprise_id=? AND archived=0
                    ORDER BY CASE email_role WHEN 'To' THEN 0 ELSE 1 END, id LIMIT 1
                """, (ent["id"],)).fetchone()

                email_to = ctc["email"] if ctc and ctc["email"] else ""
                prenom   = (ctc["prenom"] or ctc["nom"] or "") if ctc else ""
                langue   = (ctc["langue"] or "Anglais") if ctc else "Anglais"

                # Producteurs liés — extraire UNIQUEMENT les noms de producteurs
                # Format: "Maison Léda (Château Loumelat|Château Haut Selve)|Cognac Lhéraud"
                # → ["Maison Léda", "Cognac Lhéraud"] — on ignore les marques entre parenthèses
                try:
                    prods_raw = ent["producteurs_lies"] or ""
                except (IndexError, KeyError):
                    prods_raw = ""
                prods_noms = []
                depth = 0; current = ""
                for ch in prods_raw:
                    if ch == "(": depth += 1; current += ch
                    elif ch == ")": depth -= 1; current += ch
                    elif ch == "|" and depth == 0:
                        prod = re.sub(r'\s*\(.*', '', current).strip()
                        if prod and prod not in prods_noms:
                            prods_noms.append(prod)
                        current = ""
                    else:
                        current += ch
                if current.strip():
                    prod = re.sub(r'\s*\(.*', '', current).strip()
                    if prod and prod not in prods_noms:
                        prods_noms.append(prod)
                if not prods_noms:
                    prods_noms = ["Angels' Share"]

                for prod_nom in prods_noms[:2]:
                    sig = email_cfg(prod_nom)["signature"]

                    # Sujet
                    if langue == "Français":
                        subj_i = f"Comment allez-vous ? — {prod_nom}"
                        subj_a = f"Appel — {prod_nom}"
                        subj_v = f"Visioconférence — {prod_nom}"
                    elif langue == "Chinois":
                        subj_i = f"问候 — {prod_nom}"
                        subj_a = f"电话 — {prod_nom}"
                        subj_v = f"视频会议 — {prod_nom}"
                    else:
                        subj_i = f"Checking in — {prod_nom}"
                        subj_a = f"Call — {prod_nom}"
                        subj_v = f"Video call — {prod_nom}"

                    st.markdown(
                        f'<div class="from-hint">📤 Choisir expéditeur dans Outlook — '
                        f'Signature : <b>{sig}</b></div>',
                        unsafe_allow_html=True)

                    b1, b2, b3, b4 = st.columns(4)
                    prod_short = prod_nom[:12]

                    if email_to:
                        b1.markdown(btn(f"📧 {prod_short}",
                            make_mailto(email_to, subj_i, relance_body(prenom, langue, prod_nom, "inactif")),
                            "#1A6EA5"), unsafe_allow_html=True)
                        b2.markdown(btn("📞 Appel",
                            make_mailto(email_to, subj_a, relance_body(prenom, langue, prod_nom, "appel")),
                            "#8E44AD"), unsafe_allow_html=True)
                        b3.markdown(btn("🎥 Visio",
                            make_mailto(email_to, subj_v, relance_body(prenom, langue, prod_nom, "visio")),
                            "#16A085"), unsafe_allow_html=True)
                    else:
                        st.caption("⚠️ Pas d'email enregistré pour ce contact")

                    # WhatsApp (si disponible)
                    if ctc and ctc["mobile"]:
                        wa_val = ctc["whatsapp"] if "whatsapp" in ctc.keys() else ""
                        if wa_val not in ("NON", "CHINE (pas WA)"):
                            wa_num = ctc["mobile"].replace(" ","").replace("-","")
                            wa_msg = urllib.parse.quote(
                                f"Hi {prenom}, hope you are doing well! "
                                f"Just checking in — any upcoming orders I can help with? 🍷")
                            b4.markdown(btn("📱 WA",
                                f"https://wa.me/{wa_num}?text={wa_msg}",
                                "#25D366"), unsafe_allow_html=True)

                st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #eee'>",
                            unsafe_allow_html=True)
        else:
            st.markdown('<div class="al gr">✅ Tous vos clients sont actifs</div>',
                        unsafe_allow_html=True)

    st.markdown("---")

    # ── COMMANDES RÉCENTES ────────────────────────────────────────────────────
    st.markdown('<div class="sec">📋 Commandes récentes</div>', unsafe_allow_html=True)
    recentes = db.execute(
        "SELECT * FROM commandes WHERE archived=0 ORDER BY created_at DESC LIMIT 8"
    ).fetchall()
    if recentes:
        rows = []
        for o in recentes:
            comm = (o["montant"] or 0)*(o["taux_commission"] or 0)/100
            rows.append({
                "Proforma":   o["proforma"],
                "Producteur": o["producteur_nom"],
                "Client":     o["client_nom"],
                "Pays":       o["pays"],
                "Montant":    fmt_money(o["montant"], o["devise"]),
                "Commission": fmt_money(comm),
                "Statut":     o["statut"],
                "Comm.":      o["comm_statut"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune commande enregistrée.")

    # ── OBJECTIFS ─────────────────────────────────────────────────────────────
    objectifs = db.execute(
        "SELECT o.*, p.id as pid FROM objectifs o "
        "LEFT JOIN producteurs p ON p.nom=o.producteur_nom WHERE o.annee=?",
        (annee,)).fetchall()
    if objectifs:
        st.markdown('<div class="sec">🎯 Objectifs annuels</div>', unsafe_allow_html=True)
        rows_o = []
        for obj in objectifs:
            reel = db.execute(
                "SELECT COALESCE(SUM(montant),0) as t FROM commandes "
                "WHERE producteur_id=? AND archived=0 "
                "AND strftime('%Y', COALESCE(date_enlevement, date_commande))=?",
                (obj["pid"], str(annee))).fetchone()["t"] or 0
            obj_ca = obj["objectif_ca"] or 0
            pct    = int(reel/obj_ca*100) if obj_ca > 0 else 0
            bar    = "█"*min(int(pct/10),10) + "░"*max(0,10-int(pct/10))
            rows_o.append({
                "Producteur": obj["producteur_nom"],
                "Pays":       obj["pays"] or "Global",
                "Objectif":   fmt_money(obj_ca, obj["devise"]),
                "Réalisé":    fmt_money(reel, obj["devise"]),
                "Avancement": f"{pct}% {bar}",
            })
        st.dataframe(pd.DataFrame(rows_o), use_container_width=True, hide_index=True)

    db.close()
