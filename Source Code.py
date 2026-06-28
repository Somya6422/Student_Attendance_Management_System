import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import hashlib
from datetime import date
from typing import List

import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import threading
import uuid

# --- TRY IMPORTING TKCALENDAR (Date Picker Support) ---
try:
    from tkcalendar import DateEntry
    TKCALENDAR_AVAILABLE = True
except Exception:
    TKCALENDAR_AVAILABLE = False

# --- TRY IMPORTING QRCODE (Dynamic Web QR Support) ---
try:
    import qrcode
    from PIL import Image, ImageTk
    QR_AVAILABLE = True
except Exception:
    QR_AVAILABLE = False

# --- CONFIGURATION ---
import os
import sys

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "attendance.db")
MIN_ATTENDANCE_THRESHOLD = 75.0

# --- LOCAL HTTP SERVER FOR QR ATTENDANCE ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

class AttendanceHandler(BaseHTTPRequestHandler):
    active_token = None
    
    def send_html(self, content):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
        
    def send_error_page(self, msg):
        html = f"<html><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{{font-family:sans-serif;text-align:center;padding:40px; background:#f4f7f6;}} h2{{color:#e74c3c;}}</style></head><body><h2>Session Expired or Invalid</h2><p>{msg}</p></body></html>"
        self.send_html(html)
        
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        session = query.get('session', [''])[0]
        
        if not AttendanceHandler.active_token or session != AttendanceHandler.active_token:
            self.send_error_page("The QR code is no longer valid. Please ask your teacher to generate a new one.")
            return
            
        class_name = query.get('class', [''])[0]
        date_str = query.get('date', [''])[0]
        
        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Attendance Portal</title>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background: #f4f7f6; padding: 20px; }}
                .card {{ max-width: 400px; margin: auto; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                h2 {{ text-align: center; color: #2c3e50; margin-top: 0; }}
                .info {{ background: #e8f4f8; padding: 12px; border-radius: 6px; margin-bottom: 20px; color: #31708f; font-size: 14px; text-align: center;}}
                label {{ font-weight: bold; color: #333; }}
                input {{ width: 100%; padding: 12px; margin: 8px 0 20px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 16px; }}
                button {{ background: #2ecc71; color: white; padding: 14px; border: none; border-radius: 4px; width: 100%; font-size: 16px; font-weight: bold; cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Mark Attendance</h2>
                <div class="info">
                    <strong>Class:</strong> {class_name}<br>
                    <strong>Date:</strong> {date_str}
                </div>
                <form method="POST">
                    <input type="hidden" name="session" value="{session}">
                    <input type="hidden" name="class" value="{class_name}">
                    <input type="hidden" name="date" value="{date_str}">
                    <label>Student ID:</label>
                    <input type="text" name="student_id" placeholder="Enter your official Student ID" required>
                    <label>Full Name:</label>
                    <input type="text" name="name" placeholder="Enter your full name" required>
                    <button type="submit">Submit Present</button>
                </form>
            </div>
        </body>
        </html>
        """
        self.send_html(html)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(length).decode('utf-8')
        fields = urllib.parse.parse_qs(post_data)
        
        session = fields.get('session', [''])[0]
        if not AttendanceHandler.active_token or session != AttendanceHandler.active_token:
            self.send_error_page("The QR code session has expired. You cannot submit attendance anymore.")
            return
            
        class_name = fields.get('class', [''])[0]
        date_str = fields.get('date', [''])[0]
        student_id = fields.get('student_id', [''])[0]
        
        local_manager = AttendanceManager()
        success, msg = local_manager.mark_single_student_present(class_name, date_str, student_id)
        
        color = "#2ecc71" if success else "#e74c3c"
        title = "Success!" if success else "Error!"
        
        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background: #f4f7f6; padding: 20px; display: flex; justify-content: center; align-items: center; height: 80vh; }}
                .card {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); text-align: center; max-width: 400px; width: 100%; }}
                h1 {{ color: {color}; margin-top: 0; }}
                p {{ color: #555; font-size: 16px; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>{title}</h1>
                <p>{msg}</p>
                <p style="margin-top:30px; font-size:14px; color:#999;">You may now safely close this tab on your device.</p>
            </div>
        </body>
        </html>
        """
        self.send_html(html)
        
    def log_message(self, format, *args):
        pass 

def start_background_server():
    server = HTTPServer(('0.0.0.0', 0), AttendanceHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return port

# --- BACKEND: DATABASE & LOGIC ---
class AttendanceManager:
    def __init__(self, db_name: str = DB_FILE):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (role TEXT UNIQUE, pass_hash TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS students (class_name TEXT, student_id TEXT, name TEXT, UNIQUE(class_name, student_id))''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (class_name TEXT, student_id TEXT, date TEXT, status TEXT, UNIQUE(class_name, student_id, date))''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS notifications (class_name TEXT, message TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS student_alerts (student_id TEXT, class_name TEXT, message TEXT)''')
        
        self._create_user("Teacher", "teacher123")
        self._create_user("Principal", "admin123")
        self.conn.commit()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _create_user(self, role: str, default_pass: str):
        self.cursor.execute("INSERT OR IGNORE INTO users (role, pass_hash) VALUES (?, ?)", (role, self._hash_password(default_pass)))

    def verify_login(self, role: str, password: str) -> bool:
        self.cursor.execute("SELECT * FROM users WHERE role=? AND pass_hash=?", (role, self._hash_password(password)))
        return self.cursor.fetchone() is not None
        
    def verify_student(self, class_name: str, student_id: str, name: str) -> bool:
        self.cursor.execute("SELECT * FROM students WHERE class_name=? AND student_id=? AND name=?", (class_name, student_id, name))
        return self.cursor.fetchone() is not None

    def add_student(self, class_name: str, student_id: str, name: str):
        try:
            self.cursor.execute("INSERT INTO students (class_name, student_id, name) VALUES (?, ?, ?)", (class_name, student_id, name))
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("Student ID already exists in this class.")

    def delete_student(self, class_name: str, student_id: str) -> bool:
        self.cursor.execute("DELETE FROM students WHERE class_name=? AND student_id=?", (class_name, student_id))
        self.cursor.execute("DELETE FROM attendance WHERE class_name=? AND student_id=?", (class_name, student_id))
        self.cursor.execute("DELETE FROM student_alerts WHERE class_name=? AND student_id=?", (class_name, student_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def delete_class(self, class_name: str) -> bool:
        self.cursor.execute("DELETE FROM students WHERE class_name=?", (class_name,))
        self.cursor.execute("DELETE FROM attendance WHERE class_name=?", (class_name,))
        self.cursor.execute("DELETE FROM notifications WHERE class_name=?", (class_name,))
        self.cursor.execute("DELETE FROM student_alerts WHERE class_name=?", (class_name,))
        self.conn.commit()
        return True

    def get_classes(self) -> List[str]:
        self.cursor.execute("SELECT DISTINCT class_name FROM students")
        return [row[0] for row in self.cursor.fetchall()]

    def get_students(self, class_name: str) -> List[tuple]:
        self.cursor.execute("SELECT student_id, name FROM students WHERE class_name=?", (class_name,))
        return self.cursor.fetchall()

    def save_attendance(self, class_name: str, date_str: str, updates: dict):
        for s_id, status in updates.items():
            self.cursor.execute('''INSERT OR REPLACE INTO attendance (class_name, student_id, date, status) VALUES (?, ?, ?, ?)''', (class_name, s_id, date_str, status))
        self.conn.commit()

    def mark_single_student_present(self, class_name: str, date_str: str, student_id: str) -> tuple:
        self.cursor.execute("SELECT name FROM students WHERE class_name=? AND student_id=?", (class_name, student_id))
        result = self.cursor.fetchone()
        if not result:
            return False, f"Student ID '{student_id}' is not registered in '{class_name}'."
        self.cursor.execute('''INSERT OR REPLACE INTO attendance (class_name, student_id, date, status) VALUES (?, ?, ?, ?)''', (class_name, student_id, date_str, "Present"))
        self.conn.commit()
        return True, f"Attendance marked Present for {result[0]}."

    def ensure_roster_initialized(self, class_name: str, date_str: str):
        if not self.has_record_for_date(class_name, date_str):
            students = self.get_students(class_name)
            updates = {s[0]: "Absent" for s in students}
            self.save_attendance(class_name, date_str, updates)

    def get_attendance_for_date(self, class_name: str, date_str: str) -> dict:
        self.cursor.execute("SELECT student_id, status FROM attendance WHERE class_name=? AND date=?", (class_name, date_str))
        return {row[0]: row[1] for row in self.cursor.fetchall()}

    def has_record_for_date(self, class_name: str, date_str: str) -> bool:
        self.cursor.execute("SELECT 1 FROM attendance WHERE class_name=? AND date=? LIMIT 1", (class_name, date_str))
        return self.cursor.fetchone() is not None

    def add_notification(self, class_name: str, message: str):
        self.cursor.execute("INSERT INTO notifications (class_name, message) VALUES (?, ?)", (class_name, message))
        self.conn.commit()

    def clear_notifications(self):
        self.cursor.execute("DELETE FROM notifications")
        self.conn.commit()

    def get_notifications(self) -> List[str]:
        self.cursor.execute("SELECT class_name, message FROM notifications")
        return [f"[{row[0]}] - {row[1]}" for row in self.cursor.fetchall()]
        
    def add_student_alert(self, class_name: str, student_id: str, message: str):
        self.cursor.execute("INSERT INTO student_alerts (student_id, class_name, message) VALUES (?, ?, ?)", (student_id, class_name, message))
        self.conn.commit()
        
    def get_student_alerts(self, class_name: str, student_id: str) -> List[str]:
        self.cursor.execute("SELECT message FROM student_alerts WHERE class_name=? AND student_id=?", (class_name, student_id))
        return [row[0] for row in self.cursor.fetchall()]

    def get_student_stats(self, class_name: str, specific_student_id: str = None) -> dict:
        stats = {}
        if specific_student_id:
            self.cursor.execute("SELECT student_id, name FROM students WHERE class_name=? AND student_id=?", (class_name, specific_student_id))
        else:
            self.cursor.execute("SELECT student_id, name FROM students WHERE class_name=?", (class_name,))
            
        students = self.cursor.fetchall()
        for s_id, name in students:
            self.cursor.execute("SELECT COUNT(*) FROM attendance WHERE class_name=? AND student_id=?", (class_name, s_id))
            total = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT COUNT(*) FROM attendance WHERE class_name=? AND student_id=? AND status='Present'", (class_name, s_id))
            attended = self.cursor.fetchone()[0]
            pct = (attended / total * 100) if total > 0 else 0.0
            stats[s_id] = {"name": name, "attended": attended, "total": total, "pct": pct}
        return stats

    def dispatch_portal_warnings(self, class_name: str, stats: dict) -> int:
        alerts_sent = 0
        for s_id, record in stats.items():
            if record['pct'] < MIN_ATTENDANCE_THRESHOLD and record['total'] > 0:
                alert_msg = f"SYSTEM WARNING: Your attendance has dropped to {record['pct']:.1f}%. Immediate improvement required."
                self.add_student_alert(class_name, s_id, alert_msg)
                alerts_sent += 1
        return alerts_sent

# --- FRONTEND: TKINTER GUI ---
class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("School Attendance System Pro")
        self.root.geometry("1100x750")
        self.manager = AttendanceManager()
        self.current_student = {}
        
        self.server_port = start_background_server()

        style = ttk.Style()
        if 'clam' in style.theme_names(): style.theme_use('clam')
        
        style.configure("Banner.TLabel", font=('Segoe UI', 24, 'bold'), foreground="#2c3e50")
        style.configure("Header.TLabel", font=('Segoe UI', 18, 'bold'))
        style.configure("Instruct.TLabel", font=('Segoe UI', 10, 'italic'), foreground="#555")
        
        style.configure("TechTitle.TLabel", font=('Consolas', 24, 'bold'), foreground="#2ecc71", background="#1e1e1e")
        style.configure("TechSub.TLabel", font=('Consolas', 13), foreground="#d4d4d4", background="#1e1e1e")
        style.configure("TechFrame.TFrame", background="#1e1e1e")
        style.configure("Tech.TButton", font=('Consolas', 14, 'bold'), padding=15, foreground="#2c3e50")
        style.configure("Code.TLabel", font=('Consolas', 13), foreground="#569cd6", background="#1e1e1e")

        self.banner_frame = ttk.Frame(self.root, padding=15)
        self.banner_frame.pack(fill='x', side='top')
        ttk.Label(self.banner_frame, text="TEN Internship - Python Development", style="Banner.TLabel", anchor='center').pack(fill='x')
        ttk.Separator(self.root, orient='horizontal').pack(fill='x')

        self.content_frame = ttk.Frame(self.root)
        self.content_frame.pack(fill='both', expand=True)
        self.show_role_selection()

    def clear_container(self):
        for widget in self.content_frame.winfo_children(): widget.destroy()

    def animate_typing(self, widget, text, idx=0):
        if idx < len(text):
            widget.config(text=text[:idx+1] + "█")
            self.root.after(35, self.animate_typing, widget, text, idx+1)
        else:
            widget.config(text=text)

    # --- MAIN LOGIN SCREEN ---
    def show_role_selection(self):
        self.clear_container()
        term_frame = ttk.Frame(self.content_frame, style="TechFrame.TFrame")
        term_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=0.85, relheight=0.8)
        
        inner = ttk.Frame(term_frame, style="TechFrame.TFrame")
        inner.place(relx=0.5, rely=0.5, anchor='center')
        
        lbl_title = ttk.Label(inner, text="", style="TechTitle.TLabel")
        lbl_title.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        self.animate_typing(lbl_title, ">>> import ten_internship.auth as sys_auth")
        
        ttk.Label(inner, text="# Select environment to initialize the session:", style="TechSub.TLabel").grid(row=1, column=0, columnspan=3, pady=(0, 50))
        
        ttk.Label(inner, text="def auth_student():", style="Code.TLabel").grid(row=2, column=0, padx=20)
        ttk.Button(inner, text="[ 👨‍🎓 run(Student) ]", command=self.show_student_login, style="Tech.TButton", width=18).grid(row=3, column=0, padx=20, pady=10)
        
        ttk.Label(inner, text="def auth_teacher():", style="Code.TLabel").grid(row=2, column=1, padx=20)
        ttk.Button(inner, text="[ 👨‍🏫 run(Teacher) ]", command=lambda: self.show_login("Teacher"), style="Tech.TButton", width=18).grid(row=3, column=1, padx=20, pady=10)
        
        ttk.Label(inner, text="def auth_admin():", style="Code.TLabel").grid(row=2, column=2, padx=20)
        ttk.Button(inner, text="[ 👔 run(Principal) ]", command=lambda: self.show_login("Principal"), style="Tech.TButton", width=18).grid(row=3, column=2, padx=20, pady=10)

    def show_login(self, role):
        self.clear_container()
        term_frame = ttk.Frame(self.content_frame, style="TechFrame.TFrame")
        term_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=0.85, relheight=0.8)
        
        inner = ttk.Frame(term_frame, style="TechFrame.TFrame")
        inner.place(relx=0.5, rely=0.5, anchor='center')
        
        ttk.Label(inner, text=f">>> sys_auth.connect(role='{role}')", style="TechTitle.TLabel").pack(pady=20)
        ttk.Label(inner, text="# Enter cryptographic passkey:", style="TechSub.TLabel").pack(pady=10)
        
        ent_pass = tk.Entry(inner, show="*", width=35, font=('Consolas', 16), bg="#2b2b2b", fg="#ffffff", insertbackground="white", justify='center')
        ent_pass.pack(pady=20, ipady=6)
        ent_pass.focus()

        def verify_login(event=None):
            if self.manager.verify_login(role, ent_pass.get()):
                self.build_teacher_ui() if role == "Teacher" else self.build_principal_ui()
            else:
                messagebox.showerror("Access Denied", "Exception: AuthError - Invalid credentials.")
                ent_pass.delete(0, tk.END)

        ttk.Button(inner, text="execute()", command=verify_login, style="Tech.TButton", width=15).pack(pady=15)
        ttk.Button(inner, text="sys.exit()", command=self.show_role_selection, style="Tech.TButton", width=15).pack(pady=5)
        self.root.bind('<Return>', verify_login) 

    def show_student_login(self):
        self.clear_container()
        term_frame = ttk.Frame(self.content_frame, style="TechFrame.TFrame")
        term_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=0.85, relheight=0.8)
        
        inner = ttk.Frame(term_frame, style="TechFrame.TFrame")
        inner.place(relx=0.5, rely=0.5, anchor='center')
        
        ttk.Label(inner, text=">>> sys_auth.connect(role='Student')", style="TechTitle.TLabel").grid(row=0, column=0, columnspan=2, pady=(0, 40))
        
        ttk.Label(inner, text="class_name =", style="Code.TLabel").grid(row=1, column=0, pady=15, sticky='e', padx=10)
        combo_class = ttk.Combobox(inner, values=self.manager.get_classes(), state='readonly', width=30, font=('Consolas', 14))
        combo_class.grid(row=1, column=1, pady=15, sticky='w')
        
        ttk.Label(inner, text="student_id =", style="Code.TLabel").grid(row=2, column=0, pady=15, sticky='e', padx=10)
        ent_id = tk.Entry(inner, width=31, font=('Consolas', 14), bg="#2b2b2b", fg="white", insertbackground="white")
        ent_id.grid(row=2, column=1, pady=15, sticky='w')
        
        ttk.Label(inner, text="full_name =", style="Code.TLabel").grid(row=3, column=0, pady=15, sticky='e', padx=10)
        ent_name = tk.Entry(inner, width=31, font=('Consolas', 14), bg="#2b2b2b", fg="white", insertbackground="white")
        ent_name.grid(row=3, column=1, pady=15, sticky='w')

        def verify_student_auth(event=None):
            cls = combo_class.get()
            s_id = ent_id.get().strip()
            name = ent_name.get().strip()
            
            if not cls or not s_id or not name:
                messagebox.showwarning("Incomplete", "Missing parameters for initialization.")
                return
                
            if self.manager.verify_student(cls, s_id, name):
                self.current_student = {"class": cls, "id": s_id, "name": name}
                self.build_student_ui()
            else:
                messagebox.showerror("Access Denied", "Exception: AuthError - Student not found in database.")
                
        btn_frame = ttk.Frame(inner, style="TechFrame.TFrame")
        btn_frame.grid(row=4, column=0, columnspan=2, pady=40)
        
        ttk.Button(btn_frame, text="sys.exit()", command=self.show_role_selection, style="Tech.TButton", width=15).pack(side='left', padx=15)
        ttk.Button(btn_frame, text="login()", command=verify_student_auth, style="Tech.TButton", width=15).pack(side='left', padx=15)
        self.root.bind('<Return>', verify_student_auth)

    # --- STUDENT UI ---
    def build_student_ui(self):
        self.root.unbind('<Return>')
        self.clear_container()
        
        top_bar = ttk.Frame(self.content_frame)
        top_bar.pack(fill='x', padx=10, pady=5)
        ttk.Label(top_bar, text=f"Welcome, {self.current_student['name']} ({self.current_student['class']})", style="Header.TLabel").pack(side='left')
        ttk.Button(top_bar, text="Log Out", command=self.show_role_selection).pack(side='right')

        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        tab_dash = ttk.Frame(self.notebook)
        tab_req = ttk.Frame(self.notebook)
        self.notebook.add(tab_dash, text="📊 My Attendance Report")
        self.notebook.add(tab_req, text="✉️ Send Request Message")

        stats = self.manager.get_student_stats(self.current_student['class'], self.current_student['id'])
        if self.current_student['id'] in stats:
            my_stats = stats[self.current_student['id']]
        else:
            my_stats = {"attended": 0, "total": 0, "pct": 0.0}
            
        f_stats = ttk.LabelFrame(tab_dash, text=" My Current Statistics ", padding=20)
        f_stats.pack(fill='x', padx=20, pady=20)
        
        ttk.Label(f_stats, text=f"Total Classes Held: {my_stats['total']}", font=('Segoe UI', 14)).grid(row=0, column=0, padx=40, pady=10)
        ttk.Label(f_stats, text=f"Classes Attended: {my_stats['attended']}", font=('Segoe UI', 14)).grid(row=0, column=1, padx=40, pady=10)
        
        pct_color = "red" if my_stats['pct'] < MIN_ATTENDANCE_THRESHOLD else "green"
        ttk.Label(f_stats, text=f"Attendance Rate: {my_stats['pct']:.1f}%", font=('Segoe UI', 14, 'bold'), foreground=pct_color).grid(row=0, column=2, padx=40, pady=10)

        f_alerts = ttk.LabelFrame(tab_dash, text=" Important Admin Alerts ", padding=15)
        f_alerts.pack(fill='both', expand=True, padx=20, pady=10)
        
        list_alerts = tk.Listbox(f_alerts, font=('Segoe UI', 11), fg="red")
        list_alerts.pack(fill='both', expand=True, pady=10)
        
        my_alerts = self.manager.get_student_alerts(self.current_student['class'], self.current_student['id'])
        if not my_alerts:
            list_alerts.insert(tk.END, "✅ You have no warnings or alerts. Keep up the good work!")
            list_alerts.configure(fg="green")
        else:
            for alert in my_alerts:
                list_alerts.insert(tk.END, f"⚠️ {alert}")

        inst_req = ttk.LabelFrame(tab_req, text=" Instructions ", padding=10)
        inst_req.pack(fill='x', padx=20, pady=10)
        ttk.Label(inst_req, text="If you believe your attendance is recorded incorrectly, or if you need to submit a leave application, write a message below. This will be sent directly to your Teacher's alert dashboard.", style="Instruct.TLabel", wraplength=900).pack(anchor='w')

        f_msg = ttk.Frame(tab_req)
        f_msg.pack(pady=20)
        ttk.Label(f_msg, text="Your Message/Request:").grid(row=0, column=0, sticky='nw')
        txt_msg = tk.Text(f_msg, height=8, width=50, font=('Segoe UI', 11))
        txt_msg.grid(row=0, column=1, padx=10)
        
        def dispatch_student_request():
            msg_content = txt_msg.get("1.0", tk.END).strip()
            if not msg_content: return
            final_msg = f"[From Student: {self.current_student['name']} ({self.current_student['id']})] - {msg_content}"
            self.manager.add_notification(self.current_student['class'], final_msg)
            messagebox.showinfo("Success", "Your request has been sent to the administration.")
            txt_msg.delete("1.0", tk.END)

        ttk.Button(f_msg, text="Dispatch Message", command=dispatch_student_request).grid(row=1, column=1, pady=20, sticky='w')

    # --- TEACHER UI ---
    def build_teacher_ui(self):
        self.root.unbind('<Return>')
        self.clear_container()
        top_bar = ttk.Frame(self.content_frame)
        top_bar.pack(fill='x', padx=10, pady=5)
        ttk.Label(top_bar, text="Teacher Dashboard", style="Header.TLabel").pack(side='left')
        ttk.Button(top_bar, text="Log Out", command=self.show_role_selection).pack(side='right')

        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        tab_dash = ttk.Frame(self.notebook)
        tab_roster = ttk.Frame(self.notebook)
        tab_mark = ttk.Frame(self.notebook)
        self.notebook.add(tab_dash, text="🔔 Alerts")
        self.notebook.add(tab_roster, text="👥 Add Students")
        self.notebook.add(tab_mark, text="✅ Mark / Edit Attendance")

        inst_dash = ttk.LabelFrame(tab_dash, text=" Instructions ", padding=10)
        inst_dash.pack(fill='x', padx=20, pady=10)
        ttk.Label(inst_dash, text="Welcome! This tab shows direct communication from the Principal and requests sent by Students regarding attendance adjustments.", style="Instruct.TLabel", wraplength=900).pack(anchor='w')
        
        list_frame = ttk.Frame(tab_dash)
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        self.list_notif = tk.Listbox(list_frame, font=('Segoe UI', 11), fg="red")
        self.list_notif.pack(fill='both', expand=True, pady=10)
        ttk.Button(list_frame, text="Clear Notifications", command=self.t_clear_notifs).pack(pady=5)
        for msg in self.manager.get_notifications(): self.list_notif.insert(tk.END, msg)

        inst_add = ttk.LabelFrame(tab_roster, text=" Instructions ", padding=10)
        inst_add.pack(fill='x', padx=20, pady=10)
        ttk.Label(inst_add, text="Use this form to build your class roster. You must register a student here before you can mark their attendance or generate QR codes for them.", style="Instruct.TLabel", wraplength=900).pack(anchor='w')
        
        f_add = ttk.LabelFrame(tab_roster, text=" Student Details ", padding=30)
        f_add.pack(fill='both', expand=True, padx=20, pady=10)
        ttk.Label(f_add, text="Class/Subject:").grid(row=0, column=0, pady=10, sticky='e')
        self.t_ent_class = ttk.Entry(f_add, width=35)
        self.t_ent_class.grid(row=0, column=1, pady=10, padx=10)
        ttk.Label(f_add, text="Student ID:").grid(row=1, column=0, pady=10, sticky='e')
        self.t_ent_id = ttk.Entry(f_add, width=35)
        self.t_ent_id.grid(row=1, column=1, pady=10, padx=10)
        ttk.Label(f_add, text="Student Name:").grid(row=2, column=0, pady=10, sticky='e')
        self.t_ent_name = ttk.Entry(f_add, width=35)
        self.t_ent_name.grid(row=2, column=1, pady=10, padx=10)
        ttk.Button(f_add, text="Register Student", command=self.t_add_student).grid(row=3, column=1, pady=25, sticky='w')

        inst_mark = ttk.LabelFrame(tab_mark, text=" Instructions ", padding=10)
        inst_mark.pack(fill='x', padx=20, pady=10)
        ttk.Label(inst_mark, text="Step 1: Select your Class and Date.\nStep 2: Click 'Generate Attendance QR' to show the dynamic QR code to students, OR click 'Load Roster' to manually mark them. All loaded students default to ABSENT.", style="Instruct.TLabel", wraplength=900).pack(anchor='w')

        f_mark_ctrl = ttk.LabelFrame(tab_mark, text=" Class Controls ", padding=15)
        f_mark_ctrl.pack(fill='x', pady=5, padx=20)
        self.t_combo_class = ttk.Combobox(f_mark_ctrl, values=self.manager.get_classes(), state='readonly', width=20)
        self.t_combo_class.pack(side='left', padx=10)
        ttk.Label(f_mark_ctrl, text="Date:").pack(side='left')
        
        if TKCALENDAR_AVAILABLE:
            self.t_ent_date = DateEntry(f_mark_ctrl, width=12, background='#2c3e50', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        else:
            self.t_ent_date = ttk.Entry(f_mark_ctrl, width=15)
            self.t_ent_date.insert(0, str(date.today()))
            
        self.t_ent_date.pack(side='left', padx=10)
        ttk.Button(f_mark_ctrl, text="Load Roster (Manual)", command=self.t_load_roster).pack(side='left', padx=10)
        ttk.Button(f_mark_ctrl, text="Generate Attendance QR (Auto)", command=self.t_generate_qr).pack(side='left', padx=10)

        f_mark_tbl = ttk.LabelFrame(tab_mark, text=" Roster / Data ", padding=15)
        f_mark_tbl.pack(fill='both', expand=True, padx=20, pady=10)
        self.t_tree = ttk.Treeview(f_mark_tbl, columns=("ID", "Name", "Status"), show='headings', height=10)
        self.t_tree.heading("ID", text="Student ID")
        self.t_tree.heading("Name", text="Student Name")
        self.t_tree.heading("Status", text="Status (Click to Toggle)")
        self.t_tree.pack(fill='both', expand=True)
        self.t_tree.bind('<ButtonRelease-1>', self.t_toggle_status)
        ttk.Button(f_mark_tbl, text="Submit Final Attendance", command=self.t_submit_attendance).pack(pady=10)

    # --- PRINCIPAL UI ---
    def build_principal_ui(self):
        self.root.unbind('<Return>')
        self.clear_container()
        top_bar = ttk.Frame(self.content_frame)
        top_bar.pack(fill='x', padx=10, pady=5)
        ttk.Label(top_bar, text="Principal Analytics", style="Header.TLabel").pack(side='left')
        ttk.Button(top_bar, text="Log Out", command=self.show_role_selection).pack(side='right')

        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        tab_dash = ttk.Frame(self.notebook)
        tab_report = ttk.Frame(self.notebook)
        tab_req = ttk.Frame(self.notebook)
        tab_manage = ttk.Frame(self.notebook)
        
        self.notebook.add(tab_dash, text="📈 School Metrics")
        self.notebook.add(tab_report, text="📋 Reports & Export")
        self.notebook.add(tab_req, text="✉️ Teacher Requests")
        self.notebook.add(tab_manage, text="🗑️ Manage Data")

        inst_prin = ttk.LabelFrame(tab_dash, text=" Instructions ", padding=10)
        inst_prin.pack(fill='x', padx=20, pady=10)
        ttk.Label(inst_prin, text="Welcome Principal. Below is the Pie Chart representing Present vs Absent metrics. You can enter a specific Date below to view attendance for that exact day, or clear it to view All-Time aggregate metrics.", style="Instruct.TLabel", wraplength=900).pack(anchor='w')
        
        frame_chart = ttk.LabelFrame(tab_dash, text=" Attendance Metrics ", padding=15)
        frame_chart.pack(fill='both', expand=True, padx=20, pady=10)
        
        ctrl_chart = ttk.Frame(frame_chart)
        ctrl_chart.pack(fill='x', pady=5)
        ttk.Label(ctrl_chart, text="Filter by Date (YYYY-MM-DD):").pack(side='left', padx=5)
        
        if TKCALENDAR_AVAILABLE:
            self.p_chart_date = DateEntry(ctrl_chart, width=12, background='#2c3e50', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        else:
            self.p_chart_date = ttk.Entry(ctrl_chart, width=15)
            self.p_chart_date.insert(0, str(date.today()))
            
        self.p_chart_date.pack(side='left', padx=5)
        ttk.Button(ctrl_chart, text="Refresh Chart", command=self.p_draw_pie_chart).pack(side='left', padx=5)
        
        def set_all_time():
            self.p_chart_date.delete(0, tk.END)
            self.p_draw_pie_chart()
            
        ttk.Button(ctrl_chart, text="View All Time", command=set_all_time).pack(side='left', padx=15)

        self.canvas = tk.Canvas(frame_chart, bg="white")
        self.canvas.pack(fill='both', expand=True, padx=10, pady=10)
        self.p_draw_pie_chart()

        inst_rep = ttk.LabelFrame(tab_report, text=" Instructions ", padding=10)
        inst_rep.pack(fill='x', padx=20, pady=10)
        ttk.Label(inst_rep, text="Select a class to view its detailed attendance breakdown. You can dispatch automated portal alerts to students dipping below 75%. Document exports are disabled in favor of live dashboards.", style="Instruct.TLabel", wraplength=900).pack(anchor='w')

        f_rep_ctrl = ttk.Frame(tab_report)
        f_rep_ctrl.pack(fill='x', pady=5, padx=20)
        self.p_combo_class = ttk.Combobox(f_rep_ctrl, values=self.manager.get_classes(), state='readonly')
        self.p_combo_class.pack(side='left', padx=10)
        ttk.Button(f_rep_ctrl, text="Load Data", command=self.p_view_report).pack(side='left', padx=5)
        ttk.Button(f_rep_ctrl, text="Dispatch Portal Warnings (< 75%)", command=self.p_portal_warnings).pack(side='left', padx=5)

        self.p_tree = ttk.Treeview(tab_report, columns=("Class", "ID", "Name", "Attended", "Total", "Pct", "Flag"), show='headings')
        for c in ("Class", "ID", "Name", "Attended", "Total", "Pct", "Flag"): self.p_tree.heading(c, text=c)
        
        # Enhanced coloring tags for the treeview visually
        self.p_tree.tag_configure('risk', foreground='#c0392b', background='#fadbd8')
        self.p_tree.tag_configure('good', foreground='#27ae60', background='#d5f5e3')
        
        self.p_tree.pack(fill='both', expand=True, padx=20, pady=15)

        f_req = ttk.LabelFrame(tab_req, text=" Send Adjustments to Teacher ", padding=30)
        f_req.pack(fill='both', expand=True, padx=20, pady=20)
        ttk.Label(f_req, text="Class/Subject:").grid(row=0, column=0, pady=10, sticky='e')
        self.p_req_class = ttk.Combobox(f_req, values=self.manager.get_classes(), state='readonly', width=30)
        self.p_req_class.grid(row=0, column=1, pady=10, padx=10)
        ttk.Label(f_req, text="Reference (ID / Date):").grid(row=1, column=0, pady=10, sticky='e')
        self.p_req_ref = ttk.Entry(f_req, width=33)
        self.p_req_ref.grid(row=1, column=1, pady=10, padx=10)
        ttk.Label(f_req, text="Message Content:").grid(row=2, column=0, pady=10, sticky='ne')
        self.p_req_msg = tk.Text(f_req, height=6, width=40)
        self.p_req_msg.grid(row=2, column=1, pady=10, padx=10)
        ttk.Button(f_req, text="Dispatch Notification", command=self.p_send_req).grid(row=3, column=1, pady=20, sticky='w')

        f_man = ttk.LabelFrame(tab_manage, text=" Danger Zone - Permanent Deletion ", padding=30)
        f_man.pack(fill='both', expand=True, padx=20, pady=20)
        ttk.Label(f_man, text="Select Class to Remove completely:").grid(row=0, column=0, pady=10, sticky='e')
        self.p_del_class = ttk.Combobox(f_man, values=self.manager.get_classes(), state='readonly', width=30)
        self.p_del_class.grid(row=0, column=1, pady=10, padx=10)
        ttk.Button(f_man, text="Delete Entire Class", command=self.p_del_class_fn).grid(row=0, column=2, padx=10)

    # --- ACTION METHODS ---
    def t_clear_notifs(self):
        self.manager.clear_notifications()
        self.list_notif.delete(0, tk.END)

    def t_add_student(self):
        try:
            self.manager.add_student(self.t_ent_class.get(), self.t_ent_id.get(), self.t_ent_name.get())
            messagebox.showinfo("Success", "Student Registered Successfully.")
            self.t_combo_class['values'] = self.manager.get_classes()
            self.t_ent_id.delete(0, tk.END)
            self.t_ent_name.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def t_load_roster(self):
        cls, dt = self.t_combo_class.get(), self.t_ent_date.get()
        if not cls: return
        self.t_tree.delete(*self.t_tree.get_children())
        records = self.manager.get_attendance_for_date(cls, dt)
        
        for s_id, name in self.manager.get_students(cls):
            self.t_tree.insert("", tk.END, values=(s_id, name, records.get(s_id, "Absent")))

    def t_toggle_status(self, event):
        # Identify click region to prevent accidental toggling when clicking column headers to sort!
        if self.t_tree.identify_region(event.x, event.y) != 'cell':
            return
            
        item = self.t_tree.focus()
        if not item: return
        val = self.t_tree.item(item, 'values')
        self.t_tree.item(item, values=(val[0], val[1], "Absent" if val[2] == "Present" else "Present"))

    def t_submit_attendance(self):
        cls, dt = self.t_combo_class.get(), self.t_ent_date.get()
        updates = {self.t_tree.item(r, 'values')[0]: self.t_tree.item(r, 'values')[2] for r in self.t_tree.get_children()}
        
        if not updates:
            messagebox.showwarning("Warning", "Roster is empty. Please load roster first.")
            return
            
        if self.manager.has_record_for_date(cls, dt) and not messagebox.askyesno("Confirm", "Overwrite existing data?"): 
            return
            
        self.manager.save_attendance(cls, dt, updates)
        messagebox.showinfo("Success", "Attendance Saved successfully.")

    def t_generate_qr(self):
        cls = self.t_combo_class.get()
        dt = self.t_ent_date.get()
        if not cls or not dt:
            messagebox.showwarning("Error", "Select class and a valid date first.")
            return

        if not QR_AVAILABLE:
            messagebox.showerror("Libraries Missing", "Please install prerequisites via terminal: pip install qrcode[pil]")
            return

        self.manager.ensure_roster_initialized(cls, dt)
        token = str(uuid.uuid4())
        AttendanceHandler.active_token = token
        
        ip = get_local_ip()
        url = f"http://{ip}:{self.server_port}/?session={token}&class={urllib.parse.quote(cls)}&date={urllib.parse.quote(dt)}"
        
        qr = qrcode.QRCode(box_size=8, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#2c3e50", back_color="white")
        
        qr_win = tk.Toplevel(self.root)
        qr_win.title("QR Attendance Display")
        qr_win.geometry("550x650")
        qr_win.configure(bg="white")
        
        lbl_inst = ttk.Label(qr_win, text=f"Instruct students to connect to the Wi-Fi and scan this QR code with their devices.\n\nClass: {cls}  |  Date: {dt}\n\nThis code uniquely changes and will become PERMANENTLY INVALID as soon as you close this window.", justify="center", wraplength=450, font=('Segoe UI', 11))
        lbl_inst.pack(pady=20)
        
        self.tk_img = ImageTk.PhotoImage(img)
        lbl_img = tk.Label(qr_win, image=self.tk_img, bg="white")
        lbl_img.pack(pady=10)
        
        def on_close():
            AttendanceHandler.active_token = None
            qr_win.destroy()
            self.t_load_roster() 
            messagebox.showinfo("QR Closed", "The QR Code session has been terminated. Live roster refreshed.")
            
        qr_win.protocol("WM_DELETE_WINDOW", on_close)


    def p_draw_pie_chart(self):
        self.canvas.delete("all")
        classes = self.manager.get_classes()
        date_filter = self.p_chart_date.get().strip()
        
        w = self.canvas.winfo_width() or 900
        h = self.canvas.winfo_height() or 400
        
        total_present = 0
        total_absent = 0
        
        for cls in classes:
            if date_filter:
                if self.manager.has_record_for_date(cls, date_filter):
                    records = self.manager.get_attendance_for_date(cls, date_filter)
                    students = self.manager.get_students(cls)
                    if students:
                        present = sum(1 for status in records.values() if status == "Present")
                        total_present += present
                        total_absent += (len(students) - present)
            else:
                stats = self.manager.get_student_stats(cls)
                for s in stats.values():
                    total_present += s['attended']
                    total_absent += (s['total'] - s['attended'])
                
        total = total_present + total_absent
        
        if total == 0:
             msg = f"0 Classes / 0% Data for {date_filter}" if date_filter else "0 Classes / 0% Data All Time"
             self.canvas.create_text(w/2, h/2, text=msg, font=("Segoe UI", 16, "bold"), fill="gray")
             return

        cx, cy = w/2, h/2
        r = min(w, h) / 3
        
        present_angle = (total_present / total) * 360
        absent_angle = 360 - present_angle
        
        if present_angle == 360:
             self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#2ecc71", outline="white", width=2)
        elif absent_angle == 360:
             self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#e74c3c", outline="white", width=2)
        else:
            if present_angle > 0:
                self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=0, extent=present_angle, fill="#2ecc71", outline="white", width=2)
            if absent_angle > 0:
                self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=present_angle, extent=absent_angle, fill="#e74c3c", outline="white", width=2)
            
        self.canvas.create_rectangle(w-250, cy-30, w-230, cy-10, fill="#2ecc71", outline="")
        self.canvas.create_text(w-215, cy-20, text=f"Present ({total_present}) - {present_angle/360*100:.1f}%", anchor="w", font=("Segoe UI", 12))
        
        self.canvas.create_rectangle(w-250, cy+10, w-230, cy+30, fill="#e74c3c", outline="")
        self.canvas.create_text(w-215, cy+20, text=f"Absent ({total_absent}) - {absent_angle/360*100:.1f}%", anchor="w", font=("Segoe UI", 12))


    def p_view_report(self):
        cls = self.p_combo_class.get()
        if not cls: return
        self.p_tree.delete(*self.p_tree.get_children())
        for s_id, data in self.manager.get_student_stats(cls).items():
            if data['pct'] < MIN_ATTENDANCE_THRESHOLD and data['total'] > 0:
                flag = "⚠️ At Risk"
                tag = "risk"
            else:
                flag = "✅ Good"
                tag = "good"
            self.p_tree.insert("", tk.END, values=(cls, s_id, data['name'], data['attended'], data['total'], f"{data['pct']:.1f}%", flag), tags=(tag,))

    def p_portal_warnings(self):
        cls = self.p_combo_class.get()
        if not cls: return
        stats = self.manager.get_student_stats(cls)
        sent = self.manager.dispatch_portal_warnings(cls, stats)
        messagebox.showinfo("Warnings Dispatched", f"Successfully updated {sent} digital alerts in Student Portals.")

    def p_send_req(self):
        self.manager.add_notification(self.p_req_class.get(), f"Ref: {self.p_req_ref.get()} - {self.p_req_msg.get('1.0', tk.END).strip()}")
        messagebox.showinfo("Success", "Request dispatched to teacher dashboard.")
        self.p_req_msg.delete("1.0", tk.END)
        self.p_req_ref.delete(0, tk.END)

    def p_del_class_fn(self):
        cls = self.p_del_class.get()
        if cls and messagebox.askyesno("DANGER ZONE", f"Are you entirely sure you want to delete {cls} forever?"):
            self.manager.delete_class(cls)
            messagebox.showinfo("Deleted", "Class removed from system.")
            self.p_combo_class['values'] = self.manager.get_classes()
            self.p_del_class['values'] = self.manager.get_classes()

if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()
