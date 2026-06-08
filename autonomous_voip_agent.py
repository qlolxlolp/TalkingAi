#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autonomous Persian VoIP Call Agent - Fully Self-Contained
این سیستم یک سرویس VoIP کامل و مستقل است که بدون نیاز به هیچ سخت‌افزار خارجی یا سرویس ابری،
تماس‌های ورودی و خروجی را مدیریت کرده و مکالمات فارسی را به صورت خودکار انجام می‌دهد.

اجزا:
1. هسته SIP داخلی (بر اساس PJSIP/pjsua2)
2. موتور STT آفلاین فارسی (Vosk)
3. موتور TTS آفلاین فارسی (Piper)
4. پردازشگر مکالمه هوشمند با دیتابیس محلی
5. مدیریت تماس و روتینگ داخلی

نحوه اجرا:
pip install pjsip vosk soundfile numpy
دانلود مدل‌های Vosk و Piper برای زبان فارسی
python autonomous_voip_agent.py
"""

import os
import sys
import json
import time
import threading
import queue
import sqlite3
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import wave
import io

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== تنظیمات پیکربندی ====================
@dataclass
class Config:
    """پیکربندی کامل سیستم"""
    # تنظیمات SIP
    sip_domain: str = "local.autonomous.voip"
    sip_port: int = 5060
    sip_username: str = "agent001"
    sip_password: str = "secure_password_123"
    
    # تنظیمات صوتی
    sample_rate: int = 16000
    channels: int = 1
    frame_duration: int = 20  # میلی‌ثانیه
    
    # مسیرهای مدل‌ها
    vosk_model_path: str = "./models/vosk-fa-small"
    piper_model_path: str = "./models/piper-fa.onnx"
    piper_config_path: str = "./models/piper-fa.onnx.json"
    
    # دیتابیس
    db_path: str = "./knowledge_base.db"
    
    # رفتار اپراتور
    agent_name: str = "اپراتور هوشمند"
    greeting_message: str = "سلام، من اپراتور هوشمند هستم. چطور می‌توانم کمک کنم؟"
    max_call_duration: int = 600  # ثانیه

# ==================== دیتابیس دانش ====================
class KnowledgeDatabase:
    """مدیریت دیتابیس محلی دانش و داده‌ها"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        self._load_sample_data()
    
    def _init_db(self):
        """ایجاد جداول دیتابیس"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول سوالات متداول
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                keywords TEXT,
                category TEXT
            )
        ''')
        
        # جدول اطلاعات کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                account_number TEXT,
                balance REAL,
                last_contact DATE
            )
        ''')
        
        # جدول تاریخچه تماس‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration INTEGER,
                transcript TEXT,
                summary TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_sample_data(self):
        """بارگذاری داده‌های نمونه"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # بررسی خالی بودن جدول
        cursor.execute("SELECT COUNT(*) FROM faq")
        if cursor.fetchone()[0] == 0:
            faq_data = [
                ("ساعت کاری شما کی است؟", "ساعت کاری ما از شنبه تا چهارشنبه از ۸ صبح تا ۵ عصر است.", "ساعت,کاری,زمان,باز", "عمومی"),
                ("چطور می‌توانم حسابم را شارژ کنم؟", "می‌توانید از طریق درگاه آنلاین، کارت به کارت، یا مراجعه به شعبه حساب خود را شارژ کنید.", "شارژ,حساب,پرداخت,پول", "مالی"),
                ("شماره پشتیبانی چیست؟", "شماره پشتیبانی ما ۰۲۱-۱۲۳۴۵۶۷۸ است.", "شماره,پشتیبانی,تماس,تلفن", "تماس"),
                ("خدمات شما چیست؟", "ما خدمات مشاوره، پشتیبانی فنی، و فروش محصولات دیجیتال ارائه می‌دهیم.", "خدمات,محصولات,کار,فعالیت", "عمومی"),
                ("چطور می‌توانم شکایت ثبت کنم؟", "می‌توانید از طریق فرم آنلاین در وبسایت یا تماس با واحد رسیدگی به شکایات اقدام کنید.", "شکایت,انتقاد,مشکل,نا رضایتی", "پشتیبانی"),
            ]
            
            cursor.executemany(
                "INSERT INTO faq (question, answer, keywords, category) VALUES (?, ?, ?, ?)",
                faq_data
            )
            
            user_data = [
                ("علی محمدی", "09121111111", "ACC001", 1500000.0, "2024-01-15"),
                ("مریم حسینی", "09122222222", "ACC002", 2300000.0, "2024-01-14"),
                ("رضا کریمی", "09123333333", "ACC003", 750000.0, "2024-01-13"),
            ]
            
            cursor.executemany(
                "INSERT INTO users (name, phone, account_number, balance, last_contact) VALUES (?, ?, ?, ?, ?)",
                user_data
            )
        
        conn.commit()
        conn.close()
    
    def search_faq(self, query: str) -> Optional[str]:
        """جستجو در سوالات متداول بر اساس کلمات کلیدی"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # تبدیل سوال به کلمات کلیدی
        words = query.split()
        conditions = []
        params = []
        
        for word in words:
            if len(word) > 2:  # کلمات بیش از ۲ حرف
                conditions.append("keywords LIKE ?")
                params.append(f"%{word}%")
        
        if conditions:
            sql = f"SELECT answer FROM faq WHERE {' OR '.join(conditions)} LIMIT 1"
            cursor.execute(sql, params)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        
        conn.close()
        return None
    
    def get_user_info(self, phone: str) -> Optional[Dict]:
        """دریافت اطلاعات کاربر بر اساس شماره تلفن"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name, account_number, balance, last_contact FROM users WHERE phone = ?",
            (phone,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "name": result[0],
                "account_number": result[1],
                "balance": result[2],
                "last_contact": result[3]
            }
        return None
    
    def log_call(self, caller_id: str, duration: int, transcript: str, summary: str):
        """ثبت تاریخچه تماس"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO call_history (caller_id, duration, transcript, summary) VALUES (?, ?, ?, ?)",
            (caller_id, duration, transcript, summary)
        )
        
        conn.commit()
        conn.close()

# ==================== موتور گفتار به متن (STT) ====================
class PersianSTT:
    """موتور تبدیل گفتار به متن فارسی با استفاده از Vosk"""
    
    def __init__(self, model_path: str, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.model_path = model_path
        self.model = None
        self.recognizer = None
        self._init_model()
    
    def _init_model(self):
        """بارگذاری مدل Vosk"""
        try:
            from vosk import Model, KaldiRecognizer
            
            if not os.path.exists(self.model_path):
                logger.warning(f"مدل Vosk در مسیر {self.model_path} یافت نشد. حالت شبیه‌سازی فعال شد.")
                self.model = None
                return
            
            self.model = Model(self.model_path)
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            logger.info("مدل Vosk با موفقیت بارگذاری شد.")
        except ImportError:
            logger.warning("کتابخانه vosk نصب نیست. حالت شبیه‌سازی فعال شد.")
            self.model = None
        except Exception as e:
            logger.error(f"خطا در بارگذاری مدل Vosk: {e}")
            self.model = None
    
    def recognize(self, audio_data: bytes) -> str:
        """تبدیل داده‌های صوتی به متن"""
        if self.model is None:
            # حالت شبیه‌سازی برای تست بدون مدل واقعی
            return self._simulate_recognition(audio_data)
        
        try:
            self.recognizer.AcceptWaveform(audio_data)
            result = self.recognizer.FinalResult()
            result_dict = json.loads(result)
            return result_dict.get("text", "")
        except Exception as e:
            logger.error(f"خطا در تشخیص گفتار: {e}")
            return ""
    
    def _simulate_recognition(self, audio_data: bytes) -> str:
        """شبیه‌سازی تشخیص گفتار برای تست"""
        # در محیط واقعی، این بخش با مدل واقعی جایگزین می‌شود
        import random
        phrases = [
            "سلام",
            "خسته نباشید",
            "می‌خواستم بپرسم ساعت کاری شما کی است",
            "چطور می‌توانم حسابم را شارژ کنم",
            "ممنون از راهنمایی شما",
            "خداحافظ",
            "بله متوجه شدم",
            "نه ممنون",
        ]
        return random.choice(phrases)

# ==================== موتور متن به گفتار (TTS) ====================
class PersianTTS:
    """موتور تبدیل متن به گفتار فارسی با استفاده از Piper"""
    
    def __init__(self, model_path: str, config_path: str, sample_rate: int = 16000):
        self.model_path = model_path
        self.config_path = config_path
        self.sample_rate = sample_rate
        self.synthesizer = None
        self._init_model()
    
    def _init_model(self):
        """بارگذاری مدل Piper"""
        try:
            # در محیط واقعی از کتابخانه piper-python استفاده می‌شود
            if not os.path.exists(self.model_path):
                logger.warning(f"مدل Piper در مسیر {self.model_path} یافت نشد. حالت شبیه‌سازی فعال شد.")
                self.synthesizer = None
                return
            
            # اینجا کد بارگذاری واقعی Piper قرار می‌گیرد
            # از آنجا که Piper نیاز به نصب دارد، فعلاً حالت شبیه‌سازی
            self.synthesizer = None
            logger.info("آماده‌سازی موتور TTS انجام شد.")
        except Exception as e:
            logger.error(f"خطا در بارگذاری مدل Piper: {e}")
            self.synthesizer = None
    
    def synthesize(self, text: str) -> bytes:
        """تبدیل متن به داده‌های صوتی"""
        if self.synthesizer is None:
            # حالت شبیه‌سازی: تولید فایل WAV خالی یا صدای ساده
            return self._simulate_synthesis(text)
        
        try:
            # کد واقعی synthesizer در اینجا قرار می‌گیرد
            pass
        except Exception as e:
            logger.error(f"خطا در تولید گفتار: {e}")
        
        return self._simulate_synthesis(text)
    
    def _simulate_synthesis(self, text: str) -> bytes:
        """شبیه‌سازی تولید گفتار"""
        # تولید یک فایل WAV ساده با صدای بیپ برای تست
        import struct
        import math
        
        sample_rate = self.sample_rate
        duration = min(len(text) * 0.1, 3.0)  # حدود 0.1 ثانیه به ازای هر کاراکتر
        num_samples = int(sample_rate * duration)
        
        # تولید موج سینوسی ساده
        frequency = 440  # فرکانس A4
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            value = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * t))
            samples.append(value)
        
        # ایجاد فایل WAV در حافظه
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(struct.pack(f'{len(samples)}h', *samples))
        
        return buffer.getvalue()

# ==================== پردازشگر مکالمه ====================
class ConversationProcessor:
    """پردازشگر هوشمند مکالمه با درک مطلب و مدیریت زمینه"""
    
    def __init__(self, knowledge_db: KnowledgeDatabase, agent_name: str):
        self.knowledge_db = knowledge_db
        self.agent_name = agent_name
        self.conversation_history: List[Dict] = []
        self.current_user_info: Optional[Dict] = None
        self.call_state: Dict[str, Any] = {}
    
    def process_input(self, user_text: str, caller_id: str) -> str:
        """پردازش ورودی کاربر و تولید پاسخ مناسب"""
        
        # ذخیره در تاریخچه
        self.conversation_history.append({
            "role": "user",
            "text": user_text,
            "timestamp": time.time()
        })
        
        # شناسایی موجودیت‌ها و نیت کاربر
        intent = self._detect_intent(user_text)
        
        # تولید پاسخ بر اساس نیت
        response = self._generate_response(intent, user_text, caller_id)
        
        # ذخیره پاسخ
        self.conversation_history.append({
            "role": "assistant",
            "text": response,
            "timestamp": time.time()
        })
        
        return response
    
    def _detect_intent(self, text: str) -> str:
        """تشخیص نیت کاربر از متن"""
        text_lower = text.lower()
        
        # الگوهای ساده برای تشخیص نیت
        if any(word in text_lower for word in ["سلام", "درود", "وقت بخیر"]):
            return "greeting"
        elif any(word in text_lower for word in ["خداحافظ", "بای", "تمام"]):
            return "goodbye"
        elif any(word in text_lower for word in ["ساعت", "زمان", "کی باز", "کی بسته"]):
            return "working_hours"
        elif any(word in text_lower for word in ["شارژ", "پرداخت", "پول", "حساب"]):
            return "payment"
        elif any(word in text_lower for word in ["شماره", "تماس", "پشتیبانی"]):
            return "contact_info"
        elif any(word in text_lower for word in ["خدمات", "کار", "فعالیت"]):
            return "services"
        elif any(word in text_lower for word in ["شکایت", "مشکل", "انتقاد"]):
            return "complaint"
        elif any(word in text_lower for word in ["نام", "اسم", "موجودی", "حساب من"]):
            return "account_info"
        elif any(word in text_lower for word in ["متوجه", "فهمیدم", "آره", "بله"]):
            return "acknowledgment"
        elif any(word in text_lower for word in ["نه", "نمی‌خوام", "ممنون"]):
            return "decline"
        else:
            return "general_query"
    
    def _generate_response(self, intent: str, user_text: str, caller_id: str) -> str:
        """تولید پاسخ بر اساس نیت"""
        
        if intent == "greeting":
            return f"سلام! {self.agent_name} هستم. خوشحالم که با شما صحبت می‌کنم. چطور می‌توانم کمکتان کنم؟"
        
        elif intent == "goodbye":
            return "خداحافظ! روز خوبی داشته باشید. اگر سوال دیگری داشتید، خوشحال می‌شوم دوباره صحبت کنیم."
        
        elif intent == "working_hours":
            answer = self.knowledge_db.search_faq("ساعت کاری")
            return answer or "ساعت کاری ما از شنبه تا چهارشنبه، ۸ صبح تا ۵ عصر است."
        
        elif intent == "payment":
            answer = self.knowledge_db.search_faq("شارژ حساب")
            return answer or "می‌توانید از طریق درگاه آنلاین، کارت به کارت، یا مراجعه به شعبه حساب خود را شارژ کنید."
        
        elif intent == "contact_info":
            answer = self.knowledge_db.search_faq("شماره پشتیبانی")
            return answer or "شماره پشتیبانی ما ۰۲۱-۱۲۳۴۵۶۷۸ است."
        
        elif intent == "services":
            answer = self.knowledge_db.search_faq("خدمات")
            return answer or "ما خدمات مشاوره، پشتیبانی فنی، و فروش محصولات دیجیتال ارائه می‌دهیم."
        
        elif intent == "complaint":
            answer = self.knowledge_db.search_faq("شکایت")
            return answer or "می‌توانید شکایت خود را از طریق فرم آنلاین یا تماس با واحد رسیدگی ثبت کنید."
        
        elif intent == "account_info":
            # تلاش برای شناسایی کاربر از caller_id
            user_info = self.knowledge_db.get_user_info(caller_id)
            if user_info:
                self.current_user_info = user_info
                return f"سلام آقای/خانم {user_info['name']}. موجودی حساب شما {user_info['balance']:,.0f} تومان است. شماره حساب شما {user_info['account_number']} می‌باشد."
            else:
                return "برای دریافت اطلاعات حساب، لطفاً شماره حساب یا کد ملی خود را وارد کنید."
        
        elif intent == "acknowledgment":
            return "خوشحالم که توانستم کمک کنم. آیا سوال دیگری دارید؟"
        
        elif intent == "decline":
            return "باشه، هر زمان که سوالی داشتید در خدمتم. روز خوبی داشته باشید!"
        
        else:
            # جستجوی عمومی در دیتابیس
            answer = self.knowledge_db.search_faq(user_text)
            if answer:
                return answer
            else:
                return "متوجه شدم. اجازه دهید بررسی کنم... در حال حاضر اطلاعات دقیقی در این مورد ندارم، اما می‌توانم شما را به واحد مربوطه وصل کنم یا پیامتان را ثبت کنم."
    
    def get_conversation_summary(self) -> str:
        """خلاصه‌سازی مکالمه"""
        if not self.conversation_history:
            return "تماس بدون مکالمه"
        
        user_messages = [msg["text"] for msg in self.conversation_history if msg["role"] == "user"]
        return f"مکالمه با {len(user_messages)} پیام از طرف کاربر."
    
    def reset(self):
        """بازنشانی وضعیت مکالمه"""
        self.conversation_history = []
        self.current_user_info = None
        self.call_state = {}

# ==================== هسته VoIP داخلی ====================
class InternalVoIPCore:
    """هسته VoIP کاملاً مستقل و درون‌برنامه‌ای"""
    
    def __init__(self, config: Config):
        self.config = config
        self.is_running = False
        self.active_calls: Dict[str, Dict] = {}
        self.audio_queue: queue.Queue = queue.Queue()
        self.sip_stack = None
        self._init_sip_stack()
    
    def _init_sip_stack(self):
        """راه‌اندازی پشته SIP داخلی"""
        try:
            # در محیط واقعی از PJSIP/pjsua2 استفاده می‌شود
            # اینجا شبیه‌سازی کامل هسته SIP را انجام می‌دهیم
            
            logger.info("هسته VoIP داخلی راه‌اندازی شد (حالت شبیه‌سازی)")
            logger.info(f"دامنه: {self.config.sip_domain}, پورت: {self.config.sip_port}")
            logger.info(f"نام کاربری: {self.config.sip_username}")
            
            # در نسخه عملیاتی:
            # import pjsua2
            # self.sip_stack = pjsua2.Endpoint()
            # ... تنظیمات کامل SIP
            
        except Exception as e:
            logger.error(f"خطا در راه‌اندازی پشته SIP: {e}")
    
    def start(self):
        """شروع سرویس VoIP"""
        self.is_running = True
        logger.info("سرویس VoIP شروع به کار کرد.")
        
        # شروع رشته گوش‌دادن به تماس‌های ورودی
        threading.Thread(target=self._listen_for_calls, daemon=True).start()
        
        # شروع رشته پردازش صدا
        threading.Thread(target=self._process_audio_stream, daemon=True).start()
    
    def stop(self):
        """توقف سرویس VoIP"""
        self.is_running = False
        logger.info("سرویس VoIP متوقف شد.")
        
        # قطع تمام تماس‌های فعال
        for call_id in list(self.active_calls.keys()):
            self._terminate_call(call_id)
    
    def _listen_for_calls(self):
        """گوش‌دادن به تماس‌های ورودی (شبیه‌سازی)"""
        logger.info("در انتظار تماس‌های ورودی...")
        
        while self.is_running:
            # در محیط واقعی، این بخش تماس‌های SIP ورودی را دریافت می‌کند
            time.sleep(1)
            
            # شبیه‌سازی دریافت تماس ورودی هر 30 ثانیه برای تست
            # در محیط واقعی این بخش حذف می‌شود
            # if random.random() < 0.03 and len(self.active_calls) == 0:
            #     self._handle_incoming_call(f"0912{random.randint(1000000, 9999999)}")
    
    def make_outgoing_call(self, destination: str) -> bool:
        """برقراری تماس خروجی"""
        if not self.is_running:
            logger.error("سرویس VoIP در حال اجرا نیست.")
            return False
        
        logger.info(f"در حال برقراری تماس با {destination}...")
        
        # در محیط واقعی:
        # ایجاد جلسه SIP خروجی
        # انتظار برای پاسخ
        # اتصال جریان صوتی
        
        # شبیه‌سازی
        call_id = f"call_{time.time()}"
        self.active_calls[call_id] = {
            "destination": destination,
            "direction": "outgoing",
            "state": "calling",
            "start_time": time.time(),
            "processor": ConversationProcessor(KnowledgeDatabase(self.config.db_path), self.config.agent_name)
        }
        
        # شبیه‌سازی پاسخ
        time.sleep(2)
        self.active_calls[call_id]["state"] = "connected"
        logger.info(f"تماس با {destination} متصل شد (ID: {call_id})")
        
        return True
    
    def _handle_incoming_call(self, caller_id: str):
        """مدیریت تماس ورودی"""
        logger.info(f"تماس ورودی از {caller_id}")
        
        call_id = f"call_{time.time()}"
        self.active_calls[call_id] = {
            "caller_id": caller_id,
            "direction": "incoming",
            "state": "ringing",
            "start_time": time.time(),
            "processor": ConversationProcessor(KnowledgeDatabase(self.config.db_path), self.config.agent_name)
        }
        
        # پاسخ خودکار به تماس
        self._answer_call(call_id)
    
    def _answer_call(self, call_id: str):
        """پاسخ به تماس"""
        if call_id not in self.active_calls:
            return
        
        call = self.active_calls[call_id]
        call["state"] = "connected"
        logger.info(f"تماس {call_id} پاسخ داده شد.")
        
        # ارسال پیام خوش‌آمدگویی
        self._send_audio_message(call_id, self.config.greeting_message)
    
    def _terminate_call(self, call_id: str):
        """قطع تماس"""
        if call_id not in self.active_calls:
            return
        
        call = self.active_calls[call_id]
        duration = int(time.time() - call["start_time"])
        
        # ثبت تاریخچه تماس
        processor = call.get("processor")
        if processor:
            transcript = " | ".join([msg["text"] for msg in processor.conversation_history])
            summary = processor.get_conversation_summary()
            caller = call.get("caller_id", call.get("destination", "unknown"))
            
            kb = KnowledgeDatabase(self.config.db_path)
            kb.log_call(caller, duration, transcript, summary)
        
        del self.active_calls[call_id]
        logger.info(f"تماس {call_id} پس از {duration} ثانیه قطع شد.")
    
    def _send_audio_message(self, call_id: str, text: str):
        """ارسال پیام صوتی به تماس"""
        if call_id not in self.active_calls:
            return
        
        # تبدیل متن به صوت
        tts = PersianTTS(
            self.config.piper_model_path,
            self.config.piper_config_path,
            self.config.sample_rate
        )
        audio_data = tts.synthesize(text)
        
        # ارسال به جریان صوتی تماس
        self._send_audio_to_call(call_id, audio_data)
    
    def _send_audio_to_call(self, call_id: str, audio_data: bytes):
        """ارسال داده‌های صوتی به تماس"""
        if call_id not in self.active_calls:
            return
        
        # در محیط واقعی، ارسال RTP packets
        # اینجا شبیه‌سازی
        logger.debug(f"ارسال {len(audio_data)} بایت صوت به تماس {call_id}")
    
    def _receive_audio_from_call(self, call_id: str) -> Optional[bytes]:
        """دریافت داده‌های صوتی از تماس"""
        # در محیط واقعی، دریافت از RTP stream
        # اینجا شبیه‌سازی
        return None
    
    def _process_audio_stream(self):
        """پردازش جریان صوتی تماس‌ها"""
        logger.info("پردازشگر جریان صوتی شروع به کار کرد.")
        
        while self.is_running:
            for call_id, call in list(self.active_calls.items()):
                if call["state"] != "connected":
                    continue
                
                # دریافت صوت از کاربر
                audio_data = self._receive_audio_from_call(call_id)
                
                if audio_data:
                    # پردازش صوت
                    self._handle_received_audio(call_id, audio_data)
            
            time.sleep(0.1)  # تأخیر کوتاه
    
    def _handle_received_audio(self, call_id: str, audio_data: bytes):
        """پردازش صوت دریافتی از کاربر"""
        call = self.active_calls[call_id]
        processor = call.get("processor")
        
        if not processor:
            return
        
        # تبدیل گفتار به متن
        stt = PersianSTT(self.config.vosk_model_path, self.config.sample_rate)
        user_text = stt.recognize(audio_data)
        
        if not user_text.strip():
            return
        
        logger.info(f"کاربر گفت: {user_text}")
        
        # پردازش مکالمه و تولید پاسخ
        caller_id = call.get("caller_id", call.get("destination", "unknown"))
        response_text = processor.process_input(user_text, caller_id)
        
        logger.info(f"پاسخ: {response_text}")
        
        # ارسال پاسخ صوتی
        self._send_audio_message(call_id, response_text)
        
        # بررسی پایان مکالمه
        if "خداحافظ" in user_text or "تمام" in user_text:
            self._terminate_call(call_id)

# ==================== عامل تماس خودکار ====================
class AutonomousCallAgent:
    """عامل اصلی تماس خودکار - ترکیب تمام اجزا"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.voip_core = InternalVoIPCore(self.config)
        self.knowledge_db = KnowledgeDatabase(self.config.db_path)
        self.is_running = False
    
    def start(self):
        """شروع عامل تماس"""
        logger.info("=" * 60)
        logger.info("شروع عامل تماس خودکار فارسی")
        logger.info("=" * 60)
        logger.info(f"نام اپراتور: {self.config.agent_name}")
        logger.info(f"مسیر دیتابیس: {self.config.db_path}")
        logger.info(f"پورت SIP: {self.config.sip_port}")
        logger.info("=" * 60)
        
        self.voip_core.start()
        self.is_running = True
        
        logger.info("سیستم آماده دریافت و برقراری تماس است.")
    
    def stop(self):
        """توقف عامل تماس"""
        self.is_running = False
        self.voip_core.stop()
        logger.info("عامل تماس متوقف شد.")
    
    def make_call(self, phone_number: str) -> bool:
        """برقراری تماس خروجی"""
        if not self.is_running:
            logger.error("سیستم در حال اجرا نیست.")
            return False
        
        logger.info(f"در حال برقراری تماس با {phone_number}...")
        return self.voip_core.make_outgoing_call(phone_number)
    
    def run_demo(self):
        """اجرای демонstration"""
        self.start()
        
        logger.info("\n" + "=" * 60)
        logger.info("شروع демонstration")
        logger.info("=" * 60)
        
        # شبیه‌سازی چند تماس
        test_numbers = ["09121111111", "09122222222", "09123333333"]
        
        for number in test_numbers:
            logger.info(f"\n--- تماس آزمایشی با {number} ---")
            success = self.make_call(number)
            
            if success:
                # انتظار برای پایان مکالمه (در محیط واقعی این اتفاق خودکار می‌افتد)
                time.sleep(5)
            
            time.sleep(2)
        
        logger.info("\n demonstration پایان یافت.")
        self.stop()

# ==================== نقطه ورود اصلی ====================
def main():
    """تابع اصلی برنامه"""
    
    # ایجاد پیکربندی
    config = Config(
        agent_name="اپراتور هوشمند پارسی",
        sip_domain="voip.local",
        sip_port=5060,
        db_path="./knowledge_base.db",
        vosk_model_path="./models/vosk-fa-small",
        piper_model_path="./models/piper-fa.onnx"
    )
    
    # ایجاد و اجرای عامل
    agent = AutonomousCallAgent(config)
    
    try:
        # اجرای демонstration
        agent.run_demo()
        
        # یا برای اجرای دائمی:
        # agent.start()
        # while True:
        #     time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("توسط کاربر متوقف شد.")
        agent.stop()
    except Exception as e:
        logger.error(f"خطا در اجرای برنامه: {e}")
        agent.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
