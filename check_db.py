import sqlite3
db = sqlite3.connect("/Users/gautiersalinier/Documents/Angels Share Marketing Limited/Angels' Share Management/angels_share.db")
print('Total:', db.execute('SELECT COUNT(*) FROM prospection').fetchone()[0])
db.close()
