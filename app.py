import streamlit as st
import hashlib
import importlib
from database import init_db, get_db
from utils import logo_b64

st.set_page_config(
    page_title="Angels' Share — Wine & Spirits Agency",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* Cache complètement la sidebar Streamlit par défaut */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* Zone principale sans marge gauche */
.block-container { padding-top: 0.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }

/* ── Barre de navigation principale ── */
.nav-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    background: #1C1C1C;
    padding: 8px 14px;
    border-radius: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}
.nav-bar-section {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
}
.nav-separator {
    width: 1px;
    height: 24px;
    background: #3a3020;
    margin: 0 4px;
}

/* Alertes */
.alerte-rouge  { background:#FFF0F0; border-left:3px solid #C0392B; padding:8px 12px; border-radius:6px; margin:3px 0; }
.alerte-orange { background:#FFF8F0; border-left:3px solid #E67E22; padding:8px 12px; border-radius:6px; margin:3px 0; }
.alerte-verte  { background:#F0FFF4; border-left:3px solid #27AE60; padding:8px 12px; border-radius:6px; margin:3px 0; }
.alerte-bleue  { background:#F0F4FF; border-left:3px solid #2E86DE; padding:8px 12px; border-radius:6px; margin:3px 0; }
</style>
""", unsafe_allow_html=True)

PAGES = [
    # (icone, label, key, section)
    ("🔭", "Tableau de bord",  "dashboard",    "principal"),
    ("📦", "Commandes",        "commandes",    "principal"),
    ("🤝", "Commissions",      "commissions",  "principal"),
    ("🧾", "Factures",         "factures",     "principal"),
    ("🍇", "Producteurs",      "producteurs",  "repertoire"),
    ("📋", "Rapports",         "rapports",     "repertoire"),
    ("🏢", "Contacts",         "contacts",     "repertoire"),
    ("🌐", "Distribution",     "distribution", "repertoire"),
    ("🔍", "Prospection",      "prospection",  "developpement"),
    ("📈", "Objectifs",        "objectifs",    "developpement"),
    ("📆", "Calendrier",       "calendrier",   "operationnel"),
    ("✉️", "Interactions",     "interactions", "operationnel"),
    ("☑️", "Actions",          "actions",      "operationnel"),
    ("🧾", "Frais",            "frais",        "operationnel"),
    ("💾", "Exports",          "exports",      "donnees"),
]


def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()


def check_login(username, password):
    try:
        db = get_db()
        row = db.execute(
            "SELECT password_hash FROM users WHERE username=?", (username,)
        ).fetchone()
        db.close()
        return row and row["password_hash"] == _hash(password)
    except Exception:
        return False


def render_login():
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        logo = logo_b64()
        if logo:
            st.markdown(
                f'<div style="text-align:center;margin-bottom:1.5rem;">'
                f'<img src="data:image/jpeg;base64,{logo}" style="width:160px;">'
                f'</div>', unsafe_allow_html=True)
        st.markdown(
            '<h3 style="text-align:center;color:#C9A84C;margin-bottom:0.2rem;'            'font-family:\'Courier New\',Courier,monospace;letter-spacing:0.08em;font-weight:400;">'            'Where Craft, Time &amp; Trust Meet</h3>', unsafe_allow_html=True)
        st.markdown(
            '<p style="text-align:center;color:#8B7355;font-size:0.85rem;'
            'margin-bottom:1.5rem;">Connexion requise</p>', unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Identifiant", placeholder="gautier")
            password = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("🔑  Se connecter", use_container_width=True):
                if check_login(username, password):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.session_state["page"] = "dashboard"
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")


def render_navbar():
    """Barre de navigation horizontale compacte — toujours visible, sidebar remplacée."""
    page = st.session_state.get("page", "dashboard")

    # Style des boutons nav selon état actif
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] .stButton > button {
        background: transparent !important;
        border: 1px solid #3a3020 !important;
        color: #C9B88A !important;
        padding: 4px 10px !important;
        border-radius: 8px !important;
        font-size: 0.8rem !important;
        min-height: 32px !important;
        line-height: 1.2 !important;
        white-space: nowrap !important;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        background: rgba(201,168,76,0.2) !important;
        border-color: #C9A84C !important;
        color: #F0DFA0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Conteneur foncé
    st.markdown(
        '<div style="background:#1C1C1C;border-radius:12px;padding:10px 14px;'
        'margin-bottom:14px;">',
        unsafe_allow_html=True
    )

    # Logo + titre de page courant + boutons
    logo = logo_b64()
    logo_html = (
        f'<img src="data:image/jpeg;base64,{logo}" '
        f'style="height:32px;vertical-align:middle;margin-right:10px;">'
        if logo else "🍷"
    )
    current_label = next((label for _, label, key, _ in PAGES if key == page), "")
    st.markdown(
        f'<div style="display:flex;align-items:center;margin-bottom:8px;">'
        f'{logo_html}'
        f'<span style="color:#C9A84C;font-size:0.7rem;letter-spacing:0.1em;'
        f'text-transform:uppercase;margin-right:12px;">Angels\' Share Marketing</span>'
        f'<span style="color:#E8D5A0;font-size:0.85rem;font-weight:600;">'
        f'→ {current_label}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    # Rangée de boutons — tous les modules
    sections = {
        "principal":     [p for p in PAGES if p[3] == "principal"],
        "repertoire":    [p for p in PAGES if p[3] == "repertoire"],
        "developpement": [p for p in PAGES if p[3] == "developpement"],
        "operationnel":  [p for p in PAGES if p[3] == "operationnel"],
        "donnees":       [p for p in PAGES if p[3] == "donnees"],
    }
    section_labels = {
        "principal":     "📌",
        "repertoire":    "📁",
        "developpement": "🚀",
        "operationnel":  "⚙️",
        "donnees":       "💾",
    }

    all_pages_flat = list(PAGES) + [("🚪", "Déconnexion", "_logout", "")]
    cols = st.columns(len(all_pages_flat))

    for i, (icon, label, key, _) in enumerate(all_pages_flat):
        with cols[i]:
            if key == "_logout":
                if st.button("🚪", help="Déconnexion", key="btn_logout",
                             use_container_width=True):
                    st.session_state["logged_in"] = False
                    st.rerun()
            else:
                # Mettre en évidence le bouton actif via CSS inline
                is_active = page == key
                if is_active:
                    st.markdown(
                        f'<style>div[data-testid="stHorizontalBlock"] '
                        f'div:nth-child({i+1}) .stButton > button '
                        f'{{ background: rgba(201,168,76,0.3) !important; '
                        f'border-color: #C9A84C !important; '
                        f'color: #F5E6A0 !important; font-weight: 700 !important; }}</style>',
                        unsafe_allow_html=True
                    )
                if st.button(icon, help=label, key=f"nav_{key}",
                             use_container_width=True):
                    st.session_state["page"] = key
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def render_page():
    page = st.session_state.get("page", "dashboard")
    routes = {
        "dashboard":    "modules.dashboard",
        "commandes":    "modules.commandes",
        "commissions":  "modules.commissions",
        "factures":     "modules.factures",
        "producteurs":  "modules.producteurs",
        "contacts":     "modules.contacts",
        "distribution": "modules.distribution",
        "prospection":  "modules.prospection",
        "objectifs":    "modules.objectifs",
        "calendrier":   "modules.calendrier",
        "interactions": "modules.interactions",
        "actions":      "modules.actions",
        "frais":        "modules.frais",
        "exports":      "modules.exports",
        "alertes":      "modules.alertes",
        "rapports":     "modules.rapports",
    }
    mod_path = routes.get(page, "modules.dashboard")
    mod = importlib.import_module(mod_path)
    mod.render()


def main():
    init_db()
    from database import migrate_extra, get_db as _gdb; migrate_extra(_gdb())

    if not st.session_state.get("logged_in", False):
        render_login()
        return

    render_navbar()
    render_page()


if __name__ == "__main__":
    main()
