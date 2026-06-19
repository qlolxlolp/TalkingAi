"""
اسکریپت ساخت فایل اجرایی EXE برای سامانه هوشمند وصول مطالبات برق ایلام
این اسکریپت با استفاده از PyInstaller، کد پایتون را به یک فایل exe مستقل تبدیل می‌کند.
"""

import PyInstaller.__main__
import os
import shutil

def build_exe():
    """ساخت فایل اجرایی با تنظیمات بهینه"""
    
    # اطمینان از وجود پوشه‌های لازم
    os.makedirs('dist', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    print("="*80)
    print("شروع فرآیند ساخت فایل اجرایی IlamElectricAgent.exe")
    print("="*80)
    
    PyInstaller.__main__.run([
        'ilam_electric_agent.py',              # فایل اصلی برنامه
        '--name=IlamElectricAgent',            # نام فایل خروجی
        '--onefile',                           # تولید یک فایل exe واحد
        '--windowed',                          # بدون پنجره کنسول (برای نسخه نهایی)
        '--icon=NONE',                         # آیکون سفارشی (در صورت نیاز اضافه شود)
        '--add-data=README.md;.',              # افزودن فایل راهنما
        '--hidden-import=sqlite3',             # ایمپورت‌های پنهان مورد نیاز
        '--hidden-import=json',
        '--hidden-import=logging',
        '--hidden-import=datetime',
        '--exclude-module=tkinter',            # حذف ماژول‌های غیرضروری برای کاهش حجم
        '--exclude-module=PIL',
        '--clean',                             # پاکسازی فایل‌های موقت قبلی
        '--noconfirm',                         # عدم نمایش پیام تأیید
        '--log-level=WARN'                     # سطح لاگ‌گیری
    ])
    
    # بررسی موفقیت آمیز بودن ساخت
    exe_path = os.path.join('dist', 'IlamElectricAgent.exe')
    if os.path.exists(exe_path):
        file_size = os.path.getsize(exe_path) / (1024 * 1024)  # حجم به مگابایت
        print("\n" + "="*80)
        print("✅ ساخت فایل اجرایی با موفقیت انجام شد!")
        print(f"📦 مسیر فایل: {exe_path}")
        print(f"📊 حجم فایل: {file_size:.2f} MB")
        print("="*80)
        print("\nراهنمای اجرا:")
        print("1. فایل IlamElectricAgent.exe را از پوشه dist کپی کنید")
        print("2. روی هر سیستم ویندوزی اجرا کنید (نیاز به نصب پایتون نیست)")
        print("3. گزارش‌ها در پوشه logs ذخیره می‌شوند")
        print("4. دیتابیس در همان مسیر اجرا ایجاد می‌شود")
        print("="*80)
    else:
        print("\n❌ خطا در ساخت فایل اجرایی. لطفاً لاگ‌ها را بررسی کنید.")
        return False
    
    return True


if __name__ == "__main__":
    try:
        build_exe()
    except Exception as e:
        print(f"خطا در فرآیند بیلد: {e}")
        import traceback
        traceback.print_exc()
