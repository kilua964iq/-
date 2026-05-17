from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import config


# ==================== دالة مساعدة ====================

def btn(text: str,
        callback_data: str = None,
        url: str = None) -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=callback_data)


def kb(*rows) -> InlineKeyboardMarkup:
    keyboard = []
    for row in rows:
        if isinstance(row, list):
            keyboard.append(row)
        else:
            keyboard.append([row])
    return InlineKeyboardMarkup(keyboard)


# ==================== القائمة الرئيسية ====================

def main_menu_keyboard(
        is_logged_in: bool = False) -> InlineKeyboardMarkup:
    if is_logged_in:
        return kb(
            [
                btn("📢 قنواتي",    "show_channels"),
                btn("👥 مجموعاتي", "show_groups"),
            ],
            [
                btn("📦 أرشيفي",     "show_archives"),
                btn("📊 إحصائياتي", "show_stats"),
            ],
            [
                btn("🔍 بحث",     "search"),
                btn("⚙️ إعدادات", "settings"),
            ],
            [
                btn("👑 المطور", "developer"),
                btn("🚪 خروج",   "logout"),
            ],
        )
    return kb(
        [btn("🚀 تسجيل الدخول", "login")],
        [btn("❓ مساعدة",        "help")],
        [btn(
            f"👑 {config.DEVELOPER_NAME} | "
            f"{config.DEVELOPER_USERNAME}",
            "developer"
        )],
    )


# ==================== تسجيل الدخول ====================

def login_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [btn("🚀 تسجيل الدخول", "login")],
        [btn("❓ مساعدة", "help")],
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [btn("❌ إلغاء", "cancel")],
    )


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return kb(
        [
            btn("✅ تأكيد", f"confirm_{action}"),
            btn("❌ إلغاء", "cancel"),
        ],
    )


# ==================== القنوات ====================

def chat_type_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("📢 القنوات",    "show_channels"),
            btn("👥 المجموعات", "show_groups"),
        ],
        [
            btn("💬 المحادثات",  "show_private"),
            btn("📦 الكل",       "show_all_chats"),
        ],
        [btn("🔙 رجوع", "main_menu")],
    )


def chats_keyboard(chats: list,
                   chat_type: str,
                   page: int = 0,
                   per_page: int = 8) -> InlineKeyboardMarkup:
    keyboard = []

    start = page * per_page
    end   = start + per_page
    current = chats[start:end]

    for i, chat in enumerate(current):
        real_index = start + i
        icon = "📢" if chat_type == "channel" else "👥"
        name = chat.get("title", "بدون اسم")
        members = chat.get("members_count", 0)

        keyboard.append([btn(
            f"{icon} {name} ({_fmt(members)})",
            f"select_chat_{chat_type}_{real_index}"
        )])

    nav = []
    if page > 0:
        nav.append(btn("⬅️ السابق",
                       f"page_{chat_type}_{page-1}"))
    if end < len(chats):
        nav.append(btn("التالي ➡️",
                       f"page_{chat_type}_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([btn("🔙 رجوع", "main_menu")])
    return InlineKeyboardMarkup(keyboard)


def _fmt(n: int) -> str:
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


# ==================== المحتوى ====================

def content_type_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("📝 النصوص",      "content_text"),
            btn("🖼️ الصور",       "content_photos"),
        ],
        [
            btn("🎥 الفيديوهات",  "content_videos"),
            btn("📁 الملفات",     "content_files"),
        ],
        [
            btn("🎵 الصوتيات",        "content_audio"),
            btn("🎤 رسائل صوتية",     "content_voice"),
        ],
        [
            btn("🎭 الملصقات",    "content_stickers"),
            btn("📦 كل المحتوى", "content_all"),
        ],
        [btn("🔙 رجوع", "main_menu")],
    )


# ==================== حدود الجلب ====================

def fetch_limit_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("🔟 آخر 10",    "limit_10"),
            btn("5️⃣0️⃣ آخر 50",  "limit_50"),
        ],
        [
            btn("💯 آخر 100",   "limit_100"),
            btn("5️⃣0️⃣0️⃣ آخر 500", "limit_500"),
        ],
        [
            btn("🔢 آخر 1000",  "limit_1000"),
            btn("♾️ الكل ⚠️",   "limit_0"),
        ],
        [btn("🔙 رجوع", "main_menu")],
    )


