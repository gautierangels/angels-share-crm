import sqlite3

db = sqlite3.connect("/Users/gautiersalinier/Documents/Angels Share Marketing Limited/Angels\'  Share Management/angels_share.db")
db.row_factory = sqlite3.Row

# Compter avant
avant = db.execute("SELECT COUNT(*) FROM prospection WHERE archived=0").fetchone()[0]
print(f"Contacts avant : {avant}")

# Supprimer les contacts sans email valide
# (email NULL, vide, ou ne contenant pas @)
db.execute("""
    DELETE FROM prospection
    WHERE archived=0
    AND etape='Nouveau prospect'
    AND (
        contact_email IS NULL
        OR TRIM(contact_email) = ''
        OR contact_email NOT LIKE '%@%'
        OR LENGTH(contact_email) < 6
    )
""")
db.commit()

apres = db.execute("SELECT COUNT(*) FROM prospection WHERE archived=0").fetchone()[0]
print(f"Contacts après  : {apres}")
print(f"Supprimés       : {avant - apres}")
db.close()
