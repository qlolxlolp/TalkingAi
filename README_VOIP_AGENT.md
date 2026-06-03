# سیستم تماس تلفنی خودکار فارسی - VoIP کاملاً مستقل

## 🎯 معرفی

این سیستم یک **سرویس VoIP انحصاری و ۱۰۰٪ درون‌برنامه‌ای** است که بدون نیاز به هیچ سخت‌افزار تلفن، سرویس ابری یا کمک خارجی، قادر به:
- دریافت و برقراری تماس‌های تلفنی
- مکالمه خودکار به زبان فارسی
- درک مطلب و پاسخ هوشمندانه
- دسترسی به دیتابیس محلی برای پاسخ‌گویی دقیق

می‌باشد.

## 🏗️ معماری سیستم

```
┌─────────────────────────────────────────────────────────┐
│           AutonomousCallAgent (عامل اصلی)                │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ InternalVoIP │  │ Conversation │  │  Knowledge   │  │
│  │    Core      │  │  Processor   │  │  Database    │  │
│  │  (هسته SIP)  │  │ (پردازشگر)   │  │  (دیتابیس)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                  │                  │          │
│  ┌──────┴──────┐   ┌──────┴──────┐            │          │
│  │ PersianSTT  │   │ PersianTTS  │            │          │
│  │ (گفتار→متن) │   │ (متن→گفتار) │            │          │
│  └─────────────┘   └─────────────┘            │          │
└─────────────────────────────────────────────────────────┘
```

## 📦 پیش‌نیازها

### ۱. نصب پایتون و کتابخانه‌ها

```bash
# ایجاد محیط مجازی (اختیاری اما توصیه می‌شود)
python3 -m venv voip_env
source voip_env/bin/activate  # در لینوکس/مک
# یا
voip_env\Scripts\activate  # در ویندوز

# نصب کتابخانه‌های مورد نیاز
pip install vosk soundfile numpy
```

### ۲. دانلود مدل‌های هوش مصنوعی

#### مدل Vosk (گفتار به متن فارسی):
```bash
mkdir -p models
cd models

# دانلود مدل کوچک فارسی Vosk
wget https://alphacephei.com/vosk/models/vosk-model-small-fa-0.5.tar.gz
tar xzf vosk-model-small-fa-0.5.tar.gz
mv vosk-model-small-fa-0.5 vosk-fa-small

cd ..
```

#### مدل Piper (متن به گفتار فارسی):
```bash
# دانلود مدل فارسی Piper
cd models

# مدل فارسی را از مخزن Piper دانلود کنید
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x86_64.tar.gz
tar xzf piper_linux_x86_64.tar.gz

# دانلود مدل صوتی فارسی
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fa/fa_IR/amir/medium/fa_IR-amir-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fa/fa_IR/amir/medium/fa_IR-amir-medium.onnx.json

cd ..
```

### ۳. نصب PJSIP (برای عملکرد واقعی VoIP)

```bash
# در اوبونتو/دبیان
sudo apt-get update
sudo apt-get install libpjproject-dev python3-pip

pip install pjsip

# یا در مک
brew install pjproject
pip install pjsip
```

## 🚀 راه‌اندازی و اجرا

### روش ۱: اجرای демонstration (تستی)

```bash
python autonomous_voip_agent.py
```

این دستور یک демонstration کامل اجرا می‌کند که:
- سیستم را راه‌اندازی می‌کند
- چند تماس آزمایشی برقرار می‌کند
- مکالمات نمونه انجام می‌دهد
- تاریخچه را در دیتابیس ثبت می‌کند

### روش ۲: اجرای دائمی (Production)

فایل `autonomous_voip_agent.py` را ویرایش کرده و بخش `main()` را به صورت زیر تغییر دهید:

