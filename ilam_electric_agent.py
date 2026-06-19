"""
سامانه هوشمند تماس صوتی خودکار - شرکت توزیع نیروی برق استان ایلام
اپراتور هوشمند وصول مطالبات (Power Collection Agent)
نسخه عملیاتی v3.0 - کاملاً مستقل و درون‌برنامه‌ای

توسعه یافته توسط: عرفان رجبی - شرکت تلاشگر
"""

import sqlite3
import json
import logging
import time
import random
import os
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

# تنظیمات لاگ‌گیری
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/electric_agent_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# اطمینان از وجود پوشه لاگ
os.makedirs('logs', exist_ok=True)


class CallStrategy(Enum):
    """سطوح استراتژی مکالمه بر اساس بدهی و رفتار مشترک"""
    FRIENDLY = "دوستانه"
    POLITE = "محترمانه"
    FORMAL_WARNING = "رسمی و هشداردهنده"
    LEGAL_ACTION = "قاطع و حقوقی"


@dataclass
class CustomerData:
    """ساختار داده‌های مشترک"""
    customer_id: str
    full_name: str
    address: str
    phone_number: str
    debt_amount: float
    last_bill_date: str
    consumption_avg: float
    payment_history: List[str]
    status: str
    zone: str
    last_call_date: Optional[str] = None
    call_notes: Optional[str] = None


