import streamlit as st
import pandas as pd
import io
import zipfile
import shutil
from pathlib import Path
from database import get_db
from utils import fmt_date, fmt_money, DEVISES
from datetime import date

RECEIPTS_DIR = Path("/Users/gautiersalinier/Documents/Angels Share Marketing Limited/Angels' Share Management/Justificatifs")
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

MOYENS = {
    "Liquide":                              "avance",
    "QR Bangkok Bank":                      "avance",
    "QR Kasikorn":                          "avance",
    "Carte Kasikorn":                       "avance",
    "Carte Krungsri":                       "avance",
    "Carte Crédit Agricole":                "avance",
    "Carte AirWallex":                      "directe",
    "Virement Airwallex (tiers)":           "directe",
    "Virement Airwallex → Kasikorn":        "remboursement",
    "Virement Airwallex → Bangkok Bank":    "remboursement",
    "Virement Airwallex → Crédit Agricole": "remboursement",
}

CATEGORIES_FRAIS = [
    "Voyage", "Hébergement", "Restaurant", "Salon / foire",
    "Logistique", "Abonnement logiciel", "Comptabilité / audit",
    "Assurance", "Work permit", "Représentation", "Autre",
]

CAT_INFO = {
    "avance":        ("💼", "Avance de frais Gautier",    "#FFF8F0", "#E67E22"),
    "directe":       ("🏢", "Dépense directe entreprise", "#F0F4FF", "#2E86DE"),
    "remboursement": ("💸", "Remboursement de frais",     "#F0FFF4", "#27AE60"),
}

def get_cat(moyen):
    return MOYENS.get(moyen, "avance")

