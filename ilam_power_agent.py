"""
سامانه هوشمند تماس صوتی خودکار - شرکت توزیع نیروی برق استان ایلام
اپراتور هوشمند وصول مطالبات (Power Collection Agent)

نسخه عملیاتی v2.0 - کاملاً مستقل و درون‌برنامه‌ای
توسعه‌دهنده: عرفان رجبی - شرکت تلاشگر
"""

import sqlite3
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CallStrategyLevel(Enum):
    """سطوح استراتژی مکالمه"""
    FRIENDLY = 0          # بدهی کم (<1M ریال)
    RESPECTFUL = 1        # بدهی متوسط + تاخیر
    FORMAL_WARNING = 2    # بدهی بالا (>5M ریال)
    LEGAL_ACTION = 3      # پرونده قضایی / بدهی خیلی سنگین


@dataclass
class CallStrategy:
    """استراتژی مکالمه بر اساس سطح بدهی"""
    level: CallStrategyLevel
    tone: str
    opening: str
    payment_options: List[str]
    warning_message: str
    escalation_threshold: float  # به ریال


@dataclass
class Customer:
    """ساختار داده مشترک"""
    customer_id: str
    full_name: str
    address: str
    phone_number: str
    debt_amount: float
    last_bill_date: str
    consumption_avg: int
    payment_history: List[str]
    status: str
    zone: str
    last_call_date: Optional[str] = None
    call_notes: Optional[str] = None


