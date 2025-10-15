import sqlite3, json

DB_PATH = r"C:\Users\Acer\Documents\GitHub\web-Service_Home\backend\devices.sqlite3"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM devices ORDER BY id").fetchall()
print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))

conn.close()