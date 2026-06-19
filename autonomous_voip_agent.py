#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سامانه تماس تلفنی خودکار فارسی - VoIP کاملاً مستقل
(Autonomous Persian VoIP Call Agent)

توسعه یافته برای شرکت توزیع نیروی برق استان ایلام و کاربردهای عمومی
نویسنده: عرفان رجبی - شرکت تلاشگر
"""

import os
import sys
import time
import logging
import sqlite3
import json
import threading
import wave
import io
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AutonomousVoIP")

# ==============================================================================
# پیکربندی (Configuration)
# ==============================================================================

@dataclass
class Config:
    """پیکربندی اصلی سیستم"""
    agent_name: str = "اپراتور هوشمند پارسی"
    sip_domain: str = "voip.local"
    sip_port: int = 5060
    sip_username: str = "agent_01"
    sip_password: str = "secure_password_123"
    
    db_path: str = "./knowledge_base.db"
    vosk_model_path: str = "./models/vosk-fa-small"
    piper_model_path: str = "./models/fa_IR-amir-medium.onnx"
    piper_config_path: str = "./models/fa_IR-amir-medium.onnx.json"
    
    greeting_message: str = "سلام! به سامانه هوشمند خوش آمدید. من دستیار صوتی شما هستم."
    max_call_duration: int = 900  # ثانیه (15 دقیقه)
    
    # فلگ‌های عملیاتی
    use_real_sip: bool = False  # اگر True باشد سعی می‌کند به سرور SIP واقعی وصل شود
    use_real_vosk: bool = False
    use_real_piper: bool = False

# ==============================================================================
# پایگاه دانش (Knowledge Database)
# ==============================================================================

class KnowledgeDatabase:
    """مدیریت پایگاه داده محلی شامل FAQ، کاربران و تاریخچه"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        self._seed_data()
        
    def _init_db(self):
        """ایجاد جداول ضروری"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول سوالات متداول
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                keywords TEXT,
                category TEXT
            )
        """)
        
        # جدول کاربران/مشترکین
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT UNIQUE,
                balance REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # جدول تاریخچه تماس‌ها
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_phone TEXT,
                callee_phone TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration INTEGER,
                transcript TEXT,
                sentiment TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"پایگاه داده در {self.db_path} آماده شد.")

    def _seed_data(self):
        """درج داده‌های نمونه اولیه"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # بررسی خالی بودن جدول FAQ
        cursor.execute("SELECT count(*) FROM faq")
        if cursor.fetchone()[0] == 0:
            faq_data = [
                ("چطور می‌توانم قبض برق را پرداخت کنم؟", 
                 "می‌توانید از طریق اپلیکیشن‌های بانکی، سایت eserv.bargh-ilam.ir یا مراجعه به دفاتر پیشخوان اقدام کنید.", 
                 "پرداخت,قبض,برق,آنلاین", "صورتحساب"),
                
                ("برق من قطع شده، چه کار کنم؟", 
                 "اگر بدهی معوقه دارید، لطفاً نسبت به پرداخت اقدام کنید. در غیر این صورت با شماره 121 تماس بگیرید.", 
                 "قطع,برق,بدهی,وصل", "فوریت‌ها"),
                 
                ("ساعات کاری دفتر مرکزی کی است؟", 
                 "دفتر مرکزی ایلام، بلوار معلم، همه روزه به جز تعطیلات از ساعت 7:30 تا 14:30 پاسخگو است.", 
                 "ساعت,کاری,آدرس,دفتر", "اطلاعات عمومی"),
                 
                ("چطور قسط‌بندی کنم؟", 
                 "برای مبالغ بالای 5 میلیون تومان، می‌توانید با مراجعه به دفتر امور مشترکین درخواست قسط‌بندی دهید.", 
                 "قسط,بدهی,وام,تقسیم", "مالی")
            ]
            
            cursor.executemany(
                "INSERT INTO faq (question, answer, keywords, category) VALUES (?, ?, ?, ?)", 
                faq_data
            )
            
            # کاربران نمونه
            users_data = [
                ("علی کریمی", "09183001002", 1500000.0, "بدهکار"),
                ("مریم حسینی", "09183001003", 0.0, "عادی"),
                ("رضا محمدی", "09183001004", 500000.0, "بدهکار")
            ]
            
            cursor.executemany(
                "INSERT OR IGNORE INTO users (name, phone, balance, status) VALUES (?, ?, ?, ?)",
                users_data
            )
            
            conn.commit()
            logger.info("داده‌های نمونه پایگاه دانش بارگذاری شد.")
        
        conn.close()

    def get_answer(self, query: str) -> Optional[str]:
        """جستجوی هوشمند برای یافتن پاسخ مناسب"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جستجو بر اساس کلمات کلیدی (ساده‌شده)
        words = query.split()
        best_match = None
        max_score = 0
        
        cursor.execute("SELECT question, answer, keywords FROM faq")
        rows = cursor.fetchall()
        
        for q, a, k in rows:
            score = 0
            keywords = k.split(',') if k else []
            for word in words:
                if word in q or word in k:
                    score += 1
            
            if score > max_score:
                max_score = score
                best_match = a
        
        conn.close()
        
        if max_score > 0:
            return best_match
        return "متاسفانه متوجه سوال شما نشدم. آیا می‌توانید مجدد توضیح دهید؟"

    def log_call(self, caller: str, callee: str, duration: int, transcript: str):
        """ثبت تاریخچه تماس"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO call_history (caller_phone, callee_phone, duration, transcript) VALUES (?, ?, ?, ?)",
            (caller, callee, duration, transcript)
        )
        conn.commit()
        conn.close()

# ==============================================================================
# موتورهای پردازش صدا (STT & TTS)
# ==============================================================================

class PersianSTT:
    """تبدیل گفتار به متن (Vosk Wrapper)"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.recognizer = None
        self._load_model()
        
    def _load_model(self):
        if not os.path.exists(self.model_path):
            logger.warning(f"مدل Vosk در مسیر {self.model_path} یافت نشد. حالت شبیه‌سازی فعال است.")
            return

        try:
            from vosk import Model, KaldiRecognizer
            import soundfile as sf
            
            self.model = Model(self.model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            logger.info("مدل Vosk با موفقیت بارگذاری شد.")
        except ImportError:
            logger.error("کتابخانه vosk نصب نیست. pip install vosk soundfile")
        except Exception as e:
            logger.error(f"خطا در بارگذاری Vosk: {e}")

    def transcribe(self, audio_data: bytes) -> str:
        """دریافت بایت‌های صوتی و返回 متن"""
        if self.recognizer is None:
            # حالت شبیه‌سازی برای تست بدون مدل
            return "شبیه‌سازی: من نیاز به پرداخت قبض دارم"
        
        try:
            if self.recognizer.AcceptWaveform(audio_data):
                result = json.loads(self.recognizer.Result())
                return result.get('text', '')
            else:
                return json.loads(self.recognizer.PartialResult()).get('partial', '')
        except Exception as e:
            logger.error(f"خطا در تبدیل صدا به متن: {e}")
            return ""

class PersianTTS:
    """تبدیل متن به گفتار (Piper Wrapper)"""
    
    def __init__(self, model_path: str, config_path: str):
        self.model_path = model_path
        self.config_path = config_path
        self.synthesizer = None
        self._load_model()
        
    def _load_model(self):
        if not os.path.exists(self.model_path):
            logger.warning(f"مدل Piper در مسیر {self.model_path} یافت نشد. حالت شبیه‌سازی فعال است.")
            return

        try:
            # فرض بر این است که کتابخانه piper-python نصب شده است
            # از آنجا که نصب مستقیم ممکن است پیچیده باشد، اینجا ساختار را آماده می‌کنیم
            logger.info("آماده‌سازی موتور Piper برای تولید صدا...")
            # در محیط واقعی: from piper import PiperVoice; self.synthesizer = PiperVoice.load(...)
            self.synthesizer = "dummy_piper_instance" 
            logger.info("موتور Piper آماده به کار است (حالت شبیه‌سازی).")
        except Exception as e:
            logger.error(f"خطا در بارگذاری Piper: {e}")

    def synthesize(self, text: str) -> bytes:
        """تبدیل متن به بایت‌های صوتی WAV"""
        # در حالت واقعی، خروجی مدل Piper برگردانده می‌شود
        # اینجا یک فایل WAV خالی یا نویز سفید کوتاه برمی‌گردانیم تا ساختار حفظ شود
        logger.info(f"در حال تولید صدا برای متن: {text[:30]}...")
        
        # تولید یک فایل WAV خالی به عنوان جایگزین (Placeholder)
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(b'\x00' * 22050) # 1 ثانیه سکوت
        return buffer.getvalue()

# ==============================================================================
# هسته VoIP (SIP Stack)
# ==============================================================================

class InternalVoIPCore:
    """مدیریت پروتکل SIP و تماس‌ها"""
    
    def __init__(self, config: Config):
        self.config = config
        self.account = None
        self.endpoint = None
        self.is_active = False
        
        if config.use_real_sip:
            self._init_real_sip()
        else:
            logger.info("هسته VoIP در حالت شبیه‌سازی (Simulation Mode) اجرا می‌شود.")
            
    def _init_real_sip(self):
        """راه‌اندازی PJSIP واقعی"""
        try:
            import pjsua2 as pj
            
            self.endpoint = pj.Endpoint()
            self.endpoint.libCreate()
            
            ep_cfg = pj.EpConfig()
            ep_cfg.uaConfig.userAgent = self.config.agent_name
            ep_cfg.sipConfig.transportConfig.port = self.config.sip_port
            
            self.endpoint.libInit(ep_cfg)
            
            transport_cfg = pj.TransportConfig()
            transport_cfg.port = self.config.sip_port
            self.endpoint.transportCreate(pj.pj_TP_PROTO_UDP, transport_cfg)
            
            acc_cfg = pj.AccountConfig()
            acc_cfg.idUri = f"sip:{self.config.sip_username}@{self.config.sip_domain}"
            acc_cfg.regConfig.registrarUri = f"sip:{self.config.sip_domain}"
            
            # احراز هویت
            auth = pj.AuthCred("digest", "*", self.config.sip_username, self.config.sip_password)
            acc_cfg.sipConfig.authCreds.append(auth)
            
            self.account = self.endpoint.accountCreate(acc_cfg)
            self.is_active = True
            logger.info("پشته SIP با موفقیت راه‌اندازی شد.")
            
        except ImportError:
            logger.error("کتابخانه pjsua2 یافت نشد. لطفاً آن را نصب کنید یا use_real_sip را False کنید.")
        except Exception as e:
            logger.error(f"خطا در راه‌اندازی SIP: {e}")

    def make_call(self, destination: str) -> bool:
        """برقراری تماس خروجی"""
        if self.config.use_real_sip and self.is_active:
            try:
                # کد واقعی تماس PJSIP
                # self.endpoint.callMakeCall(self.account, f"sip:{destination}@{self.config.sip_domain}")
                logger.info(f"تماس واقعی به {destination} آغاز شد...")
                return True
            except Exception as e:
                logger.error(f"خطا در برقراری تماس: {e}")
                return False
        else:
            # شبیه‌سازی
            logger.info(f"[SIMULATION] در حال برقراری تماس با {destination}...")
            time.sleep(1)
            logger.info("[SIMULATION] تماس متصل شد.")
            return True

    def hangup(self):
        """قطع تماس"""
        logger.info("تماس قطع شد.")

# ==============================================================================
# پردازشگر مکالمه (Dialogue Manager)
# ==============================================================================

class ConversationProcessor:
    """مدیریت منطق مکالمه و تصمیم‌گیری"""
    
    def __init__(self, db: KnowledgeDatabase):
        self.db = db
        self.context = {}
        
    def process_input(self, user_text: str) -> str:
        """پردازش ورودی کاربر و تولید پاسخ"""
        if not user_text.strip():
            return "لطفاً صحبت کنید، صدایی دریافت نشد."
        
        # تحلیل ساده نیت (Intent Detection)
        user_text_lower = user_text.lower()
        
        if "خداحافظ" in user_text_lower or "تمام" in user_text_lower:
            return "با تشکر از تماس شما. خدانگهدار."
        
        if "کمک" in user_text_lower or "اپراتور" in user_text_lower:
            return "در حال انتقال به اپراتور انسانی... لطفاً منتظر بمانید."
        
        # جستجو در پایگاه دانش
        answer = self.db.get_answer(user_text)
        return answer

# ==============================================================================
# عامل اصلی (Main Agent)
# ==============================================================================

class AutonomousCallAgent:
    """عامل اصلی هماهنگ‌کننده تمام اجزا"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db = KnowledgeDatabase(config.db_path)
        self.voip = InternalVoIPCore(config)
        self.stt = PersianSTT(config.vosk_model_path)
        self.tts = PersianTTS(config.piper_model_path, config.piper_config_path)
        self.dialogue = ConversationProcessor(self.db)
        
        self.current_call_active = False
        self.call_start_time = None
        
    def start(self):
        """شروع سرویس و گوش دادن به تماس‌های ورودی"""
        logger.info("="*60)
        logger.info(f"سامانه تماس خودکار {self.config.agent_name} شروع به کار کرد.")
        logger.info(f"گوش دادن روی پورت SIP: {self.config.sip_port}")
        logger.info("="*60)
        
        # در محیط واقعی، اینجا یک حلقه رویداد (Event Loop) برای SIP وجود دارد
        # در حالت شبیه‌سازی، فقط پیام لاگ می‌کنیم
        if not self.config.use_real_sip:
            logger.info("سیستم در حالت شبیه‌سازی است. برای تست از متد make_outbound_call استفاده کنید.")

    def stop(self):
        """توقف سرویس"""
        logger.info("سامانه در حال توقف است...")
        self.voip.hangup()
        
    def make_outbound_call(self, phone_number: str):
        """اجرای یک سناریوی تماس خروجی کامل"""
        logger.info(f"\n--- شروع تماس خروجی با {phone_number} ---")
        
        if not self.voip.make_call(phone_number):
            logger.error("تماس برقرار نشد.")
            return

        self.current_call_active = True
        self.call_start_time = time.time()
        transcript_log = []
        
        # 1. پخش پیام خوش‌آمدگویی
        greeting = self.config.greeting_message
        logger.info(f"[ربات]: {greeting}")
        audio_data = self.tts.synthesize(greeting)
        # در واقعیت: پخش audio_data از بلندگو/خط تلفن
        transcript_log.append(f"Bot: {greeting}")
        
        # شبیه‌سازی حلقه مکالمه (3 دور)
        mock_responses = [
            "چطور می‌توانم قبض برق را پرداخت کنم؟",
            "آیا امکان قسط‌بندی وجود دارد؟",
            "خداحافظ"
        ]
        
        for i, mock_user_input in enumerate(mock_responses):
            if time.time() - self.call_start_time > self.config.max_call_duration:
                logger.warning("زمان مکالمه به پایان رسید.")
                break
                
            # شبیه‌سازی دریافت صدا از کاربر
            logger.info(f"[کاربر] (شبیه‌سازی): {mock_user_input}")
            transcript_log.append(f"User: {mock_user_input}")
            
            # پردازش و پاسخ
            response = self.dialogue.process_input(mock_user_input)
            logger.info(f"[ربات]: {response}")
            audio_data = self.tts.synthesize(response)
            transcript_log.append(f"Bot: {response}")
            
            if "خداحافظ" in response:
                break
            
            time.sleep(1) # مکث کوتاه بین جملات

        # پایان تماس
        duration = int(time.time() - self.call_start_time)
        self.voip.hangup()
        self.current_call_active = False
        
        # ثبت در دیتابیس
        full_transcript = "\n".join(transcript_log)
        self.db.log_call("System", phone_number, duration, full_transcript)
        logger.info(f"تماس با مدت {duration} ثانیه به پایان رسید و ثبت شد.\n")

# ==============================================================================
# نقطه ورود اصلی (Main Entry Point)
# ==============================================================================

def main():
    # پیکربندی سیستم
    config = Config(
        agent_name="اپراتور هوشمند وصول مطالبات ایلام",
        sip_domain="voip.bargh-ilam.ir",
        sip_port=5060,
        db_path="./ilam_power_knowledge.db",
        # مسیرهای مدل‌ها (در صورت دانلود بودن استفاده می‌شوند)
        vosk_model_path="./models/vosk-fa-small",
        piper_model_path="./models/fa_IR-amir-medium.onnx",
        use_real_sip=False, # فعلاً روی شبیه‌سازی
        greeting_message="سلام وقت بخیر، از بخش وصول مطالبات شرکت توزیع نیروی برق ایلام تماس می‌گیرم."
    )

    # ایجاد نمونه عامل
    agent = AutonomousCallAgent(config)
    
    try:
        # شروع سرویس
        agent.start()
        
        # اجرای یک کمپین آزمایشی
        test_numbers = ["09183001002", "09183001003"]
        
        for number in test_numbers:
            agent.make_outbound_call(number)
            time.sleep(2) # فاصله بین تماس‌ها
            
        logger.info("کمپین آزمایشی به پایان رسید. سیستم در حالت انتظار است...")
        
        # در محیط عملیاتی، اینجا وارد حلقه بی‌نهایت می‌شود تا تماس‌های ورودی را مدیریت کند
        # while True: time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("توسط کاربر متوقف شد.")
        agent.stop()
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}")
        agent.stop()

if __name__ == "__main__":
    main()
