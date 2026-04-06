from fastapi import FastAPI, Query, Response
import sqlite3
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from fastapi import HTTPException
from pydantic import BaseModel
from init_db import hash_password
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import FileResponse
from openpyxl import Workbook
from datetime import datetime, timezone, timedelta
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import uuid
from dotenv import load_dotenv
import psycopg2
from zoneinfo import ZoneInfo
import psycopg2.extras
import secrets
from workbook import build_timesheet_wb


load_dotenv()

router = APIRouter()
# 🔥 PUT YOUR REAL VALUES HERE
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")  # your Twilio number
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
FRONTEND_URL = os.getenv("FRONTEND_URL")

client = Client(TWILIO_SID, TWILIO_AUTH)

def send_email(to_email, subject, message):
    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = "testingApp@pbe.com"
        msg["To"] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

        print(f"Email sent to {to_email}")

    except Exception as e:
        print("EMAIL ERROR:", e)

def send_sms(phone, message):
    try:
        msg = client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=phone
        )
        print("SMS sent:", msg.sid)

    except Exception as e:
        print("SMS ERROR:", e)

def format_phone(phone: str):
    phone = phone.strip().replace("-", "").replace("(", "").replace(")", "").replace(" ", "")

    if not phone.startswith("+"):
        if phone.startswith("1"):
            phone = "+" + phone
        else:
            phone = "+1" + phone

    return phone
class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    username: str
    password: str

class ItemRequest(BaseModel):
    name: str
    code: str
    
class LoginRequest(BaseModel):
    username: str
    password: str
class RoleUpdate(BaseModel):
    role: str

class TicketRequest(BaseModel):
    description: str
    username: str

class UserSettingsUpdate(BaseModel):
    email_notifications: bool
    sms_notifications: bool
class TimeEdit(BaseModel):
    clock_in: str
    clock_out: str
    item_id: int
    job_code: str
class ClockInRequest(BaseModel):
    user_id: int
    item_id: int | None = None
    job_code: str | None = None

class TimeUpdate(BaseModel):
    clock_in: str
    clock_out: str
    job_code: str | None = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.options("/{rest_of_path:path}")
def preflight_handler(rest_of_path: str):
    return Response(status_code=200)
def get_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain, hashed):
    plain = plain.encode("utf-8")[:72]  # 🔥 fix bcrypt limit
    return pwd_context.verify(plain, hashed)


@app.post("/reset-password")
def reset_password(data: dict):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        token = data.get("token")
        new_password = data.get("password")

        # 🔍 Find user by token
        cursor.execute("""
            SELECT id, reset_token_expiry
            FROM users
            WHERE reset_token=%s
        """, (token,))

        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid token")

        user_id = user["id"]
        expiry = user["reset_token_expiry"]

        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry)
        # ⏱ Check expiration
        if datetime.now(timezone.utc) > expiry:
            raise HTTPException(status_code=400, detail="Token expired")

        # 🔐 Hash new password
        hashed_pw = hash_password(new_password)

        # 💾 Update password + clear token
        cursor.execute("""
            UPDATE users
            SET password_hash=%s, reset_token=NULL, reset_token_expiry=NULL
            WHERE id=%s
        """, (hashed_pw, user_id))

        conn.commit()

        return {"message": "Password reset successful"}

@app.post("/forgot-password")
def forgot_password(data: dict):
     with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        username = data.get("username")

        # 🔍 Find user
        cursor.execute("SELECT id, email FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["id"]
        email = user["email"]

        # 🔐 Generate secure token
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now(timezone.utc) + timedelta(hours=1))
        # 💾 Save token
        cursor.execute("""
            UPDATE users
            SET reset_token=%s, reset_token_expiry=%s
            WHERE id=%s
        """, (token, expiry, user_id))

        conn.commit()

        # 📧 Send email (YOU already have this function)
        reset_link = f"{FRONTEND_URL}/reset-password?token={token}"

        send_email(
            email,
            "Password Reset",
            f"Click this link to reset your password:\n{reset_link}"
        )

        return {"message": "Reset email sent"}