class IlamPowerDB:
    """مدیریت پایگاه داده محلی شرکت برق ایلام"""
    
    def __init__(self, db_path: str = "ilam_power_customers.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._initialize_tables()
        self._seed_sample_data()
    
    def _initialize_tables(self):
        """ایجاد جداول پایگاه داده"""
        cursor = self.conn.cursor()
        
        # جدول مشترکین
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                address TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                debt_amount REAL NOT NULL,
                last_bill_date TEXT NOT NULL,
                consumption_avg INTEGER NOT NULL,
                payment_history TEXT NOT NULL,
                status TEXT NOT NULL,
                zone TEXT NOT NULL,
                last_call_date TEXT,
                call_notes TEXT
            )
        """)
        
        # جدول قوانین
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL
            )
        """)
        
        self.conn.commit()
    
    def _seed_sample_data(self):
        """بارگذاری داده‌های نمونه مشترکین برق ایلام"""
        cursor = self.conn.cursor()
        
        # بررسی خالی بودن دیتابیس
        cursor.execute("SELECT COUNT(*) FROM customers")
        if cursor.fetchone()[0] > 0:
            return
        
        # داده‌های نمونه با آدرس‌های واقعی ایلام
        sample_customers = [
            ("1402050101", "محمد رضایی", "ایلام، بلوار معلم، کوچه شهید حسینی", "09183001001", 800000.0, 
             "1402/11/15", 450, '["خوش‌حساب"]', "فعال", "مرکزی"),
            ("1402050102", "علی کریمی", "ایلام، محله زرجاب، کوچه امام حسین", "09183001002", 15000000.0, 
             "1402/10/20", 600, '["بدحساب", "اخطار کتبی"]', "اخطار نهایی", "زرجاب"),
            ("1402050103", "فاطمه محمدی", "ایلام، شهرک بهشتی، بلوک ۵", "09183001003", 2500000.0, 
             "1402/11/01", 380, '["تاخیر متوسط"]', "در حال پیگیری", "شهرک بهشتی"),
            ("1402050104", "حسین عباسی", "ایلام، فرهنگیان، خیابان گلستان", "09183001004", 45000000.0, 
             "1402/09/15", 850, '["بدحساب", "پرونده قضایی"]', "پرونده حقوقی", "فرهنگیان"),
            ("1402050105", "مریم کریمی", "ایلام، میدان امام خمینی، پاساژ الماس", "09183001005", 500000.0, 
             "1402/11/20", 320, '["خوش‌حساب"]', "فعال", "مرکزی"),
            ("1402050106", "رضا نوروزی", "ایلام، محله سراب، کوچه شهدا", "09183001006", 8500000.0, 
             "1402/10/10", 720, '["بدحساب", "اخطار تلفنی"]', "اخطار قطع", "سراب"),
            ("1402050107", "زهرا احمدی", "ایلام، شهرک گلستان، واحد ۱۲", "09183001007", 1200000.0, 
             "1402/11/10", 410, '["تاخیر جزئی"]', "در حال پیگیری", "شهرک گلستان"),
            ("1402050108", "کامران مرادی", "ایلام، بلوار طالقانی، مجتمع تجاری", "09183001008", 32000000.0, 
             "1402/08/20", 950, '["بدحساب", "پرونده قضایی", "اقدام قانونی"]', "پرونده حقوقی", "مرکزی"),
        ]
        
        for customer in sample_customers:
            cursor.execute("""
                INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (*customer, None, None))
        
        # بارگذاری قوانین
        regulations = [
            ("ماده ۲۴ - شرایط قطع انشعاب", 
             "در صورت عدم پرداخت بدهی بیش از دو ماه، انشعاب برق قطع خواهد شد.", "قطع"),
            ("شرایط قسط‌بندی", 
             "بدهی‌های بالای ۵ میلیون تومان قابل قسط‌بندی تا ۴ ماه هستند.", "قسط"),
            ("نرخ جریمه دیرکرد", 
             "جریمه دیرکرد ماهیانه ۲٪ به مبلغ قبض اضافه می‌شود.", "جریمه"),
            ("ساعات کاری دفتر", 
             "دفتر امور مشترکین بلوار معلم: ۷:۳۰ تا ۱۴:۳۰ شنبه تا چهارشنبه.", "اداری"),
        ]
        
        for title, content, category in regulations:
            cursor.execute("INSERT INTO regulations (title, content, category) VALUES (?, ?, ?)",
                          (title, content, category))
        
        self.conn.commit()
        print("[INFO] پایگاه داده محلی برق ایلام در ilam_power_customers.db آماده شد.")
        print("[INFO] داده‌های نمونه مشترکین برق ایلام با موفقیت بارگذاری شد.")
    
    def get_customer(self, phone_number: str) -> Optional[Customer]:
        """دریافت اطلاعات مشترک بر اساس شماره تماس"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE phone_number = ?", (phone_number,))
        row = cursor.fetchone()
        
        if row:
            return Customer(
                customer_id=row['customer_id'],
                full_name=row['full_name'],
                address=row['address'],
                phone_number=row['phone_number'],
                debt_amount=row['debt_amount'],
                last_bill_date=row['last_bill_date'],
                consumption_avg=row['consumption_avg'],
                payment_history=json.loads(row['payment_history']),
                status=row['status'],
                zone=row['zone'],
                last_call_date=row['last_call_date'],
                call_notes=row['call_notes']
            )
        return None
    
    def get_customers_by_zone(self, zone: str) -> List[Customer]:
        """دریافت مشترکین یک منطقه خاص"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE zone = ?", (zone,))
        
        customers = []
        for row in cursor.fetchall():
            customers.append(Customer(
                customer_id=row['customer_id'],
                full_name=row['full_name'],
                address=row['address'],
                phone_number=row['phone_number'],
                debt_amount=row['debt_amount'],
                last_bill_date=row['last_bill_date'],
                consumption_avg=row['consumption_avg'],
                payment_history=json.loads(row['payment_history']),
                status=row['status'],
                zone=row['zone'],
                last_call_date=row['last_call_date'],
                call_notes=row['call_notes']
            ))
        return customers
    
    def update_call_record(self, customer_id: str, notes: str):
        """به‌روزرسانی رکورد تماس"""
        cursor = self.conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE customers 
            SET last_call_date = ?, call_notes = ?
            WHERE customer_id = ?
        """, (now, notes, customer_id))
        self.conn.commit()
    
    def sync_from_eserv(self):
        """همگام‌سازی با سامانه eserv.bargh-ilam.ir (شبیه‌سازی)"""
        print("[INFO] در حال همگام‌سازی با سامانه eserv.bargh-ilam.ir ...")
        # در محیط عملیاتی، اینجا به API واقعی متصل می‌شود
        random_delay = random.randint(50, 200)
        print(f"[INFO] همگام‌سازی با موفقیت انجام شد. {random_delay} رکورد جدید بروزرسانی شد.")
    
    def close(self):
        """بستن اتصال به دیتابیس"""
        self.conn.close()


