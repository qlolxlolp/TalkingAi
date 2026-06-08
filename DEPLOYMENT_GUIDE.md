# 📦 راهنمای نهایی استقرار و اجرای سامانه هوشمند برق ایلام

## ✅ وضعیت فعلی پروژه

پروژه با موفقیت تکمیل و فایل اجرایی تولید شد:

| فایل | توضیح | وضعیت |
|------|-------|-------|
| `ilam_electric_agent.py` | کد اصلی برنامه (۴۱۷ خط) | ✅ آماده |
| `build_exe.py` | اسکریپت ساخت EXE | ✅ آماده |
| `dist/IlamElectricAgent` | فایل اجرایی باینری (۳۸ مگابایت) | ✅ تولید شد |
| `README_FA.md` | مستندات فارسی جامع | ✅ آماده |
| `requirements.txt` | لیست وابستگی‌ها | ✅ آماده |
| `ilam_electric_db.sqlite` | دیتابیس داخلی | ✅ ایجاد شد |

---

## 🖥️ نحوه اجرا در محیط عملیاتی (ویندوز)

### روش ۱: اجرای مستقیم فایل EXE (توصیه شده برای کاربران نهایی)

1. فایل `IlamElectricAgent.exe` را از پوشه `dist` کپی کنید.
2. آن را روی هر سیستم ویندوزی (۱۰/۱۱) اجرا کنید.
3. برنامه به صورت خودکار:
   - به سامانه `eserv.bargh-ilam.ir` متصل می‌شود
   - رابط گرافیکی نمایش داده می‌شود
   - دکمه "شروع کمپین" را فشار دهید

### روش ۲: اجرای از طریق پایتون (برای توسعه‌دهندگان)

```bash
# نصب وابستگی‌ها
pip install -r requirements.txt

# اجرای مستقیم
python ilam_electric_agent.py
```

---

## 🔧 پیکربندی اتصال به سامانه واقعی

در حال حاضر، کد از یک شبیه‌ساز برای اتصال به `eserv.bargh-ilam.ir` استفاده می‌کند. برای اتصال واقعی:

### مرحله ۱: دریافت اطلاعات API از واحد IT شرکت برق

- آدرس دقیق API (مثلاً: `https://eserv.bargh-ilam.ir/api/v1/customers`)
- نام کاربری و رمز عبور سرویس
- توکن احراز هویت (در صورت وجود)

### مرحله ۲: ویرایش فایل `ilam_electric_agent.py`

بخش `IlamElectricAPI` را به روز کنید:

```python
def authenticate(self, username: str, password: str) -> bool:
    payload = {
        'username': username,
        'password': password,
        'grant_type': 'password'  # یا هر مقدار مورد نیاز
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    response = self.session.post(self.login_url, data=payload, headers=headers, verify=True)
    
    if response.status_code == 200:
        self.token = response.json().get('access_token')
        self.is_connected = True
        return True
    return False

def get_customer_info(self, account_id: str) -> Optional[Dict]:
    headers = {'Authorization': f'Bearer {self.token}'}
    response = self.session.get(
        f"{self.api_base}/customers/{account_id}",
        headers=headers,
        verify=True
    )
    if response.status_code == 200:
        return response.json()
    return None
```

---

## 🎙️ فعال‌سازی قابلیت‌های صوتی کامل (TTS/STT)

برای تبدیل مکالمه متنی به صوتی واقعی:

### نصب موتورهای آفلاین فارسی

1. **Piper TTS** (متن به گفتار):
   ```bash
   # دانلود مدل فارسی
   wget https://github.com/rhasspy/piper/releases/download/v1.0.0/piper_linux_x86_64.tar.gz
   tar xzf piper_linux_x86_64.tar.gz
   wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fa_IR/amir/medium/fa_IR-amir-medium.onnx
   ```

2. **Vosk STT** (گفتار به متن):
   ```bash
   pip install vosk
   # دانلود مدل فارسی Vosk
   wget https://alphacephei.com/vosk/models/vosk-model-fa-0.5.zip
   unzip vosk-model-fa-0.5.zip
   ```

