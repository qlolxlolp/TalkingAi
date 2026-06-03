#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
سامانه هوشمند تماس صوتی خودکار - نسخه تخصصی صنعت برق
زیرسیستم: اپراتور هوشمند وصول مطالبات
شرکت: توزیع نیروی برق استان ایلام - شهرستان ایلام
================================================================================
توصیف:
این ماژول هسته مرکزی هوش مصنوعی است که مستقیماً با داده‌های مشترکین برق ایلام
متصل شده و به عنوان یک اپراتور انسانی و قاطع برای وصول مطالبات عمل می‌کند.
ویژگی‌ها:
- اتصال شبیه‌سازی شده به eserv.bargh-ilam.ir و همگام‌سازی локал
- تحلیل رفتار بدهکار و انتخاب استراتژی مکالمه (نرم، اخطار، قطع)
- تولید گفتار فارسی با لهجه و ادبیات رسمی اداری
- کاملاً مستقل، بدون وابستگی به سخت‌افزار خارجی (VoIP Software Stack)
================================================================================
"""

import sqlite3
import json
import random
import datetime
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

# تنظیمات لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("IlamPowerAgent")

# ==============================================================================
# 1. ساختارهای داده و مدل‌های_domain (Domain Models)
# ==============================================================================

@dataclass
class CustomerProfile:
    """پروفایل کامل مشترک برق"""
    customer_id: str          # شناسه اشتراک (مثلاً 10 رقمی)
    full_name: str            # نام و نام خانوادگی
    address: str              # آدرس دقیق در ایلام
    phone_number: str         # شماره تماس متصل به کنتور
    debt_amount: float        # مبلغ بدهی به ریال
    last_bill_date: str       # تاریخ آخرین قبض
    consumption_avg: float    # میانگین مصرف ماهانه (کیلووات ساعت)
    payment_history: List[str] # تاریخچه پرداخت‌ها (خوش‌حساب/بدحساب)
    status: str               # وضعیت (فعال، بدهکار، قطع موقت، پرونده قضایی)
    zone: str                 # منطقه برق‌رسانی (مثلاً مرکزی، شهرک بهشتی، زرجاب)

@dataclass
class CallStrategy:
    """استراتژی مکالمه بر اساس نوع بدهکار"""
    tone: str                 # لحن صدا (دوستانه، رسمی، قاطع، هشداردهنده)
    script_template: str      # الگوی اولیه مکالمه
    offer_installment: bool   # آیا پیشنهاد قسط‌بندی دهد؟
    threat_disconnection: bool # آیا هشدار قطع انشعاب دهد؟
    escalation_level: int     # سطح تشدید (1: یادآوری، 2: اخطار، 3: قطع)

# ==============================================================================
# 2. لایه دسترسی به داده‌ها (Data Access Layer)
# شبیه‌ساز اتصال به eserv.bargh-ilam.ir و دیتابیس محلی
# ==============================================================================

class IlamPowerDB:
    """
    مدیریت دیتابیس محلی و همگام‌سازی با سامانه eserv.bargh-ilam.ir
    در محیط عملیاتی واقعی، متد sync_from_eserv به API داخلی شرکت متصل می‌شود.
    """
    
    def __init__(self, db_path: str = "ilam_power_customers.db"):
        self.db_path = db_path
        self.init_db()
        self.seed_sample_data() # بارگذاری داده‌های نمونه برای تست
        
    def init_db(self):
        """ایجاد جداول دیتابیس تخصصی برق"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول مشترکین
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                full_name TEXT,
                address TEXT,
                phone_number TEXT,
                debt_amount REAL,
                last_bill_date TEXT,
                consumption_avg REAL,
                payment_history TEXT, -- JSON stored as text
                status TEXT,
                zone TEXT,
                last_call_date TEXT,
                call_notes TEXT
            )
        ''')
        
        # جدول قوانین و مقررات شرکت برق ایلام
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regulations (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                content TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"پایگاه داده محلی برق ایلام در {self.db_path} آماده شد.")

    def seed_sample_data(self):
        """تزریق داده‌های نمونه واقعی‌نمای شهرستان ایلام"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # بررسی خالی بودن دیتابیس
        cursor.execute("SELECT count(*) FROM customers")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return

        sample_customers = [
            ("1402050101", "محمد رضایی", "ایلام، شهرک شهید بهشتی، خیابان گلستان، پلاک 12", "09183001001", 2500000.0, "1402/12/01", 350.0, '["خوش‌حساب تا 1401", "تاخیر 1 ماهه"]', "بدهکار", "مرکزی"),
            ("1402050102", "علی کریمی", "ایلام، محله زرجاب، کوچه امام حسین، پلاک 5", "09183001002", 15000000.0, "1402/11/15", 600.0, '["بدحساب", "اخطار کتبی"]', "اخطار نهایی", "زرجاب"),
            ("1402050103", "مریم احمدی", "ایلام، بلوار معلم، جنب بانک ملی", "09183001003", 450000.0, "1403/01/10", 120.0, '["خوش‌حساب"]', "فعال", "مرکزی"),
            ("1402050104", "حسن عباسی", "ایلام، شهرک فرهنگیان، واحد 4", "09183001004", 8700000.0, "1402/10/05", 450.0, '["چک برگشتی", "عدم پاسخگویی"]', "پرونده قضایی", "فرهنگیان"),
            ("1402050105", "رضا مرادی", "ایلام، جاده بین‌المللی، روبروی پالایشگاه", "09183001005", 1200000.0, "1403/01/05", 200.0, '["تاخیر جزئی"]', "بدهکار", "صنعتی"),
        ]
        
        for cust in sample_customers:
            cursor.execute('''
                INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            ''', (*cust,))
            
        # قوانین نمونه
        regulations = [
            ("قطع انشعاب", "طبق ماده 24 شرایط عمومی فروش برق، در صورت عدم پرداخت بدهی بیش از دو ماه، انشعاب بدون اطلاع قبلی قطع می‌گردد."),
            ("قسط‌بندی", "مشترکین می‌توانند بدهی‌های بالای 5 میلیون تومان را در حداکثر 4 قسط با مراجعه به دفتر امور مشترکین ایلام تسویه کنند."),
            ("جریمه دیرکرد", "به مبالغ معوقه ماهیانه 2 درصد جریمه دیرکرد تعلق می‌گیرد."),
            ("ساعات پاسخگویی", "دفتر خدمات مشترکین ایلام واقع در بلوار معلم، همه روزه از ساعت 7:30 تا 14:30 پاسخگو است.")
        ]
        for reg in regulations:
            cursor.execute("INSERT INTO regulations (topic, content) VALUES (?, ?)", reg)
            
        conn.commit()
        conn.close()
        logger.info("داده‌های نمونه مشترکین برق ایلام با موفقیت بارگذاری شد.")

    def get_customer_by_phone(self, phone: str) -> Optional[CustomerProfile]:
        """دریافت پروفایل مشترک بر اساس شماره تلفن"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM customers WHERE phone_number = ?", (phone,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return CustomerProfile(
                customer_id=row['customer_id'],
                full_name=row['full_name'],
                address=row['address'],
                phone_number=row['phone_number'],
                debt_amount=row['debt_amount'],
                last_bill_date=row['last_bill_date'],
                consumption_avg=row['consumption_avg'],
                payment_history=json.loads(row['payment_history']),
                status=row['status'],
                zone=row['zone']
            )
        return None

    def update_call_log(self, customer_id: str, notes: str):
        """ثبت گزارش تماس در پرونده مشترک"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            UPDATE customers 
            SET last_call_date = ?, call_notes = ?
            WHERE customer_id = ?
        ''', (now, notes, customer_id))
        conn.commit()
        conn.close()

    def sync_from_eserv(self):
        """
        شبیه‌ساز همگام‌سازی با سامانه eserv.bargh-ilam.ir
        در محیط واقعی: درخواست HTTPS امضا شده به API شرکت ارسال می‌شود.
        """
        logger.info("در حال همگام‌سازی با سامانه eserv.bargh-ilam.ir ...")
        # اینجا کد واقعی درخواست به سرور شرکت برق قرار می‌گیرد
        # response = requests.post('https://eserv.bargh-ilam.ir/api/v1/debts', headers=auth_headers)
        # پردازش و آپدیت دیتابیس محلی
        logger.info("همگام‌سازی با موفقیت انجام شد. 150 رکورد جدید بروزرسانی شد.")

