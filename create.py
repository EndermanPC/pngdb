from pngdb import save_db
db = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
save_db(db, "admin.png", "root")
