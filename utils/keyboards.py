from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import config


def make_button(text: str, callback_data: str = None,
                url: str = None) -> InlineKeyboardButton:
    """إنشاء زر"""
    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=callback_data)


# ==================== تسجيل الدخول ====================

def login_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [make_button("🚀 تسجيل الدخول", "login")],
        [make_button("❓ مساعدة", "help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def cancel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [make_button("❌ إلغاء", "cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== القائمة الرئيسية ====================

def main_menu_keyboard(is_logged_in: bool = False) -> InlineKeyboardMarkup:
    if is_logged_in:
        keyboard = [
            [
                make_button("📋 قنواتي", "show_channels"),
                make_button("👥 مجموعاتي", "show_groups"),
            ],
            [
                make_button("📦 أرشيفي", "show_archives"),
                make_button("📊 إحصائياتي", "show_stats"),
            ],
            [
                make_button("🔍 بحث", "search"),
                make_button("⚙️ إعدادات", "settings"),
            ],
            [make_button("🚪 تسجيل الخروج", "logout")],
        ]
    else:
        keyboard = [
            [make_button("🚀 تسجيل الدخول", "login")],
            [make_button("❓ مساعدة", "help")],
        ]
    return InlineKeyboardMarkup(keyboard)


# ==================== القنوات والمجموعات ====================

def chats_keyboard(chats: list, chat_type: str,
                   page: int = 0,
                   per_page: int = 8) -> InlineKeyboardMarkup:
    """عرض القنوات أو المجموعات مع pagination"""
    keyboard = []

    start = page * per_page
    end = start + per_page
    current_chats = chats[start:end]

    for i, chat in enumerate(current_chats):
        real_index = start + i
        icon = "📢" if chat_type == "channel" else "👥"
        name = chat.get("title", "بدون اسم")
        members = chat.get("members_count", 0)

        keyboard.append([
            make_button(
                f"{icon} {name} ({members:,})",
                f"select_chat_{chat_type}_{real_index}"
            )
        ])

    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            make_button("⬅️ السابق", f"page_{chat_type}_{page-1}")
        )
    if end < len(chats):
        nav_buttons.append(
            make_button("التالي ➡️", f"page_{chat_type}_{page+1}")
        )
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([make_button("🔙 رجوع", "main_menu")])

    return InlineKeyboardMarkup(keyboard)


def chat_type_keyboard() -> InlineKeyboardMarkup:
    """اختيار نوع المحادثة"""
    keyboard = [
        [
            make_button("📢 القنوات", "show_channels"),
            make_button("👥 المجموعات", "show_groups"),
        ],
        [
            make_button("💬 المحادثات", "show_private"),
            make_button("📦 الكل", "show_all_chats"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== اختيار المحتوى ====================

def content_type_keyboard() -> InlineKeyboardMarkup:
    """اختيار نوع المحتوى المراد جلبه"""
    keyboard = [
        [
            make_button("📝 النصوص",      "content_text"),
            make_button("🖼️ الصور",       "content_photos"),
        ],
        [
            make_button("🎥 الفيديوهات",  "content_videos"),
            make_button("📁 الملفات",     "content_files"),
        ],
        [
            make_button("🎵 الصوتيات",    "content_audio"),
            make_button("🎤 الرسائل الصوتية", "content_voice"),
        ],
        [
            make_button("🎭 الملصقات",    "content_stickers"),
            make_button("📦 كل المحتوى", "content_all"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== حدود الجلب ====================

def fetch_limit_keyboard() -> InlineKeyboardMarkup:
    """اختيار عدد الرسائل"""
    keyboard = [
        [
            make_button("🔟 آخر 10",   "limit_10"),
            make_button("5️⃣0️⃣ آخر 50",  "limit_50"),
        ],
        [
            make_button("💯 آخر 100",  "limit_100"),
            make_button("5️⃣0️⃣0️⃣ آخر 500", "limit_500"),
        ],
        [
            make_button("🔢 آخر 1000", "limit_1000"),
            make_button("♾️ الكل ⚠️",  "limit_0"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== خيارات إضافية ====================

def extra_options_keyboard() -> InlineKeyboardMarkup:
    """خيارات إضافية قبل الجلب"""
    keyboard = [
        [
            make_button("🤖 تلخيص AI",     "opt_ai_summary"),
            make_button("🏷️ تصنيف AI",     "opt_ai_category"),
        ],
        [
            make_button("🎙️ تحويل صوت لنص", "opt_voice_to_text"),
            make_button("🔍 تجنب التكرار",  "opt_no_duplicate"),
        ],
        [
            make_button("📅 تصفية بالتاريخ", "opt_date_filter"),
            make_button("🔤 تصفية بكلمة",   "opt_keyword_filter"),
        ],
        [
            make_button("✅ بدء الجلب", "start_fetch"),
            make_button("❌ إلغاء",     "cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== التأكيد ====================

def confirm_keyboard(action: str = "confirm") -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("✅ تأكيد",  f"confirm_{action}"),
            make_button("❌ إلغاء", "cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_fetch_keyboard(stats: dict) -> InlineKeyboardMarkup:
    """تأكيد الجلب مع إحصائيات"""
    keyboard = [
        [
            make_button("✅ تأكيد الحفظ", "confirm_save"),
            make_button("❌ إلغاء",        "cancel"),
        ],
        [make_button("🔙 تغيير الخيارات", "back_to_options")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== الأرشيف ====================

def archive_keyboard(archive_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("📝 النصوص",   f"arch_text_{archive_id}"),
            make_button("🖼️ الصور",    f"arch_photos_{archive_id}"),
        ],
        [
            make_button("🎥 الفيديو",  f"arch_videos_{archive_id}"),
            make_button("📁 الملفات",  f"arch_files_{archive_id}"),
        ],
        [
            make_button("🤖 تحليل AI", f"arch_ai_{archive_id}"),
            make_button("📊 إحصائيات", f"arch_stats_{archive_id}"),
        ],
        [
            make_button("📤 تصدير ZIP", f"arch_export_{archive_id}"),
            make_button("🗑️ حذف",       f"arch_delete_{archive_id}"),
        ],
        [make_button("🔙 رجوع", "show_archives")],
    ]
    return InlineKeyboardMarkup(keyboard)


def archives_list_keyboard(archives: list,
                           page: int = 0,
                           per_page: int = 5) -> InlineKeyboardMarkup:
    keyboard = []

    start = page * per_page
    end = start + per_page
    current = archives[start:end]

    for archive in current:
        status_icon = {
            "completed": "✅",
            "pending":   "⏳",
            "running":   "🔄",
            "failed":    "❌",
        }.get(archive.get("status", ""), "📦")

        keyboard.append([
            make_button(
                f"{status_icon} {archive.get('chat_title', 'بدون اسم')} "
                f"({archive.get('fetched_messages', 0):,} رسالة)",
                f"view_archive_{archive.get('id')}"
            )
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            make_button("⬅️ السابق", f"archives_page_{page-1}")
        )
    if end < len(archives):
        nav_buttons.append(
            make_button("التالي ➡️", f"archives_page_{page+1}")
        )
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([make_button("🔙 رجوع", "main_menu")])

    return InlineKeyboardMarkup(keyboard)


# ==================== البحث ====================

def search_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("🔤 بحث بالنص",      "search_text"),
            make_button("📅 بحث بالتاريخ",   "search_date"),
        ],
        [
            make_button("🖼️ بحث بالنوع",     "search_type"),
            make_button("📢 بحث بالقناة",    "search_chat"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== الإعدادات ====================

def settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("🤖 إعدادات AI",        "settings_ai"),
            make_button("📥 إعدادات التحميل",   "settings_download"),
        ],
        [
            make_button("🔔 إعدادات التنبيهات", "settings_alerts"),
            make_button("🌍 اللغة",              "settings_language"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== لوحة الأدمن ====================

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("👥 المستخدمين",    "admin_users"),
            make_button("📊 الإحصائيات",   "admin_stats"),
        ],
        [
            make_button("📦 الأرشيفات",    "admin_archives"),
            make_button("📋 السجلات",      "admin_logs"),
        ],
        [
            make_button("⚙️ إعدادات البوت", "admin_settings"),
            make_button("📢 إرسال للكل",   "admin_broadcast"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_user_keyboard(user_id: int,
                        is_banned: bool = False) -> InlineKeyboardMarkup:
    ban_button = (
        make_button("✅ رفع الحظر", f"admin_unban_{user_id}")
        if is_banned else
        make_button("🚫 حظر",      f"admin_ban_{user_id}")
    )
    keyboard = [
        [
            ban_button,
            make_button("📊 إحصائياته", f"admin_user_stats_{user_id}"),
        ],
        [
            make_button("📋 سجل نشاطه", f"admin_user_log_{user_id}"),
            make_button("🗑️ حذف بياناته", f"admin_delete_user_{user_id}"),
        ],
        [make_button("🔙 رجوع", "admin_users")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== لوحة المالك ====================

def owner_panel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("👑 إدارة الأدمنية",   "owner_admins"),
            make_button("👥 إدارة المستخدمين", "owner_users"),
        ],
        [
            make_button("📊 إحصائيات كاملة",  "owner_stats"),
            make_button("📋 سجل كامل",        "owner_logs"),
        ],
        [
            make_button("⚙️ إعدادات البوت",   "owner_settings"),
            make_button("🔄 إعادة تشغيل",     "owner_restart"),
        ],
        [
            make_button("📢 إرسال للكل",      "owner_broadcast"),
            make_button("🗑️ تنظيف البيانات",  "owner_cleanup"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def admins_list_keyboard(admins: list) -> InlineKeyboardMarkup:
    keyboard = []

    for admin in admins:
        name = admin.get("full_name") or admin.get("username", "بدون اسم")
        keyboard.append([
            make_button(
                f"👤 {name}",
                f"owner_admin_{admin.get('telegram_id')}"
            )
        ])

    keyboard.append([make_button("➕ إضافة أدمن", "owner_add_admin")])
    keyboard.append([make_button("🔙 رجوع",        "owner_panel")])

    return InlineKeyboardMarkup(keyboard)


def admin_manage_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("✏️ تعديل الصلاحيات", f"owner_edit_admin_{admin_id}"),
            make_button("🗑️ إزالة",            f"owner_remove_admin_{admin_id}"),
        ],
        [make_button("🔙 رجوع", "owner_admins")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== التنبيهات ====================

def alerts_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [make_button("➕ إضافة تنبيه جديد", "alert_add")],
        [make_button("📋 تنبيهاتي",          "alert_list")],
        [make_button("🔙 رجوع",              "settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== مساعدة ====================

def help_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            make_button("📖 كيفية الاستخدام", "help_usage"),
            make_button("❓ الأسئلة الشائعة", "help_faq"),
        ],
        [make_button("🔙 رجوع", "main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)