# ==============================================================================
# 3. موتور هوش تجاری و استراتژی وصول (Business Logic Engine)
# ==============================================================================

class CollectionStrategyEngine:
    """
    تعیین استراتژی مکالمه بر اساس میزان بدهی و رفتار گذشته مشترک
    مخصوص شرکت توزیع نیروی برق ایلام
    """
    
    def analyze(self, customer: CustomerProfile) -> CallStrategy:
        debt = customer.debt_amount
        history = customer.payment_history
        status = customer.status
        
        # منطق تصمیم‌گیری سلسله مراتبی
        if "پرونده قضایی" in status or debt > 20000000:
            return CallStrategy(
                tone="قاطع و حقوقی",
                script_template="حقوقی_نهایی",
                offer_installment=False,
                threat_disconnection=True,
                escalation_level=3
            )
        elif debt > 5000000 or "اخطار" in status or "بدحساب" in history:
            return CallStrategy(
                tone="رسمی و هشداردهنده",
                script_template="اخطار_قطع",
                offer_installment=True, # پیشنهاد قسط برای جلوگیری از قطع
                threat_disconnection=True,
                escalation_level=2
            )
        elif debt > 1000000 and "تاخیر" in str(history):
            return CallStrategy(
                tone="محترمانه و یادآور",
                script_template="یادآوری_پرداخت",
                offer_installment=False,
                threat_disconnection=False,
                escalation_level=1
            )
        else:
            # بدهی کم یا مشتری خوش‌حساب با تاخیر جزئی
            return CallStrategy(
                tone="دوستانه و صمیمی",
                script_template="خوش‌آمدگویی_پرداخت",
                offer_installment=False,
                threat_disconnection=False,
                escalation_level=0
            )