```python
def main():
    config = Config(
        agent_name="اپراتور هوشمند پارسی",
        sip_domain="voip.yourcompany.local",
        sip_port=5060,
        db_path="./knowledge_base.db",
        vosk_model_path="./models/vosk-fa-small",
        piper_model_path="./models/fa_IR-amir-medium.onnx"
    )
    
    agent = AutonomousCallAgent(config)
    
    try:
        agent.start()
        # حلقه اصلی برای اجرای دائمی
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("توسط کاربر متوقف شد.")
        agent.stop()
```

سپس اجرا کنید:
```bash
python autonomous_voip_agent.py
```

## 📞 نحوه استفاده

### برقراری تماس خروجی

```python
from autonomous_voip_agent import AutonomousCallAgent, Config

config = Config()
agent = AutonomousCallAgent(config)
agent.start()

# برقراری تماس
success = agent.make_call("09121234567")

if success:
    print("تماس با موفقیت برقرار شد")
else:
    print("خطا در برقراری تماس")
```

### دریافت تماس ورودی

سیستم به صورت خودکار روی پورت SIP تنظیم شده گوش می‌دهد و تماس‌های ورودی را پاسخ می‌دهد.

### سفارشی‌سازی رفتار اپراتور

فایل `Config` را ویرایش کنید:

```python
config = Config(
    agent_name="پشتیبان هوشمند شرکت",
    greeting_message="سلام! به شرکت ما خوش آمدید. من دستیار هوشمند شما هستم.",
    max_call_duration=900,  # ۱۵ دقیقه
    sip_username="support_agent",
    sip_password="your_secure_password"
)
```

## 💾 مدیریت دیتابیس دانش

دیتابیس به صورت خودکار ایجاد می‌شود، اما می‌توانید داده‌های بیشتری اضافه کنید:

```python
from autonomous_voip_agent import KnowledgeDatabase

db = KnowledgeDatabase("./knowledge_base.db")

# افزودن سوال جدید به صورت دستی
import sqlite3
conn = sqlite3.connect("./knowledge_base.db")
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO faq (question, answer, keywords, category) 
    VALUES (?, ?, ?, ?)
""", (
    "چطور می‌توانم رمز عبورم را تغییر دهم؟",
    "برای تغییر رمز عبور، به پنل کاربری خود مراجعه کرده و از بخش تنظیمات اقدام کنید.",
    "رمز,عبور,تغییر,پسورد",
    "امنیت"
))

conn.commit()
conn.close()
```

## 🔧 فعال‌سازی حالت عملیاتی کامل

برای تبدیل سیستم از حالت شبیه‌سازی به عملیاتی کامل:

### ۱. فعال‌سازی PJSIP در هسته VoIP

در کلاس `InternalVoIPCore`، متد `_init_sip_stack` را به صورت زیر تغییر دهید:

```python
def _init_sip_stack(self):
    import pjsua2 as pj
    
    self.ep = pj.Endpoint()
    self.ep.libCreate()
    
    # تنظیمات SIP
    ep_cfg = pj.EpConfig()
    ep_cfg.uaConfig.userAgent = "AutonomousPersianAgent"
    ep_cfg.sipConfig.transportConfig.port = self.config.sip_port
    
    self.ep.libInit(ep_cfg)
    
    # ایجاد_transport UDP
    transport_cfg = pj.TransportConfig()
    transport_cfg.port = self.config.sip_port
    self.ep.transportCreate(pj.PJ_TP_PROTO_UDP, transport_cfg)
    
    # ثبت حساب SIP
    acc_cfg = pj.AccountConfig()
    id_uri = f"sip:{self.config.sip_username}@{self.config.sip_domain}"
    reg_uri = f"sip:{self.config.sip_domain}"
    
    acc_cfg.idUri = id_uri
    acc_cfg.regConfig.registrarUri = reg_uri
    acc_cfg.sipConfig.authCreds.append(pj.AuthCred(
        "digest", "*", 
        self.config.sip_username, 
        self.config.sip_password
    ))
    
    self.acc = self.ep.accountCreate(acc_cfg)
    
    logger.info("پشته SIP با موفقیت راه‌اندازی شد")
```

