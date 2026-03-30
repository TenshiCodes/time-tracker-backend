import os
import psycopg2
from passlib.context import CryptContext

print("Running from:", os.getcwd())

# 🔐 Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password):
    password = password.encode("utf-8")[:72]
    return pwd_context.hash(password)

# 🔌 Connect to Postgres (Render)
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for Render (sometimes uses postgres://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# =========================
# 🧱 CREATE TABLES
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL
)
""")

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
    sms_notifications BOOLEAN DEFAULT FALSE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS time_entries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    clock_in TIMESTAMP,
    clock_out TIMESTAMP,
    total_hours REAL,
    notes TEXT,
    edited BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
# 🔹 RESET ITEMS (optional)
# =========================
cursor.execute("DELETE FROM items")

# =========================
# 🔹 INSERT ITEMS
# =========================
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
    ("Doncasters Visualization & Alarm Escalation", "J_SCA001147"),
    ("ITW Support", "J_SCA001149"),
    ("Nalco Historian Update T&M", "J_SCA001150"),
    ("Sheeter, Processor, Extruder Assessment", "J_SCA001151"),
    ("Cable Connection Mark-50", "J_SCA001154"),
    ("ASRS Safety Update Application", "J_SCA001158"),
    ("Omaha Remote Support", "J_SCA001160"),
    ("3 week T&M Safety Engineering", "J_SCA001163"),
    ("Steam generation control project", "J_SCA001165"),
    ("San Leandro WTP-RFQ Modifications", "J_SCA001167"),
    ("Bergman KPRS_ Pump Controls Integration", "J_SCA001168"),
    ("Prolec GE - Boxin Commissioning", "J_SCA001172"),
    ("Injection Molding Machines Safety Review", "J_SCA001173"),
    ("Waldale Boxin Download", "J_SCA001174"),
    ("12 Oz Communication Controls Upgrade", "J_SCA001175"),
    ("Bruce Aerospace Hydro", "J_SCA001176"),
    ("UPS/Battery Panel", "J_SCA001177"),
    ("AB Hydro HRT-600", "J_SCA001178"),
    ("Line 8-9 Dryer Additions", "J_SCA001184"),
    ("Sweed Chopper Assessment", "J_SCA001185"),
    ("P&F Purge System Assembly", "J_SCA001186"),
    ("AAON Tulsa Remote Work", "J_SCA001191"),
    ("Energy Monitoring Integration", "J_SCA001196"),
    ("905 SAT T&M Support", "J_SCA001201"),
    ("Bay Valley 3rd Shift Support", "J_SCA001202"),
    ("Kirchhoff Onsite Mexico Commissioning", "J_SCA001203"),
    ("Change Order for PDUs for Power SCADA Server Racks", "J_SCA001205"),
    ("Line 8 Expansion Safety Assessment", "J_SCA001206"),
    ("MFG/Show Press", "J_SCA001208"),
    ("Stanley Black and Decker Troubleshooting", "J_SCA001210"),
    ("GE Prolec China Download", "J_SCA001212"),
    ("GE Prolec China Download", "J_SCA001215"),
    ("Retrofitted Mark-121 / Emerson Tool Company MX", "J_SCA001216"),
    ("Trim Stamping Remote Support", "J_SCA001217"),
    ("NovaTech Remote Support", "J_SCA001218"),
    ("Malarkey Firmware Upgrade Service Call", "J_SCA001219"),
    ("NovaTech Software Programming", "J_SCA001220"),
    ("Oliver Tech Remote Support", "J_SCA001222"),
    ("920B Verification", "J_SCA001223"),
    ("Modesto TC Oven and Sheeter Verification and Validation", "J_SCA001224"),
    ("Stacker and Press Safety Assessment", "J_SCA001225"),
    ("MESS Validation VP Line at Blue Ridge", "J_SCA001226"),
    ("DI Water Dosing Controls", "J_SCA001227"),
    ("GXVS21-TS Sealer Assessment", "J_SCA001228"),
    ("Siemens MX Remote Support", "J_SCA001229"),
    ("Ladessa MX - China Download", "J_SCA001230"),
    ("Reno Press Line Safety Remediation", "J_SCA001231"),
    ("Speed Indicator Integration", "J_SCA001232"),
    ("Metal Plasma Tech Service Call", "J_SCA001233"),
    ("Shot / Dispense Controls Modification", "J_SCA001235"),
    ("Inframark VFD Installation", "J_SCA001236"),
    ("P902 Coaster", "J_SCA001237"),
    ("Smith & Wesson Remote Support", "J_SCA001238"),
    ("Inframark 150HP VFD Installation", "J_SCA001239"),
    ("Lab MT Scale Panel Build", "J_SCA001240"),
    ("VFD Service Call", "J_SCA001241"),
    ("MaxPak Horizontal Baler Assessment", "J_SCA001242"),
    ("Howmet Torrance Service Call", "J_SCA001243"),
    ("Clayton Homes", "J_SCA001244"),
    ("Stanley Black & Decker", "J_SCA001245"),
    ("Stone Mountain Verification and Validation", "J_SCA001246"),
    ("MT Scale Connections", "J_SCA001247"),
    ("PK EIOC installation", "J_SCA001248"),
    ("Owens Corning Flowmeter Installation", "J_SCA001249"),
    ("Lancaster TX Auto LPN Turn Key Proposal", "J_SCA001250"),
    ("Multivac Sealer Assessment for R&D", "J_SCA001251"),
    ("Service Call", "J_SCA001252"),
    ("Shield HealthCare Service Call", "J_SCA001253"),
    ("Malarkay Roofing Ultra Service Call", "J_SCA001254"),
    ("Preform Line Products", "J_SCA001256"),
    ("Cable Connection @ Nevada", "J_SCA001257"),
    ("Paramount Mattco Forge VFD Startup", "J_SCA001258"),
    ("Prolec GE Press Commissioning", "J_SCA001259"),
    ("Novatech Dwell Remote Troubleshooting", "J_SCA001260"),
    ("Kirchhoff Peripheral Hydraulic System/Die Programming", "J_SCA001261"),
    ("FTOptix T&M Engagement", "J_SCA001262"),
    ("Torrance Service Call", "J_SCA001263"),
    ("Houston Verification and Validation", "J_SCA001264"),
    ("Mechanical AB Program Optimization", "J_SCA001265"),
    ("Optical Sensor Service Call", "J_SCA001266"),
    ("DMC Emergency Service Call", "J_SCA001267"),
    ("Inframark Fan Re-wire", "J_SCA001268"),
    ("Slide Parallelism Monitoring System", "J_SCA001269"),
    ("Service Call", "J_SCA001270"),
    ("Service Call 2/20", "J_SCA001271"),
    ("Denver TC Oven Assessment", "J_SCA001272"),
    ("Lab MT Scale Panel Build", "J_SCA001273"),
    ("Emerson Support", "J_SCA001274"),
    ("Digester Electrical Schematic Development", "J_SCA001275"),
    ("MIB#2 Project", "J_SCA001276"),
    ("Sutherland Hydro Manual / Continuous Development", "J_SCA001277"),
    ("Manhasset Remote Support", "J_SCA001278"),
    ("Cable Connection Footswitch Project", "J_SCA001279"),
    ("Trim Stamping Remote Support", "J_SCA001280"),
    ("IPS-CIRCUIT BREAKER", "J_SCA001281"),
    ("Las Vegas Verification and Validation", "J_SCA001282"),
    ("Shutdown Refinery Sensor Integration", "J_SCA001283"),
    ("PanelView Service Call", "J_SCA001284"),
    ("CompactLogix Service Call", "J_SCA001285"),
    ("Precise Metal Products Hydro Support", "J_SCA001286"),
    ("HMI Service Call", "J_SCA001287"),
    ("Cam Chain SP1-660 Download", "J_SCA001288"),
    ("Jonesboro AR Wrappers Validation", "J_SCA001290"),
    ("12184-W Additional Programming changes", "J_SCA001291"),
    ("Eaton Breakers & Hardware", "J_SCA001292"),
    ("T&M Safety Engineering Support", "J_SCA001293"),
    ("Vacuum Controls Upgrade", "J_SCA001294"),
    ("Tolleson AZ Ancra Assessments", "J_SCA001295"),
    ("Amber Industrial Service Call", "J_SCA001296"),
    ("900 & 902 Coaster", "J_SCA001297"),
    ("Olivertech", "J_SCA001298"),
    ("Kirchoff Support", "J_SCA001300"),
    ("Jig and Server Rack Installation and Wiring T&M", "J_SCA001301"),
    ("Service Call", "J_SCA001302"),
    ("T&M Support for ISO13849 Compliance", "J_SCA001303"),
    ("Pallet Lifts and Skate Loader Assessments", "J_SCA001304"),
    ("Inframark Service Call 5/20", "J_SCA001305"),
    ("Tolleson Club Manual Line Auto LPN Integration", "J_SCA001306"),
    ("Dallas Forth Worth Better Together Greenfield Assessments", "J_SCA001307"),
    ("Slicer DRA, SRS, Verification, and Validation", "J_SCA001308"),
    ("Corn Chip Extruder DRA", "J_SCA001309"),
    ("Tolleson VPN Auto LPN Project", "J_SCA001310"),
    ("Line 2, Line 6, Line 7, Line 4 DRAs", "J_SCA001311"),
    ("Forklift Crossing Risk Assessment", "J_SCA001312"),
]

cursor.executemany(
    "INSERT INTO items (name, code) VALUES (%s, %s)",
    sample_items
)

# =========================
# 🔹 INSERT USERS
# =========================
users = [
    ("Admin", "User", "admin@email.com", "1234567890", "admin", hash_password("admin123"), "admin", False, False),
    ("Angel", "Cazares", "angel@email.com", "1234567890", "angel", hash_password("password123"), "user", False, False),
]

cursor.executemany(
    """
    INSERT INTO users 
    (first_name, last_name, email, phone, username, password_hash, role, email_notifications, sms_notifications)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (username) DO NOTHING
    """,
    users
)

# =========================
# 💾 SAVE & CLOSE
# =========================
conn.commit()
cursor.close()
conn.close()

print("✅ Postgres DB initialized")