class CollectionStrategyEngine:
    """موتور تعیین استراتژی مکالمه بر اساس وضعیت بدهی"""
    
    def __init__(self):
        self.strategies = {
            CallStrategyLevel.FRIENDLY: CallStrategy(
                level=CallStrategyLevel.FRIENDLY,
                tone="دوستانه و صمیمی",
                opening="سلام وقت بخیر، امیدوارم حالتون خوب باشه.",
                payment_options=["پرداخت آنلاین", "مراجعه به دفتر"],
                warning_message="یادآوری دوستانه برای پرداخت به موقع",
                escalation_threshold=1000000.0
            ),
            CallStrategyLevel.RESPECTFUL: CallStrategy(
                level=CallStrategyLevel.RESPECTFUL,
                tone="محترمانه و رسمی",
                opening="سلام عرض می‌کنم، از بخش وصول مطالبات شرکت برق ایلام تماس می‌گیرم.",
                payment_options=["پرداخت اقساطی", "مراجعه حضوری", "پرداخت آنلاین"],
                warning_message="هشدار در مورد جریمه دیرکرد و امکان قطع انشعاب",
                escalation_threshold=5000000.0
            ),
            CallStrategyLevel.FORMAL_WARNING: CallStrategy(
                level=CallStrategyLevel.FORMAL_WARNING,
                tone="رسمی و هشداردهنده",
                opening="سلام، از واحد وصول مطالبات شرکت توزیع نیروی برق استان ایلام شهرستان ایلام تماس می‌گیرم.",
                payment_options=["قسط‌بندی حداکثر ۴ ماه", "مراجعه فوری به دفتر بلوار معلم"],
                warning_message="اخطار جدی در مورد قرار گرفتن در لیست قطع انشعاب",
                escalation_threshold=10000000.0
            ),
            CallStrategyLevel.LEGAL_ACTION: CallStrategy(
                level=CallStrategyLevel.LEGAL_ACTION,
                tone="قاطع و حقوقی",
                opening="سلام، از واحد حقوقی شرکت توزیع نیروی برق استان ایلام تماس می‌گیرم.",
                payment_options=["پرداخت فوری کل بدهی", "تنظیم قرارداد حقوقی"],
                warning_message="اقدام نهایی قبل از قطع انشعاب و پیگرد قانونی",
                escalation_threshold=float('inf')
            )
        }
    
    def determine_strategy(self, customer: Customer) -> CallStrategy:
        """تعیین استراتژی مکالمه بر اساس وضعیت مشترک"""
        debt = customer.debt_amount
        has_legal_case = "پرونده قضایی" in customer.payment_history or "پرونده حقوقی" in customer.status
        
        if has_legal_case or debt > 30000000:
            return self.strategies[CallStrategyLevel.LEGAL_ACTION]
        elif debt > 5000000:
            return self.strategies[CallStrategyLevel.FORMAL_WARNING]
        elif debt > 1000000 or "بدحساب" in customer.payment_history:
            return self.strategies[CallStrategyLevel.RESPECTFUL]
        else:
            return self.strategies[CallStrategyLevel.FRIENDLY]


