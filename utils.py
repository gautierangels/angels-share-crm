from datetime import datetime, timedelta, date
import base64
from pathlib import Path


def fmt_date(d: str) -> str:
    if not d:
        return "—"
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return d


def fmt_money(n, devise="EUR") -> str:
    if n is None or n == "":
        return "—"
    try:
        return f"{int(float(n)):,} {devise}".replace(",", "\u202f")
    except Exception:
        return str(n)


def get_echeance(enlevement: str, terms: int):
    """Retourne la date d'échéance (date object) ou None."""
    if not enlevement:
        return None
    try:
        d = datetime.strptime(enlevement, "%Y-%m-%d").date()
        return d + timedelta(days=int(terms or 0))
    except Exception:
        return None


def alert_level(enlevement: str, terms: int, statut: str) -> str:
    """Retourne : 'green', 'red', 'orange', 'blue', 'gray'"""
    if statut == "Payé":
        return "green"
    ech = get_echeance(enlevement, terms)
    if not ech:
        return "gray"
    diff = (ech - date.today()).days
    if diff < 0:
        return "red"
    if diff <= 7:
        return "orange"
    return "blue"


def logo_b64() -> str:
    """Retourne le logo encodé en base64 pour affichage HTML."""
    logo_path = Path(__file__).parent / "assets" / "logo.jpg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


PAYS_LISTE = [
    "Chine", "Japon", "Corée du Sud", "Macao", "Hong Kong", "Taiwan",
    "Philippines", "Laos", "Myanmar", "Cambodge", "Vietnam", "Thaïlande",
    "Malaisie", "Singapour", "Indonésie", "Australie", "Nouvelle-Zélande", "Inde"
]

DEVISES = ["EUR", "USD", "HKD", "SGD", "JPY", "THB", "AUD", "CNY"]

MOYENS_PAIEMENT = [
    "Carte AirWallex", "Liquide", "Carte Kasikorn", "Carte Krungsri",
    "Carte Crédit Agricole", "Virement Airwallex", "Virement Crédit Agricole",
    "Virement Kasikorn", "Virement Bangkok Bank",
    "QR Bangkok Bank", "QR Kasikorn",
]

CATEGORIES_FRAIS = [
    "Voyage", "Hébergement", "Restaurant", "Salon / foire",
    "Logistique", "Abonnement logiciel", "Comptabilité / audit",
    "Assurance", "Work permit", "Autre",
]

STATUTS_COMM = ["Non éligible", "En attente", "Payé"]

TYPES_PRODUIT = [
    "Armagnac", "Cognac", "Vin rouge", "Vin blanc", "Vin rosé",
    "Champagne", "Crémant", "Pétillant naturel", "Whisky",
    "Cidre", "Autre spiritueux", "Autre vin",
]

ROLES_CONTACT_PROD = [
    "Contact principal", "Comptabilité", "Logistique",
    "Export", "Direction", "Vignoble / production", "Autre",
]

STATUTS_MANDAT = [
    "Distribué sous votre suivi",
    "Libre / à développer",
    "Déjà ouvert par producteur",
    "Interdit / hors mandat",
    "En discussion",
    "Perdu / arrêté",
]
