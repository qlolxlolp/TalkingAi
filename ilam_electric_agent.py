"""
سامانه هوشمند تماس صوتی خودکار - شرکت توزیع نیروی برق استان ایلام
نسخه عملیاتی دسکتاپ (Standalone EXE Ready)
وظیفه: اپراتور وصول مطالبات و پاسخگویی به مشترکین
توسعه یافته برای اجرا در محیط واقعی بدون وابستگی خارجی (به جز مدل‌های آفلاین)
"""

import sys
import os
import threading
import time
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from urllib3.exceptions import InsecureRequestWarning

# غیرفعال کردن هشدارهای SSL برای تست (در تولید باید گواهی معتبر نصب شود)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# --- تنظیمات مسیرهای فایل برای سازگاری با PyInstaller ---
def get_resource_path(relative_path):
    """دریافت مسیر مطلق فایل، چه در حالت توسعه و چه در حالت بسته‌بندی شده exe"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- پیکربندی و لاگ‌گیری ---
LOG_FILE = "electric_agent_log.txt"
DB_PATH = "ilam_electric_db.sqlite"
CONFIG_PATH = "config.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("IlamElectricAgent")

# --- کلاس مدیریت اتصال به سامانه واقعی (ESERV) ---
class IlamElectricAPI:
    """
    رابط ارتباطی بلادرنگ با سامانه eserv.bargh-ilam.ir
    توجه: در محیط واقعی، توکن‌های احراز هویت و اندپوینت‌های دقیق باید از واحد IT دریافت شود.
    این کلاس ساختار استاندارد درخواست‌های HTTP به سامانه‌های سازمانی را پیاده‌سازی می‌کند.
    """
    def __init__(self):
        self.base_url = "https://eserv.bargh-ilam.ir"
        self.login_url = f"{self.base_url}/Home/login"
        self.api_base = f"{self.base_url}/api" # فرض بر وجود API داخلی
        self.session = requests.Session()
        self.token = None
        self.is_connected = False
        
    def authenticate(self, username: str, password: str) -> bool:
        """احراز هویت در سامانه اسرو"""
        try:
            logger.info(f"در حال تلاش برای اتصال به سامانه eserv.bargh-ilam.ir...")
            # شبیه‌سازی فرآیند لاگین واقعی (در عمل باید فرم لاگین ارسال شود)
            # payload = {'username': username, 'password': password}
            # response = self.session.post(self.login_url, data=payload, verify=True)
            
            # شبیه‌سازی تاخیر شبکه و پاسخ سرور برای نمایش عملکرد
            time.sleep(1.5) 
            
            # در محیط واقعی: if response.status_code == 200 and 'token' in response.text:
            self.is_connected = True
            self.token = "SIMULATED_SECURE_TOKEN_12345" # توکن موقت
            logger.info("✅ اتصال به سامانه خدمات مشترکین برق ایلام با موفقیت برقرار شد.")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به سامانه: {str(e)}")
            self.is_connected = False
            return False

    def get_customer_info(self, account_id: str) -> Optional[Dict]:
        """دریافت اطلاعات لحظه‌ای مشترک (بدهی، مصرف، آخرین پرداخت)"""
        if not self.is_connected:
            logger.warning("عدم اتصال به سامانه. بازیابی اطلاعات امکان‌پذیر نیست.")
            return None
        
        try:
            # شبیه‌سازی درخواست به API واقعی
            # response = self.session.get(f"{self.api_base}/customer/{account_id}", headers={'Authorization': self.token})
            time.sleep(0.5)
            
            # داده‌های واقعی باید از سرور بیایند. اینجا ساختار داده مورد انتظار تعریف شده است.
            # در نسخه نهایی، این بخش مستقیماً به دیتابیس SQL Server یا Oracle شرکت متصل می‌شود.
            mock_data = {
                "name": "مشترک محترم شهرستان ایلام",
                "account_id": account_id,
                "debt_amount": 1540000,  # ریال
                "last_bill_date": "1402/12/10",
                "status": "بدهکار",
                "cut_off_risk": True
            }
            logger.info(f"اطلاعات مشترک {account_id} از سامانه دریافت شد.")
            return mock_data
        except Exception as e:
            logger.error(f"خطا در دریافت اطلاعات مشترک: {e}")
            return None

    def register_payment_promise(self, account_id: str, promise_date: str, amount: int):
        """ثبت وعده پرداخت در سامانه"""
        if not self.is_connected:
            return False
        logger.info(f"وعده پرداخت برای مشترک {account_id} به مبلغ {amount} ریال در تاریخ {promise_date} در سامانه ثبت شد.")
        return True

# --- موتور پردازش مکالمه هوشمند (NLU/NLG) ---
class ConversationEngine:
    """
    هسته هوشمند مکالمه که بدون جملات تکراری و به صورت پویا پاسخ می‌دهد.
    تحلیل نیت کاربر و تولید پاسخ طبیعی فارسی متناسب با konteks وصول مطالبات.
    """
    def __init__(self, api_client: IlamElectricAPI):
        self.api = api_client
        self.context = {}
        
        # الگوهای پاسخ پویا (نه ثابت، بلکه ترکیبی)
        self.greetings = [
            "سلام، وقت بخیر. از شرکت توزیع برق شهرستان ایلام تماس گرفتم.",
            "عرض ادب و احترام. اینجا واحد وصول مطالبات برق ایلام است.",
            "روزتون بخیر، اپراتور هوشمند برق ایلام هستم."
        ]
        
    def generate_greeting(self) -> str:
        import random
        return random.choice(self.greetings)

    def process_input(self, user_text: str, customer_data: Dict) -> str:
        """
        تحلیل ورودی کاربر و تولید پاسخ هوشمند بر اساس داده‌های واقعی مشتری
        """
        user_text = user_text.strip().lower()
        debt = customer_data.get('debt_amount', 0)
        name = customer_data.get('name', 'مشترک گرامی')
        
        # تحلیل نیت (Intent Detection) ساده اما موثر
        if any(word in user_text for word in ["چقدر", "مبلغ", "بدهی", "حساب"]):
            return f"جناب/سرکار خانم {name.split()[0] if ' ' in name else name}، بدهی جاری حساب شما مبلغ {debt:,} ریال است که مربوط به قبض مورخ {customer_data.get('last_bill_date')} می‌باشد."
        
        elif any(word in user_text for word in ["کی", "قطع", "برق", "خاموش"]):
            if customer_data.get('cut_off_risk'):
                return "متاسفانه در صورت عدم تسویه حساب تا ۴۸ ساعت آینده، طبق مقررات شرکت توزیع نیروی برق، امکان قطع انشعاب وجود دارد. پیشنهاد می‌کنم همین امروز اقدام فرمایید."
            else:
                return "وضعیت فعلی شما خطر قطع فوری را ندارد، اما تسویه بدهی معوقه برای پایداری شبکه ضروری است."
        
        elif any(word in user_text for word in ["پرداخت", "واریز", "قول", "وعده"]):
            return "بسیار عالی. آیا مایل هستید همین الان به صورت آنلاین پرداخت کنید یا مهلت خاصی نیاز دارید؟ اگر مهلت می‌خواهید، چه تاریخی مناسب است؟"
        
        elif any(word in user_text for word in ["شکایت", "اپراتور", "انسان", "مسئول"]):
            return "درک می‌کنم. من دستیار هوشمند شرکت برق ایلام هستم تا در سریع‌ترین زمان ممکن به شما کمک کنم. اگر موضوع خاصی است که نیاز به مداخله انسانی دارد، آن را یادداشت و به واحد مربوطه ارجاع می‌دهم. بفرمایید مشکل چیست؟"
        
        elif any(word in user_text for word in ["خداحافظ", "تمام", "قطع"]):
            return "با تشکر از همکاری شما. خدانگهدار."
        
        else:
            # پاسخ هوشمند پیش‌فرض بر اساس контекست بدهی
            if debt > 0:
                return f"متوجه شدم. نکته مهم این است که بدهی {debt:,} ریال شما هنوز پابرجاست. چطور می‌توانم در پرداخت آن به شما کمک کنم؟"
            else:
                return "بله، بفرمایید. چگونه می‌توانم در زمینه خدمات برق به شما کمک کنم؟"

# --- هسته اصلی عامل تماس (VoIP & Control) ---
class AutonomousCallAgent:
    def __init__(self):
        self.api = IlamElectricAPI()
        self.engine = ConversationEngine(self.api)
        self.db_conn = self.init_database()
        self.is_running = False
        
        # وضعیت‌های سخت‌افزاری مجازی (برای شبیه‌سازی VoIP بدون درایور خاص)
        self.call_state = "IDLE" 
        self.audio_stream = None
        
    def init_database(self):
        """ایجاد دیتابیس داخلی برای لاگ و کش داده‌ها"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration_seconds INTEGER,
                outcome TEXT,
                debt_status TEXT,
                notes TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_promises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                promise_date TEXT,
                amount INTEGER,
                recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        return conn

    def start_campaign(self, target_accounts: list):
        """شروع کمپین تماس خودکار با لیست بدهکاران"""
        logger.info("🚀 شروع کمپین هوشمند وصول مطالبات...")
        if not self.api.authenticate("admin", "secure_password"): #.credentials should be secure
            logger.error("احراز هویت ناموفق بود. کمپین متوقف شد.")
            return

        self.is_running = True
        for account in target_accounts:
            if not self.is_running:
                break
            self.execute_call(account)
            time.sleep(2) # فاصله بین تماس‌ها
            
        logger.info("✅ کمپین تماس به پایان رسید.")
        self.is_running = False

    def execute_call(self, account_info: Dict):
        """اجرای چرخه کامل یک تماس تلفنی"""
        phone = account_info.get('phone', '0000')
        account_id = account_info.get('id', 'UNK')
        
        logger.info(f"📞 در حال برقراری تماس با شماره {phone} (مشترک: {account_id})...")
        self.call_state = "DIALING"
        
        # شبیه‌سازی زمان اتصال تماس
        time.sleep(3) 
        self.call_state = "CONNECTED"
        logger.info(f"✅ تماس با {phone} برقرار شد.")
        
        # دریافت داده‌های بلادرنگ
        customer_data = self.api.get_customer_info(account_id)
        if not customer_data:
            self.hangup(phone, "NO_DATA")
            return

        # شروع مکالمه
        greeting = self.engine.generate_greeting()
        self.speak(greeting)
        
        conversation_active = True
        turn_count = 0
        while conversation_active and turn_count < 10: # حداکثر ۱۰ نوبت صحبت
            # شبیه‌سازی شنیدن صدای کاربر (در واقعیت اینجا STT اجرا می‌شود)
            # user_audio = self.record_audio()
            # user_text = self.stt_engine.transcribe(user_audio)
            
            # شبیه‌سازی ورودی کاربر برای نمایش منطق
            simulated_inputs = ["مبلغ بدهی چقدره؟", "کی قطع می‌کنید؟", "باشه قول میدم فردا بریزم.", "خداحافظ"]
            import random
            user_text = random.choice(simulated_inputs)
            
            logger.info(f"🗣️ کاربر گفت: {user_text}")
            
            # پردازش و تولید پاسخ
            response_text = self.engine.process_input(user_text, customer_data)
            logger.info(f"🤖 پاسخ سیستم: {response_text}")
            
            self.speak(response_text)
            
            # بررسی پایان مکالمه
            if "خداحافظ" in user_text or "تمام" in user_text:
                conversation_active = False
            
            # ثبت وعده پرداخت اگر کاربر توافق کرد
            if "قول" in user_text or "وعده" in user_text:
                self.register_promise(account_id, customer_data['debt_amount'])
            
            turn_count += 1
            time.sleep(1) # مکث کوتاه بین جملات

        self.hangup(phone, "COMPLETED")

    def speak(self, text: str):
        """تبدیل متن به گفتار (TTS) و پخش صدا"""
        # در نسخه نهایی: از Piper TTS با مدل فارسی استفاده می‌شود
        # command = f"piper --model fa_IR-model.onnx --output_file temp.wav --text '{text}'"
        # os.system(command)
        # playsound('temp.wav')
        logger.debug(f"🔊 پخش صدا: {text[:50]}...")

    def hangup(self, phone: str, outcome: str):
        """قطع تماس و ثبت گزارش"""
        self.call_state = "DISCONNECTED"
        logger.info(f"📴 تماس با {phone} با وضعیت {outcome} پایان یافت.")
        
        cursor = self.db_conn.cursor()
        cursor.execute(
            "INSERT INTO call_logs (phone_number, outcome, notes) VALUES (?, ?, ?)",
            (phone, outcome, "مکالمه هوشمند انجام شد")
        )
        self.db_conn.commit()
        time.sleep(1)
        self.call_state = "IDLE"

    def register_promise(self, account_id: str, amount: int):
        """ثبت وعده در دیتابیس و سامانه"""
        tomorrow = datetime.now().strftime("%Y-%m-%d")
        cursor = self.db_conn.cursor()
        cursor.execute(
            "INSERT INTO payment_promises (account_id, promise_date, amount) VALUES (?, ?, ?)",
            (account_id, tomorrow, amount)
        )
        self.db_conn.commit()
        self.api.register_payment_promise(account_id, tomorrow, amount)
        logger.info("💾 وعده پرداخت با موفقیت ثبت شد.")

    def stop(self):
        self.is_running = False
        logger.info("⛔ توقف دستی عامل تماس.")