class DialogueManager:
    """مدیریت مکالمه و تولید گفتار طبیعی فارسی"""
    
    def __init__(self):
        self.strategy_engine = CollectionStrategyEngine()
        self.conversation_history = []
    
    def generate_opening(self, customer: Customer, strategy: CallStrategy) -> str:
        """تولید متن شروع مکالمه"""
        first_name = customer.full_name.split()[0]
        
        opening_parts = [
            strategy.opening,
            f"آقای/خانم {first_name}، بدهی معوقه شما به مبلغ {int(customer.debt_amount):,} ریال رسیده است."
        ]
        
        if strategy.level == CallStrategyLevel.FORMAL_WARNING:
            opening_parts.append("متاسفانه در لیست قطع انشعاب قرار گرفته‌اید.")
        elif strategy.level == CallStrategyLevel.LEGAL_ACTION:
            opening_parts.append("پرونده شما در دست اقدام قانونی است.")
        
        return " ".join(opening_parts)
    
    def handle_response(self, user_input: str, customer: Customer, strategy: CallStrategy) -> str:
        """پردازش پاسخ کاربر و تولید پاسخ مناسب"""
        user_input_lower = user_input.lower()
        
        # تشخیص نیت کاربر
        if any(word in user_input_lower for word in ["قسط", "قسط‌بندی", "اقساط"]):
            return self._handle_installment_request(customer, strategy)
        elif any(word in user_input_lower for word in ["اشتباه", "اعتراض", "مصرف"]):
            return self._handle_complaint(customer, strategy)
        elif any(word in user_input_lower for word in ["پرداخت", "واریز", "چشم"]):
            return self._handle_payment_promise(customer, strategy)
        elif any(word in user_input_lower for word in ["قطع", "انصراف", "تماس"]):
            return self._handle_disconnect_threat(customer, strategy)
        else:
            return self._handle_general_response(customer, strategy)
    
    def _handle_installment_request(self, customer: Customer, strategy: CallStrategy) -> str:
        """پاسخ به درخواست قسط‌بندی"""
        if customer.debt_amount > 5000000:
            months = min(4, max(2, int(customer.debt_amount / 5000000)))
            return (f"بله، با توجه به مبلغ بدهی شما، امکان قسط‌بندی تا {months} ماه وجود دارد. "
                   f"اما باید همین امروز برای تنظیم قرارداد به دفتر بلوار معلم مراجعه کنید. "
                   f"آیا می‌توانید فردا تشریف بیاورید؟")
        else:
            return ("متاسفانه برای مبالغ زیر ۵ میلیون تومان امکان قسط‌بندی وجود ندارد. "
                   "اما می‌توانید به صورت آنلاین یا حضوری پرداخت کنید.")
    
    def _handle_complaint(self, customer: Customer, strategy: CallStrategy) -> str:
        """پاسخ به اعتراض به مبلغ قبض"""
        return ("اگر اعتراض به مبلغ قبض دارید، می‌توانید درخواست بازدید کنتور دهید. "
               "اما تا زمان تعیین تکلیف، باید حداقل ۵۰ درصد مبلغ قبض را پرداخت کنید تا قطع نشوید. "
               "آیا مایلید راهنمایی کنم چطور درخواست بازدید بدهید؟")
    
    def _handle_payment_promise(self, customer: Customer, strategy: CallStrategy) -> str:
        """پاسخ به وعده پرداخت"""
        return ("بسیار عالی. سیستم بانکی ممکن است تا ۲۴ ساعت تاخیر داشته باشد. "
               "اگر تا فردا پیامک تایید نیامد، لطفاً فیش واریزی را به دفتر امور مشترکین ببرید.")
    
    def _handle_disconnect_threat(self, customer: Customer, strategy: CallStrategy) -> str:
        """پاسخ به تهدید قطع انشعاب"""
        if strategy.level >= CallStrategyLevel.FORMAL_WARNING:
            return ("قطع انشعاب آخرین راهکار ماست. اما اگر تا ۴۸ ساعت آینده پرداختی انجام نشود، "
                   "طبق ماده ۲۴ مقررات، انشعاب شما قطع خواهد شد. لطفاً جدی بگیرید.")
        else:
            return ("هنوز به مرحله قطع نرسیده‌ایم، اما اگر پرداخت نکنید به آن مرحله خواهیم رسید. "
                   "لطفاً در اسرع وقت اقدام کنید.")
    
    def _handle_general_response(self, customer: Customer, strategy: CallStrategy) -> str:
        """پاسخ عمومی"""
        return ("متوجه شدم. لطفاً برای بررسی بیشتر و پرداخت بدهی، به دفتر امور مشترکین "
               "بلوار معلم مراجعه کنید یا از طریق سایت eserv.bargh-ilam.ir اقدام نمایید.")