# ==================== خيارات إضافية ====================

def extra_options_keyboard(
        options: dict = None) -> InlineKeyboardMarkup:
    if options is None:
        options = {}

    def s(key):
        return "✅" if options.get(key) else "☑️"

    return kb(
        [
            btn(f"{s('ai_summary')} تلخيص AI",
                "opt_ai_summary"),
            btn(f"{s('ai_category')} تصنيف AI",
                "opt_ai_category"),
        ],
        [
            btn(f"{s('voice_to_text')} تحويل صوت",
                "opt_voice_to_text"),
            btn(f"{s('no_duplicate')} تجنب التكرار",
                "opt_no_duplicate"),
        ],
        [
            btn(f"{s('smart_extract')} استخراج ذكي",
                "opt_smart_extract"),
            btn(f"{s('save_txt')} حفظ كـ TXT",
                "opt_save_txt"),
        ],
        [
            btn("▶️ بدء الجلب", "start_fetch"),
            btn("❌ إلغاء",      "cancel"),
        ],
    )


def confirm_fetch_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("✅ تأكيد الحفظ", "confirm_save"),
            btn("❌ إلغاء",        "cancel"),
        ],
        [btn("🔙 تغيير الخيارات", "back_to_options")],
    )


# ==================== الأرشيف ====================

def archive_keyboard(archive_id: int) -> InlineKeyboardMarkup:
    return kb(
        [
            btn("📝 النصوص",   f"arch_text_{archive_id}"),
            btn("🖼️ الصور",    f"arch_photos_{archive_id}"),
        ],
        [
            btn("🎥 الفيديو",  f"arch_videos_{archive_id}"),
            btn("📁 الملفات",  f"arch_files_{archive_id}"),
        ],
        [
            btn("🤖 تحليل AI",  f"arch_ai_{archive_id}"),
            btn("📊 إحصائيات", f"arch_stats_{archive_id}"),
        ],
        [
            btn("📄 تصدير TXT", f"arch_txt_{archive_id}"),
            btn("📦 تصدير ZIP", f"arch_zip_{archive_id}"),
        ],
        [
            btn("💡 استخراج ذكي", f"arch_extract_{archive_id}"),
            btn("🗑️ حذف",          f"arch_delete_{archive_id}"),
        ],
        [btn("🔙 رجوع", "show_archives")],
    )


def archives_list_keyboard(archives: list,
                           page: int = 0,
                           per_page: int = 5) -> InlineKeyboardMarkup:
    keyboard = []

    start = page * per_page
    end   = start + per_page
    current = archives[start:end]

    for archive in current:
        status_icon = {
            "completed": "✅",
            "pending":   "⏳",
            "running":   "🔄",
            "failed":    "❌",
            "cancelled": "⚠️",
        }.get(archive.get("status", ""), "📦")

        keyboard.append([btn(
            f"{status_icon} "
            f"{archive.get('chat_title', '')[:20]} "
            f"({_fmt(archive.get('fetched_messages', 0))})",
            f"view_archive_{archive.get('id')}"
        )])

    nav = []
    if page > 0:
        nav.append(btn("⬅️ السابق",
                       f"archives_page_{page-1}"))
    if end < len(archives):
        nav.append(btn("التالي ➡️",
                       f"archives_page_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([btn("🔙 رجوع", "main_menu")])
    return InlineKeyboardMarkup(keyboard)


# ==================== البحث ====================

def search_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("🔤 بحث بالنص",    "search_text"),
            btn("📅 بحث بالتاريخ", "search_date"),
        ],
        [
            btn("🖼️ بحث بالنوع",  "search_type"),
            btn("📢 بحث بالقناة", "search_chat"),
        ],
        [btn("🌐 بحث في الكل", "search_all")],
        [btn("🔙 رجوع", "main_menu")],
    )


# ==================== الإعدادات ====================

