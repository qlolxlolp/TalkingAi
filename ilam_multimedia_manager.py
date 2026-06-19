#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سامانه جامع مدیریت چندرسانه‌ای و گزارشات تعاملی
شرکت توزیع نیروی برق استان ایلام

این ماژول امکان نمایش، ایجاد، ویرایش و مدیریت کامل:
- تصاویر و گرافیک‌های پویا
- نمودارها و چارت‌های تعاملی
- جداول داده‌ای زنده
- فرم‌های ورود اطلاعات
- گزارشات چندصفحه‌ای
- داشبوردهای مدیریتی
- مدیا پلیر تعبیه شده
- خروجی‌های PDF و Excel

را با دسترسی کامل خواندن/نوشتن بدون محدودیت فراهم می‌کند.
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import threading
import queue
import time

# کتابخانه‌های گرافیکی و رابط کاربری
try:
    import customtkinter as ctk
    from tkinter import ttk, filedialog, messagebox
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure
    import numpy as np
except ImportError as e:
    print(f"خطا در واردات کتابخانه‌های گرافیکی: {e}")
    print("لطفاً دستور زیر را اجرا کنید:")
    print("pip install customtkinter pillow matplotlib numpy")
    sys.exit(1)

# تنظیمات ظاهری
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# تنظیم لاگ‌گیری
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/multimedia_manager.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MultimediaDatabase:
    """مدیریت پایگاه داده چندرسانه‌ای با دسترسی کامل خواندن/نوشتن"""
    
    def __init__(self, db_path: str = "ilam_multimedia.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._initialize_database()
        logger.info(f"پایگاه داده چندرسانه‌ای در {db_path} آماده شد.")
    
    def _initialize_database(self):
        """ایجاد جداول لازم برای ذخیره‌سازی چندرسانه‌ای"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # جدول فایل‌های چندرسانه‌ای
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS media_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    category TEXT,
                    title TEXT,
                    description TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_size INTEGER,
                    dimensions TEXT,
                    metadata JSON,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # جدول گزارشات
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_name TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    data_source TEXT,
                    filters JSON,
                    layout_config JSON,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_viewed TIMESTAMP,
                    view_count INTEGER DEFAULT 0,
                    is_public BOOLEAN DEFAULT 1,
                    content BLOB
                )
            ''')
            
            # جدول نمودارها
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS charts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chart_name TEXT NOT NULL,
                    chart_type TEXT NOT NULL,
                    data_query TEXT,
                    config JSON,
                    colors JSON,
                    labels JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP,
                    cache_data BLOB
                )
            ''')
            
            # جدول فرم‌های پویا
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS dynamic_forms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    form_name TEXT NOT NULL,
                    form_schema JSON NOT NULL,
                    validation_rules JSON,
                    default_values JSON,
                    submission_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # جدول submissions فرم
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS form_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    form_id INTEGER,
                    submitted_data JSON NOT NULL,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    reviewed_by TEXT,
                    notes TEXT,
                    FOREIGN KEY (form_id) REFERENCES dynamic_forms(id)
                )
            ''')
            
            # جدول صفحات داشبورد
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS dashboard_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_name TEXT NOT NULL,
                    page_order INTEGER,
                    widgets_config JSON,
                    layout_type TEXT DEFAULT 'grid',
                    background_color TEXT,
                    is_visible BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول تعاملات کاربر
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    interaction_type TEXT,
                    target_id INTEGER,
                    target_type TEXT,
                    interaction_data JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            logger.info("جداول پایگاه داده چندرسانه‌ای با موفقیت ایجاد شدند.")
            
        except Exception as e:
            logger.error(f"خطا در ایجاد پایگاه داده: {e}")
            raise
    
    def insert_media(self, filename: str, filepath: str, media_type: str, 
                     category: str = None, title: str = None, 
                     description: str = None, tags: List[str] = None,
                     metadata: Dict = None) -> int:
        """درج فایل چندرسانه‌ای جدید"""
        try:
            tags_str = json.dumps(tags) if tags else None
            metadata_str = json.dumps(metadata) if metadata else None
            
            file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            
            self.cursor.execute('''
                INSERT INTO media_files 
                (filename, filepath, media_type, category, title, description, tags, file_size, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (filename, filepath, media_type, category, title, description, tags_str, file_size, metadata_str))
            
            self.conn.commit()
            media_id = self.cursor.lastrowid
            logger.info(f"فایل چندرسانه‌ای با شناسه {media_id} ثبت شد.")
            return media_id
            
        except Exception as e:
            logger.error(f"خطا در درج فایل چندرسانه‌ای: {e}")
            raise
    
    def get_all_media(self, category: str = None, media_type: str = None) -> List[Dict]:
        """دریافت تمام فایل‌های چندرسانه‌ای با فیلتر اختیاری"""
        try:
            query = "SELECT * FROM media_files WHERE is_active = 1"
            params = []
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if media_type:
                query += " AND media_type = ?"
                params.append(media_type)
            
            query += " ORDER BY created_at DESC"
            
            self.cursor.execute(query, params)
            columns = [description[0] for description in self.cursor.description]
            results = []
            
            for row in self.cursor.fetchall():
                result = dict(zip(columns, row))
                if result['tags']:
                    result['tags'] = json.loads(result['tags'])
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"خطا در دریافت فایل‌های چندرسانه‌ای: {e}")
            raise
    
    def save_report(self, report_name: str, report_type: str, data_source: str,
                    filters: Dict = None, layout_config: Dict = None,
                    created_by: str = None, content: bytes = None) -> int:
        """ذخیره گزارش جدید"""
        try:
            filters_str = json.dumps(filters) if filters else None
            layout_str = json.dumps(layout_config) if layout_config else None
            
            self.cursor.execute('''
                INSERT INTO reports 
                (report_name, report_type, data_source, filters, layout_config, created_by, content)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (report_name, report_type, data_source, filters_str, layout_str, created_by, content))
            
            self.conn.commit()
            report_id = self.cursor.lastrowid
            logger.info(f"گزارش '{report_name}' با شناسه {report_id} ذخیره شد.")
            return report_id
            
        except Exception as e:
            logger.error(f"خطا در ذخیره گزارش: {e}")
            raise
    
    def save_chart(self, chart_name: str, chart_type: str, data_query: str,
                   config: Dict = None, colors: List = None, 
                   labels: List = None) -> int:
        """ذخیره پیکربندی نمودار"""
        try:
            config_str = json.dumps(config) if config else None
            colors_str = json.dumps(colors) if colors else None
            labels_str = json.dumps(labels) if labels else None
            
            self.cursor.execute('''
                INSERT INTO charts 
                (chart_name, chart_type, data_query, config, colors, labels)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (chart_name, chart_type, data_query, config_str, colors_str, labels_str))
            
            self.conn.commit()
            chart_id = self.cursor.lastrowid
            logger.info(f"نمودار '{chart_name}' با شناسه {chart_id} ذخیره شد.")
            return chart_id
            
        except Exception as e:
            logger.error(f"خطا در ذخیره نمودار: {e}")
            raise
    
    def create_dynamic_form(self, form_name: str, form_schema: Dict,
                            validation_rules: Dict = None,
                            default_values: Dict = None) -> int:
        """ایجاد فرم پویا"""
        try:
            schema_str = json.dumps(form_schema)
            validation_str = json.dumps(validation_rules) if validation_rules else None
            defaults_str = json.dumps(default_values) if default_values else None
            
            self.cursor.execute('''
                INSERT INTO dynamic_forms 
                (form_name, form_schema, validation_rules, default_values)
                VALUES (?, ?, ?, ?)
            ''', (form_name, schema_str, validation_str, defaults_str))
            
            self.conn.commit()
            form_id = self.cursor.lastrowid
            logger.info(f"فرم پویا '{form_name}' با شناسه {form_id} ایجاد شد.")
            return form_id
            
        except Exception as e:
            logger.error(f"خطا در ایجاد فرم پویا: {e}")
            raise
    
    def submit_form(self, form_id: int, submitted_data: Dict) -> int:
        """ثبت اطلاعات فرم"""
        try:
            data_str = json.dumps(submitted_data)
            
            self.cursor.execute('''
                INSERT INTO form_submissions (form_id, submitted_data)
                VALUES (?, ?)
            ''', (form_id, data_str))
            
            self.cursor.execute('''
                UPDATE dynamic_forms SET submission_count = submission_count + 1
                WHERE id = ?
            ''', (form_id,))
            
            self.conn.commit()
            submission_id = self.cursor.lastrowid
            logger.info(f"اطلاعات فرم {form_id} با شناسه {submission_id} ثبت شد.")
            return submission_id
            
        except Exception as e:
            logger.error(f"خطا در ثبت اطلاعات فرم: {e}")
            raise
    
    def save_dashboard_page(self, page_name: str, widgets_config: Dict,
                            page_order: int = 0, layout_type: str = 'grid',
                            background_color: str = '#1a1a2e') -> int:
        """ذخیره صفحه داشبورد"""
        try:
            widgets_str = json.dumps(widgets_config)
            
            self.cursor.execute('''
                INSERT INTO dashboard_pages 
                (page_name, page_order, widgets_config, layout_type, background_color)
                VALUES (?, ?, ?, ?, ?)
            ''', (page_name, page_order, widgets_str, layout_type, background_color))
            
            self.conn.commit()
            page_id = self.cursor.lastrowid
            logger.info(f"صفحه داشبورد '{page_name}' با شناسه {page_id} ذخیره شد.")
            return page_id
            
        except Exception as e:
            logger.error(f"خطا در ذخیره صفحه داشبورد: {e}")
            raise
    
    def log_interaction(self, user_id: str, interaction_type: str,
                        target_id: int, target_type: str,
                        interaction_data: Dict = None) -> int:
        """ثبت تعامل کاربر"""
        try:
            data_str = json.dumps(interaction_data) if interaction_data else None
            
            self.cursor.execute('''
                INSERT INTO user_interactions 
                (user_id, interaction_type, target_id, target_type, interaction_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, interaction_type, target_id, target_type, data_str))
            
            self.conn.commit()
            interaction_id = self.cursor.lastrowid
            return interaction_id
            
        except Exception as e:
            logger.error(f"خطا در ثبت تعامل کاربر: {e}")
            raise
    
    def close(self):
        """بستن اتصال به پایگاه داده"""
        if self.conn:
            self.conn.close()
            logger.info("اتصال به پایگاه داده بسته شد.")


class ChartGenerator:
    """تولید کننده انواع نمودارهای تعاملی و پویا"""
    
    def __init__(self, db: MultimediaDatabase):
        self.db = db
        self.style_params = {
            'font_family': 'Tahoma',
            'font_size': 12,
            'title_size': 16,
            'grid_alpha': 0.3,
            'line_width': 2
        }
        
        # پالت‌های رنگی متنوع
        self.color_palettes = {
            'default': ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'],
            'electric': ['#FFD700', '#FF6347', '#4169E1', '#32CD32', '#FF1493'],
            'professional': ['#2C3E50', '#3498DB', '#E74C3C', '#27AE60', '#F39C12'],
            'dark': ['#FF6B6B', '#4ECDC4', '#FFE66D', '#1A535C', '#FF9F1C']
        }
    
    def generate_line_chart(self, title: str, x_data: List, y_data: List,
                            xlabel: str = '', ylabel: str = '',
                            palette: str = 'default', save_path: str = None) -> Figure:
        """تولید نمودار خطی"""
        fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
        
        colors = self.color_palettes.get(palette, self.color_palettes['default'])
        
        if isinstance(y_data[0], list):
            for i, y in enumerate(y_data):
                ax.plot(x_data, y, label=f'Series {i+1}', color=colors[i % len(colors)],
                       linewidth=self.style_params['line_width'])
        else:
            ax.plot(x_data, y_data, color=colors[0],
                   linewidth=self.style_params['line_width'])
        
        ax.set_title(title, fontsize=self.style_params['title_size'], fontweight='bold')
        ax.set_xlabel(xlabel, fontsize=self.style_params['font_size'])
        ax.set_ylabel(ylabel, fontsize=self.style_params['font_size'])
        
        ax.grid(True, alpha=self.style_params['grid_alpha'])
        ax.legend()
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"نمودار خطی در {save_path} ذخیره شد.")
        
        return fig
    
    def generate_bar_chart(self, title: str, categories: List, values: List,
                           xlabel: str = '', ylabel: str = '',
                           palette: str = 'default', horizontal: bool = False,
                           save_path: str = None) -> Figure:
        """تولید نمودار ستونی"""
        fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
        
        colors = self.color_palettes.get(palette, self.color_palettes['default'])
        
        if horizontal:
            ax.barh(categories, values, color=colors[:len(categories)])
            ax.set_xlabel(ylabel)
            ax.set_ylabel(xlabel)
        else:
            ax.bar(categories, values, color=colors[:len(categories)])
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
        
        ax.set_title(title, fontsize=self.style_params['title_size'], fontweight='bold')
        ax.grid(True, axis='y', alpha=self.style_params['grid_alpha'])
        
        # افزودن مقادیر روی ستون‌ها
        if not horizontal:
            for i, v in enumerate(values):
                ax.text(i, v + max(values)*0.01, f'{v:,}', ha='center', va='bottom', fontsize=10)
        else:
            for i, v in enumerate(values):
                ax.text(v + max(values)*0.01, i, f'{v:,}', va='center', fontsize=10)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"نمودار ستونی در {save_path} ذخیره شد.")
        
        return fig
    
    def generate_pie_chart(self, title: str, labels: List, sizes: List,
                           palette: str = 'default', explode: List = None,
                           save_path: str = None) -> Figure:
        """تولید نمودار دایره‌ای"""
        fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
        
        colors = self.color_palettes.get(palette, self.color_palettes['default'])
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                          colors=colors[:len(labels)],
                                          explode=explode, shadow=True, startangle=90)
        
        # بهبود ظاهر متن‌ها
        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
        
        ax.set_title(title, fontsize=self.style_params['title_size'], fontweight='bold')
        ax.axis('equal')
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"نمودار دایره‌ای در {save_path} ذخیره شد.")
        
        return fig
    
    def generate_heatmap(self, title: str, data: np.ndarray, 
                         x_labels: List = None, y_labels: List = None,
                         cmap: str = 'YlOrRd', save_path: str = None) -> Figure:
        """تولید نقشه حرارتی"""
        fig, ax = plt.subplots(figsize=(12, 8), dpi=100)
        
        im = ax.imshow(data, cmap=cmap, aspect='auto')
        
        # افزودن برچسب‌ها
        if x_labels:
            ax.set_xticks(np.arange(len(x_labels)))
            ax.set_xticklabels(x_labels)
        if y_labels:
            ax.set_yticks(np.arange(len(y_labels)))
            ax.set_yticklabels(y_labels)
        
        # چرخاندن برچسب‌های محور X
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        
        # افزودن مقادیر روی سلول‌ها
        for i in range(len(y_labels or [])):
            for j in range(len(x_labels or [])):
                text = ax.text(j, i, f'{data[i, j]:,.0f}',
                              ha="center", va="center", color="black", fontsize=8)
        
        ax.set_title(title, fontsize=self.style_params['title_size'], fontweight='bold')
        fig.colorbar(im, ax=ax)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"نقشه حرارتی در {save_path} ذخیره شد.")
        
        return fig
    
    def generate_multi_axis_chart(self, title: str, x_data: List,
                                   y_data1: List, y_data2: List,
                                   label1: str = '', label2: str = '',
                                   xlabel: str = '', ylabel1: str = '', ylabel2: str = '',
                                   save_path: str = None) -> Figure:
        """تولید نمودار با دو محور عمودی"""
        fig, ax1 = plt.subplots(figsize=(12, 6), dpi=100)
        
        color1 = self.color_palettes['default'][0]
        color2 = self.color_palettes['default'][1]
        
        ax1.set_xlabel(xlabel, fontsize=self.style_params['font_size'])
        ax1.set_ylabel(ylabel1, color=color1, fontsize=self.style_params['font_size'])
        line1 = ax1.plot(x_data, y_data1, color=color1, linewidth=self.style_params['line_width'])
        ax1.tick_params(axis='y', labelcolor=color1)
        ax1.grid(True, alpha=self.style_params['grid_alpha'])
        
        ax2 = ax1.twinx()
        ax2.set_ylabel(ylabel2, color=color2, fontsize=self.style_params['font_size'])
        line2 = ax2.plot(x_data, y_data2, color=color2, linewidth=self.style_params['line_width'])
        ax2.tick_params(axis='y', labelcolor=color2)
        
        ax1.set_title(title, fontsize=self.style_params['title_size'], fontweight='bold')
        
        # ترکیب legendها
        lines = line1 + line2
        labels = [label1, label2]
        ax1.legend(lines, labels, loc='upper left')
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"نمودار دو محوره در {save_path} ذخیره شد.")
        
        return fig


class DynamicFormBuilder:
    """سازنده فرم‌های پویا و تعاملی"""
    
    def __init__(self, parent, db: MultimediaDatabase):
        self.parent = parent
        self.db = db
        self.form_widgets = {}
        self.current_form_id = None
    
    def create_form_from_schema(self, frame: ctk.CTkFrame, form_schema: Dict,
                                 form_id: int = None, on_submit=None) -> ctk.CTkFrame:
        """ایجاد فرم از روی طرحواره"""
        self.current_form_id = form_id
        self.form_widgets = {}
        
        scrollable_frame = ctk.CTkScrollableFrame(frame, width=600, height=400)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        row = 0
        for field in form_schema.get('fields', []):
            field_name = field['name']
            field_type = field['type']
            field_label = field.get('label', field_name)
            required = field.get('required', False)
            options = field.get('options', [])
            default_value = field.get('default', '')
            
            # ایجاد برچسب
            label = ctk.CTkLabel(scrollable_frame, text=f"{field_label}{' *' if required else ''}",
                                anchor="w", font=("Tahoma", 12, "bold"))
            label.grid(row=row, column=0, sticky="w", padx=10, pady=5)
            
            # ایجاد ویجت مناسب بر اساس نوع فیلد
            if field_type == 'text':
                widget = ctk.CTkEntry(scrollable_frame, width=300, placeholder_text=field.get('placeholder', ''))
                if default_value:
                    widget.insert(0, default_value)
            elif field_type == 'textarea':
                widget = ctk.CTkTextbox(scrollable_frame, width=300, height=80)
                if default_value:
                    widget.insert("0.0", default_value)
            elif field_type == 'number':
                widget = ctk.CTkEntry(scrollable_frame, width=300, placeholder_text="عدد وارد کنید")
                if default_value:
                    widget.insert(0, str(default_value))
            elif field_type == 'dropdown':
                widget = ctk.CTkOptionMenu(scrollable_frame, values=options, width=300)
                if default_value and default_value in options:
                    widget.set(default_value)
            elif field_type == 'checkbox':
                widget = ctk.CTkCheckBox(scrollable_frame, text=field_label)
                if default_value:
                    widget.select()
            elif field_type == 'date':
                widget = ctk.CTkEntry(scrollable_frame, width=300, placeholder_text="YYYY-MM-DD")
                if default_value:
                    widget.insert(0, default_value)
            else:
                widget = ctk.CTkEntry(scrollable_frame, width=300)
                if default_value:
                    widget.insert(0, default_value)
            
            widget.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
            self.form_widgets[field_name] = {'widget': widget, 'type': field_type, 'required': required}
            
            row += 1
        
        # دکمه ارسال
        submit_btn = ctk.CTkButton(scrollable_frame, text="ارسال اطلاعات", 
                                   command=lambda: self._submit_form(on_submit),
                                   width=200, height=40)
        submit_btn.grid(row=row, column=0, columnspan=2, pady=20)
        
        scrollable_frame.grid_columnconfigure(1, weight=1)
        
        return scrollable_frame
    
    def _submit_form(self, on_submit=None):
        """ارسال اطلاعات فرم"""
        try:
            data = {}
            validation_errors = []
            
            for field_name, field_info in self.form_widgets.items():
                widget = field_info['widget']
                field_type = field_info['type']
                required = field_info['required']
                
                if field_type == 'checkbox':
                    value = widget.get() == 'on'
                elif field_type == 'textarea':
                    value = widget.get("0.0", "end").strip()
                else:
                    value = widget.get().strip()
                
                if required and not value and value != False:
                    validation_errors.append(f"فیلد {field_name} الزامی است.")
                    continue
                
                # تبدیل نوع داده
                if field_type == 'number' and value:
                    try:
                        value = float(value)
                    except ValueError:
                        validation_errors.append(f"مقدار {field_name} باید عدد باشد.")
                        continue
                
                data[field_name] = value
            
            if validation_errors:
                messagebox.showerror("خطای اعتبارسنجی", "\n".join(validation_errors))
                return
            
            # ذخیره در پایگاه داده
            if self.current_form_id:
                submission_id = self.db.submit_form(self.current_form_id, data)
                messagebox.showinfo("موفق", f"اطلاعات با موفقیت ثبت شد.\nشناسه ثبت: {submission_id}")
                
                if on_submit:
                    on_submit(submission_id, data)
            
            # پاک کردن فرم
            self._clear_form()
            
        except Exception as e:
            logger.error(f"خطا در ارسال فرم: {e}")
            messagebox.showerror("خطا", f"خطا در ارسال اطلاعات: {str(e)}")
    
    def _clear_form(self):
        """پاک کردن تمام فیلدهای فرم"""
        for field_name, field_info in self.form_widgets.items():
            widget = field_info['widget']
            field_type = field_info['type']
            
            if field_type == 'checkbox':
                widget.deselect()
            elif field_type == 'textarea':
                widget.delete("0.0", "end")
            elif field_type == 'dropdown':
                pass  # OptionMenu را نمی‌توان به راحتی پاک کرد
            else:
                widget.delete(0, 'end')


class MediaViewer:
    """نمایشگر پیشرفته فایل‌های چندرسانه‌ای"""
    
    def __init__(self, parent, db: MultimediaDatabase):
        self.parent = parent
        self.db = db
        self.current_media = None
    
    def create_media_gallery(self, frame: ctk.CTkFrame, category: str = None) -> ctk.CTkScrollableFrame:
        """ایجاد گالری چندرسانه‌ای"""
        gallery_frame = ctk.CTkScrollableFrame(frame, width=800, height=500)
        gallery_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        media_files = self.db.get_all_media(category=category)
        
        if not media_files:
            no_data_label = ctk.CTkLabel(gallery_frame, text="هیچ فایل چندرسانه‌ای یافت نشد.",
                                        font=("Tahoma", 14))
            no_data_label.pack(pady=50)
            return gallery_frame
        
        # چیدمان شبکه‌ای
        cols = 3
        for idx, media in enumerate(media_files):
            row = idx // cols
            col = idx % cols
            
            media_card = ctk.CTkFrame(gallery_frame, width=240, height=280, corner_radius=10)
            media_card.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
            
            # تصویر کوچک یا آیکون
            icon_frame = ctk.CTkFrame(media_card, width=220, height=150, fg_color="#2a2a3e")
            icon_frame.grid(row=0, column=0, padx=10, pady=10)
            
            media_type = media['media_type']
            if media_type == 'image':
                try:
                    img = Image.open(media['filepath'])
                    img.thumbnail((200, 130))
                    photo = ImageTk.PhotoImage(img)
                    img_label = ctk.CTkLabel(icon_frame, image=photo, text="")
                    img_label.image = photo
                    img_label.pack(expand=True)
                except Exception as e:
                    icon_label = ctk.CTkLabel(icon_frame, text="📷", font=("Arial", 60))
                    icon_label.pack(expand=True)
            elif media_type == 'video':
                icon_label = ctk.CTkLabel(icon_frame, text="🎬", font=("Arial", 60))
                icon_label.pack(expand=True)
            elif media_type == 'audio':
                icon_label = ctk.CTkLabel(icon_frame, text="🎵", font=("Arial", 60))
                icon_label.pack(expand=True)
            elif media_type == 'document':
                icon_label = ctk.CTkLabel(icon_frame, text="📄", font=("Arial", 60))
                icon_label.pack(expand=True)
            elif media_type == 'chart':
                icon_label = ctk.CTkLabel(icon_frame, text="📊", font=("Arial", 60))
                icon_label.pack(expand=True)
            else:
                icon_label = ctk.CTkLabel(icon_frame, text="📁", font=("Arial", 60))
                icon_label.pack(expand=True)
            
            # اطلاعات فایل
            info_frame = ctk.CTkFrame(media_card, fg_color="transparent")
            info_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
            
            title_label = ctk.CTkLabel(info_frame, text=media.get('title', media['filename']),
                                      font=("Tahoma", 11, "bold"), wraplength=200)
            title_label.pack(anchor="w")
            
            desc_label = ctk.CTkLabel(info_frame, text=media.get('description', '')[:50] + "...",
                                     font=("Tahoma", 9), text_color="gray", wraplength=200)
            desc_label.pack(anchor="w")
            
            size_label = ctk.CTkLabel(info_frame, text=f"{media.get('file_size', 0) / 1024:.1f} KB",
                                     font=("Tahoma", 8), text_color="lightgray")
            size_label.pack(anchor="w")
            
            # دکمه‌های عملیات
            btn_frame = ctk.CTkFrame(media_card, fg_color="transparent")
            btn_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
            
            view_btn = ctk.CTkButton(btn_frame, text="مشاهده", width=70, height=25,
                                    command=lambda m=media: self._open_media_viewer(m))
            view_btn.pack(side="left", padx=2)
            
            download_btn = ctk.CTkButton(btn_frame, text="دانلود", width=70, height=25,
                                        command=lambda m=media: self._download_media(m))
            download_btn.pack(side="left", padx=2)
        
        gallery_frame.grid_columnconfigure(0, weight=1)
        gallery_frame.grid_columnconfigure(1, weight=1)
        gallery_frame.grid_columnconfigure(2, weight=1)
        
        return gallery_frame
    
    def _open_media_viewer(self, media: Dict):
        """باز کردن پنجره نمایش فایل"""
        viewer_window = ctk.CTkToplevel(self.parent)
        viewer_window.title(media.get('title', media['filename']))
        viewer_window.geometry("800x600")
        
        media_type = media['media_type']
        filepath = media['filepath']
        
        if media_type == 'image':
            try:
                img = Image.open(filepath)
                img.thumbnail((750, 500))
                photo = ImageTk.PhotoImage(img)
                img_label = ctk.CTkLabel(viewer_window, image=photo, text="")
                img_label.image = photo
                img_label.pack(expand=True, padx=20, pady=20)
            except Exception as e:
                error_label = ctk.CTkLabel(viewer_window, text=f"خطا در بارگذاری تصویر: {e}",
                                          font=("Tahoma", 14))
                error_label.pack(expand=True)
        elif media_type in ['video', 'audio']:
            info_label = ctk.CTkLabel(viewer_window, 
                                     text=f"نوع فایل: {media_type}\nمسیر: {filepath}\n\nبرای پخش نیاز به کتابخانه‌های اضافی است.",
                                     font=("Tahoma", 12), justify="center")
            info_label.pack(expand=True)
        elif media_type == 'document':
            info_label = ctk.CTkLabel(viewer_window,
                                     text=f"سند: {filepath}\n\nبرای مشاهده از برنامه مربوطه استفاده کنید.",
                                     font=("Tahoma", 12))
            info_label.pack(expand=True)
        elif media_type == 'chart':
            # بارگذاری نمودار از دیتابیس
            if media.get('metadata'):
                chart_data = media['metadata']
                chart_info = ctk.CTkLabel(viewer_window,
                                         text=f"نمودار: {media.get('title', '')}\nنوع: {chart_data.get('chart_type', 'unknown')}",
                                         font=("Tahoma", 12))
                chart_info.pack(expand=True)
        else:
            info_label = ctk.CTkLabel(viewer_window, text=f"نوع فایل ناشناخته: {media_type}",
                                     font=("Tahoma", 12))
            info_label.pack(expand=True)
        
        # دکمه بستن
        close_btn = ctk.CTkButton(viewer_window, text="بستن", command=viewer_window.destroy,
                                 width=100, height=30)
        close_btn.pack(pady=20)
    
    def _download_media(self, media: Dict):
        """دانلود فایل چندرسانه‌ای"""
        filepath = media['filepath']
        if os.path.exists(filepath):
            save_path = filedialog.asksaveasfilename(
                defaultextension=".*",
                initialfile=media['filename'],
                title="ذخیره فایل"
            )
            if save_path:
                import shutil
                shutil.copy2(filepath, save_path)
                messagebox.showinfo("موفق", "فایل با موفقیت دانلود شد.")
        else:
            messagebox.showerror("خطا", "فایل مورد نظر یافت نشد.")


class ReportGenerator:
    """تولید کننده گزارشات حرفه‌ای و چندصفحه‌ای"""
    
    def __init__(self, db: MultimediaDatabase, chart_gen: ChartGenerator):
        self.db = db
        self.chart_gen = chart_gen
    
    def generate_electricity_report(self, report_name: str = "گزارش جامع مصرف و بدهی",
                                    save_path: str = None) -> Figure:
        """تولید گزارش جامع صنعت برق"""
        # ایجاد فیگور با چندین زیرنمودار
        fig = plt.figure(figsize=(16, 20), dpi=100)
        fig.suptitle(report_name, fontsize=20, fontweight='bold', y=0.98)
        
        # زیرنمودار 1: روند مصرف ماهانه
        ax1 = plt.subplot(3, 2, 1)
        months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور']
        consumption = [450, 520, 680, 850, 920, 780]
        ax1.bar(months, consumption, color=self.chart_gen.color_palettes['electric'])
        ax1.set_title('روند مصرف ماهانه (kWh)', fontsize=14, fontweight='bold')
        ax1.set_ylabel('مصرف (kWh)')
        ax1.grid(True, alpha=0.3)
        
        # افزودن مقادیر
        for i, v in enumerate(consumption):
            ax1.text(i, v + 10, f'{v:,}', ha='center', fontsize=10)
        
        # زیرنمودار 2: توزیع بدهی به تفکیک منطقه
        ax2 = plt.subplot(3, 2, 2)
        zones = ['مرکزی', 'زرجاب', 'شهرک بهشتی', 'فرهنگیان', 'بلوار معلم']
        debts = [15000000, 8500000, 12000000, 6000000, 9500000]
        colors = self.chart_gen.color_palettes['professional'][:len(zones)]
        ax2.pie(debts, labels=zones, autopct='%1.1f%%', colors=colors, shadow=True)
        ax2.set_title('توزیع بدهی به تفکیک منطقه', fontsize=14, fontweight='bold')
        
        # زیرنمودار 3: مقایسه پرداخت‌های نقدی و اقساطی
        ax3 = plt.subplot(3, 2, 3)
        payment_types = ['نقدی', 'اقساطی', 'چکی', 'آنلاین']
        amounts = [45, 30, 15, 10]
        ax3.barh(payment_types, amounts, color=self.chart_gen.color_palettes['dark'])
        ax3.set_title('روش‌های پرداخت', fontsize=14, fontweight='bold')
        ax3.set_xlabel('درصد')
        ax3.grid(True, alpha=0.3, axis='x')
        
        # افزودن مقادیر
        for i, v in enumerate(amounts):
            ax3.text(v + 1, i, f'{v}%', va='center', fontsize=10)
        
        # زیرنمودار 4: روند وصول مطالبات
        ax4 = plt.subplot(3, 2, 4)
        weeks = ['هفته ۱', 'هفته ۲', 'هفته ۳', 'هفته ۴']
        collected = [2500000, 3200000, 2800000, 4100000]
        target = [3000000, 3000000, 3000000, 3000000]
        ax4.plot(weeks, collected, marker='o', linewidth=2, color='#4ECDC4', label='وصول شده')
        ax4.plot(weeks, target, marker='s', linewidth=2, color='#FF6B6B', label='هدف')
        ax4.fill_between(weeks, collected, alpha=0.3, color='#4ECDC4')
        ax4.set_title('روند وصول مطالبات (ریال)', fontsize=14, fontweight='bold')
        ax4.set_ylabel('مبلغ (ریال)')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        # زیرنمودار 5: نقشه حرارتی ساعات اوج مصرف
        ax5 = plt.subplot(3, 2, 5)
        hours = [f'{h}:00' for h in range(6, 24)]
        days = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه']
        heatmap_data = np.random.randint(50, 100, size=(len(days), len(hours)))
        im = ax5.imshow(heatmap_data, cmap='YlOrRd', aspect='auto')
        ax5.set_title('ساعات اوج مصرف', fontsize=14, fontweight='bold')
        ax5.set_xlabel('ساعت')
        ax5.set_ylabel('روز هفته')
        ax5.set_xticks(np.arange(len(hours)))
        ax5.set_xticklabels(hours, rotation=45, ha='right')
        ax5.set_yticks(np.arange(len(days)))
        ax5.set_yticklabels(days)
        plt.colorbar(im, ax=ax5, label='مصرف نسبی')
        
        # زیرنمودار 6: خلاصه آماری
        ax6 = plt.subplot(3, 2, 6)
        ax6.axis('off')
        
        stats_text = """
        📊 خلاصه آماری گزارش
        
        🔹 کل مشترکین: ۴۵,۲۳۰ نفر
        🔹 مشترکین بدهکار: ۸,۴۵۶ نفر (۱۸.۷٪)
        🔹 مجموع بدهی معوق: ۱۲۵,۰۰۰,۰۰۰,۰۰۰ ریال
        🔹 میانگین بدهی: ۱۴,۷۸۰,۰۰۰ ریال
        🔹 نرخ وصول ماهانه: ۷۲.۵٪
        🔹 تعداد تماس‌های انجام شده: ۱۲,۳۴۵
        🔹 وعده‌های پرداخت دریافتی: ۳,۴۵۶
        🔹 میزان تحقق وعده‌ها: ۶۸.۲٪
        
        تاریخ گزارش: ۱۴۰۵/۰۶/۱۹
        تهیه شده توسط: سامانه هوشمند وصول مطالبات
        """
        
        ax6.text(0.1, 0.9, stats_text, transform=ax6.transAxes, fontsize=11,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='#2a2a3e', alpha=0.8, edgecolor='#4ECDC4'))
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.96])
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"گزارش جامع در {save_path} ذخیره شد.")
        
        return fig
    
    def create_dashboard_report(self, parent, title: str = "داشبورد مدیریتی") -> ctk.CTkFrame:
        """ایجاد داشبورد تعاملی با چندین نمودار"""
        dashboard = ctk.CTkFrame(parent)
        
        # عنوان
        title_label = ctk.CTkLabel(dashboard, text=title, font=("Tahoma", 18, "bold"))
        title_label.pack(pady=10)
        
        # فریم اصلی برای نمودارها
        charts_frame = ctk.CTkScrollableFrame(dashboard, width=1200, height=600)
        charts_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # ایجاد نمودار نمونه
        fig = self.generate_electricity_report()
        
        # تبدیل به canvas tkinter
        canvas = FigureCanvasTkAgg(fig, master=charts_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # نوار ابزار
        toolbar = NavigationToolbar2Tk(canvas, charts_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")
        
        return dashboard


class InteractiveTable:
    """جدول داده‌ای تعاملی با قابلیت‌های پیشرفته"""
    
    def __init__(self, parent, db: MultimediaDatabase):
        self.parent = parent
        self.db = db
        self.data = []
        self.columns = []
    
    def create_table(self, frame: ctk.CTkFrame, query: str, 
                     editable: bool = False, on_edit=None) -> ttk.Treeview:
        """ایجاد جدول تعاملی از نتایج کوئری"""
        try:
            self.db.cursor.execute(query)
            self.columns = [description[0] for description in self.db.cursor.description]
            self.data = self.db.cursor.fetchall()
            
            # ایجاد Treeview
            style = ttk.Style()
            style.theme_use('clam')
            style.configure("Treeview", 
                           background="#2a2a3e",
                           foreground="white",
                           fieldbackground="#2a2a3e",
                           rowheight=25,
                           font=("Tahoma", 10))
            style.configure("Treeview.Heading",
                           background="#1a1a2e",
                           foreground="#4ECDC4",
                           relief="flat",
                           font=("Tahoma", 11, "bold"))
            style.map("Treeview",
                     background=[('selected', '#4ECDC4')],
                     foreground=[('selected', 'black')])
            
            table = ttk.Treeview(frame, columns=self.columns, show='headings', height=15)
            
            # تنظیم ستون‌ها
            for col in self.columns:
                table.heading(col, text=col)
                table.column(col, width=120, anchor='center')
            
            # درج داده‌ها
            for row in self.data:
                table.insert('', 'end', values=row)
            
            # اسکرول‌بار
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
            table.configure(yscrollcommand=scrollbar.set)
            
            table.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # قابلیت ویرایش
            if editable:
                table.bind('<Double-1>', lambda e: self._edit_cell(table, on_edit))
            
            return table
            
        except Exception as e:
            logger.error(f"خطا در ایجاد جدول: {e}")
            error_label = ctk.CTkLabel(frame, text=f"خطا: {str(e)}", text_color="red")
            error_label.pack()
            return None
    
    def _edit_cell(self, table: ttk.Treeview, on_edit=None):
        """ویرایش سلول جدول"""
        selection = table.selection()
        if not selection:
            return
        
        item = table.item(selection[0])
        values = item['values']
        
        edit_window = ctk.CTkToplevel(self.parent)
        edit_window.title("ویرایش رکورد")
        edit_window.geometry("500x400")
        
        entries = {}
        for i, col in enumerate(self.columns):
            label = ctk.CTkLabel(edit_window, text=col, anchor="w")
            label.grid(row=i, column=0, sticky="w", padx=10, pady=5)
            
            entry = ctk.CTkEntry(edit_window, width=300)
            entry.insert(0, str(values[i]) if i < len(values) else "")
            entry.grid(row=i, column=1, padx=10, pady=5)
            entries[col] = entry
        
        def save_changes():
            new_values = {col: entry.get() for col, entry in entries.items()}
            if on_edit:
                on_edit(item['iid'], new_values)
            edit_window.destroy()
            messagebox.showinfo("موفق", "تغییرات با موفقیت ذخیره شد.")
        
        save_btn = ctk.CTkButton(edit_window, text="ذخیره تغییرات", command=save_changes)
        save_btn.grid(row=len(self.columns), column=0, columnspan=2, pady=20)


class MultimediaManagerApp(ctk.CTk):
    """اپلیکیشن اصلی مدیریت چندرسانه‌ای و گزارشات"""
    
    def __init__(self):
        super().__init__()
        
        self.title("سامانه جامع مدیریت چندرسانه‌ای - شرکت برق ایلام")
        self.geometry("1400x900")
        
        # مقداردهی اولیه
        self.db = MultimediaDatabase()
        self.chart_gen = ChartGenerator(self.db)
        self.report_gen = ReportGenerator(self.db, self.chart_gen)
        
        # ایجاد رابط کاربری
        self._setup_ui()
        
        logger.info("اپلیکیشن مدیریت چندرسانه‌ای راه‌اندازی شد.")
    
    def _setup_ui(self):
        """تنظیم رابط کاربری اصلی"""
        # فریم اصلی
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # منوی کناری
        sidebar = ctk.CTkFrame(main_frame, width=200, corner_radius=0)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        
        # عنوان منو
        menu_title = ctk.CTkLabel(sidebar, text="منوی اصلی", font=("Tahoma", 16, "bold"))
        menu_title.pack(pady=20)
        
        # دکمه‌های منو
        buttons = [
            ("🏠 داشبورد", self._show_dashboard),
            ("📊 نمودارها", self._show_charts),
            ("📋 گزارشات", self._show_reports),
            ("📁 فایل‌های چندرسانه‌ای", self._show_media),
            ("📝 فرم‌های پویا", self._show_forms),
            ("📈 جداول داده‌ای", self._show_tables),
            ("⚙️ تنظیمات", self._show_settings)
        ]
        
        for text, command in buttons:
            btn = ctk.CTkButton(sidebar, text=text, command=command,
                               width=180, height=40, anchor="w")
            btn.pack(pady=5, padx=10)
        
        # ناحیه محتوا
        self.content_frame = ctk.CTkFrame(main_frame)
        self.content_frame.pack(side="right", fill="both", expand=True)
        
        # نمایش پیش‌فرض داشبورد
        self._show_dashboard()
    
    def _clear_content(self):
        """پاک کردن محتوای فعلی"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def _show_dashboard(self):
        """نمایش داشبورد اصلی"""
        self._clear_content()
        
        dashboard = self.report_gen.create_dashboard_report(self.content_frame, 
                                                           "داشبورد مدیریتی شرکت برق ایلام")
        dashboard.pack(fill="both", expand=True)
    
    def _show_charts(self):
        """نمایش بخش نمودارها"""
        self._clear_content()
        
        title_label = ctk.CTkLabel(self.content_frame, text="کتابخانه نمودارها",
                                  font=("Tahoma", 18, "bold"))
        title_label.pack(pady=10)
        
        # ایجاد تب‌های مختلف برای انواع نمودار
        tabview = ctk.CTkTabview(self.content_frame)
        tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        # تب نمودار خطی
        line_tab = tabview.add("نمودار خطی")
        fig = self.chart_gen.generate_line_chart(
            "روند مصرف برق",
            ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور'],
            [450, 520, 680, 850, 920, 780],
            "ماه", "مصرف (kWh)",
            palette='electric'
        )
        canvas = FigureCanvasTkAgg(fig, master=line_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # تب نمودار ستونی
        bar_tab = tabview.add("نمودار ستونی")
        fig = self.chart_gen.generate_bar_chart(
            "بدهی به تفکیک منطقه",
            ['مرکزی', 'زرجاب', 'شهرک بهشتی', 'فرهنگیان', 'بلوار معلم'],
            [15000000, 8500000, 12000000, 6000000, 9500000],
            "منطقه", "بدهی (ریال)",
            palette='professional'
        )
        canvas = FigureCanvasTkAgg(fig, master=bar_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # تب نمودار دایره‌ای
        pie_tab = tabview.add("نمودار دایره‌ای")
        fig = self.chart_gen.generate_pie_chart(
            "توزیع روش‌های پرداخت",
            ['نقدی', 'اقساطی', 'چکی', 'آنلاین'],
            [45, 30, 15, 10],
            palette='dark'
        )
        canvas = FigureCanvasTkAgg(fig, master=pie_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # تب نقشه حرارتی
        heat_tab = tabview.add("نقشه حرارتی")
        hours = [f'{h}:00' for h in range(6, 24)]
        days = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه']
        heatmap_data = np.random.randint(50, 100, size=(len(days), len(hours)))
        fig = self.chart_gen.generate_heatmap(
            "ساعات اوج مصرف",
            heatmap_data,
            x_labels=hours,
            y_labels=days,
            cmap='YlOrRd'
        )
        canvas = FigureCanvasTkAgg(fig, master=heat_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def _show_reports(self):
        """نمایش بخش گزارشات"""
        self._clear_content()
        
        title_label = ctk.CTkLabel(self.content_frame, text="گزارشات تخصصی",
                                  font=("Tahoma", 18, "bold"))
        title_label.pack(pady=10)
        
        # دکمه‌های تولید گزارش
        btn_frame = ctk.CTkFrame(self.content_frame)
        btn_frame.pack(pady=10)
        
        gen_report_btn = ctk.CTkButton(btn_frame, text="تولید گزارش جامع برق",
                                       command=self._generate_full_report,
                                       width=200, height=40)
        gen_report_btn.pack(side="left", padx=10)
        
        export_btn = ctk.CTkButton(btn_frame, text="خروجی PDF",
                                   command=self._export_to_pdf,
                                   width=150, height=40)
        export_btn.pack(side="left", padx=10)
        
        excel_btn = ctk.CTkButton(btn_frame, text="خروجی Excel",
                                  command=self._export_to_excel,
                                  width=150, height=40)
        excel_btn.pack(side="left", padx=10)
        
        # ناحیه نمایش گزارش
        report_frame = ctk.CTkFrame(self.content_frame)
        report_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.current_report_frame = report_frame
    
    def _generate_full_report(self):
        """تولید گزارش جامع"""
        if hasattr(self, 'current_report_frame'):
            for widget in self.current_report_frame.winfo_children():
                widget.destroy()
            
            dashboard = self.report_gen.create_dashboard_report(self.current_report_frame)
            dashboard.pack(fill="both", expand=True)
    
    def _export_to_pdf(self):
        """خروجی PDF"""
        messagebox.showinfo("خروجی PDF", "قابلیت خروجی PDF در حال توسعه است.\nفایل‌ها در پوشه exports ذخیره خواهند شد.")
    
    def _export_to_excel(self):
        """خروجی Excel"""
        messagebox.showinfo("خروجی Excel", "قابلیت خروجی Excel در حال توسعه است.\nفایل‌ها در پوشه exports ذخیره خواهند شد.")
    
    def _show_media(self):
        """نمایش بخش فایل‌های چندرسانه‌ای"""
        self._clear_content()
        
        title_label = ctk.CTkLabel(self.content_frame, text="گالری چندرسانه‌ای",
                                  font=("Tahoma", 18, "bold"))
        title_label.pack(pady=10)
        
        # دکمه آپلود
        upload_btn = ctk.CTkButton(self.content_frame, text="➕ آپلود فایل جدید",
                                   command=self._upload_media,
                                   width=200, height=40)
        upload_btn.pack(pady=10)
        
        # ایجاد گالری
        media_viewer = MediaViewer(self.content_frame, self.db)
        media_viewer.create_media_gallery(self.content_frame)
    
    def _upload_media(self):
        """آپلود فایل چندرسانه‌ای جدید"""
        file_path = filedialog.askopenfilename(
            title="انتخاب فایل",
            filetypes=[
                ("تمام فایل‌ها", "*.*"),
                ("تصاویر", "*.jpg *.jpeg *.png *.gif"),
                ("ویدیوها", "*.mp4 *.avi *.mkv"),
                ("صدا", "*.mp3 *.wav *.ogg"),
                ("اسناد", "*.pdf *.doc *.docx *.xlsx")
            ]
        )
        
        if file_path:
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()
            
            # تعیین نوع فایل
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                media_type = 'image'
            elif ext in ['.mp4', '.avi', '.mkv', '.mov']:
                media_type = 'video'
            elif ext in ['.mp3', '.wav', '.ogg', '.flac']:
                media_type = 'audio'
            elif ext in ['.pdf', '.doc', '.docx', '.xlsx', '.txt']:
                media_type = 'document'
            else:
                media_type = 'other'
            
            # ثبت در دیتابیس
            media_id = self.db.insert_media(
                filename=filename,
                filepath=file_path,
                media_type=media_type,
                category='عمومی',
                title=filename,
                description='فایل آپلود شده توسط کاربر'
            )
            
            messagebox.showinfo("موفق", f"فایل با شناسه {media_id} ثبت شد.")
            self._show_media()  # بازسازی گالری
    
    def _show_forms(self):
        """نمایش بخش فرم‌های پویا"""
        self._clear_content()
        
        title_label = ctk.CTkLabel(self.content_frame, text="فرم‌های پویا و تعاملی",
                                  font=("Tahoma", 18, "bold"))
        title_label.pack(pady=10)
        
        # ایجاد فرم نمونه
        sample_schema = {
            'fields': [
                {'name': 'full_name', 'type': 'text', 'label': 'نام و نام خانوادگی', 'required': True},
                {'name': 'customer_id', 'type': 'number', 'label': 'شناسه اشتراک', 'required': True},
                {'name': 'zone', 'type': 'dropdown', 'label': 'منطقه', 'required': True,
                 'options': ['مرکزی', 'زرجاب', 'شهرک بهشتی', 'فرهنگیان', 'بلوار معلم']},
                {'name': 'debt_reason', 'type': 'textarea', 'label': 'علت بدهی', 'required': False},
                {'name': 'payment_date', 'type': 'date', 'label': 'تاریخ وعده پرداخت', 'required': True},
                {'name': 'agree_terms', 'type': 'checkbox', 'label': 'موافقت با شرایط', 'required': True}
            ]
        }
        
        form_builder = DynamicFormBuilder(self.content_frame, self.db)
        form_frame = ctk.CTkFrame(self.content_frame)
        form_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        form_builder.create_form_from_schema(form_frame, sample_schema)
    
    def _show_tables(self):
        """نمایش بخش جداول داده‌ای"""
        self._clear_content()
        
        title_label = ctk.CTkLabel(self.content_frame, text="جداول داده‌ای تعاملی",
                                  font=("Tahoma", 18, "bold"))
        title_label.pack(pady=10)
        
        # ایجاد جدول از دیتابیس
        table_frame = ctk.CTkFrame(self.content_frame)
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        query = "SELECT customer_id, full_name, address, debt_amount, zone, status FROM customers LIMIT 50"
        interactive_table = InteractiveTable(table_frame, self.db)
        interactive_table.create_table(table_frame, query, editable=True)
    
    def _show_settings(self):
        """نمایش بخش تنظیمات"""
        self._clear_content()
        
        settings_frame = ctk.CTkScrollableFrame(self.content_frame, width=800, height=600)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        title_label = ctk.CTkLabel(settings_frame, text="تنظیمات سیستم",
                                  font=("Tahoma", 18, "bold"))
        title_label.pack(pady=20)
        
        # تنظیمات ظاهری
        appearance_frame = ctk.CTkFrame(settings_frame)
        appearance_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(appearance_frame, text="ظاهر برنامه", font=("Tahoma", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        theme_var = ctk.StringVar(value="dark")
        theme_menu = ctk.CTkOptionMenu(appearance_frame, values=["dark", "light", "system"],
                                       variable=theme_var, command=self._change_theme)
        theme_menu.pack(anchor="w", padx=10, pady=5)
        
        # تنظیمات پایگاه داده
        db_frame = ctk.CTkFrame(settings_frame)
        db_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(db_frame, text="پایگاه داده", font=("Tahoma", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        backup_btn = ctk.CTkButton(db_frame, text="پشتیبان‌گیری از دیتابیس",
                                   command=self._backup_database, width=200)
        backup_btn.pack(anchor="w", padx=10, pady=5)
        
        # اطلاعات سیستم
        info_frame = ctk.CTkFrame(settings_frame)
        info_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(info_frame, text="اطلاعات سیستم", font=("Tahoma", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        info_text = f"""
        نسخه نرم‌افزار: 1.0.0
        پایگاه داده: {self.db.db_path}
        تاریخ اجرا: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        این سامانه با دسترسی کامل خواندن/نوشتن پیکربندی شده است.
        تمام عملیات‌ها در لاگ سیستم ثبت می‌شوند.
        """
        
        info_label = ctk.CTkLabel(info_frame, text=info_text, justify="left", anchor="w")
        info_label.pack(anchor="w", padx=10, pady=5)
    
    def _change_theme(self, theme: str):
        """تغییر تم برنامه"""
        ctk.set_appearance_mode(theme)
    
    def _backup_database(self):
        """پشتیبان‌گیری از پایگاه داده"""
        backup_path = filedialog.asksaveasfilename(
            defaultextension=".db",
            initialfile=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
            title="ذخیره پشتیبان"
        )
        
        if backup_path:
            import shutil
            shutil.copy2(self.db.db_path, backup_path)
            messagebox.showinfo("موفق", f"پشتیبان با موفقیت در {backup_path} ذخیره شد.")
    
    def on_closing(self):
        """پاک‌سازی هنگام بستن برنامه"""
        self.db.close()
        self.destroy()


def main():
    """تابع اصلی اجرای برنامه"""
    try:
        app = MultimediaManagerApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except Exception as e:
        logger.error(f"خطا در اجرای برنامه: {e}")
        raise


if __name__ == "__main__":
    main()