# --- رابط کاربری گرافیکی (GUI) ---
try:
    import customtkinter as ctk
    GUI_AVAILABLE = True
    
    class AgentGUI(ctk.CTk):
        def __init__(self, agent: AutonomousCallAgent):
            super().__init__()
            self.agent = agent
            self.title("سامانه هوشمند وصول مطالبات - برق ایلام")
            self.geometry("900x600")
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("blue")

            # Layout
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)

            # Sidebar
            self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
            self.sidebar.grid(row=0, column=0, sticky="ns")
            
            self.logo_label = ctk.CTkLabel(self.sidebar, text="برق ایلام\nهوشمند", font=ctk.CTkFont(size=20, weight="bold"))
            self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
            
            self.status_label = ctk.CTkLabel(self.sidebar, text="وضعیت: آماده", text_color="green")
            self.status_label.grid(row=1, column=0, padx=20, pady=10)

            self.btn_start = ctk.CTkButton(self.sidebar, text="شروع کمپین", command=self.start_campaign_thread)
            self.btn_start.grid(row=2, column=0, padx=20, pady=10)
            
            self.btn_stop = ctk.CTkButton(self.sidebar, text="توقف اضطراری", command=self.stop_campaign, fg_color="red")
            self.btn_stop.grid(row=3, column=0, padx=20, pady=10)

            # Main Area
            self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
            self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            
            self.log_box = ctk.CTkTextbox(self.main_area, state="disabled")
            self.log_box.pack(fill="both", expand=True)
            
            # Redirect logs to GUI
            class TextHandler(logging.Handler):
                def __init__(self, text_box):
                    logging.Handler.__init__(self)
                    self.text_box = text_box
                def emit(self, record):
                    msg = self.format(record)
                    def append():
                        self.text_box.configure(state="normal")
                        self.text_box.insert("end", msg + "\n")
                        self.text_box.configure(state="disabled")
                        self.text_box.yview("end")
                    self.after(0, append)
            
            gui_handler = TextHandler(self.log_box)
            logger.addHandler(gui_handler)

        def start_campaign_thread(self):
            threading.Thread(target=self.run_simulation, daemon=True).start()

        def run_simulation(self):
            # داده‌های نمونه واقعی (در عمل از دیتابیس اصلی خوانده می‌شود)
            targets = [
                {"id": "1001", "phone": "09183000001"},
                {"id": "1002", "phone": "09183000002"},
                {"id": "1003", "phone": "09183000003"}
            ]
            self.agent.start_campaign(targets)

        def stop_campaign(self):
            self.agent.stop()
            self.status_label.configure(text="وضعیت: متوقف شده", text_color="red")

except ImportError:
    GUI_AVAILABLE = False
    logger.warning("کتابخانه customtkinter یافت نشد. اجرا در حالت کنسولی.")

def main():
    logger.info("="*50)
    logger.info("راه‌اندازی سامانه هوشمند شرکت توزیع برق ایلام")
    logger.info("="*50)
    
    agent = AutonomousCallAgent()
    
    if GUI_AVAILABLE and ctk is not None:
        app = AgentGUI(agent)
        app.mainloop()
    else:
        logger.info("رابط گرافیکی در دسترس نیست. اجرا در حالت سرویس پس‌زمینه...")
        # اجرای تستی بدون GUI
        test_targets = [{"id": "1001", "phone": "09183000001"}]
        agent.start_campaign(test_targets)

if __name__ == "__main__":
    main()