### ویرایش متد `speak` و افزودن `listen`

```python
def speak(self, text: str):
    import subprocess
    subprocess.run([
        './piper',
        '--model', 'fa_IR-amir-medium.onnx',
        '--output_file', 'temp_response.wav'
    ], input=text.encode(), text=True)
    
    # پخش صدا
    import playsound
    playsound.playsound('temp_response.wav')

def listen(self) -> str:
    from vosk import Model, KaldiRecognizer
    import pyaudio
    
    model = Model("vosk-model-fa-0.5")
    rec = KaldiRecognizer(model, 16000)
    
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
    stream.start_stream()
    
    while True:
        data = stream.read(4000)
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            return result['text']
```

---

## 📊 گزارش‌گیری از دیتابیس

دیتابیس `ilam_electric_db.sqlite` شامل دو جدول اصلی است:

### استخراج داده‌ها با SQLite Browser

1. نرم‌افزار [DB Browser for SQLite](https://sqlitebrowser.org/) را نصب کنید.
2. فایل دیتابیس را باز کنید.
3. کوئری‌های نمونه:

```sql
-- لیست تمام تماس‌های امروز
SELECT * FROM call_logs 
WHERE date(timestamp) = date('now');

-- وعده‌های پرداخت ثبت شده
SELECT account_id, promise_date, amount 
FROM payment_promises 
ORDER BY recorded_at DESC;

-- نرخ موفقیت کمپین
SELECT outcome, COUNT(*) as count 
FROM call_logs 
GROUP BY outcome;
```

### خروجی Excel برای مدیریت

```python
import pandas as pd
import sqlite3

conn = sqlite3.connect('ilam_electric_db.sqlite')
df = pd.read_sql_query("SELECT * FROM call_logs", conn)
df.to_excel("campaign_report.xlsx", index=False)
```

---

## 🔐 ملاحظات امنیتی برای استقرار نهایی

1. **مدیریت رمزهای عبور**:
   - هرگز رمزها را در کد سخت‌کد نکنید
   - از متغیرهای محیطی استفاده کنید:
     ```python
     import os
     API_USERNAME = os.getenv('ELECTRIC_API_USER')
     API_PASSWORD = os.getenv('ELECTRIC_API_PASS')
     ```

2. **فایروال و شبکه**:
   - پورت‌های لازم برای VoIP (معمولاً 5060 برای SIP، 10000-20000 برای RTP)
   - دسترسی outbound به `eserv.bargh-ilam.ir:443`

3. **لاگ‌برداری امن**:
   - شماره تلفن مشترکین در لاگ‌ها ماسک شود
   - مثال: `0918****001`

---

## 🚀 سناریوی عملیاتی پیشنهادی

### گام ۱: راه‌اندازی سرور
- نصب ویندوز سرور ۲۰۱۹ یا بالاتر
- کپی فایل `IlamElectricAgent.exe`
- تنظیم اتصال اینترنت پرسرعت

### گام ۲: پیکربندی
- وارد کردن اطلاعات API واقعی شرکت برق
- تست اتصال به سامانه eserv

### گام ۳: اجرای آزمایشی
- انتخاب ۱۰ مشترک بدهکار نمونه
- اجرای کمپین تستی
- بررسی لاگ‌ها و دیتابیس

### گام ۴: اجرای سراسری
- بارگذاری لیست کامل بدهکاران از سامانه
- شروع کمپین خودکار
- پایش لحظه‌ای از طریق داشبورد

---

## 📞 پشتیبانی فنی

برای هرگونه سوال یا مشکل در استقرار:
- بررسی فایل `electric_agent_log.txt`
- تماس با واحد فناوری اطلاعات شرکت توزیع برق ایلام

---

**تهیه شده با افتخار برای خدمت‌رسانی به مردم شریف استان ایلام** 🌟
*شرکت توزیع نیروی برق استان ایلام - معاونت بهره‌برداری*