# ==============================================================================
# 4. موتور تولید مکالمه طبیعی (Natural Conversation Generator)
# ==============================================================================

class IlamPowerDialogueManager:
    """
    مدیریت جریان مکالمه با ادبیات رسمی و بومی استان ایلام
    """
    
    def __init__(self):
        self.company_name = "شرکت توزیع نیروی برق استان ایلام"
        self.support_address = "ایلام، بلوار معلم، دفتر امور مشترکین"
        self.payment_methods = [
            "درگاه اینترنتی eserv.bargh-ilam.ir",
            "کدهای دستوری USSD",
            "دفاتر پیشخوان دولت در سراسر شهر ایلام",
            "عابر بانک‌های منتخب"
        ]

    def generate_opening(self, customer: CustomerProfile, strategy: CallStrategy) -> str:
        """تولید متن شروع مکالمه"""
        name = customer.full_name.split()[0] # استفاده از نام کوچک برای صمیمیت کنترل شده
        
        templates = {
            "حقوقی_نهایی": f"سلام آقای/خانم {name}. از واحد حقوقی {self.company_name} تماس می‌گیرم. پرونده بدهی سنگین شما به مبلغ {int(customer.debt_amount):,} ریال در مرحله نهایی قبل از اقدام قضایی و قطع دائم است.",
            "اخطار_قطع": f"سلام وقت بخیر، آقای/خانم {name}. از بخش وصول مطالبات {self.company_name} شهرستان ایلام تماس می‌گیرم. بدهی معوقه شما به مبلغ {int(customer.debt_amount):,} ریال رسیده و متاسفانه در لیست قطع انشعاب قرار گرفته‌اید.",
            "یادآوری_پرداخت": f"سلام روز بخیر، آقای/خانم {name}. از {self.company_name} مزاحم می‌شم. خواستم یادآوری کنم مبلغ {int(customer.debt_amount):,} ریال از قبض برق شما unpaid مانده است.",
            "خوش‌آمدگویی_پرداخت": f"سلام ارادت، آقای/خانم {name}. از {self.company_name} تماس گرفتم. یه بدهی کوچیک به مبلغ {int(customer.debt_amount):,} ریال دارید که اگر زودتر پرداخت کنید جریمه نمی‌شید."
        }
        return templates.get(strategy.script_template, templates["یادآوری_پرداخت"])

    def handle_response(self, user_input: str, strategy: CallStrategy, customer: CustomerProfile) -> str:
        """تحلیل پاسخ کاربر و تولید جواب مناسب"""
        user_input = user_input.lower()
        
        # تشخیص نیت (Intent Detection) ساده اما موثر
        if any(word in user_input for word in ["قسط", "قسط‌بندی", "تقسیم", "کمکم"]):
            if strategy.offer_installment:
                return "بله، با توجه به مبلغ بدهی شما، امکان قسط‌بندی تا 4 ماه وجود دارد. اما باید همین امروز برای تنظیم قرارداد به دفتر بلوار معلم مراجعه کنید. آیا می‌توانید فردا تشریف بیاورید؟"
            else:
                return "متاسفانه با توجه به وضعیت پرونده شما (اقدامات قانونی قبلی)، امکان قسط‌بندی وجود ندارد و باید کل مبلغ تسویه شود."
                
        elif any(word in user_input for word in ["قطع", "برق", "تاریک", "خاموش"]):
            if strategy.threat_disconnection:
                return "دقیقاً. اگر تا 48 ساعت آینده پرداختی ثبت نشود، سیستم به صورت خودکار دستور قطع انشعاب منطقه شما را صادر می‌کند و هزینه وصل مجدد هم بر عهده شماست."
            else:
                return "نگران نباشید، هنوز نوبت به قطع نرسیده، فقط خواستیم یادآوری کنیم پرداخت کنید."
                
        elif any(word in user_input for word in ["پرداختم", "ریختم", "واریز", "بانک"]):
            return "بسیار عالی. سیستم بانکی ممکن است تا 24 ساعت تاخیر داشته باشد. اگر تا فردا پیامک تایید نیامد، لطفاً فیش واریزی را به شماره واتساپ پشتیبانی یا دفتر امور مشترکین ببرید. شناسه قبض شما چیست؟"
            
        elif any(word in user_input for word in ["شکایت", "مصرف", "اشتباه", "زیاد"]):
            return f"اگر اعتراض به مبلغ قبض دارید، می‌توانید درخواست بازدید کنتور دهید. اما تا زمان تعیین تکلیف، باید حداقل 50 درصد مبلغ قبض را پرداخت کنید تا قطع نشوید. آیا مایلید راهنمایی کنم چطور درخواست بازدید بدهید؟"
            
        elif any(word in user_input for word in ["خداحافظ", "تموم", "بعدا"]):
            return "باشه، پس منتظر پرداخت شما هستیم. به امید همکاری بهتر. خدانگهدار."
            
        else:
            # پاسخ پیش‌فرض هوشمند
            return f"متوجه شدم. اما نکته مهم این است که بدهی شما در سیستم {self.company_name} ثبت شده و برای جلوگیری از مشکلات بعدی، پیشنهاد می‌کنم از طریق سایت eserv.bargh-ilam.ir همین الان چک کنید. سوال دیگری دارید؟"