@app.get("/calendar/event/{entry_id}")
def create_calendar_event(entry_id: int,tz: str = "UTC"):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT clock_in, clock_out, job_code
            FROM time_entries
            WHERE id = %s
        """, (entry_id,))

        entry = cursor.fetchone()

    if not entry:
        raise HTTPException(404, "Entry not found")

    start = entry["clock_in"]
    end = entry["clock_out"]
    job = entry["job_code"]

    if not start or not end:
        raise HTTPException(400, "Entry not complete")

    uid = str(uuid.uuid4())
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    start_dt = start.astimezone(ZoneInfo(tz))
    end_dt = end.astimezone(ZoneInfo(tz))

    start_str = start_dt.strftime("%Y%m%dT%H%M%S")
    end_str = end_dt.strftime("%Y%m%dT%H%M%S")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//YourApp//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:Work - {job or 'No Job'}",
        f"DTSTART:{start_str}Z",
        f"DTEND:{end_str}Z",
        f"DESCRIPTION:Worked on {job or 'No Job'}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]

    file_path = f"event_{entry_id}.ics"

    with open(file_path, "w") as f:
        f.write("\r\n".join(lines))

    return FileResponse(
        path=file_path,
        filename=file_path,
        media_type="text/calendar"
    )
@app.post("/export/email/{user_id}")
def email_time_entries(user_id: int, tz: str = "UTC"):
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # ✅ Get user email
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()

            if not user:
                raise HTTPException(404, "User not found")

            email_to = user["email"]
            fname = user["first_name"]
            lname = user["last_name"]
            # ✅ SAME QUERY AS EXPORT
            cursor.execute("""
                SELECT date, clock_in, clock_out, job_code
                FROM time_entries
                WHERE user_id = %s
                ORDER BY clock_in
            """, (user_id,))
            time_entries = cursor.fetchall()

            # ✅ SAME PROJECTS QUERY
            cursor.execute("SELECT name, code FROM items ORDER BY name;")
            projects = cursor.fetchall()

        # ✅ BUILD USING SAME FUNCTION
        wb = build_timesheet_wb(projects, time_entries, tz)

        file_path = f"{fname}_{lname}_Timesheet.xlsx"
        wb.save(file_path)

        # -----------------------------------
        # 📧 EMAIL ATTACHMENT
        # -----------------------------------
        msg = MIMEMultipart()
        msg["Subject"] = "Your Timesheet"
        msg["From"] = EMAIL_USER
        msg["To"] = email_to

        with open(file_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={fname}_{lname}_Timesheet.xlsx"
        )
        msg.attach(part)

        # ✅ SEND EMAIL
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

        print(f"✅ Email sent to {email_to}")

        return {"message": f"Email sent to {email_to}"}

    except Exception as e:
        print("🔥 EMAIL EXPORT ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/export/time")
def export_time_entries(user_id: int, tz: str = "UTC"):
    with get_db() as db:
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # ✅ Get user email
        cursor.execute("SELECT first_name, last_name FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(404, "User not found")

        fname = user["first_name"]
        lname = user["last_name"]

        # Get time entries
        cursor.execute("""
            SELECT date, clock_in, clock_out, job_code
            FROM time_entries
            WHERE user_id = %s
            ORDER BY clock_in
        """, (user_id,))
        time_entries = cursor.fetchall()

        # Get projects
        cursor.execute("SELECT name, code FROM items ORDER BY name;")
        projects = cursor.fetchall()

    # Build workbook
    wb = build_timesheet_wb(projects, time_entries, tz)

    file_path = f"{fname}_{lname}_Timesheet.xlsx"
    wb.save(file_path)

    return FileResponse(
        path=file_path,
        file_path = f"{fname}_{lname}_Timesheet.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.post("/time/clock-in")
def clock_in(data: ClockInRequest):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # prevent double clock in
        cursor.execute("""
            SELECT * FROM time_entries 
            WHERE user_id = %s AND clock_out IS NULL
        """, (data.user_id,))
        
        if cursor.fetchone():
        
            raise HTTPException(400, "Already clocked in")

        # ✅ FIX: include item_id + job_code
        cursor.execute("""
            INSERT INTO time_entries 
            (user_id, date, clock_in, item_id, job_code)
            VALUES (%s, CURRENT_DATE, NOW(), %s, %s)
        """, (
            data.user_id,
            data.item_id,
            data.job_code
        ))

        conn.commit()
    return {"message": "Clocked in"}

@app.get("/time/entry/{entry_id}")
def get_entry(entry_id: int):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM time_entries WHERE id = %s", (entry_id,))
        entry = cursor.fetchone()
    

        if not entry:
            raise HTTPException(404, "Not found")

    return dict(entry)

@app.post("/time/clock-out")
def clock_out(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT id, clock_in FROM time_entries
            WHERE user_id = %s AND date = CURRENT_DATE
            ORDER BY id DESC LIMIT 1
        """, (user_id,))

        entry = cursor.fetchone()

        if not entry:
            raise HTTPException(404, "No clock-in found")

        cursor.execute("""
            UPDATE time_entries
            SET clock_out = NOW(),
                total_hours = EXTRACT(EPOCH FROM (NOW() - clock_in)) / 3600.0
            WHERE id = %s
        """, (entry["id"],))

        conn.commit()
  
    return {"message": "Clocked out"}
