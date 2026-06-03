"""
اسکریپت ساخت فایل اجرایی (EXE) برای سامانه هوشمند برق ایلام
این اسکریپت از PyInstaller برای بسته‌بندی کامل برنامه استفاده می‌کند.
"""

import os
import sys
import subprocess

def build_exe():
    print("🚀 شروع فرآیند ساخت فایل اجرایی مستقل (EXE)...")
    
    # نام فایل اصلی
    script_name = "ilam_electric_agent.py"
    app_name = "IlamElectricAgent"
    
    if not os.path.exists(script_name):
        print(f"❌ خطا: فایل {script_name} یافت نشد.")
        return

    # دستور PyInstaller با تنظیمات بهینه برای برنامه‌های فارسی و چندفایلی
    # --onefile: همه چیز در یک فایل exe
    # --windowed: بدون پنجره کنسول (برای نسخه نهایی)، فعلا کنسول را نگه میداریم برای دیباگ
    # --add-data: شامل کردن فایل‌های اضافی مثل مدل‌ها و دیتابیس
    # --hidden-import: ایمپورت‌های پنهان که ممکن است تشخیص داده نشوند
    
    cmd = [
        "pyinstaller",
        "--name", app_name,
        "--onefile",
        "--console",  # در نسخه نهایی می‌توان به --windowed تغییر داد
        "--add-data", f"ilam_electric_db.sqlite{os.pathsep}.",  # دیتابیس (اگر وجود داشته باشد)
        "--hidden-import", "customtkinter",
        "--hidden-import", "requests",
        "--hidden-import", "urllib3",
        "--hidden-import", "sqlite3",
        "--noconfirm",
        script_name
    ]
    
    # اگر فایل دیتابیس وجود ندارد، آرگومان آن را حذف کن تا خطا ندهد
    if not os.path.exists("ilam_electric_db.sqlite"):
        cmd.remove("--add-data")
        cmd.remove("ilam_electric_db.sqlite;.")
        print("⚠️ دیتابیس اولیه یافت نشد. برنامه در اولین اجرا آن را می‌سازد.")

    print(f"📦 در حال بسته‌بندی: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print("\n" + "="*50)
        print("✅ ساخت فایل EXE با موفقیت انجام شد!")
        print(f"📂 فایل اجرایی در پوشه 'dist' قرار دارد: dist/{app_name}.exe")
        print("="*50)
        print("📝 نکات مهم:")
        print("1. فایل exe تولید شده کاملاً مستقل است و روی هر ویندوزی اجرا می‌شود.")
        print("2. برای عملکرد کامل صوتی، باید موتورهای TTS/STT نیز در کنار exe باشند یا درون آن تعبیه شوند.")
        print("3. اتصال به eserv.bargh-ilam.ir نیازمند اینترنت فعال است.")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ خطا در فرآیند بیلد: {e}")
        print("💡 اطمینان حاصل کنید که PyInstaller نصب است: pip install pyinstaller")

if __name__ == "__main__":
    build_exe()