class IlamPowerDB:
    """مدیریت پایگاه داده محلی و همگام‌سازی با سامانه eserv"""
    
    def __init__(self, db_path: str = "ilam_power_customers.db"):
        self.db_path = db_path
        self._init_database()
        logger.info(f"پایگاه داده محلی برق ایلام در {db_path} آماده شد.")
    
    def _init_database(self):
        """ایجاد جداول لازم در صورت عدم وجود"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول مشترکین
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                address TEXT,
                phone_number TEXT,
                debt_amount REAL DEFAULT 0.0,
                last_bill_date TEXT,
                consumption_avg REAL,
                payment_history TEXT,
                status TEXT,
                zone TEXT,
                last_call_date TEXT,
                call_notes TEXT
            )
        ''')
        
        # جدول تاریخچه تماس‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                phone_number TEXT,
                timestamp TEXT,
                duration_seconds INTEGER,
                result TEXT,
                notes TEXT,
                strategy_used TEXT
            )
        ''')
        
        # جدول وعده‌های پرداخت
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_promises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                promise_date TEXT,
                promised_amount REAL,
                recorded_at TEXT,
                fulfilled BOOLEAN DEFAULT FALSE
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def seed_sample_data(self):
        """بارگذاری داده‌های نمونه برای تست (شبیه‌سازی داده‌های اسرو)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sample_data = [
            ("1402050101", "محمد رضایی", "ایلام، بلوار معلم، کوچه شهید حسینی", "09183001001", 500000.0, "1402/11/10", 450, '["خوش‌حساب"]', "عادی", "مرکزی"),
            ("1402050102", "علی کریمی", "ایلام، محله زرجاب، کوچه امام حسین", "09183001002", 15000000.0, "1402/11/15", 600, '["بدحساب", "اخطار کتبی"]', "اخطار نهایی", "زرجاب"),
            ("1402050103", "فاطمه احمدی", "ایلام، شهرک بهشتی، خیابان گلستان", "09183001003", 2500000.0, "1402/11/20", 320, '["تاخیر کم"]', "هشدار", "شهرک بهشتی"),
            ("1402050104", "حسین مرادی", "ایلام، فرهنگیان، بلوار دانشجو", "09183001004", 8500000.0, "1402/10/05", 700, '["بدحساب", "پرونده قضایی"]', "قطع انشعاب", "فرهنگیان"),
            ("1402050105", "زهرا کریمی", "ایلام، میدان آزادی، خیابان طالقانی", "09183001005", 0.0, "1402/11/25", 280, '["خوش‌حساب"]', "عادی", "مرکزی"),
        ]
        
        for data in sample_data:
            cursor.execute('''
                INSERT OR REPLACE INTO customers 
                (customer_id, full_name, address, phone_number, debt_amount, last_bill_date, 
                 consumption_avg, payment_history, status, zone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
        
        conn.commit()
        conn.close()
        logger.info("داده‌های نمونه مشترکین برق ایلام با موفقیت بارگذاری شد.")
    
    def get_customer(self, phone_number: str) -> Optional[CustomerData]:
        """دریافت اطلاعات مشترک بر اساس شماره تلفن"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM customers WHERE phone_number = ?", (phone_number,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return CustomerData(
                customer_id=row[0], full_name=row[1], address=row[2], phone_number=row[3],
                debt_amount=row[4], last_bill_date=row[5], consumption_avg=row[6],
                payment_history=json.loads(row[7]), status=row[8], zone=row[9],
                last_call_date=row[10], call_notes=row[11]
            )
        return None
    
    def log_call(self, customer_id: str, phone_number: str, duration: int, 
                 result: str, notes: str, strategy: str):
        """ثبت تاریخچه تماس"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO call_logs 
            (customer_id, phone_number, timestamp, duration_seconds, result, notes, strategy_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (customer_id, phone_number, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
              duration, result, notes, strategy))
        
        # بروزرسانی آخرین تماس مشتری
        cursor.execute('''
            UPDATE customers SET last_call_date = ?, call_notes = ?
            WHERE customer_id = ?
        ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), notes, customer_id))
        
        conn.commit()
        conn.close()
    
    def register_payment_promise(self, customer_id: str, date: str, amount: float):
        """ثبت وعده پرداخت"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO payment_promises (customer_id, promise_date, promised_amount, recorded_at)
            VALUES (?, ?, ?, ?)
        ''', (customer_id, date, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        logger.info(f"وعده پرداخت برای مشترک {customer_id} ثبت شد: {amount} ریال تا تاریخ {date}")
    
    def sync_from_eserv(self):
        """
        شبیه‌سازی همگام‌سازی با سامانه eserv.bargh-ilam.ir
        در نسخه واقعی، این متد به API واقعی متصل می‌شود.
        """
        logger.info("در حال همگام‌سازی با سامانه eserv.bargh-ilam.ir ...")
        time.sleep(1.5)  # شبیه‌سازی تاخیر شبکه
        logger.info("همگام‌سازی با موفقیت انجام شد. (نسخه نمایشی)")


class CollectionStrategyEngine:
    """موتور تعیین استراتژی مکالمه بر اساس وضعیت مشترک"""
    
    @staticmethod
    def determine_strategy(customer: CustomerData) -> Tuple[CallStrategy, str]:
        """تعیین استراتژی و لحن مکالمه"""
        debt = customer.debt_amount
        
        if debt == 0:
            return CallStrategy.FRIENDLY, "تماس رضایت‌مندی و تشکر"
        elif debt < 1_000_000:
            return CallStrategy.FRIENDLY, "یادآوری دوستانه"
        elif debt < 5_000_000 and "اخطار کتبی" not in customer.payment_history:
            return CallStrategy.POLITE, "هشدار محترمانه درباره جریمه"
        elif debt >= 5_000_000 or "اخطار کتبی" in customer.payment_history:
            return CallStrategy.FORMAL_WARNING, "هشدار جدی و پیشنهاد قسط"
        elif "پرونده قضایی" in customer.payment_history or customer.status == "قطع انشعاب":
            return CallStrategy.LEGAL_ACTION, "اقدام نهایی حقوقی قبل از قطع"
        
        return CallStrategy.POLITE, "بررسی وضعیت"


class DialogueManager:
    """مدیریت هوشمند مکالمه و تولید پاسخ‌های طبیعی"""
    
    def __init__(self):
        self.conversation_memory = {}
    
    def generate_greeting(self, customer: CustomerData, strategy: CallStrategy) -> str:
        """تولید پیام خوش‌آمدگویی متناسب با استراتژی"""
        name = customer.full_name.split()[0]  # استفاده از نام کوچک
        
        greetings = {
            CallStrategy.FRIENDLY: [
                f"سلام وقت بخیر آقای/خانم {name}، از بخش خدمات مشترکین برق ایلام تماس می‌گیرم.",
                f"سلام {name} عزیز، روزتون بخیر. از شرکت توزیع برق شهرستان ایلام هستم."
            ],
            CallStrategy.POLITE: [
                f"سلام عرض می‌کنم آقای/خانم {name}، از واحد وصول مطالبات برق ایلام تماس می‌گیرم.",
                f"با سلام و احترام، {name} گرامی، از شرکت توزیع نیروی برق استان ایلام مزاحم می‌شم."
            ],
            CallStrategy.FORMAL_WARNING: [
                f"سلام، آقای/خانم {name}. از بخش حقوقی و وصول مطالبات شرکت توزیع نیروی برق استان ایلام تماس می‌گیرم.",
                f"با سلام، {name} عزیز. این تماس از سوی مدیریت توزیع برق شهرستان ایلام در خصوص بدهی معوقه شماست."
            ],
            CallStrategy.LEGAL_ACTION: [
                f"آقای/خانم {name}، از واحد اجراییات شرکت توزیع نیروی برق استان ایلام تماس می‌گیرم.",
                f"سلام، این تماس رسمی از طرف شرکت برق ایلام در مورد پرونده بدهی شماست."
            ]
        }
        
        base_msg = random.choice(greetings.get(strategy, greetings[CallStrategy.POLITE]))
        
        if strategy == CallStrategy.FORMAL_WARNING:
            base_msg += f" بدهی معوقه شما به مبلغ {int(customer.debt_amount):,} ریال رسیده و متاسفانه در لیست قطع انشعاب قرار گرفته‌اید."
        elif strategy == CallStrategy.LEGAL_ACTION:
            base_msg += f" با توجه به بدهی سنگین {int(customer.debt_amount):,} ریالی و اخطارهای قبلی، پرونده شما در آستانه اقدام قانونی و قطع دائمی است."
        elif customer.debt_amount > 0:
            base_msg += f" جهت یادآوری، مبلغ {int(customer.debt_amount):,} ریال بدهی قبض برق شما معوق شده است."
            
        return base_msg
    
    def process_user_input(self, user_text: str, customer: CustomerData, strategy: CallStrategy) -> str:
        """پردازش ورودی کاربر و تولید پاسخ هوشمند (شبیه‌سازی NLU)"""
        user_text = user_text.lower()
        
        # تشخیص نیت‌ها (در نسخه واقعی از مدل‌های NLP استفاده می‌شود)
        if any(word in user_text for word in ["قسط", "قسط‌بندی", "قسمت", "مدت"]):
            return self._handle_installment_request(customer, strategy)
        
        elif any(word in user_text for word in ["اعتراض", "اشتباه", "مصرف", "قبض"]):
            return self._handle_complaint(customer)
        
        elif any(word in user_text for word in ["پرداخت", "واریز", "چشم", "الان"]):
            return self._handle_payment_promise(customer)
        
        elif any(word in user_text for word in ["قطع", "برق", "وصل"]):
            return self._handle_power_outage(customer)
        
        elif any(word in user_text for word in ["انسان", "اپراتور", "مسئول"]):
            return "درخواست شما برای صحبت با اپراتور انسانی ثبت شد. لطفاً منتظر بمانید تا به صف انتظار منتقل شوید."
        
        else:
            return self._default_response(strategy)
    
    def _handle_installment_request(self, customer: CustomerData, strategy: CallStrategy) -> str:
        """مدیریت درخواست قسط‌بندی"""
        if strategy in [CallStrategy.FORMAL_WARNING, CallStrategy.LEGAL_ACTION]:
            months = 4 if customer.debt_amount > 10_000_000 else 3
            return (f"بله، با توجه به مبلغ بدهی شما، امکان قسط‌بندی تا {months} ماه وجود دارد. "
                    f"اما باید همین امروز برای تنظیم قرارداد به دفتر بلوار معلم مراجعه کنید. "
                    f"آیا می‌توانید فردا تشریف بیاورید؟")
        else:
            return "برای مبالغ پایین‌تر معمولاً نیاز به قسط‌بندی نیست، اما اگر تمایل دارید می‌توانید به دفتر امور مشترکین مراجعه کنید."
    
    def _handle_complaint(self, customer: CustomerData) -> str:
        """مدیریت اعتراض به قبض"""
        return ("اگر اعتراض به مبلغ قبض دارید، می‌توانید درخواست بازدید کنتور دهید. "
                "اما تا زمان تعیین تکلیف، باید حداقل ۵۰ درصد مبلغ قبض را پرداخت کنید تا قطع نشوید. "
                "آیا مایلید راهنمایی کنم چطور درخواست بازدید بدهید؟")
    
    def _handle_payment_promise(self, customer: CustomerData) -> str:
        """مدیریت وعده پرداخت"""
        # ثبت وعده در دیتابیس (شبیه‌سازی)
        promise_date = (datetime.now() + timedelta(days=2)).strftime("%Y/%m/%d")
        # در نسخه واقعی تاریخ دقیق از کاربر پرسیده می‌شود
        return (f"بسیار عالی. سیستم بانکی ممکن است تا ۲۴ ساعت تاخیر داشته باشد. "
                f"وعده پرداخت شما تا تاریخ {promise_date} ثبت شد. "
                f"اگر تا آن زمان پیامک تایید نیامد، لطفاً فیش واریزی را به دفتر امور مشترکین ببرید.")
    
    def _handle_power_outage(self, customer: CustomerData) -> str:
        """مدیریت سوال درباره قطع برق"""
        if customer.status == "قطع انشعاب":
            return "انشعاب شما به دلیل بدهی معوقه قطع شده است. پس از تسویه حساب کامل، حداکثر تا ۴۸ ساعت برق شما وصل خواهد شد."
        else:
            return "اگر قطعی برق در منطقه شما وجود دارد، احتمالاً ناشی از خرابی شبکه است. لطفاً با شماره ۱۲۱ تماس بگیرید یا از طریق سامانه اسرو اعلام خرابی کنید."
    
    def _default_response(self, strategy: CallStrategy) -> str:
        """پاسخ پیش‌فرض"""
        responses = {
            CallStrategy.FRIENDLY: "متوجه شدم. آیا سوال دیگری دارید؟",
            CallStrategy.POLITE: "بفرمایید، در خدمتم.",
            CallStrategy.FORMAL_WARNING: "لطفاً در مورد نحوه پرداخت بدهی تصمیم بگیرید.",
            CallStrategy.LEGAL_ACTION: "زمان برای حل این موضوع محدود است. لطفاً سریعاً اقدام کنید."
        }
        return responses.get(strategy, "متوجه نشدم، لطفاً واضح‌تر بفرمایید.")


class InternalVoIPCore:
    """
    هسته نرم‌افزاری VoIP (شبیه‌سازی شده برای محیط بدون سخت‌افزار)
    در محیط عملیاتی، این کلاس به PJSIP یا Asterisk متصل می‌شود.
    """
    
    def __init__(self):
        self.is_call_active = False
        self.call_duration = 0
        logger.info("ماژول VoIP نرم‌افزاری (SIP Stack) با موفقیت بارگذاری شد.")
    
    def make_call(self, phone_number: str) -> bool:
        """شبیه‌سازی برقراری تماس خروجی"""
        logger.info(f"--- شروع تماس با شماره: {phone_number} ---")
        self.is_call_active = True
        self.call_duration = 0
        
        # شبیه‌سازی وضعیت‌های مختلف خط
        outcomes = ["connected", "busy", "no_answer", "connected"]
        result = random.choice(outcomes)
        
        if result == "busy":
            logger.info("خط اشغال است.")
            self.is_call_active = False
            return False
        elif result == "no_answer":
            logger.info("پاسخی دریافت نشد.")
            self.is_call_active = False
            return False
        
        logger.info("تماس برقرار شد.")
        return True
    
    def receive_audio(self) -> str:
        """شبیه‌سازی دریافت صدا و تبدیل به متن (STT)"""
        if not self.is_call_active:
            return ""
        
        # شبیه‌سازی ورودی کاربر
        inputs = [
            "میشه قسط بندید؟",
            "این قبض اشتباه اومده، مصرف من اینقدر نبوده!",
            "چشم الان واریز می‌کنم.",
            "برق ما قطعه، کی وصل میشه؟",
            "می‌خوام با یه نفر صحبت کنم."
        ]
        time.sleep(1)  # شبیه‌سازی تاخیر مکالمه
        self.call_duration += 1
        return random.choice(inputs)
    
    def send_audio(self, text: str):
        """شبیه‌سازی تبدیل متن به صدا و پخش (TTS)"""
        if not self.is_call_active:
            return
        logger.info(f"[ربات]: {text}")
        time.sleep(2)  # شبیه‌سازی زمان صحبت ربات
        self.call_duration += 2
    
    def end_call(self):
        """پایان تماس"""
        self.is_call_active = False
        logger.info(f"تماس پایان یافت. مدت زمان: {self.call_duration} ثانیه")
        return self.call_duration


class PowerCollectionAgent:
    """عامل اصلی هماهنگ‌کننده تمام اجزای سیستم"""
    
    def __init__(self):
        self.db = IlamPowerDB()
        self.strategy_engine = CollectionStrategyEngine()
        self.dialogue_manager = DialogueManager()
        self.voip_core = InternalVoIPCore()
        
        # بارگذاری داده‌های نمونه اگر دیتابیس خالی باشد
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM customers")
        if cursor.fetchone()[0] == 0:
            self.db.seed_sample_data()
        conn.close()
    
    def run_campaign(self, target_zone: Optional[str] = None):
        """اجرای کمپین تماس برای یک منطقه خاص یا همه مناطق"""
        logger.info("="*80)
        logger.info("سامانه هوشمند وصول مطالبات - شرکت توزیع نیروی برق استان ایلام")
        logger.info("نسخه عملیاتی v3.0 - کاملاً مستقل و درون‌برنامه‌ای")
        logger.info("="*80)
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        query = "SELECT phone_number FROM customers WHERE debt_amount > 0"
        params = []
        
        if target_zone:
            query += " AND zone = ?"
            params.append(target_zone)
            logger.info(f"شروع کمپین تماس برای منطقه: {target_zone}")
        else:
            logger.info("شروع کمپین تماس عمومی برای تمام بدهکاران")
        
        cursor.execute(query, params)
        phone_numbers = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not phone_numbers:
            logger.info("هیچ مشترک بدهکاری برای تماس یافت نشد.")
            return
        
        for phone in phone_numbers:
            self.make_outbound_call(phone)
            time.sleep(2)  # فاصله بین تماس‌ها
    
    def make_outbound_call(self, phone_number: str):
        """انجام یک تماس خروجی کامل"""
        customer = self.db.get_customer(phone_number)
        if not customer:
            logger.warning(f"مشترکی با شماره {phone_number} یافت نشد.")
            return
        
        if customer.debt_amount <= 0:
            return  # عدم تماس با مشترکین بدون بدهی در کمپین وصول
        
        success = self.voip_core.make_call(phone_number)
        if not success:
            self.db.log_call(
                customer.customer_id, phone_number, 0, 
                "عدم برقراری تماس", "خط اشغال یا عدم پاسخ", "-"
            )
            return
        
        # تعیین استراتژی
        strategy, strategy_desc = self.strategy_engine.determine_strategy(customer)
        logger.info(f"استراتژی انتخاب شده: {strategy_desc} | سطح تشدید: {strategy.name}")
        
        # شروع مکالمه
        greeting = self.dialogue_manager.generate_greeting(customer, strategy)
        self.voip_core.send_audio(greeting)
        
        # حلقه مکالمه (حداکثر ۵ دور)
        for _ in range(5):
            if not self.voip_core.is_call_active:
                break
                
            user_input = self.voip_core.receive_audio()
            if not user_input:
                break
            
            response = self.dialogue_manager.process_user_input(user_input, customer, strategy)
            self.voip_core.send_audio(response)
            
            # بررسی پایان مکالمه (مثلاً بعد از وعده پرداخت)
            if "وعده پرداخت" in response or "ثبت شد" in response:
                # استخراج فرضی تاریخ و مبلغ (در نسخه واقعی از NLP استفاده می‌شود)
                self.db.register_payment_promise(customer.customer_id, "1403/02/01", customer.debt_amount / 2)
                break
        
        duration = self.voip_core.end_call()
        self.db.log_call(
            customer.customer_id, phone_number, duration, 
            "تماس موفق", f"استراتژی: {strategy.name}", "پیگیری لازم دارد"
        )


def main():
    """نقطه ورود اصلی برنامه"""
    try:
        agent = PowerCollectionAgent()
        
        # اجرای کمپین برای منطقه زرجاب به عنوان نمونه
        agent.run_campaign(target_zone="زرجاب")
        
        # یا اجرای عمومی:
        # agent.run_campaign()
        
    except KeyboardInterrupt:
        logger.info("توسط کاربر متوقف شد.")
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}", exc_info=True)


if __name__ == "__main__":
    main()