def save_receipt(frais_id, uploaded_file):
    ext = Path(uploaded_file.name).suffix.lower()
    filename = f"frais_{frais_id}{ext}"
    with open(RECEIPTS_DIR / filename, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filename

def render():
    st.markdown("## 🧾 Frais")
    db = get_db()

    # Migrations silencieuses
    for sql in [
        "ALTER TABLE frais ADD COLUMN justificatif TEXT",
        "ALTER TABLE frais ADD COLUMN cat_comptable TEXT",
        "ALTER TABLE frais ADD COLUMN lie_a TEXT",
        "ALTER TABLE frais ADD COLUMN lie_a_type TEXT",
        "ALTER TABLE frais ADD COLUMN lie_a_contact TEXT",
    ]:
        try: db.execute(sql); db.commit()
        except: pass

    # Corriger cat_comptable NULL sur anciens enregistrements
    nulls = db.execute(
        "SELECT id, moyen_paiement FROM frais WHERE cat_comptable IS NULL OR cat_comptable=''"
    ).fetchall()
    for row in nulls:
        db.execute("UPDATE frais SET cat_comptable=? WHERE id=?",
                   (get_cat(row["moyen_paiement"] or ""), row["id"]))
    if nulls: db.commit()

    tab1, tab2, tab3 = st.tabs(["📋 Mes frais", "➕ Nouveau frais", "📊 Export comptable"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — LISTE DES FRAIS EXISTANTS
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        f1, f2, f3, f4 = st.columns(4)
        f_cat  = f1.selectbox("Catégorie", ["Toutes"] + CATEGORIES_FRAIS, key="fc1")
        f_type = f2.selectbox("Type comptable", [
            "Tous","Avance de frais Gautier",
            "Dépense directe entreprise","Remboursement de frais"], key="fc2")
        f_mois = f3.text_input("Mois (YYYY-MM)", placeholder="2026-05", key="fc3")
        f_srch = f4.text_input("Recherche", placeholder="Description…", key="fc4")

        q = "SELECT * FROM frais WHERE 1=1"
        p = []
        if f_cat != "Toutes":  q += " AND categorie=?";       p.append(f_cat)
        if f_mois:             q += " AND date_frais LIKE ?";  p.append(f"{f_mois}%")
        if f_srch:             q += " AND description LIKE ?"; p.append(f"%{f_srch}%")
        if f_type != "Tous":
            tm = {
                "Avance de frais Gautier":    "avance",
                "Dépense directe entreprise": "directe",
                "Remboursement de frais":     "remboursement",
            }
            q += " AND cat_comptable=?"; p.append(tm[f_type])
        q += " ORDER BY date_frais DESC"
        frais_list = db.execute(q, p).fetchall()

        if not frais_list:
            st.info("Aucun frais enregistré.")
        else:
            ta = sum(f["montant"] or 0 for f in frais_list if f["cat_comptable"]=="avance")
            td = sum(f["montant"] or 0 for f in frais_list if f["cat_comptable"]=="directe")
            tr = sum(f["montant"] or 0 for f in frais_list if f["cat_comptable"]=="remboursement")
            m1, m2, m3 = st.columns(3)
            m1.metric("💼 Avances Gautier",    fmt_money(ta))
            m2.metric("🏢 Dépenses directes",  fmt_money(td))
            m3.metric("💸 Remboursements",      fmt_money(tr))
            solde = ta - tr
            if solde > 0:
                st.warning(f"💼 L'entreprise vous doit : **{fmt_money(solde)}**")
            elif solde == 0 and ta > 0:
                st.success("✅ Avances entièrement remboursées.")
            st.divider()

            for f in frais_list:
                cat_c = f["cat_comptable"] or get_cat(f["moyen_paiement"] or "")
                icon, label, bg, border = CAT_INFO.get(cat_c, ("📄","—","#F8F8F8","#CCC"))
                justif_badge = " 📎" if f["justificatif"] else " ⚠️ sans justificatif"

                with st.expander(
                    f'{icon} {fmt_date(f["date_frais"])} — {f["description"]} '
                    f'| {fmt_money(f["montant"], f["devise"])}{justif_badge}'
                ):
                    ca, cb, cc, cd = st.columns(4)
                    ca.markdown(f"**Type :** {icon} {label}")
                    cb.markdown(f"**Catégorie :** {f['categorie'] or '—'}")
                    cc.markdown(f"**Paiement :** {f['moyen_paiement'] or '—'}")
                    # Lien client/producteur
                    lie_type = f["lie_a_type"] if "lie_a_type" in f.keys() else ""
                    lie_a    = f["lie_a"] if "lie_a" in f.keys() else ""
                    lie_ctc  = f["lie_a_contact"] if "lie_a_contact" in f.keys() else ""
                    if lie_type and lie_a:
                        lbl = "👥" if lie_type=="Client" else "🍇"
                        cd.markdown(f"**{lbl} {lie_type} :** {lie_a}"
                                    + (f"<br><small>{lie_ctc}</small>" if lie_ctc else ""),
                                    unsafe_allow_html=True)
                    if f["notes"]: st.caption(f["notes"])

                    if f["justificatif"]:
                        rp = RECEIPTS_DIR / f["justificatif"]
                        if rp.exists():
                            ext = rp.suffix.lower()
                            if ext in (".jpg",".jpeg",".png",".webp",".heic"):
                                st.image(str(rp), width=350)
                            else:
                                with open(rp,"rb") as fp:
                                    st.download_button(
                                        f"⬇️ {f['justificatif']}",
                                        data=fp.read(),
                                        file_name=f["justificatif"],
                                        key=f"dl_{f['id']}")
                        else:
                            st.caption(f"⚠️ Fichier introuvable : {f['justificatif']}")

                    st.markdown("**📎 Remplacer le justificatif :**")
                    up2 = st.file_uploader(
                        "Photo, PDF, Excel…",
                        type=["jpg","jpeg","png","webp","heic","pdf","xlsx","xls","csv"],
                        key=f"up2_{f['id']}"
                    )
                    if up2:
                        fn = save_receipt(f["id"], up2)
                        db.execute("UPDATE frais SET justificatif=? WHERE id=?", (fn, f["id"]))
                        db.commit()
                        st.success(f"✅ {up2.name} enregistré."); st.rerun()

                    if st.button("🗑️ Supprimer ce frais", key=f"del_{f['id']}"):
                        if f["justificatif"]:
                            rp2 = RECEIPTS_DIR / f["justificatif"]
                            if rp2.exists(): rp2.unlink()
                        db.execute("DELETE FROM frais WHERE id=?", (f["id"],))
                        db.commit(); st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — NOUVEAU FRAIS (avec upload immédiat)
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("### Enregistrer un nouveau frais")

        # Étape 1 : saisie
        r1, r2 = st.columns(2)
        n_date = r1.date_input("📅 Date *", value=date.today(), key="nf_date")
        n_desc = r2.text_input("📝 Description *",
                               placeholder="Ex: Billet Bangkok–Singapour", key="nf_desc")

        c1, c2, c3, c4 = st.columns(4)
        n_cat   = c1.selectbox("Catégorie", CATEGORIES_FRAIS, key="nf_cat")
        n_moyen = c2.selectbox("Moyen de paiement", list(MOYENS.keys()), key="nf_moyen")
        n_mt    = c3.number_input("Montant *", min_value=0.0,
                                  step=1.0, format="%.2f", key="nf_mt")
        n_dev   = c4.selectbox("Devise", DEVISES, key="nf_dev")

        # Choix manuel de la catégorie comptable
        cat_options = {
            "💼 Avance de frais Gautier":    "avance",
            "🏢 Dépense directe entreprise": "directe",
            "💸 Remboursement de frais":     "remboursement",
        }
        # Suggestion automatique selon le moyen de paiement
        suggestion = get_cat(n_moyen)
        suggestion_label = next(k for k,v in cat_options.items() if v == suggestion)
        cat_labels = list(cat_options.keys())
        idx_suggestion = cat_labels.index(suggestion_label)

        n_cat_comptable_label = st.selectbox(
            "📊 Catégorie comptable *",
            cat_labels,
            index=idx_suggestion,
            help="Suggestion automatique selon le moyen de paiement — modifiable librement",
            key="nf_cat_comptable"
        )
        cat_preview = cat_options[n_cat_comptable_label]
        icon_p, label_p, bg_p, border_p = CAT_INFO[cat_preview]
        st.caption(f"💡 Suggestion basée sur le moyen de paiement : **{suggestion_label}**"
                   + (" ✅" if cat_preview == suggestion else " (modifié)"))

        n_notes = st.text_area("Notes (optionnel)", height=60, key="nf_notes")

        # Lien optionnel avec un client ou producteur
        st.markdown("**🔗 Associer à un client ou producteur (optionnel) :**")
        la1, la2, la3 = st.columns(3)
        n_lie_type = la1.selectbox("Type", ["—", "Client", "Producteur"], key="nf_lie_type")

        n_lie_a = ""
        n_lie_contact = ""
        if n_lie_type == "Client":
            clients_list = [r["nom"] for r in db.execute(
                "SELECT nom FROM entreprises WHERE archived=0 ORDER BY nom").fetchall()]
            n_lie_a = la2.selectbox("Client", ["—"] + clients_list, key="nf_lie_client")
            if n_lie_a and n_lie_a != "—":
                ent = db.execute(
                    "SELECT id FROM entreprises WHERE nom=?", (n_lie_a,)).fetchone()
                if ent:
                    contacts = [f"{c['prenom'] or ''} {c['nom'] or ''}".strip()
                                for c in db.execute(
                        "SELECT prenom, nom FROM contacts WHERE entreprise_id=? AND archived=0",
                        (ent["id"],)).fetchall()]
                    if contacts:
                        n_lie_contact = la3.selectbox(
                            "Contact", ["—"] + contacts, key="nf_lie_ctc")
        elif n_lie_type == "Producteur":
            prods_list = [r["nom"] for r in db.execute(
                "SELECT nom FROM producteurs WHERE archived=0 ORDER BY nom").fetchall()]
            n_lie_a = la2.selectbox("Producteur", ["—"] + prods_list, key="nf_lie_prod")
            n_lie_contact = ""
        else:
            n_lie_a = ""
            n_lie_contact = ""

        # Étape 2 : upload AVANT validation (hors form car Streamlit l'exige)
        st.markdown("**📎 Justificatif (photo, PDF, Excel) — optionnel :**")
        n_upload = st.file_uploader(
            "Glissez ou cliquez pour sélectionner",
            type=["jpg","jpeg","png","webp","heic","pdf","xlsx","xls","csv"],
            key="nf_upload"
        )

        st.markdown("")
        if st.button("💾 Enregistrer ce frais", use_container_width=True, type="primary"):
            if not n_desc or n_mt <= 0:
                st.error("⚠️ Description et montant sont obligatoires.")
            else:
                # Insérer le frais
                lie_a_val     = n_lie_a if n_lie_a and n_lie_a != "—" else None
                lie_type_val  = n_lie_type if n_lie_type != "—" else None
                lie_ctc_val   = n_lie_contact if n_lie_contact and n_lie_contact != "—" else None

                cur = db.execute(
                    """INSERT INTO frais
                       (date_frais, description, categorie, moyen_paiement,
                        montant, devise, notes, cat_comptable,
                        lie_a, lie_a_type, lie_a_contact)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (n_date.strftime("%Y-%m-%d"), n_desc, n_cat, n_moyen,
                     n_mt, n_dev, n_notes, cat_preview,
                     lie_a_val, lie_type_val, lie_ctc_val)
                )
                new_id = cur.lastrowid

                # Sauvegarder le justificatif si fourni
                if n_upload:
                    fn = save_receipt(new_id, n_upload)
                    db.execute("UPDATE frais SET justificatif=? WHERE id=?", (fn, new_id))

                db.commit()
                st.success(f"✅ Frais enregistré — {icon_p} {label_p}"
                           + (f" — 📎 {n_upload.name}" if n_upload else " — ⚠️ sans justificatif"))
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — EXPORT COMPTABLE
    # ══════════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown("### 📊 Export comptable professionnel")
        st.markdown(
            "Génère un **fichier Excel** récapitulatif + une **archive ZIP** "
            "contenant tous les justificatifs — prêts à envoyer à votre comptable."
        )

        ec1, ec2 = st.columns(2)
        ex_debut = ec1.date_input("Du", value=date.today().replace(day=1), key="ex_d")
        ex_fin   = ec2.date_input("Au", value=date.today(), key="ex_f")

        all_f = db.execute(
            "SELECT * FROM frais WHERE date_frais BETWEEN ? AND ? ORDER BY date_frais",
            (str(ex_debut), str(ex_fin))
        ).fetchall()

        if not all_f:
            st.info("Aucun frais sur cette période.")
        else:
            ta = sum(f["montant"] or 0 for f in all_f if f["cat_comptable"]=="avance")
            td = sum(f["montant"] or 0 for f in all_f if f["cat_comptable"]=="directe")
            tr = sum(f["montant"] or 0 for f in all_f if f["cat_comptable"]=="remboursement")
            solde = ta - tr

            m1,m2,m3,m4 = st.columns(4)
            m1.metric("💼 Avances",          fmt_money(ta))
            m2.metric("🏢 Dépenses directes", fmt_money(td))
            m3.metric("💸 Remboursements",    fmt_money(tr))
            m4.metric("Solde à rembourser",   fmt_money(solde))

            # Tableau prévisualisation
            rows = [{
                "Date":            fmt_date(f["date_frais"]),
                "Description":     f["description"],
                "Catégorie":       f["categorie"] or "—",
                "Moyen paiement":  f["moyen_paiement"] or "—",
                "Type comptable":  CAT_INFO.get(f["cat_comptable"],("","—","",""))[1],
                "Montant":         f["montant"] or 0,
                "Devise":          f["devise"] or "THB",
                "Client / Producteur": (f["lie_a"] if "lie_a" in f.keys() and f["lie_a"] else "—"),
                "Contact":         (f["lie_a_contact"] if "lie_a_contact" in f.keys() and f["lie_a_contact"] else "—"),
                "Justificatif":    f["justificatif"] or "⚠️ manquant",
                "Notes":           f["notes"] or "",
            } for f in all_f]
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            nb_sans = sum(1 for f in all_f if not f["justificatif"])
            if nb_sans:
                st.warning(f"⚠️ {nb_sans} frais sans justificatif — pensez à les ajouter.")

            st.divider()
            st.markdown("#### ⬇️ Téléchargements")
            dl1, dl2 = st.columns(2)

            # Export Excel
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Frais")
                # Onglet récapitulatif
                recap = pd.DataFrame([
                    {"Type": "💼 Avances de frais Gautier",    "Total": ta},
                    {"Type": "🏢 Dépenses directes entreprise","Total": td},
                    {"Type": "💸 Remboursements reçus",        "Total": tr},
                    {"Type": "Solde à rembourser",             "Total": solde},
                ])
                recap.to_excel(writer, index=False, sheet_name="Récapitulatif")
            buf.seek(0)

            nom_periode = f"{ex_debut.strftime('%Y%m%d')}_{ex_fin.strftime('%Y%m%d')}"
            dl1.download_button(
                "📊 Télécharger Excel",
                data=buf.read(),
                file_name=f"Frais_AngelsShare_{nom_periode}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # Export ZIP (Excel + justificatifs)
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                # Excel dans le zip
                buf2 = io.BytesIO()
                with pd.ExcelWriter(buf2, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Frais")
                zf.writestr(f"Frais_{nom_periode}.xlsx", buf2.getvalue())

                # Justificatifs
                for f in all_f:
                    if f["justificatif"]:
                        rp = RECEIPTS_DIR / f["justificatif"]
                        if rp.exists():
                            nom_doc = f"{f['date_frais']}_{f['description'][:30].replace('/','_')}{rp.suffix}"
                            zf.write(str(rp), arcname=f"Justificatifs/{nom_doc}")

            zip_buf.seek(0)
            dl2.download_button(
                "🗜️ Télécharger ZIP complet",
                data=zip_buf.read(),
                file_name=f"Frais_complet_{nom_periode}.zip",
                mime="application/zip",
                use_container_width=True,
                help="Contient le fichier Excel + tous les justificatifs — envoyez ce ZIP à votre comptable"
            )

    db.close()
