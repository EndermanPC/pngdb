import os
import json
import math
from PIL import Image
from hashlib import sha256
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

PBKDF2_ITER = 300_000
KEY_LEN = 32  # AES-256
SALT_LEN = 16
IV_LEN = 12  # AES-GCM
LEN_HEADER = 8

def encrypt(data_bytes, password):
    salt = get_random_bytes(SALT_LEN)
    iv = get_random_bytes(IV_LEN)
    key = PBKDF2(password, salt, dkLen=KEY_LEN, count=PBKDF2_ITER)
    
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(data_bytes)
    
    # Structure: [salt][iv][tag][len][ciphertext]
    length = len(ciphertext).to_bytes(LEN_HEADER, 'big')
    return salt + iv + tag + length + ciphertext

def decrypt(enc_bytes, password):
    salt = enc_bytes[:SALT_LEN]
    iv = enc_bytes[SALT_LEN:SALT_LEN+IV_LEN]
    tag = enc_bytes[SALT_LEN+IV_LEN:SALT_LEN+IV_LEN+16]
    length = int.from_bytes(enc_bytes[SALT_LEN+IV_LEN+16:SALT_LEN+IV_LEN+16+LEN_HEADER], 'big')
    ciphertext = enc_bytes[SALT_LEN+IV_LEN+16+LEN_HEADER:SALT_LEN+IV_LEN+16+LEN_HEADER+length]
    
    key = PBKDF2(password, salt, dkLen=KEY_LEN, count=PBKDF2_ITER)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    
    return cipher.decrypt_and_verify(ciphertext, tag)

def bytes_to_image(data_bytes, filename="db.png"):
    length = len(data_bytes)
    w = math.ceil(math.sqrt(length / 3))
    h = w
    img = Image.new("RGB", (w, h))
    pixels = []
    i = 0
    while i < length:
        r = data_bytes[i] if i < length else 0
        g = data_bytes[i+1] if i+1 < length else 0
        b = data_bytes[i+2] if i+2 < length else 0
        pixels.append((r, g, b))
        i += 3
    while len(pixels) < w*h:
        pixels.append((0, 0, 0))
    img.putdata(pixels)
    img.save(filename)

def image_to_bytes(filename="db.png"):
    img = Image.open(filename)
    pixels = list(img.getdata())
    data_bytes = bytearray()
    for px in pixels:
        data_bytes.extend(px)
    return bytes(data_bytes)

def load_db(filename, password):
    raw = image_to_bytes(filename)
    decrypted = decrypt(raw, password)
    return json.loads(decrypted.decode("utf-8"))

def save_db(data_dict, filename, password):
    j = json.dumps(data_dict).encode("utf-8")
    encrypted = encrypt(j, password)
    bytes_to_image(encrypted, filename)

