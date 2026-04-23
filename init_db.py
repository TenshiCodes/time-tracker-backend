import os
from dotenv import load_dotenv
import psycopg2
from passlib.context import CryptContext

# =========================
# 🚀 LOAD ENV VARS
# =========================
load_dotenv()
print("Running from:", os.getcwd())

# 🔐 Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password):
    password = password.encode("utf-8")[:72]
    return pwd_context.hash(password)

# =========================
# 🔌 CONNECT TO POSTGRES
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# =========================
# 🧱 CREATE TABLES
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    email_notifications BOOLEAN DEFAULT FALSE,
    sms_notifications BOOLEAN DEFAULT FALSE,
    reset_token TEXT,
    reset_token_expiry TIMESTAMPTZ
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    job_code TEXT NOT NULL UNIQUE,
    job_name TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_job_assignments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
    UNIQUE(user_id, item_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS time_entries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    clock_in TIMESTAMPTZ,
    clock_out TIMESTAMPTZ,
    total_hours REAL,
    notes TEXT,
    edited BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    item_id INTEGER,
    job_code TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    rejected_at TIMESTAMP,
    approved_by TEXT,
    rejected_by TEXT
)
""")

# =========================
# 🌱 SEED ITEMS (ONLY IF EMPTY)
# =========================

cursor.execute("SELECT COUNT(*) FROM items")
count = cursor.fetchone()[0]

if count == 0:
    print("🌱 Seeding items...")

    sample_items = [
        ("LAX: Front End Engineering", "J_SCA000906"),
        ("Project Allée", "J_SCA000926"),
        ("Non-billable Hours", "J_SCA000947"),
        ("Riverside: Line 2 Palletizer and Wrapper Machine Safety Remediation", "J_SCA000966"),
        ("Fuel Cell Control Stage 1 Additional Hardware", "J_SCA000976"),
        ("Fuel Cell Control Stage 1", "J_SCA000977"),
        ("Power SCADA Server Racks", "J_SCA000981"),
        ("Fuel Cell Control Part 2 SHA, Panel Assembly, and Programming T&M", "J_SCA001007"),
        ("Jaws RCS and RSS Redline Updates", "J_SCA001039"),
        ("ITW Boxin Download 202112013", "J_SCA001058"),
        ("SOP for AB/Rockwell license management", "J_SCA001060"),
        ("2023 Non Job Specific Costs", "J_SCA001069"),
        ("The Cable Connection_ Boxin Download", "J_SCA001091"),
        ("Aaon China Download", "J_SCA001092"),
        ("3 Month Controls Engineering Support", "J_SCA001111"),
        ("T&M IT Audit", "J_SCA001114"),
        ("Aaon Onsite Commissioning", "J_SCA001121"),
        ("ITW Support", "J_SCA001123"),
        ("Safety Scanner Integration", "J_SCA001128"),
        ("PepsiCo Mustang Verification & Validation", "J_SCA001136"),
        # (you can keep the rest — trimmed here for readability)
    ]

    cursor.executemany(
        "INSERT INTO items (job_name, job_code) VALUES (%s, %s)",
        sample_items
    )

    # ✅ Sync sequence WITHOUT ownership issues
    cursor.execute("""
        SELECT setval(
            pg_get_serial_sequence('items', 'id'),
            (SELECT MAX(id) FROM items)
        );
    """)

    print("✅ Items seeded (IDs start at 1)")

else:
    print("⏭️ Items already exist — skipping seed")

# =========================
# 💾 SAVE & CLOSE
# =========================
conn.commit()
cursor.close()
conn.close()

print("✅ Postgres DB initialized")