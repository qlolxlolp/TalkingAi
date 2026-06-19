# -*- coding: utf-8 -*-
"""
اسکریپت ساخت فایل اجرایی EXE برای سامانه برق ایلام
با استفاده از PyInstaller
"""

import os
import sys
import subprocess
import shutil

def build_exe():
    print("=" * 60)
    print("سامانه ساخت فایل اجرایی - شرکت توزیع نیروی برق ایلام")
    print("=" * 60)
    
    # بررسی وجود پایتون و pyinstaller
    try:
        import PyInstaller
        print("[OK] کتابخانه PyInstaller یافت شد.")
    except ImportError:
        print("[ERROR] کتابخانه PyInstaller نصب نیست.")
        print("در حال نصب خودکار...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller با موفقیت نصب شد.")
    
    # مسیر فایل اصلی
    main_script = "ilam_power_multimedia_agent.py"
    
    if not os.path.exists(main_script):
        print(f"[ERROR] فایل {main_script} یافت نشد!")
        return False
    
    print(f"\n[INFO] در حال ساخت فایل اجرایی از {main_script}...")
    
    # دستور PyInstaller
    # --onefile: تمام برنامه در یک فایل exe واحد
    # --noconsole: بدون پنجره کنسول (برای برنامه‌های GUI)
    # --name: نام فایل خروجی
    # --icon: آیکون برنامه (اختیاری)
    # --add-data: افزودن فایل‌های اضافی (در صورت نیاز)
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "IlamPowerAgent",
        "--clean",  # پاک کردن کش قبلی
        main_script
    ]
    
    # اگر آیکون داشتید، خط زیر را از کامنت خارج کنید
    # cmd.extend(["--icon", "logo.ico"])
    
    try:
        print("[INFO] اجرای PyInstaller...")
        print("[INFO] این فرآیند ممکن است چند دقیقه طول بکشد.")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print("\n" + "=" * 60)
        print("[SUCCESS] فایل اجرایی با موفقیت ساخته شد!")
        print("=" * 60)
        
        # مسیر فایل خروجی
        dist_folder = "dist"
        exe_path = os.path.join(dist_folder, "IlamPowerAgent.exe")
        
        if os.path.exists(exe_path):
            file_size = os.path.getsize(exe_path) / (1024 * 1024)  # مگابایت
            print(f"\n📦 مسیر فایل اجرایی: {os.path.abspath(exe_path)}")
            print(f"📊 حجم فایل: {file_size:.2f} MB")
            print(f"\n✅ آماده اجرا روی هر سیستم ویندوزی بدون نیاز به نصب پایتون!")
            
            # کپی فایل به پوشه اصلی برای دسترسی آسان‌تر
            final_path = "IlamPowerAgent.exe"
            shutil.copy(exe_path, final_path)
            print(f"\n💾 یک کپی از فایل در مسیر اصلی پروژه نیز قرار گرفت: {os.path.abspath(final_path)}")
            
        else:
            print("[WARNING] فایل exe ساخته شده اما در مسیر مورد انتظار یافت نشد.")
            
        # نمایش راهنمای نهایی
        print("\n" + "=" * 60)
        print("راهنمای استفاده:")
        print("=" * 60)
        print("1. فایل IlamPowerAgent.exe را کپی کرده و روی سیستم مقصد اجرا کنید.")
        print("2. هیچ نیازی به نصب پایتون یا کتابخانه‌های جانبی نیست.")
        print("3. دیتابیس به صورت خودکار در کنار فایل exe ایجاد می‌شود.")
        print("4. برای اجرای همزمان چند نمونه، از کپی‌های جداگانه فایل استفاده کنید.")
        print("=" * 60)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] خطا در ساخت فایل اجرایی:")
        print(e.stderr)
        print("\nراه‌حل‌های ممکن:")
        print("- مطمئن شوید تمام وابستگی‌ها نصب هستند: pip install pyinstaller")
        print("- بررسی کنید فایل اصلی ilam_power_multimedia_agent.py بدون خطا باشد.")
        print("- آنتی‌ویروس را موقتاً غیرفعال کنید (گاهی تداخل ایجاد می‌کند).")
        return False
        
    except Exception as e:
        print(f"\n[ERROR] خطای غیرمنتظره: {str(e)}")
        return False

if __name__ == "__main__":
    success = build_exe()
    if success:
        print("\n🎉 عملیات با موفقیت به پایان رسید!")
    else:
        print("\n❌ عملیات با خطا مواجه شد.")
        sys.exit(1)