@app.get("/time/status/{user_id}")
def get_time_status(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT clock_in, job_code
            FROM time_entries
            WHERE user_id = %s AND clock_out IS NULL
            ORDER BY id DESC LIMIT 1
        """, (user_id,))

        entry = cursor.fetchone()

    if not entry:
        return {"clocked_in": False}

    return {
        "clocked_in": True,
        "clock_in": entry["clock_in"],
        "job_code": entry["job_code"],
        "job_name": entry["job_code"],  # optional (replace if you join items table)
    }
def format_row(row):
    data = dict(row)

    local_tz = ZoneInfo("America/Los_Angeles")  # 🔥 your timezone

    if data.get("clock_in"):
        data["clock_in"] = data["clock_in"].astimezone(local_tz).isoformat()

    if data.get("clock_out"):
        data["clock_out"] = data["clock_out"].astimezone(local_tz).isoformat()

    return data
@app.get("/time/{user_id}")
def get_time_entries(user_id: int):
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT * FROM time_entries
                WHERE user_id = %s
                ORDER BY clock_in DESC, id DESC
            """, (user_id,))

            results = cursor.fetchall()

        return [format_row(row) for row in results]

    except Exception as e:
        print("🔥 ERROR IN /time:", e)
        raise HTTPException(500, str(e))

@app.get("/users/{user_id}")
def get_user(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT id, first_name, last_name, email, phone, username, role,
                email_notifications, sms_notifications
            FROM users
            WHERE id = %s
        """, (user_id,))

        user = cursor.fetchone()


    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return dict(user)

@app.put("/time/{entry_id}")
def update_entry(entry_id: int, data: dict):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            UPDATE time_entries
            SET clock_in = %s, clock_out = %s, job_code = %s, item_id = %s
            WHERE id = %s
        """, (
            data.get("clock_in"),
            data.get("clock_out"),
            data.get("job_code"),
            data.get("item_id"),
            entry_id
        ))

        conn.commit()

    return {"message": "Updated"}

@app.put("/users/{user_id}/settings")
def update_settings(user_id: int, data: dict):
    try:
        print("🔥 HIT SETTINGS ENDPOINT", user_id, data)

        email_val = data.get("email_notifications", False)
        sms_val = data.get("sms_notifications", False)

        # ✅ Force boolean safely
        email_val = True if email_val in [True, "true", 1, "1"] else False
        sms_val = True if sms_val in [True, "true", 1, "1"] else False

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET email_notifications = %s,
                    sms_notifications = %s
                WHERE id = %s
            """, (
                email_val,
                sms_val,
                user_id
            ))

            conn.commit()

        return {"message": "Settings updated"}

    except Exception as e:
        print("🔥 SETTINGS ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.put("/users/{user_id}/role")
def update_role(user_id: int, data: RoleUpdate):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "UPDATE users SET role = %s WHERE id = %s",
            (data.role, user_id)
        )

        conn.commit()

    return {"message": "Role updated"}

@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()

    return {"message": "User deleted"}

@app.get("/users")
def get_users():
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT id, first_name, last_name, email, phone, username, role,
                email_notifications, sms_notifications
            FROM users
        """)

        users = cursor.fetchall()

    return [dict(u) for u in users]
      