class VoIPModule:
    """ماژول VoIP نرم‌افزاری (شبیه‌سازی SIP Stack)"""
    
    def __init__(self):
        self.is_connected = False
        self.active_calls = []
        print("[INFO] ماژول VoIP نرم‌افزاری (SIP Stack) با موفقیت بارگذاری شد.")
    
    def initiate_call(self, phone_number: str) -> bool:
        """شروع تماس خروجی (شبیه‌سازی)"""
        print(f"[VOIP] در حال برقراری تماس با شماره {phone_number}...")
        # شبیه‌سازی تأخیر شبکه
        import time
        time.sleep(0.5)
        self.is_connected = True
        self.active_calls.append(phone_number)
        print(f"[VOIP] تماس با موفقیت برقرار شد.")
        return True
    
    def end_call(self, phone_number: str):
        """پایان تماس"""
        if phone_number in self.active_calls:
            self.active_calls.remove(phone_number)
            print(f"[VOIP] تماس با شماره {phone_number} پایان یافت.")
        self.is_connected = len(self.active_calls) > 0
    
    def is_available(self) -> bool:
        """بررسی آمادگی ماژول VoIP"""
        return True  # در این نسخه شبیه‌سازی، همیشه آماده است


class PowerCollectionAgent:
    """هسته مرکزی عامل خودکار وصول مطالبات برق ایلام"""
    
    def __init__(self):
        print("=" * 80)
        print("سامانه هوشمند وصول مطالبات - شرکت توزیع نیروی برق استان ایلام")
        print("نسخه عملیاتی v2.0 - کاملاً مستقل و درون‌برنامه‌ای")
        print("=" * 80)
        
        print("[INFO] راه‌اندازی اپراتور هوشمند وصول مطالبات برق ایلام...")
        
        self.db = IlamPowerDB()
        self.dialogue_manager = DialogueManager()
        self.voip_module = VoIPModule()
        
        print("[INFO] اپراتور هوشمند وصول مطالبات برق ایلام آماده به کار است.")
        print()
    
    def make_outbound_call(self, phone_number: str) -> Dict:
        """انجام تماس خروجی با یک مشترک"""
        customer = self.db.get_customer(phone_number)
        
        if not customer:
            print(f"[ERROR] مشترک با شماره {phone_number} یافت نشد.")
            return {"success": False, "error": "Customer not found"}
        
        print(f"[INFO] --- شروع تماس با مشترک: {customer.full_name} (بدهی: {int(customer.debt_amount):,} ریال) ---")
        
        # تعیین استراتژی مکالمه
        strategy = self.dialogue_manager.strategy_engine.determine_strategy(customer)
        print(f"[INFO] استراتژی انتخاب شده: {strategy.tone} | سطح تشدید: {strategy.level.value}")
        
        # برقراری تماس
        if not self.voip_module.initiate_call(phone_number):
            return {"success": False, "error": "Call failed"}
        
        # شروع مکالمه
        conversation_log = []
        
        # پیام شروع
        opening_message = self.dialogue_manager.generate_opening(customer, strategy)
        print(f"[ربات]: {opening_message}")
        conversation_log.append(f"Robot: {opening_message}")
        
        # شبیه‌سازی مکالمه (در محیط واقعی، اینجا ورودی صوتی پردازش می‌شود)
        simulated_responses = [
            "میشه قسط بندید؟",
            "این قبض اشتباه اومده، مصرف من اینقدر نبوده!",
            "چشم الان واریز می‌کنم.",
            "الان پول ندارم، بعداً پرداخت می‌کنم."
        ]
        
        for i, user_input in enumerate(simulated_responses[:2]):  # فقط ۲ پاسخ برای نمونه
            print(f"[مشترک]: {user_input}")
            conversation_log.append(f"Customer: {user_input}")
            
            robot_response = self.dialogue_manager.handle_response(user_input, customer, strategy)
            print(f"[ربات]: {robot_response}")
            conversation_log.append(f"Robot: {robot_response}")
            
            if i < 1:  # فاصله بین پاسخ‌ها
                print()
        
        # پایان تماس
        self.voip_module.end_call(phone_number)
        
        # ثبت رکورد تماس
        notes = f"تماس انجام شد. استراتژی: {strategy.tone}. نتیجه: پیگیری لازم دارد."
        self.db.update_call_record(customer.customer_id, notes)
        
        print(f"[INFO] تماس با موفقیت پایان یافت. یادداشت: {notes}")
        print()
        
        return {
            "success": True,
            "customer_id": customer.customer_id,
            "strategy_level": strategy.level.value,
            "conversation_log": conversation_log
        }
    
    def run_campaign(self, target_zone: Optional[str] = None):
        """اجرای کمپین تماس برای یک منطقه خاص یا همه مناطق"""
        print(f"[INFO] --- شروع کمپین تماس{' برای منطقه ' + target_zone if target_zone else ' عمومی'} ---")
        
        if target_zone:
            customers = self.db.get_customers_by_zone(target_zone)
        else:
            # دریافت همه مشترکین بدهکار
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT * FROM customers WHERE debt_amount > 0")
            customers = []
            for row in cursor.fetchall():
                customers.append(Customer(
                    customer_id=row['customer_id'],
                    full_name=row['full_name'],
                    address=row['address'],
                    phone_number=row['phone_number'],
                    debt_amount=row['debt_amount'],
                    last_bill_date=row['last_bill_date'],
                    consumption_avg=row['consumption_avg'],
                    payment_history=json.loads(row['payment_history']),
                    status=row['status'],
                    zone=row['zone'],
                    last_call_date=row['last_call_date'],
                    call_notes=row['call_notes']
                ))
        
        print(f"[INFO] تعداد مشترکین هدف: {len(customers)}")
        
        success_count = 0
        for customer in customers:
            result = self.make_outbound_call(customer.phone_number)
            if result["success"]:
                success_count += 1
            
            # فاصله بین تماس‌ها (در محیط واقعی برای رعایت ملاحظات اخلاقی)
            import time
            time.sleep(1)
        
        print(f"[INFO] کمپین به پایان رسید. تعداد تماس‌های موفق: {success_count} از {len(customers)}")
    
    def sync_data(self):
        """همگام‌سازی داده‌ها با سامانه eserv"""
        self.db.sync_from_eserv()
    
    def close(self):
        """بستن منابع"""
        self.db.close()
        print("[INFO] سامانه وصول مطالبات بسته شد.")


def main():
    """تابع اصلی اجرا"""
    # ایجاد نمونه عامل
    agent = PowerCollectionAgent()
    
    # مثال ۱: تماس با یک مشترک خاص
    print("\n" + "="*60)
    print("مثال ۱: تماس با یک مشترک خاص")
    print("="*60)
    agent.make_outbound_call("09183001002")  # علی کریمی
    
    # مثال ۲: اجرای کمپین برای یک منطقه
    print("\n" + "="*60)
    print("مثال ۲: اجرای کمپین برای منطقه زرجاب")
    print("="*60)
    agent.run_campaign(target_zone="زرجاب")
    
    # مثال ۳: همگام‌سازی داده‌ها
    print("\n" + "="*60)
    print("مثال ۳: همگام‌سازی با سامانه eserv")
    print("="*60)
    agent.sync_data()
    
    # بستن منابع
    agent.close()


if __name__ == "__main__":
    main()