def settings_keyboard(
        settings: dict = None) -> InlineKeyboardMarkup:
    if settings is None:
        settings = {}

    def s(key):
        return "✅" if settings.get(key, True) else "❌"

    return kb(
        [
            btn(f"{s('smart_filter')} تصفية ذكية",
                "setting_smart_filter"),
            btn(f"{s('extract_cards')} استخراج بطاقات",
                "setting_extract_cards"),
        ],
        [
            btn(f"{s('extract_phones')} استخراج هواتف",
                "setting_extract_phones"),
            btn(f"{s('extract_emails')} استخراج إيميلات",
                "setting_extract_emails"),
        ],
        [
            btn(f"{s('extract_urls')} استخراج روابط",
                "setting_extract_urls"),
            btn(f"{s('ai_summary')} تلخيص AI",
                "setting_ai_summary"),
        ],
        [
            btn(f"{s('voice_to_text')} تحويل صوت لنص",
                "setting_voice_to_text"),
            btn(f"{s('save_txt')} حفظ كـ TXT دائماً",
                "setting_save_txt"),
        ],
        [btn("🔙 رجوع", "main_menu")],
    )


# ==================== الإحصائيات ====================

def stats_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("📊 مفصلة",   "stats_detailed"),
            btn("📅 أسبوعي",  "stats_weekly"),
        ],
        [
            btn("💾 التخزين", "stats_storage"),
            btn("📈 مقارنة",  "stats_compare"),
        ],
        [btn("🗑️ تنظيف", "cleanup_storage")],
        [btn("🔙 رجوع",  "main_menu")],
    )


# ==================== لوحة الأدمن ====================

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("👥 المستخدمين",   "admin_users"),
            btn("📊 الإحصائيات",  "admin_stats"),
        ],
        [
            btn("📦 الأرشيفات",   "admin_archives"),
            btn("📋 السجلات",     "admin_logs"),
        ],
        [
            btn("⚙️ إعدادات البوت", "admin_settings"),
            btn("📢 إرسال للكل",    "admin_broadcast"),
        ],
        [btn("🔙 رجوع", "main_menu")],
    )


# ==================== لوحة المالك ====================

def owner_panel_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("👑 الأدمنية",        "owner_admins"),
            btn("👥 المستخدمين",      "owner_users"),
        ],
        [
            btn("📊 إحصائيات كاملة", "owner_stats"),
            btn("📋 سجل كامل",       "owner_logs"),
        ],
        [
            btn("⚙️ إعدادات",        "owner_settings"),
            btn("🔄 إعادة تشغيل",    "owner_restart"),
        ],
        [
            btn("📢 إرسال للكل",     "owner_broadcast"),
            btn("🗑️ تنظيف",          "owner_cleanup"),
        ],
        [btn("🔙 رجوع", "main_menu")],
    )


def admins_list_keyboard(admins: list) -> InlineKeyboardMarkup:
    keyboard = []

    for admin in admins:
        name = (
            admin.get("full_name") or
            admin.get("username", "بدون اسم")
        )
        keyboard.append([btn(
            f"👤 {name}",
            f"owner_admin_{admin.get('telegram_id')}"
        )])

    keyboard.append([btn("➕ إضافة أدمن", "owner_add_admin")])
    keyboard.append([btn("🔙 رجوع", "owner_panel")])
    return InlineKeyboardMarkup(keyboard)


def admin_manage_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    return kb(
        [
            btn("✏️ تعديل الصلاحيات",
                f"owner_edit_admin_{admin_id}"),
            btn("🗑️ إزالة",
                f"owner_remove_admin_{admin_id}"),
        ],
        [btn("🔙 رجوع", "owner_admins")],
    )


def admin_user_keyboard(user_id: int,
                        is_banned: bool = False) -> InlineKeyboardMarkup:
    ban_btn = (
        btn("✅ رفع الحظر", f"admin_unban_{user_id}")
        if is_banned else
        btn("🚫 حظر", f"admin_ban_{user_id}")
    )
    return kb(
        [
            ban_btn,
            btn("📊 إحصائياته",
                f"admin_user_stats_{user_id}"),
        ],
        [btn("🔙 رجوع", "admin_users")],
    )


# ==================== مساعدة ====================

def help_keyboard() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("📖 كيفية الاستخدام", "help_usage"),
            btn("❓ الأسئلة الشائعة",  "help_faq"),
        ],
        [btn("🔙 رجوع", "main_menu")],
    )