### ۲. فعال‌سازی Vosk واقعی

مدل Vosk را دانلود کرده و مسیر آن را در Config تنظیم کنید. سیستم به صورت خودکار تشخیص می‌دهد و از مدل واقعی استفاده می‌کند.

### ۳. فعال‌سازی Piper واقعی

مدل Piper را نصب و راه‌اندازی کنید:

```python
def _init_model(self):
    try:
        from piper import PiperVoice
        
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"مدل یافت نشد: {self.model_path}")
        
        self.synthesizer = PiperVoice.load(
            model_path=self.model_path,
            config_path=self.config_path
        )
        logger.info("موتور Piper با موفقیت بارگذاری شد")
        
    except Exception as e:
        logger.error(f"خطا در بارگذاری Piper: {e}")
        self.synthesizer = None
```

## 📊 مشاهده تاریخچه تماس‌ها

```bash
sqlite3 knowledge_base.db

# مشاهده تمام تماس‌ها
SELECT * FROM call_history ORDER BY timestamp DESC;

# مشاهده سوالات متداول
SELECT question, answer FROM faq;

# مشاهده اطلاعات کاربران
SELECT name, phone, balance FROM users;
```

## 🔒 امنیت

- تغییر رمز عبور پیش‌فرض در Config
- محدود کردن IP‌های مجاز برای تماس ورودی
- استفاده از TLS/SRTP برای رمزنگاری تماس‌ها
- لاگ‌گیری تمام فعالیت‌ها

## 🎯 سناریوهای کاربردی

### ۱. پشتیبانی مشتریان
```python
config.agent_name = "پشتیبان هوشمند"
config.greeting_message = "سلام! برای چه موضوعی تماس گرفته‌اید؟"
```

### ۲. نوبت‌دهی خودکار
اضافه کردن جدول نوبت‌ها به دیتابیس و پردازش درخواست‌های رزرو

### ۳. نظرسنجی تلفنی
ایجاد الگوهای مکالمه برای جمع‌آوری نظرات مشتریان

### ۴. اطلاع‌رسانی انبوه
برقراری تماس خودکار با لیستی از شماره‌ها برای اطلاع‌رسانی

## 🛠️ عیب‌یابی

### مشکل: مدل Vosk بارگذاری نمی‌شود
```bash
# بررسی وجود مدل
ls -la models/vosk-fa-small

# دانلود مجدد
wget https://alphacephei.com/vosk/models/vosk-model-small-fa-0.5.tar.gz
```

### مشکل: پورت SIP اشغال است
```bash
# بررسی پورت
sudo netstat -tulpn | grep 5060

# تغییر پورت در Config
config.sip_port = 5061
```

### مشکل: کیفیت صدا پایین است
- افزایش sample_rate در Config به 22050 یا 44100
- استفاده از مدل‌های بزرگ‌تر Vosk و Piper

## 📈 بهینه‌سازی برای Production

1. **استفاده از Redis** برای کش کردن پاسخ‌های متداول
2. **Load Balancing** برای مدیریت تماس‌های همزمان زیاد
3. **Monitoring** با Prometheus و Grafana
4. **Backup** خودکار از دیتابیس
5. **Failover** برای افزونگی

## 📝 مجوز و حقوق

این سیستم کاملاً متن‌باز و قابل استفاده برای اهداف تجاری و شخصی است.

---

## 🎉 نتیجه‌گیری

این سیستم یک راه‌حل کامل و مستقل برای اتوماسیون تماس‌های تلفنی به زبان فارسی است که:
- ✅ بدون نیاز به سخت‌افزار خارجی
- ✅ بدون وابستگی به سرویس‌های ابری
- ✅ کاملاً قابل سفارشی‌سازی
- ✅ مقیاس‌پذیر برای محیط‌های عملیاتی

می‌باشد.

برای شروع کافیست دستور `python autonomous_voip_agent.py` را اجرا کنید!
