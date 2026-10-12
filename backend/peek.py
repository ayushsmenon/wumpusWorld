from ingestion import registry

conn = registry.connect()
file_id = conn.execute(
    "SELECT id FROM files WHERE status = 'parsed' ORDER BY id DESC LIMIT 1"
).fetchone()["id"]

for unit in registry.get_units(conn, file_id):
    for i, table in enumerate(unit["tables"], start=1):
        print(f"--- Page {unit['number']}, table {i} ---")
        for row in table:
            print(row)