def execute_query(db, line):
    line = line.strip()

    # JSONGET
    if m := re.match(r"JSONGET\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*(\d+);", line, re.I):
        table, field, value = m.group(1), m.group(2), int(m.group(3))
        results = [row for row in db.get(table, []) if row.get(field) == value]
        print(json.dumps(results, indent=2))
        sys.exit(0)

    elif m := re.match(r"JSONGET\s+(\w+)\s*;", line, re.I):
        table = m.group(1)
        print(json.dumps(db.get(table, []), indent=2))
        sys.exit(0)
    
    elif m := re.match(r"JSONGET\s+\*\s*;", line, re.I):
        print(json.dumps(db, indent=2))
        sys.exit(0)

    # JSONPUSH all
    elif m := re.match(r"JSONPUSH\s+\*\s*+VALUES\s+(\[.*\]);", line, re.I):
        json_arr = m.group(1)
        try:
            data = json.loads(json_arr)
            if not isinstance(data, list):
                raise ValueError("Must be a JSON array.")
            db = data
            print(f"[+] Entire database replaced.")
            return True
        except Exception as e:
            print(f"[!] Invalid JSON for JSONPUSH *: {e}")
            return False

    # JSONPUSH with WHERE
    elif m := re.match(r"JSONPUSH\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*(\d+)\s+VALUES\s+(\{.*\});", line, re.I):
        table, field, value, json_obj = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        try:
            new_data = json.loads(json_obj)
            updated = False
            for i, row in enumerate(db.get(table, [])):
                if row.get(field) == value:
                    db[table][i] = new_data
                    updated = True
            if not updated:
                print(f"[!] No matching row found in {table} for {field}={value}")
            return True
        except json.JSONDecodeError:
            print("[!] Invalid JSON for JSONPUSH")
            return False

    # JSONPUSH all table
    elif m := re.match(r"JSONPUSH\s+(\w+)\s+\*\s+VALUES\s+(\[.*\]);", line, re.I):
        table, json_arr = m.group(1), m.group(2)
        try:
            data = json.loads(json_arr)
            if not isinstance(data, list):
                raise ValueError("Must be a JSON array.")
            db[table] = data
            print(f"[+] Entire table '{table}' replaced.")
            return True
        except Exception as e:
            print(f"[!] Invalid JSON for JSONPUSH *: {e}")
            return False

    # SELECT *;
    elif m := re.match(r"SELECT\s+\*\s*;", line, re.I):
        print(json.dumps(db, indent=2))

    # SELECT table;
    elif m := re.match(r"SELECT\s+(\w+)\s*;", line, re.I):
        table = m.group(1)
        print(json.dumps(db.get(table, []), indent=2))

    # SELECT table WHERE field="str";
    elif m := re.match(r"SELECT\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*\"(.+)\";", line, re.I):
        table, field, value = m.group(1), m.group(2), m.group(3)
        results = [row for row in db.get(table, []) if str(row.get(field)) == value]
        print(json.dumps(results, indent=2))

    elif m := re.match(r"LIST\s+TABLES\s*;", line, re.I):
        print(json.dumps(list(db.keys()), indent=2))

    elif m := re.match(r"DESCRIBE\s+(\w+)\s*;", line, re.I):
        table = m.group(1)
        if table in db and db[table]:
            print(json.dumps(list(db[table][0].keys()), indent=2))
        else:
            print(f"[!] Table '{table}' is empty or not found.")

    elif m := re.match(r"SELECT\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*(\d+);", line, re.I):
        table, field, value = m.group(1), m.group(2), int(m.group(3))
        results = [row for row in db.get(table, []) if row.get(field) == value]
        print(json.dumps(results, indent=2))

    elif m := re.match(r"GET\s+(\w+)\.(\w+)\s+WHERE\s+(\w+)\s*=\s*(\d+);", line, re.I):
        table, field, cond_field, cond_val = m.group(1), m.group(2), m.group(3), int(m.group(4))
        results = [row[field] for row in db.get(table, []) if row.get(cond_field) == cond_val]
        if results:
            print(results[0])
        else:
            print("[!] No match found.")

    elif m := re.match(r"GET\s+(\w+)\.(\w+)\s+WHERE\s+(\w+)\s+CONTAINS\s+\"(.+)\";", line, re.I):
        table, field, cond_field, substr = m.group(1), m.group(2), m.group(3), m.group(4)
        results = [row[field] for row in db.get(table, []) if substr in str(row.get(cond_field, ""))]
        print(json.dumps(results, indent=2) if results else "[!] No match found.")

    elif m := re.match(r"UPDATE\s+(\w+)\s+SET\s+(\w+)\s*=\s*\"(.+)\"\s+WHERE\s+(\w+)\s*=\s*(\d+);", line, re.I):
        table, field, val, cond_field, cond_val = m.group(1), m.group(2), m.group(3), m.group(4), int(m.group(5))
        modified = False
        for row in db.get(table, []):
            if row.get(cond_field) == cond_val:
                row[field] = val
                modified = True
        if modified:
            print(f"[+] Updated {table} where {cond_field}={cond_val}")
            return True
        else:
            print(f"[!] No rows matched in {table}")

    elif m := re.match(r"INSERT\s+INTO\s+(\w+)\s+VALUES\s+(\{.*\});", line, re.I):
        table, json_obj = m.group(1), m.group(2)
        try:
            row = json.loads(json_obj)
            db.setdefault(table, []).append(row)
            print(f"[+] Inserted into {table}")
            return True
        except json.JSONDecodeError:
            print("[!] Invalid JSON object for INSERT.")

    elif m := re.match(r"DELETE\s+FROM\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*(\d+);", line, re.I):
        table, field, value = m.group(1), m.group(2), int(m.group(3))
        original_len = len(db.get(table, []))
        db[table] = [row for row in db.get(table, []) if row.get(field) != value]
        deleted = original_len - len(db[table])
        if deleted:
            print(f"[+] Deleted {deleted} row(s) from {table}")
            return True
        else:
            print(f"[!] No matching rows to delete in {table}")

    elif m := re.match(r"COUNT\s+(\w+)\s*;", line, re.I):
        table = m.group(1)
        count = len(db.get(table, []))
        print(f"[+] {table} has {count} row(s).")

    # DELETE * FROM table;
    elif m := re.match(r"DELETE\s+\*\s+FROM\s+(\w+);", line, re.I):
        table = m.group(1)
        db[table] = []
        print(f"[+] Cleared table '{table}'.")

    # UPDATE table SET field="val" WHERE cond=val;
    elif m := re.match(r"UPDATE\s+(\w+)\s+SET\s+(\w+)\s*=\s*\"(.+)\"\s+WHERE\s+(\w+)\s*=\s*(\d+);", line, re.I):
        table, field, val, cond_field, cond_val = m.group(1), m.group(2), m.group(3), m.group(4), int(m.group(5))
        modified = False
        for row in db.get(table, []):
            if row.get(cond_field) == cond_val:
                row[field] = val
                modified = True
        print(f"[+] Updated {table}" if modified else "[!] No row updated.")

    # UPDATE table SET field="val";
    elif m := re.match(r"UPDATE\s+(\w+)\s+SET\s+(\w+)\s*=\s*\"(.+)\";", line, re.I):
        table, field, val = m.group(1), m.group(2), m.group(3)
        for row in db.get(table, []):
            row[field] = val
        print(f"[+] Updated all rows in {table}.")

    # INSERT INTO table VALUES {...};
    elif m := re.match(r"INSERT\s+INTO\s+(\w+)\s+VALUES\s+(\{.*\});", line, re.I):
        table, json_obj = m.group(1), m.group(2)
        try:
            row = json.loads(json_obj)
            db.setdefault(table, []).append(row)
            print(f"[+] Inserted into {table}")
            return True
        except json.JSONDecodeError:
            print("[!] Invalid JSON object for INSERT.")

    # INSERT INTO table SET a=1,b="x";
    elif m := re.match(r"INSERT\s+INTO\s+(\w+)\s+SET\s+(.+);", line, re.I):
        table, set_str = m.group(1), m.group(2)
        try:
            fields = dict()
            for pair in set_str.split(","):
                key, val = pair.strip().split("=")
                key = key.strip()
                val = val.strip().strip('"')
                try:
                    val = int(val)
                except:
                    pass
                fields[key] = val
            db.setdefault(table, []).append(fields)
            print(f"[+] Inserted into {table}")
            return True
        except Exception as e:
            print(f"[!] Invalid INSERT SET syntax: {e}")
            return False

    # GET table.field WHERE cond = val;
    elif m := re.match(r"GET\s+(\w+)\.(\w+)\s+WHERE\s+(\w+)\s*=\s*(\d+);", line, re.I):
        table, field, cond_field, cond_val = m.group(1), m.group(2), m.group(3), int(m.group(4))
        results = [row[field] for row in db.get(table, []) if row.get(cond_field) == cond_val]
        if results:
            print(results[0])
        else:
            print("[!] No match found.")

    else:
        print(f"[!] Unsupported or invalid query: {line}")
    return False

def run_pngdb_script(pngdb_file, db_file="db.png", password="secret"):
    with open(pngdb_file, "r") as f:
        lines = f.readlines()

    db = load_db(db_file, password)
    modified = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        if execute_query(db, line):
            modified = True

    if modified:
        save_db(db, db_file, password)
        print("[✓] Changes saved.")
    else:
        print("[i] No changes made.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python pngdb.py <pngdb_file> <db_file> <password>")
        exit(1)
    pngdb_file = sys.argv[1]
    db_file = sys.argv[2]
    password = sys.argv[3]
    run_pngdb_script(pngdb_file, db_file, password)
