import sqlite3
import hashlib
from pathlib import Path

# ── Chemin de stockage ───────────────────────────────────────────────────────
# Stocké dans Documents/Angels Share Marketing Limited — synchronisé par iCloud
APP_DIR = Path("/Users/gautiersalinier/Documents/Angels Share Marketing Limited/Angels' Share Management")
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "angels_share.db"

SCHEMA_VERSION = 6


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ver(conn) -> int:
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return row["version"] if row else 0
    except Exception:
        return 0


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _col_exists(conn, table, col):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return col in cols


def init_db():
    conn = get_db()
    v = _ver(conn)

    if v < 1:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER);
        INSERT INTO schema_version VALUES (0);

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS pays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL,
            actif INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS producteurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            region TEXT,
            statut TEXT DEFAULT 'Actif',
            adresse TEXT,
            website TEXT,
            notes TEXT,
            ca_objectif REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            archived INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS producteur_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producteur_id INTEGER REFERENCES producteurs(id),
            role TEXT,
            nom TEXT,
            email TEXT,
            tel TEXT,
            mobile TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS producteur_mandats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producteur_id INTEGER REFERENCES producteurs(id),
            pays TEXT,
            statut TEXT,
            commission_applicable INTEGER DEFAULT 1,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producteur_id INTEGER REFERENCES producteurs(id),
            nom TEXT NOT NULL,
            type_produit TEXT,
            style TEXT,
            statut TEXT DEFAULT 'Actif',
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS entreprises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            type TEXT DEFAULT 'Client actif',
            pays_destination TEXT,
            pays_facturation TEXT,
            activite TEXT,
            statut TEXT DEFAULT 'Actif',
            adresse TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            archived INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entreprise_id INTEGER REFERENCES entreprises(id),
            nom TEXT NOT NULL,
            position TEXT,
            email TEXT,
            mobile TEXT,
            tel_fixe TEXT,
            direct TEXT,
            whatsapp TEXT,
            wechat TEXT,
            langue TEXT DEFAULT 'Anglais',
            email_role TEXT DEFAULT 'To',
            notes TEXT,
            archived INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proforma TEXT NOT NULL UNIQUE,
            cmd_client TEXT,
            facture_finale TEXT,
            entreprise_id INTEGER REFERENCES entreprises(id),
            client_nom TEXT,
            pays TEXT,
            producteur_id INTEGER REFERENCES producteurs(id),
            producteur_nom TEXT,
            montant REAL DEFAULT 0,
            devise TEXT DEFAULT 'EUR',
            taux_commission REAL DEFAULT 0,
            payment_terms INTEGER DEFAULT 30,
            date_commande TEXT DEFAULT (date('now')),
            date_enlevement TEXT,
            statut TEXT DEFAULT 'En cours',
            comm_statut TEXT DEFAULT 'Non éligible',
            co_agent TEXT,
            taux_co_agent REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            archived INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            entite_type TEXT,
            entite_id INTEGER,
            entite_nom TEXT,
            priorite TEXT DEFAULT 'Normale',
            statut TEXT DEFAULT 'À faire',
            due_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS frais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_frais TEXT NOT NULL,
            description TEXT NOT NULL,
            categorie TEXT,
            moyen_paiement TEXT,
            montant REAL DEFAULT 0,
            devise TEXT DEFAULT 'EUR',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_interaction TEXT DEFAULT (datetime('now')),
            type TEXT,
            entite_type TEXT,
            entite_id INTEGER,
            entite_nom TEXT,
            description TEXT,
            notes TEXT
        );

        UPDATE schema_version SET version = 1;
        """)
        conn.commit()
        _seed(conn)
        v = 1

    # Migrations futures — ajouter ici sans toucher aux données existantes
    if v < 6:
        conn.execute("UPDATE schema_version SET version = 6")
        conn.commit()

    conn.close()


def _seed(conn):
    # ── Utilisateur par défaut ──────────────────────────────────────────────
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?,?)",
        ("gautier", _hash("angels2026"))
    )

    # ── Pays ────────────────────────────────────────────────────────────────
    for p in [
        "Chine", "Japon", "Corée du Sud", "Macao", "Hong Kong", "Taiwan",
        "Philippines", "Laos", "Myanmar", "Cambodge", "Vietnam", "Thaïlande",
        "Malaisie", "Singapour", "Indonésie", "Australie", "Nouvelle-Zélande", "Inde"
    ]:
        conn.execute("INSERT OR IGNORE INTO pays (nom) VALUES (?)", (p,))

    # ── Producteurs ─────────────────────────────────────────────────────────
    for nom, code, region in [
        ("Maison Léda",           "LEDA", "Armagnac"),
        ("Famille Fabre",         "FAB",  "Languedoc"),
        ("G.H. Martel & Co",      "GHM",  "Champagne"),
        ("Cognac Lhéraud",        "LHE",  "Cognac"),
        ("Domaine Ostertag",      "OST",  "Alsace"),
        ("Alain Jaume",           "AJ",   "Rhône"),
        ("Plaimont",              "PLA",  "Gascogne"),
        ("Yves Cuilleron",        "YC",   "Rhône"),
        ("Camille Giroud",        "CGI",  "Bourgogne"),
        ("Alain Chabanon",        "ACH",  "Languedoc"),
        ("Anne Gros",             "AGR",  "Bourgogne"),
        ("Antonin Guyon",         "AGU",  "Bourgogne"),
        ("Asianet Fine Sourcing", "AFS",  "Co-agent"),
        ("Famille Baldès",        "FBA",  "Cahors"),
        ("Elian Da Ros",          "EDR",  "Côtes du Marmandais"),
        ("François Vilard",       "FV",   "Rhône"),
        ("Domaine Plageoles",     "DPL",  "Gaillac"),
        ("Domaine Pignier",       "DPI",  "Jura"),
        ("Trapet & Fils",         "TRA",  "Bourgogne"),
        ("Pierre Damoy",          "PDA",  "Bourgogne"),
        ("Sylvain Cathiard",      "SCA",  "Bourgogne"),
        ("Ghislaine Barthod",     "GBA",  "Bourgogne"),
        ("Domaine Pansiot",       "DPA2", "Bourgogne"),
    ]:
        conn.execute(
            "INSERT OR IGNORE INTO producteurs (nom, code, region) VALUES (?,?,?)",
            (nom, code, region)
        )
    conn.commit()

    def pid(code):
        return conn.execute("SELECT id FROM producteurs WHERE code=?", (code,)).fetchone()["id"]

    # ── Contacts Maison Léda ─────────────────────────────────────────────
    for role, nom, email, tel, mobile in [
        ("Contact principal", "Marie Dupont",   "marie@maisonleda.fr",  "+33 5 62 00 00 01", "+33 6 12 34 56 78"),
        ("Comptabilité",      "Pierre Martin",  "compta@maisonleda.fr", "+33 5 62 00 00 02", ""),
        ("Logistique",        "Sophie Bernard", "logistique@maisonleda.fr", "", "+33 6 98 76 54 32"),
    ]:
        conn.execute(
            "INSERT INTO producteur_contacts (producteur_id,role,nom,email,tel,mobile) VALUES (?,?,?,?,?,?)",
            (pid("LEDA"), role, nom, email, tel, mobile)
        )

    # ── Produits Maison Léda ─────────────────────────────────────────────
    for nom, tp, style in [
        ("Maison Léda VSOP",         "Armagnac", "Amber"),
        ("Maison Léda XO",           "Armagnac", "Amber"),
        ("Maison Léda Blanche",      "Armagnac", "White"),
        ("Maison Léda 1990 Millésime","Armagnac", "Amber"),
        ("Maison Léda 2005 Millésime","Armagnac", "Amber"),
    ]:
        conn.execute(
            "INSERT INTO produits (producteur_id,nom,type_produit,style) VALUES (?,?,?,?)",
            (pid("LEDA"), nom, tp, style)
        )

    # ── Contacts Famille Fabre ───────────────────────────────────────────
    for role, nom, email, tel, mobile in [
        ("Contact principal", "Jean Fabre",      "jean@famillefahre.fr",  "+33 4 67 00 00 01", "+33 6 11 22 33 44"),
        ("Comptabilité",      "Lucie Fabre",     "compta@famillefahre.fr","",                  ""),
    ]:
        conn.execute(
            "INSERT INTO producteur_contacts (producteur_id,role,nom,email,tel,mobile) VALUES (?,?,?,?,?,?)",
            (pid("FAB"), role, nom, email, tel, mobile)
        )

    # ── Entreprises clientes ─────────────────────────────────────────────
    entreprises = [
        ("Imex Asia Spirits",    "Client actif", "Hong Kong",    "Importateur",  "Actif"),
        ("Asia Wines & Spirits", "Client actif", "Singapour",    "Distributeur", "Actif"),
        ("Dragon Cellar Co.",    "Client actif", "Chine",        "Importateur",  "Actif"),
        ("Nihon Vins SARL",      "Client actif", "Japon",        "Importateur",  "Actif"),
        ("Bangkok Fine Wines",   "Client actif", "Thaïlande",    "Distributeur", "Actif"),
        ("Seoul Selection",      "Client actif", "Corée du Sud", "Importateur",  "Actif"),
        ("Macao Luxury Drinks",  "Client actif", "Macao",        "Importateur",  "Actif"),
        ("Pacific Spirits Taiwan","Prospect",    "Taiwan",       "Distributeur", "En discussion"),
    ]
    for nom, tp, pays, act, statut in entreprises:
        conn.execute(
            "INSERT INTO entreprises (nom,type,pays_destination,activite,statut) VALUES (?,?,?,?,?)",
            (nom, tp, pays, act, statut)
        )
    conn.commit()

    def eid(nom):
        return conn.execute("SELECT id FROM entreprises WHERE nom=?", (nom,)).fetchone()["id"]

    # ── Contacts individuels ─────────────────────────────────────────────
    for enom, cnom, pos, email, mobile, wechat, langue in [
        ("Imex Asia Spirits",    "James Wong",      "Directeur achats",  "james@imexasia.com",  "+852 9123 4567", "jameswong_hk",   "Anglais"),
        ("Asia Wines & Spirits", "Sarah Tan",       "Managing Director", "stan@awspte.sg",      "+65 9876 5432",  "",               "Anglais"),
        ("Dragon Cellar Co.",    "Liu Wei",         "Acheteur principal","lwei@dragoncellar.cn","+86 138 1234 5678","dragonwei2024", "Anglais"),
        ("Nihon Vins SARL",      "Takeshi Mori",    "Président",         "t.mori@nihonvins.jp", "+81 90 1234 5678","",              "Anglais"),
        ("Bangkok Fine Wines",   "Pattaraporn K.",  "Owner",             "pat@bkfwines.th",     "+66 81 234 5678", "",              "Anglais"),
        ("Seoul Selection",      "Kim Ji-yeon",     "Import Manager",    "jykim@seoulsel.kr",   "+82 10 1234 5678","",              "Anglais"),
        ("Macao Luxury Drinks",  "Carlos Fong",     "CEO",               "cfong@macaolux.mo",   "+853 6123 4567",  "",              "Anglais"),
    ]:
        conn.execute(
            "INSERT INTO contacts (entreprise_id,nom,position,email,mobile,wechat,langue) VALUES (?,?,?,?,?,?,?)",
            (eid(enom), cnom, pos, email, mobile, wechat, langue)
        )

    # ── Commandes de démonstration ───────────────────────────────────────
    for pf, client, pays, prod_code, mt, dev, taux, terms, enlev, statut, cs in [
        ("PF-2026-001","Imex Asia Spirits",   "Hong Kong",    "LEDA",18500,"EUR",10,30,"2026-01-15","Payé",    "Payé"),
        ("PF-2026-002","Asia Wines & Spirits","Singapour",    "FAB", 9200, "EUR",12,45,"2026-02-10","Livré",   "En attente"),
        ("PF-2026-003","Nihon Vins SARL",     "Japon",        "GHM",24000,"EUR",8, 60,"2026-02-20","Livré",   "En attente"),
        ("PF-2026-004","Dragon Cellar Co.",   "Chine",        "LEDA",31000,"EUR",10,30,"2026-03-05","En cours","Non éligible"),
        ("PF-2026-005","Bangkok Fine Wines",  "Thaïlande",    "LEDA",7600, "EUR",11,45,None,        "En cours","Non éligible"),
        ("PF-2026-006","Macao Luxury Drinks", "Macao",        "LHE",15800,"EUR",10,30,"2026-01-28","En retard","En attente"),
        ("PF-2026-007","Seoul Selection",     "Corée du Sud", "AJ",  5400,"EUR",13,30,"2026-03-12","En cours","Non éligible"),
    ]:
        p_id = pid(prod_code)
        conn.execute("""
            INSERT OR IGNORE INTO commandes
            (proforma,client_nom,pays,producteur_id,producteur_nom,montant,devise,
             taux_commission,payment_terms,date_enlevement,statut,comm_statut)
            VALUES (?,?,?,?,
                (SELECT nom FROM producteurs WHERE id=?),
                ?,?,?,?,?,?,?)
        """, (pf, client, pays, p_id, p_id, mt, dev, taux, terms, enlev, statut, cs))

    # ── Actions de démonstration ─────────────────────────────────────────
    for titre, entite, prio, due, statut, notes in [
        ("Relancer Dragon Cellar — paiement PF-2026-006","Commande","Urgente","2026-05-07","À faire","Vérifier d'abord avec compta Lhéraud"),
        ("Envoyer présentation Maison Léda à Pacific Spirits Taiwan","Prospect","Haute","2026-05-09","À faire",""),
        ("Préparer rapport activité Famille Fabre — mai 2026","Producteur","Normale","2026-05-15","À faire",""),
        ("Vérifier documents export PF-2026-004 (Chine)","Commande","Haute","2026-05-08","En cours","Analyses phtalates en attente"),
        ("Appeler Bangkok Fine Wines — date enlèvement PF-2026-005","Client","Normale","2026-05-10","À faire",""),
    ]:
        conn.execute(
            "INSERT INTO actions (titre,entite_type,priorite,due_date,statut,notes) VALUES (?,?,?,?,?,?)",
            (titre, entite, prio, due, statut, notes)
        )

    # ── Frais de démonstration ───────────────────────────────────────────
    for dt, desc, cat, moyen, mt in [
        ("2026-05-02","Billets Bangkok–Hong Kong Vinexpo","Voyage","Carte AirWallex",320),
        ("2026-05-03","Hébergement Vinexpo Asia 2 nuits","Hébergement","Virement Airwallex",480),
        ("2026-04-28","Digico abonnement mensuel","Abonnement logiciel","Carte AirWallex",45),
        ("2026-04-15","Dîner client Seoul Selection","Restaurant","Carte Kasikorn",210),
    ]:
        conn.execute(
            "INSERT INTO frais (date_frais,description,categorie,moyen_paiement,montant) VALUES (?,?,?,?,?)",
            (dt, desc, cat, moyen, mt)
        )

    conn.commit()


def migrate_extra(db):
    """Migrations supplémentaires — appelées au démarrage."""
    # Corriger les anciennes valeurs comm_statut
    try:
        db.execute("""UPDATE commandes SET comm_statut='À venir'
            WHERE comm_statut NOT IN ('À venir','Dues','Payé') OR comm_statut IS NULL""")
        db.commit()
    except Exception:
        pass
    extras = [
        ("entreprises", "docs_requis",      "TEXT"),
        ("entreprises", "tarifs_envoyes",   "INTEGER DEFAULT 0"),
        ("commandes",   "tarifs_envoyes",   "INTEGER DEFAULT 0"),
        ("contacts",    "prenom",           "TEXT"),
        ("contacts",    "civilite",         "TEXT"),
        ("contacts",    "date_naissance",   "TEXT"),
        ("contacts",    "conjoint",         "TEXT"),
        ("contacts",    "enfants",          "TEXT"),
        ("contacts",    "prefs_vins",       "TEXT"),
        ("contacts",    "prefs_cuisine",    "TEXT"),
        ("contacts",    "loisirs",          "TEXT"),
        ("contacts",    "infos_perso",      "TEXT"),
        ("contacts",    "prefs_pro",        "TEXT"),
        ("producteur_contacts", "prenom",         "TEXT"),
        ("producteur_contacts", "civilite",       "TEXT"),
        ("producteur_contacts", "date_naissance", "TEXT"),
        ("producteurs", "adresse_ligne1",   "TEXT"),
        ("producteurs", "adresse_ligne2",   "TEXT"),
        ("producteurs", "code_postal",      "TEXT"),
        ("producteurs", "ville",            "TEXT"),
        ("producteurs", "pays_adresse",     "TEXT"),
        ("producteurs", "ca_objectif",      "REAL DEFAULT 0"),
    ]
    for table, col, defn in extras:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
            db.commit()
        except Exception:
            pass
