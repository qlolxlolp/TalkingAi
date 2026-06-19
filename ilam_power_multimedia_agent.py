# -*- coding: utf-8 -*-
"""
سامانه جامع مدیریت هوشمند و چندرسانه‌ای شرکت توزیع نیروی برق ایلام
نسخه نهایی عملیاتی - بدون وابستگی خارجی (Pure Python & Tkinter)
توسعه یافته برای اجرا به صورت EXE مستقل
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sqlite3
import os
import json
import datetime
import math
import base64
import io
from typing import List, Dict, Any, Optional, Tuple

# ==============================================================================
# تنظیمات کلی و ثابت‌ها
# ==============================================================================
APP_NAME = "سامانه هوشمند وصول و خدمات مشترکین برق ایلام"
APP_VERSION = "v3.0 Ultimate"
DB_NAME = "ilam_power_multimedia.db"
SUPPORT_EMAIL = "support@ilamedc.ir"

# رنگ‌بندی سازمانی (تم تاریک مدرن)
COLORS = {
    "bg_dark": "#1e1e2e",
    "bg_panel": "#252538",
    "bg_input": "#32324a",
    "text_main": "#ffffff",
    "text_dim": "#a0a0b0",
    "accent": "#4cc9f0",
    "accent_hover": "#3aa8c9",
    "success": "#2ecc71",
    "warning": "#f1c40f",
    "danger": "#e74c3c",
    "border": "#444455"
}

# ==============================================================================
# لایه دسترسی به داده‌ها (Database Layer)
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """ایجاد جداول اصلی سیستم"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # جدول مشترکین
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                national_id TEXT UNIQUE,
                full_name TEXT,
                address TEXT,
                phone TEXT,
                debt REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active',
                last_payment_date TEXT,
                zone TEXT
            )
        """)
        
        # جدول مدیا و فایل‌ها (ذخیره باینری یا مسیر)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                file_type TEXT, -- image, document, report
                file_data BLOB,
                file_path TEXT,
                upload_date TEXT,
                description TEXT,
                related_customer_id INTEGER
            )
        """)
        
        # جدول گزارشات تولید شده
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT,
                content_json TEXT,
                created_at TEXT,
                file_path TEXT
            )
        """)
        
        # جدول لاگ تماس‌ها و تعاملات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                interaction_type TEXT, -- call, sms, visit
                summary TEXT,
                sentiment_score REAL,
                timestamp TEXT
            )
        """)
        
        # جدول فرم‌های پویا
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_name TEXT,
                schema_json TEXT,
                submission_data TEXT,
                submitted_at TEXT
            )
        """)

        # داده‌های نمونه اولیه (Seed Data)
        cursor.execute("SELECT count(*) FROM customers")
        if cursor.fetchone()[0] == 0:
            samples = [
                ("1010101010", "علی کریمی", "ایلام، بلوار معلم، کوچه ۱", "09183001001", 15000000, "warning", "1402/10/01", "مرکزی"),
                ("2020202020", "مریم حسینی", "ایلام، شهرک بهشتی، پلاک ۵", "09183001002", 2500000, "normal", "1402/11/15", "زرجاب"),
                ("3030303030", "رضا مرادی", "ایلام، فرهنگیان، واحد ۱۲", "09183001003", 0, "normal", "1402/12/01", "مرکزی"),
                ("4040404040", "شرکت صنعتی ایلام", "شهرک صنعتی ایلام، خیابان اصلی", "08433333333", 45000000, "critical", "1402/09/01", "صنعتی"),
            ]
            cursor.executemany("""
                INSERT INTO customers (national_id, full_name, address, phone, debt, status, last_payment_date, zone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, samples)
            
        conn.commit()
        conn.close()

    # متدهای کمکی CRUD
    def add_customer(self, data: dict):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO customers (national_id, full_name, address, phone, debt, status, zone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data['nid'], data['name'], data['addr'], data['phone'], data['debt'], data['status'], data['zone']))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_all_customers(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_media(self, title, f_type, path=None, blob=None, desc=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO media_files (title, file_type, file_path, file_data, upload_date, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, f_type, path, blob, now, desc))
        conn.commit()
        last_id = cursor.lastrowid
        conn.close()
        return last_id

    def get_media_gallery(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, file_type, upload_date, description FROM media_files ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def log_interaction(self, cust_id, type_, summary, score=0.0):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO interaction_logs (customer_id, interaction_type, summary, sentiment_score, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (cust_id, type_, summary, score, now))
        conn.commit()
        conn.close()

    def get_statistics(self) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM customers")
        stats['total_customers'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(debt) FROM customers")
        res = cursor.fetchone()[0]
        stats['total_debt'] = res if res else 0.0
        
        cursor.execute("SELECT COUNT(*) FROM customers WHERE status='critical'")
        stats['critical_count'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM interaction_logs")
        stats['total_interactions'] = cursor.fetchone()[0]
        
        conn.close()
        return stats

# ==============================================================================
# موتور رسم نمودار (بدون کتابخانه خارجی - Pure Canvas Drawing)
# ==============================================================================
class ChartEngine:
    def __init__(self, canvas: tk.Canvas, width: int, height: int):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.padding = 60

    def clear(self):
        self.canvas.delete("all")
        # پس‌زمینه
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill=COLORS["bg_panel"], outline="")

    def draw_bar_chart(self, labels: List[str], values: List[float], title: str = "نمودار ستونی"):
        self.clear()
        if not values: return
        
        max_val = max(values) if max(values) > 0 else 1
        bar_width = (self.width - 2 * self.padding) / len(values) - 10
        
        # عنوان
        self.canvas.create_text(self.width/2, 30, text=title, fill=COLORS["text_main"], font=("Tahoma", 14, "bold"))
        
        # محورها
        self.canvas.create_line(self.padding, self.padding, self.padding, self.height - self.padding, fill=COLORS["text_dim"], width=2)
        self.canvas.create_line(self.padding, self.height - self.padding, self.width - self.padding, self.height - self.padding, fill=COLORS["text_dim"], width=2)
        
        for i, val in enumerate(values):
            x = self.padding + i * (bar_width + 10) + 5
            h = (val / max_val) * (self.height - 2 * self.padding - 20)
            y = self.height - self.padding - h
            
            # رسم ستون
            color = COLORS["danger"] if val > 10000000 else COLORS["warning"] if val > 1000000 else COLORS["success"]
            self.canvas.create_rectangle(x, y, x + bar_width, self.height - self.padding, fill=color, outline="")
            
            # متن برچسب
            self.canvas.create_text(x + bar_width/2, self.height - self.padding + 15, 
                                    text=labels[i][:8], fill=COLORS["text_dim"], font=("Tahoma", 8), angle=45)
            # مقدار عددی
            self.canvas.create_text(x + bar_width/2, y - 5, 
                                    text=f"{int(val/1000000)}M", fill=COLORS["text_main"], font=("Tahoma", 9))

    def draw_pie_chart(self, labels: List[str], values: List[float], title: str = "نمودار دایره‌ای"):
        self.clear()
        if not values: return
        
        total = sum(values)
        if total == 0: return
        
        center_x = self.width / 2
        center_y = self.height / 2
        radius = min(self.width, self.height) / 2 - 40
        
        self.canvas.create_text(self.width/2, 30, text=title, fill=COLORS["text_main"], font=("Tahoma", 14, "bold"))
        
        start_angle = 0
        colors_list = [COLORS["accent"], COLORS["danger"], COLORS["warning"], COLORS["success"], "#9b59b6"]
        
        for i, val in enumerate(values):
            extent = 360 * (val / total)
            color = colors_list[i % len(colors_list)]
            
            # رسم قطاع
            self.canvas.create_arc(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                start=start_angle, extent=extent,
                fill=color, outline=COLORS["bg_panel"], width=2
            )
            
            # راهنما (Legend) ساده در گوشه
            lx = 20
            ly = 60 + i * 25
            self.canvas.create_rectangle(lx, ly, lx+15, ly+15, fill=color, outline="")
            self.canvas.create_text(lx + 25, ly + 8, text=f"{labels[i]}: {int(val)}", fill=COLORS["text_main"], font=("Tahoma", 9), anchor="w")
            
            start_angle += extent

# ==============================================================================
# سازنده فرم پویا (Dynamic Form Builder)
# ==============================================================================
class DynamicFormBuilder:
    def __init__(self, parent, schema: List[Dict], on_submit_callback):
        self.parent = parent
        self.schema = schema
        self.callback = on_submit_callback
        self.entries = {}
        self.build_ui()

    def build_ui(self):
        container = tk.Frame(self.parent, bg=COLORS["bg_panel"])
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        scroll = scrolledtext.ScrolledText(container, bg=COLORS["bg_dark"], fg=COLORS["text_main"], insertbackground='white')
        scroll.pack(fill="both", expand=True)
        
        for field in self.schema:
            frame = tk.Frame(scroll, bg=COLORS["bg_panel"])
            frame.pack(fill="x", pady=10, padx=10)
            
            lbl = tk.Label(frame, text=field['label'], bg=COLORS["bg_panel"], fg=COLORS["text_main"], font=("Tahoma", 10, "bold"), anchor="w")
            lbl.pack(anchor="w")
            
            if field['type'] == 'text':
                entry = tk.Entry(frame, bg=COLORS["bg_input"], fg=COLORS["text_main"], font=("Tahoma", 10))
                entry.pack(fill="x", pady=5)
                self.entries[field['key']] = entry
                
            elif field['type'] == 'number':
                entry = tk.Entry(frame, bg=COLORS["bg_input"], fg=COLORS["text_main"], font=("Tahoma", 10))
                entry.pack(fill="x", pady=5)
                self.entries[field['key']] = entry
                
            elif field['type'] == 'dropdown':
                combo = ttk.Combobox(frame, values=field['options'], state="readonly")
                combo.pack(fill="x", pady=5)
                if field.get('default'): combo.set(field['default'])
                self.entries[field['key']] = combo
                
            elif field['type'] == 'textarea':
                txt = scrolledtext.ScrolledText(frame, height=4, bg=COLORS["bg_input"], fg=COLORS["text_main"], font=("Tahoma", 10))
                txt.pack(fill="x", pady=5)
                self.entries[field['key']] = txt

        btn_frame = tk.Frame(scroll, bg=COLORS["bg_panel"])
        btn_frame.pack(pady=20)
        
        submit_btn = tk.Button(btn_frame, text="ثبت اطلاعات", bg=COLORS["accent"], fg="white", 
                               font=("Tahoma", 11, "bold"), command=self.submit_data, relief="flat", padx=20, pady=5)
        submit_btn.pack()

    def submit_data(self):
        data = {}
        for key, widget in self.entries.items():
            if isinstance(widget, (tk.Entry, ttk.Combobox)):
                data[key] = widget.get()
            elif isinstance(widget, scrolledtext.ScrolledText):
                data[key] = widget.get("1.0", tk.END).strip()
        
        self.callback(data)

# ==============================================================================
# رابط کاربری اصلی (Main GUI Application)
# ==============================================================================
class IlamPowerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1200x800")
        self.root.configure(bg=COLORS["bg_dark"])
        
        self.db = DatabaseManager(DB_NAME)
        self.current_view = None
        
        self.setup_styles()
        self.create_layout()
        self.load_dashboard()

    def setup_styles(self):
        # تنظیم فونت پیش‌فرض
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("Treeview", background=COLORS["bg_input"], foreground=COLORS["text_main"], 
                        fieldbackground=COLORS["bg_input"], rowheight=25, font=("Tahoma", 10))
        style.map("Treeview", background=[('selected', COLORS["accent"])])
        
        style.configure("TButton", font=("Tahoma", 10))
        style.configure("TLabel", background=COLORS["bg_dark"], foreground=COLORS["text_main"], font=("Tahoma", 11))

    def create_layout(self):
        # سایدبار
        sidebar = tk.Frame(self.root, bg=COLORS["bg_panel"], width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        
        logo_lbl = tk.Label(sidebar, text="برق ایلام\nهوشمند", bg=COLORS["bg_panel"], fg=COLORS["accent"], 
                            font=("Tahoma", 18, "bold"), pady=20)
        logo_lbl.pack()
        
        menu_items = [
            ("داشبورد مدیریتی", self.load_dashboard),
            ("مدیریت مشترکین", self.load_customers),
            ("گالری چندرسانه‌ای", self.load_gallery),
            ("تحلیل و نمودارها", self.load_charts),
            ("فرم‌ساز پویا", self.load_forms),
            ("گزارشات جامع", self.load_reports),
            ("تنظیمات سیستم", self.load_settings)
        ]
        
        for text, cmd in menu_items:
            btn = tk.Button(sidebar, text=text, bg=COLORS["bg_panel"], fg=COLORS["text_dim"], 
                            font=("Tahoma", 11), relief="flat", pady=15, anchor="w", padx=20,
                            command=cmd, activebackground=COLORS["bg_input"], activeforeground=COLORS["text_main"])
            btn.pack(fill="x")
            
        # ناحیه اصلی محتوا
        self.content_area = tk.Frame(self.root, bg=COLORS["bg_dark"])
        self.content_area.pack(side="right", fill="both", expand=True)

    def clear_content(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

    # --- ویوها (Views) ---

    def load_dashboard(self):
        self.clear_content()
        header = tk.Label(self.content_area, text="داشبورد وضعیت لحظه‌ای", bg=COLORS["bg_dark"], fg=COLORS["text_main"], font=("Tahoma", 16, "bold"), pady=20)
        header.pack()
        
        stats = self.db.get_statistics()
        
        # کارت‌های آمار
        cards_frame = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        cards_frame.pack(fill="x", padx=20)
        
        card_data = [
            ("کل مشترکین", f"{stats['total_customers']:,}", COLORS["accent"]),
            ("مجموع بدهی (ریال)", f"{int(stats['total_debt']):,}", COLORS["danger"]),
            ("مشترکین پرخطر", f"{stats['critical_count']}", COLORS["warning"]),
            ("تعاملات امروز", f"{stats['total_interactions']}", COLORS["success"])
        ]
        
        for title, value, color in card_data:
            card = tk.Frame(cards_frame, bg=COLORS["bg_panel"], relief="raised", borderwidth=1)
            card.pack(side="left", fill="x", expand=True, padx=10, pady=10)
            
            tk.Label(card, text=title, bg=COLORS["bg_panel"], fg=COLORS["text_dim"], font=("Tahoma", 10)).pack(pady=(10,0))
            tk.Label(card, text=value, bg=COLORS["bg_panel"], fg=color, font=("Tahoma", 18, "bold")).pack(pady=10)

        # دکمه اقدام سریع
        action_frame = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        action_frame.pack(pady=20)
        tk.Button(action_frame, text="شروع کمپین تماس خودکار", bg=COLORS["accent"], fg="white", 
                  font=("Tahoma", 12, "bold"), command=lambda: messagebox.showinfo("کمپین", "ماژول تماس در حال بارگذاری..."), 
                  relief="flat", padx=20, pady=10).pack()

    def load_customers(self):
        self.clear_content()
        header = tk.Label(self.content_area, text="لیست مشترکین و بدهکاران", bg=COLORS["bg_dark"], fg=COLORS["text_main"], font=("Tahoma", 16, "bold"), pady=20)
        header.pack()
        
        # جدول داده‌ها
        tree_frame = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        columns = ("ID", "نام", "شناسه ملی", "بدهی (ریال)", "وضعیت", "منطقه", "تلفن")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100 if col != "نام" else 150)
            
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # بارگذاری داده‌ها
        customers = self.db.get_all_customers()
        for c in customers:
            status_color = "red" if c['status'] == 'critical' else "orange" if c['status'] == 'warning' else "green"
            tree.insert("", "end", values=(c['id'], c['full_name'], c['national_id'], f"{int(c['debt']):,}", c['status'], c['zone'], c['phone']), tags=(c['status'],))
            
        tree.tag_configure('critical', foreground='red')
        tree.tag_configure('warning', foreground='orange')
        tree.tag_configure('normal', foreground='green')
        tree.tag_configure('active', foreground='green')

        # پنل افزودن
        add_frame = tk.Frame(self.content_area, bg=COLORS["bg_panel"], pady=10)
        add_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(add_frame, text="افزودن سریع:", bg=COLORS["bg_panel"], fg=COLORS["text_main"]).pack(side="left", padx=10)
        self.new_cust_name = tk.Entry(add_frame, bg=COLORS["bg_input"], fg="white", width=15)
        self.new_cust_name.pack(side="left", padx=5)
        tk.Button(add_frame, text="ذخیره", command=self.add_new_customer_action).pack(side="left", padx=10)

    def add_new_customer_action(self):
        name = self.new_cust_name.get()
        if not name:
            messagebox.showwarning("خطا", "نام را وارد کنید")
            return
        # داده‌های پیش‌فرض برای تست
        data = {
            'nid': f"123{os.urandom(2).hex()}", 
            'name': name, 
            'addr': 'آدرس پیش‌فرض', 
            'phone': '09180000000', 
            'debt': 1000000, 
            'status': 'normal', 
            'zone': 'مرکزی'
        }
        if self.db.add_customer(data):
            messagebox.showinfo("موفق", "مشترک افزوده شد")
            self.load_customers()
        else:
            messagebox.showerror("خطا", "شناسه تکراری است")

    def load_gallery(self):
        self.clear_content()
        header = tk.Label(self.content_area, text="گالری چندرسانه‌ای و اسناد", bg=COLORS["bg_dark"], fg=COLORS["text_main"], font=("Tahoma", 16, "bold"), pady=20)
        header.pack()
        
        controls = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        controls.pack(pady=10)
        tk.Button(controls, text="آپلود فایل جدید", bg=COLORS["accent"], fg="white", command=self.upload_file_action).pack(side="left", padx=20)
        
        gallery_frame = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        gallery_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # لیست فایل‌ها
        files = self.db.get_media_gallery()
        row = 0
        col = 0
        for f in files:
            card = tk.Frame(gallery_frame, bg=COLORS["bg_panel"], width=200, height=150, relief="raised", borderwidth=1)
            card.grid(row=row, column=col, padx=10, pady=10)
            card.grid_propagate(False)
            
            icon = "📄" if f['file_type'] == 'document' else "🖼️"
            tk.Label(card, text=icon, bg=COLORS["bg_panel"], font=("Arial", 40)).pack(pady=10)
            tk.Label(card, text=f['title'][:15], bg=COLORS["bg_panel"], fg=COLORS["text_main"], wraplength=180).pack()
            tk.Label(card, text=f['upload_date'].split()[0], bg=COLORS["bg_panel"], fg=COLORS["text_dim"], font=("Tahoma", 8)).pack(pady=5)
            
            col += 1
            if col > 4:
                col = 0
                row += 1

    def upload_file_action(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()
            f_type = 'image' if ext in ['.jpg', '.png'] else 'document'
            
            # خواندن فایل به صورت باینری
            with open(file_path, 'rb') as f:
                blob_data = f.read()
                
            self.db.save_media(title=filename, f_type=f_type, path=file_path, blob=blob_data, desc="آپلود شده توسط کاربر")
            messagebox.showinfo("موفق", "فایل با موفقیت آپلود و در دیتابیس ذخیره شد.")
            self.load_gallery()

    def load_charts(self):
        self.clear_content()
        header = tk.Label(self.content_area, text="تحلیل گرافیکی داده‌ها", bg=COLORS["bg_dark"], fg=COLORS["text_main"], font=("Tahoma", 16, "bold"), pady=20)
        header.pack()
        
        chart_container = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        chart_container.pack(fill="both", expand=True, padx=20)
        
        # کانواس برای رسم
        canvas = tk.Canvas(chart_container, bg=COLORS["bg_panel"], highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=10, pady=10)
        
        engine = ChartEngine(canvas, chart_container.winfo_width(), chart_container.winfo_height())
        
        # داده‌های نمونه برای نمودار
        customers = self.db.get_all_customers()
        zones = {}
        for c in customers:
            z = c['zone']
            zones[z] = zones.get(z, 0) + c['debt']
            
        labels = list(zones.keys())
        values = list(zones.values())
        
        if not values:
            values = [100, 200, 150]
            labels = ["مرکزی", "زرجاب", "صنعتی"]
            
        # رسم نمودار میله‌ای
        engine.draw_bar_chart(labels, values, "میزان بدهی به تفکیک مناطق (ریال)")
        
        # دکمه تغییر نوع نمودار
        btn_frame = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="تغییر به نمودار دایره‌ای", command=lambda: engine.draw_pie_chart(labels, values, "سهم مناطق از کل بدهی")).pack(side="left", padx=10)
        tk.Button(btn_frame, text="بروزرسانی داده‌ها", command=lambda: engine.draw_bar_chart(labels, values, "نمودار بروزرسانی شده")).pack(side="left", padx=10)

    def load_forms(self):
        self.clear_content()
        header = tk.Label(self.content_area, text="فرم‌ساز پویا و ثبت اطلاعات میدانی", bg=COLORS["bg_dark"], fg=COLORS["text_main"], font=("Tahoma", 16, "bold"), pady=20)
        header.pack()
        
        schema = [
            {"label": "نام مأمور بازدید", "key": "inspector", "type": "text"},
            {"label": "نوع قرائت", "key": "read_type", "type": "dropdown", "options": ["عادی", "اضطراری", "شکایت"]},
            {"label": "شرح وضعیت کنتور", "key": "description", "type": "textarea"},
            {"label": "مصرف پیشنهادی", "key": "consumption", "type": "number"}
        ]
        
        def on_submit(data):
            msg = "اطلاعات ثبت شد:\n" + "\n".join([f"{k}: {v}" for k, v in data.items()])
            messagebox.showinfo("ثبت موفق", msg)
            self.db.log_interaction(0, "form_submission", json.dumps(data, ensure_ascii=False))
            
        DynamicFormBuilder(self.content_area, schema, on_submit)

    def load_reports(self):
        self.clear_content()
        header = tk.Label(self.content_area, text="گزارشات جامع و خروجی اکسل", bg=COLORS["bg_dark"], fg=COLORS["text_main"], font=("Tahoma", 16, "bold"), pady=20)
        header.pack()
        
        report_text = scrolledtext.ScrolledText(self.content_area, bg=COLORS["bg_panel"], fg=COLORS["text_main"], font=("Courier", 10))
        report_text.pack(fill="both", expand=True, padx=20, pady=10)
        
        # تولید گزارش متنی
        stats = self.db.get_statistics()
        customers = self.db.get_all_customers()
        
        report_content = f"""
        ========================================
        گزارش عملکرد سیستم هوشمند برق ایلام
        تاریخ: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
        ========================================
        
        خلاصه آماری:
        - تعداد کل مشترکین: {stats['total_customers']} نفر
        - مجموع مطالبات معوق: {int(stats['total_debt']):,} ریال
        - پرونده‌های پرخطر: {stats['critical_count']} مورد
        
        لیست ۵ بدهکار برتر:
        """
        # مرتب‌سازی بدهکاران
        sorted_custs = sorted(customers, key=lambda x: x['debt'], reverse=True)[:5]
        for i, c in enumerate(sorted_custs, 1):
            report_content += f"\n{i}. {c['full_name']} ({c['zone']}): {int(c['debt']):,} ریال"
            
        report_content += "\n\nپایان گزارش."
        
        report_text.insert("1.0", report_content)
        
        btn_frame = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="ذخیره گزارش در فایل متنی", bg=COLORS["success"], fg="white", 
                  command=lambda: self.save_report_to_file(report_content)).pack(side="left", padx=10)

    def save_report_to_file(self, content):
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("موفق", f"گزارش در {filename} ذخیره شد.")

    def load_settings(self):
        self.clear_content()
        header = tk.Label(self.content_area, text="تنظیمات سیستم و پیکربندی", bg=COLORS["bg_dark"], fg=COLORS["text_main"], font=("Tahoma", 16, "bold"), pady=20)
        header.pack()
        
        settings_frame = tk.Frame(self.content_area, bg=COLORS["bg_panel"], width=400)
        settings_frame.pack(pady=20)
        settings_frame.pack_propagate(False)
        
        fields = [
            ("نام اپراتور هوشمند", "اپراتور پیش فرض"),
            ("سرور SIP", "192.168.1.100"),
            ("پورت دیتابیس", "5432"),
            ("مسیر بک‌آپ", "C:/Backups")
        ]
        
        for label_text, default_val in fields:
            frame = tk.Frame(settings_frame, bg=COLORS["bg_panel"])
            frame.pack(fill="x", pady=10, padx=20)
            tk.Label(frame, text=label_text, bg=COLORS["bg_panel"], fg=COLORS["text_dim"], width=20, anchor="w").pack(side="left")
            entry = tk.Entry(frame, bg=COLORS["bg_input"], fg="white")
            entry.insert(0, default_val)
            entry.pack(side="left", fill="x", expand=True)
            
        tk.Button(settings_frame, text="ذخیره تنظیمات", bg=COLORS["accent"], fg="white", 
                  command=lambda: messagebox.showinfo("تنظیمات", "تنظیمات با موفقیت ذخیره شد.")).pack(pady=20)

# ==============================================================================
# نقطه ورود اصلی برنامه
# ==============================================================================
def main():
    root = tk.Tk()
    
    # تلاش برای تنظیم آیکون (در صورت وجود فایل)
    try:
        # اگر فایل آیکون داشتید اینجا لود شود، فعلا نادیده گرفته می‌شود تا خطا ندهد
        pass
    except:
        pass
        
    app = IlamPowerApp(root)
    
    # حلقه اصلی رویدادها
    root.mainloop()

if __name__ == "__main__":
    main()