@app.post("/users")
def create_user(user: UserCreate):
    email = user.email.lower()
    if "@" not in email:
        raise HTTPException(
            status_code=400,
            detail="Invalid email"
        )
    # ✅ DOMAIN VALIDATION (put it HERE)
    domain = user.email.lower().split("@")[-1]
    if domain != "pacificblueengineering.com":
        raise HTTPException(
            status_code=404,
            detail=""
        )
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        hashed_password = hash_password(user.password)

        formatted_phone = format_phone(user.phone)  # 🔥 ADD THIS

        base_username = user.email.split("@")[0]
        generated_username = base_username

        count = 1
        while True:
            cursor.execute("SELECT * FROM users WHERE username = %s", (generated_username,))
            if not cursor.fetchone():
                break
            generated_username = f"{base_username}{count}"
            count += 1

        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, phone, username, password_hash, role)
            VALUES (%s, %s, %s, %s, %s, %s, 'user')
        """, (
            user.first_name,
            user.last_name,
            user.email,
            formatted_phone,  # 🔥 USE FORMATTED
            generated_username,
            hashed_password
        ))

        conn.commit()

    return {"message": "User created", "username": generated_username}

@app.get("/tickets/history")
def get_ticket_history():
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "SELECT * FROM tickets WHERE status != 'pending' ORDER BY id DESC"
        )

        results = cursor.fetchall()

    return [dict(row) for row in results]

@app.get("/tickets")
def get_pending_tickets():
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "SELECT * FROM tickets WHERE status = 'pending' ORDER BY id DESC"
        )

        results = cursor.fetchall()

    return [dict(row) for row in results]

@app.post("/tickets")
def create_ticket(data: TicketRequest):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "INSERT INTO tickets (description, username) VALUES (%s, %s)",
            (data.description, data.username)
        )

        conn.commit()

        # 🔥 GET ADMINS WHO WANT NOTIFICATIONS
        cursor.execute("""
            SELECT email, phone, email_notifications, sms_notifications
            FROM users
            WHERE role = 'admin'
        """)

        admins = cursor.fetchall()

        for admin in admins:
            email = admin["email"]
            phone = admin["phone"]
            email_on = admin["email_notifications"]
            sms_on = admin["sms_notifications"]

            if email_on:
                send_email(
                    email,
                    "New Ticket Submitted",
                    f"A new ticket was submitted by {data.username}"
                )

            if sms_on:
                send_sms(phone, "New ticket submitted")

    return {"message": "Ticket submitted"}

@app.post("/tickets/{ticket_id}/approve")
def approve_ticket(ticket_id: int, username: str):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 🔍 get ticket owner
        cursor.execute("SELECT username FROM tickets WHERE id = %s", (ticket_id,))
        ticket = cursor.fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket_username = ticket["username"]

        # 🔄 update ticket
        cursor.execute("""
            UPDATE tickets
            SET status = 'approved',
                approved_at = CURRENT_TIMESTAMP,
                approved_by = %s
            WHERE id = %s
        """, (username, ticket_id))

        conn.commit()

        # 🔍 get user info
        cursor.execute("""
            SELECT email, phone, email_notifications, sms_notifications
            FROM users
            WHERE username = %s
        """, (ticket_username,))

        user = cursor.fetchone()

        if user:
            if user["email_notifications"]:
                send_email(
                    user["email"],
                    "Ticket Approved",
                    "Your ticket has been approved"
                )

            if user["sms_notifications"]:
                send_sms(user["phone"], "Your ticket was approved")


    return {"message": "Ticket approved"}

@app.post("/tickets/{ticket_id}/reject")
def reject_ticket(ticket_id: int, username: str):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT username FROM tickets WHERE id = %s", (ticket_id,))
        ticket = cursor.fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket_username = ticket["username"]

        cursor.execute("""
            UPDATE tickets
            SET status = 'rejected',
                rejected_at = CURRENT_TIMESTAMP,
                rejected_by = %s
            WHERE id = %s
        """, (username, ticket_id))

        conn.commit()

        cursor.execute("""
            SELECT email, phone, email_notifications, sms_notifications
            FROM users
            WHERE username = %s
        """, (ticket_username,))

        user = cursor.fetchone()

        if user:
            if user["email_notifications"]:
                send_email(
                    user["email"],
                    "Ticket Rejected",
                    "Your ticket has been rejected"
                )

            if user["sms_notifications"]:
                send_sms(user["phone"], "Your ticket was rejected")


    return {"message": "Ticket rejected"}

@app.post("/items")
def create_item(data: ItemRequest):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "INSERT INTO items (name, code) VALUES (%s, %s)",
            (data.name, data.code)
        )

        conn.commit()

    return {"message": "Item created"}


@app.post("/login")
def login(data: LoginRequest):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "SELECT * FROM users WHERE username = %s",
            (data.username,)
        )

        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username")

    user = dict(user)

    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid password")

    return {
    "message": "Login successful",
    "id": user["id"],   # ✅ MUST EXIST
    "username": user["username"],
    "role": user["role"]
}
@app.get("/search")
def search_items(q: str):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        words = q.split()
        query = " AND ".join(["name ILIKE %s" for _ in words])
        params = [f"%{word}%" for word in words]

        cursor.execute(f"""
            SELECT id, name, code FROM items
            WHERE {query}
            LIMIT 20
        """, params)

        results = cursor.fetchall()

    return [dict(row) for row in results]