# ==============================================================================
# 5. هسته اصلی عامل خودکار (Autonomous Agent Core)
# ==============================================================================

class PowerCollectionAgent:
    """
    عامل هوشمند اصلی که تمام اجزا را هماهنگ می‌کند
    """
    
    def __init__(self):
        logger.info("راه‌اندازی اپراتور هوشمند وصول مطالبات برق ایلام...")
        self.db = IlamPowerDB()
        self.strategy_engine = CollectionStrategyEngine()
        self.dialogue_manager = IlamPowerDialogueManager()
        self.voip_stack = self._init_voip_stack() # مقداردهی اولیه ماژول VoIP نرم‌افزاری
        
    def _init_voip_stack(self):
        """
        شبیه‌سازی初始化 ماژول VoIP نرم‌افزاری
        در محیط واقعی: PJSIP یا Asterisk AGI اینجا فراخوانی می‌شود
        """
        logger.info("ماژول VoIP نرم‌افزاری (SIP Stack) با موفقیت بارگذاری شد.")
        return {"status": "ready", "protocol": "SIP/2.0", "codec": "G.729/Persian-Optimized"}

    def make_outbound_call(self, phone_number: str):
        """شروع تماس خروجی خودکار"""
        customer = self.db.get_customer_by_phone(phone_number)
        
        if not customer:
            logger.warning(f"شماره {phone_number} در دیتابیس مشترکین یافت نشد.")
            return

        logger.info(f"--- شروع تماس با مشترک: {customer.full_name} (بدهی: {customer.debt_amount}) ---")
        
        # 1. تحلیل استراتژی
        strategy = self.strategy_engine.analyze(customer)
        logger.info(f"استراتژی انتخاب شده: {strategy.tone} | سطح تشدید: {strategy.escalation_level}")
        
        # 2. تولید متن شروع (TTS Input)
        opening_text = self.dialogue_manager.generate_opening(customer, strategy)
        print(f"\n[ربات]: {opening_text}")
        
        # شبیه‌سازی حلقه مکالمه (Conversation Loop)
        conversation_turns = 0
        max_turns = 5
        call_active = True
        
        while call_active and conversation_turns < max_turns:
            # شبیه‌سازی دریافت ورودی کاربر (STT Output)
            # در محیط واقعی: صدا ضبط شده -> Vosk -> متن
            user_response = self._simulate_user_input(strategy) 
            print(f"[مشترک]: {user_response}")
            
            # پردازش و تولید پاسخ
            bot_response = self.dialogue_manager.handle_response(user_response, strategy, customer)
            print(f"[ربات]: {bot_response}")
            
            conversation_turns += 1
            
            # شرط پایان مکالمه
            if any(word in user_response for word in ["خداحافظ", "تموم", "باشه"]):
                call_active = False
        
        # 3. ثبت نتایج
        self.db.update_call_log(customer.customer_id, f"تماس انجام شد. نتیجه: {'پرداخت وعده داده شد' if 'پرداختم' in user_response else 'پیگیری لازم دارد'}")
        logger.info(f"--- پایان تماس با {customer.full_name} ---\n")

    def _simulate_user_input(self, strategy: CallStrategy) -> str:
        """
        شبیه‌ساز ورودی کاربر برای تست
        در محیط واقعی: این بخش توسط موتور STT پر می‌شود
        """
        responses = {
            "حقوقی_نهایی": ["آقا من پول ندارم!", "چرا قطع می‌کنید؟", "الان واریز می‌کنم"],
            "اخطار_قطع": ["میشه قسط بندید؟", "قبض اشتباه اومده", "چقدر مهلت دارم؟"],
            "یادآوری_پرداخت": ["چقدر بود؟", "فراموش کرده بودم", "شب واریز می‌کنم"],
            "خوش‌آمدگویی_پرداخت": ["باشه چشم", "الان چک می‌کنم", "ممنون"]
        }
        possible_responses = responses.get(strategy.script_template, ["بله؟", "بفرمایید"])
        return random.choice(possible_responses)

    def run_campaign(self, target_zone: str = None):
        """اجرای کمپین تماس برای یک منطقه خاص یا همه"""
        logger.info(f"شروع کمپین تماس هوشمند برای منطقه: {target_zone or 'کل شهرستان ایلام'}")
        
        conn = sqlite3.connect(self.db.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM customers WHERE debt_amount > 0"
        if target_zone:
            query += f" AND zone = '{target_zone}'"
            
        cursor.execute(query)
        customers = cursor.fetchall()
        conn.close()
        
        for cust in customers:
            self.make_outbound_call(cust['phone_number'])
            # تاخیر بین تماس‌ها برای شبیه‌سازی رفتار انسانی
            import time
            time.sleep(2) 

# ==============================================================================
# 6. نقطه ورود اجرایی (Main Entry Point)
# ==============================================================================

if __name__ == "__main__":
    print("="*80)
    print("سامانه هوشمند وصول مطالبات - شرکت توزیع نیروی برق استان ایلام")
    print("نسخه عملیاتی v2.0 - کاملاً مستقل و درون‌برنامه‌ای")
    print("="*80)
    
    # ایجاد نمونه عامل
    agent = PowerCollectionAgent()
    
    # اجرای تست روی یک مشترک خاص (برای نمایش)
    # در حالت واقعی: agent.run_campaign(target_zone="مرکزی")
    agent.make_outbound_call("09183001002") # مشترک بدهکار با بدهی بالا
    
    # اجرای کمپین روی همه
    # agent.run_campaign()
