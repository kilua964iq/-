import asyncio
import os
import telebot
from telebot.types import Message, CallbackQuery
from datetime import datetime
from config import config
from services.telegram_client import telegram_service
from services.downloader import download_manager
from services.queue_service import (
    queue_service,
    TaskPriority,
)
from utils.keyboards import (
    content_type_keyboard,
    fetch_limit_keyboard,
    extra_options_keyboard,
    confirm_fetch_keyboard,
    archive_keyboard,
    archives_list_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from utils.helpers import (
    format_number,
    format_size,
    format_date,
    build_stats_message,
    build_fetch_progress_message,
    classify_message,
    smart_extract,
    format_extracted_data,
    clean_text,
    save_as_txt,
)
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)
from handlers.auth import (
    get_state,
    set_state,
    clear_state,
    get_user_data,
    STATE_IDLE,
)


# ==================== تسجيل الهاندلرز ====================

def register_archive_handlers(bot: telebot.TeleBot):
    """تسجيل كل هاندلرز الأرشيف"""

    # ==================== اختيار المحتوى ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("content_")
    )
    def content_type_callback(call: CallbackQuery):
        user_id      = call.from_user.id
        bot.answer_callback_query(call.id)
        content_type = call.data.replace("content_", "")

        set_state(
            user_id,
            STATE_IDLE,
            content_type=content_type,
        )

        content_name = config.CONTENT_TYPES.get(
            content_type, content_type
        )

        bot.send_message(
            user_id,
            f"✅ النوع المختار: **{content_name}**\n\n"
            f"🔢 **كم رسالة تريد جلبها؟**",
            reply_markup=fetch_limit_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== اختيار الحد ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("limit_")
    )
    def fetch_limit_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        limit = int(call.data.replace("limit_", ""))

        set_state(
            user_id,
            STATE_IDLE,
            fetch_limit=limit,
        )

        content_type = get_user_data(
            user_id, "content_type"
        ) or "all"
        content_name = config.CONTENT_TYPES.get(
            content_type, content_type
        )
        chat = get_user_data(
            user_id, "selected_chat"
        ) or {}
        options = get_user_data(
            user_id, "options"
        ) or {}

        limit_text = (
            f"آخر {format_number(limit)}"
            if limit > 0 else "كل المحتوى"
        )

        bot.send_message(
            user_id,
            f"✅ **ملخص الاختيارات**\n\n"
            f"📢 القناة:  `{chat.get('title', '')}`\n"
            f"📌 النوع:   `{content_name}`\n"
            f"🔢 الكمية:  `{limit_text}`\n\n"
            f"⚙️ **خيارات إضافية؟**",
            reply_markup=extra_options_keyboard(options),
            parse_mode="Markdown"
        )

    # ==================== الخيارات الإضافية ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("opt_")
    )
    def toggle_option_callback(call: CallbackQuery):
        user_id = call.from_user.id

        option  = call.data.replace("opt_", "")
        options = get_user_data(user_id, "options") or {}

        options[option] = not options.get(option, False)

        set_state(
            user_id,
            STATE_IDLE,
            options=options,
        )

        option_names = {
            "ai_summary":    "تلخيص AI",
            "ai_category":   "تصنيف AI",
            "voice_to_text": "تحويل صوت لنص",
            "no_duplicate":  "تجنب التكرار",
            "smart_extract": "استخراج ذكي",
            "save_txt":      "حفظ كـ TXT",
        }

        name   = option_names.get(option, option)
        status = "✅" if options[option] else "☑️"

        bot.answer_callback_query(
            call.id,
            f"{status} {name}",
            show_alert=False
        )

        # تحديث الأزرار
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=extra_options_keyboard(options)
            )
        except Exception:
            pass

    # ==================== بدء الجلب ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "start_fetch"
    )
    def start_fetch_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        chat         = get_user_data(
            user_id, "selected_chat"
        ) or {}
        content_type = get_user_data(
            user_id, "content_type"
        ) or "all"
        limit        = get_user_data(
            user_id, "fetch_limit"
        ) or 100
        options      = get_user_data(
            user_id, "options"
        ) or {}

        if not chat:
            bot.send_message(
                user_id,
                "❌ لم يتم اختيار قناة\nابدأ من جديد"
            )
            return

        content_name = config.CONTENT_TYPES.get(
            content_type, content_type
        )
        limit_text = (
            f"آخر {format_number(limit)}"
            if limit > 0 else "كل المحتوى"
        )

        options_text = ""
        if options.get("ai_summary"):
            options_text += "🤖 تلخيص AI\n"
        if options.get("ai_category"):
            options_text += "🏷️ تصنيف AI\n"
        if options.get("voice_to_text"):
            options_text += "🎙️ تحويل صوت لنص\n"
        if options.get("no_duplicate"):
            options_text += "🔍 تجنب التكرار\n"
        if options.get("smart_extract"):
            options_text += "💡 استخراج ذكي\n"
        if options.get("save_txt"):
            options_text += "📄 حفظ كـ TXT\n"

        bot.send_message(
            user_id,
            f"📋 **تأكيد الجلب**\n\n"
            f"📢 القناة:  `{chat.get('title', '')}`\n"
            f"📌 النوع:   `{content_name}`\n"
            f"🔢 الكمية:  `{limit_text}`\n"
            f"{options_text}\n"
            f"هل تريد البدء؟",
            reply_markup=confirm_fetch_keyboard(),
            parse_mode="Markdown"
        )

    # ==================== تأكيد الجلب ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "confirm_save"
    )
    def confirm_save_callback(call: CallbackQuery):
        asyncio.run(_confirm_save(bot, call))

    async def _confirm_save(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        chat         = get_user_data(
            user_id, "selected_chat"
        ) or {}
        content_type = get_user_data(
            user_id, "content_type"
        ) or "all"
        limit        = get_user_data(
            user_id, "fetch_limit"
        ) or 100
        options      = get_user_data(
            user_id, "options"
        ) or {}

        if not chat:
            bot.send_message(
                user_id,
                "❌ لم يتم اختيار قناة"
            )
            return

        # إنشاء أرشيف
        archive = await db.create_archive(
            owner_id     = user_id,
            chat_id      = chat.get("id"),
            chat_title   = chat.get("title", ""),
            content_type = content_type,
            settings     = {
                "limit":   limit,
                "options": options,
            }
        )

        archive_id = archive["id"]

        # رسالة التقدم
        progress_msg = bot.send_message(
            user_id,
            f"🚀 **بدأ الجلب...**\n\n"
            f"📢 {chat.get('title', '')}\n\n"
            f"⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\n"
            f"`0` رسالة",
            parse_mode="Markdown"
        )

        set_state(
            user_id,
            STATE_IDLE,
            progress_msg_id=progress_msg.message_id,
            archive_id=archive_id,
            is_cancelled=False,
        )

        # إضافة للطابور
        task = await queue_service.add_task(
            owner_id  = user_id,
            task_type = "fetch",
            coroutine = _fetch_and_save(
                bot          = bot,
                user_id      = user_id,
                archive_id   = archive_id,
                chat         = chat,
                content_type = content_type,
                limit        = limit,
                options      = options,
                progress_msg = progress_msg,
            ),
            priority = TaskPriority.NORMAL,
            data     = {
                "archive_id":   archive_id,
                "chat_title":   chat.get("title"),
                "content_type": content_type,
                "limit":        limit,
            }
        )

        set_state(
            user_id,
            STATE_IDLE,
            current_task_id=task.task_id,
        )

    # ==================== عملية الجلب ====================

    async def _fetch_and_save(
            bot: telebot.TeleBot,
            user_id: int,
            archive_id: int,
            chat: dict,
            content_type: str,
            limit: int,
            options: dict,
            progress_msg):
        """عملية الجلب والحفظ الكاملة"""
        from database import db
        from services.ai_service import ai_service

        chat_id    = chat.get("id")
        chat_title = chat.get("title", "")
        entity     = chat.get("entity")

        stats = {
            "text":       0,
            "photos":     0,
            "videos":     0,
            "files":      0,
            "audio":      0,
            "voice":      0,
            "stickers":   0,
            "total":      0,
            "failed":     0,
            "total_size": 0,
        }

        last_update     = datetime.now()
        update_interval = 5
        all_texts       = []

        try:
            await db.update_archive(
                archive_id,
                status="running"
            )

            async for msg_data in telegram_service.fetch_messages(
                user_id      = user_id,
                entity       = entity,
                content_type = content_type,
                limit        = limit,
            ):
                # التحقق من الإلغاء
                if get_user_data(user_id, "is_cancelled"):
                    break

                message  = msg_data["message"]
                msg_type = msg_data["type"]
                stats    = msg_data["stats"]

                file_path = None
                file_size = 0
                file_name = None

                # تحميل الميديا
                if (message.media and
                        msg_type not in ["text", "stickers"]):
                    try:
                        file_path = await telegram_service.download_media(
                            user_id  = user_id,
                            message  = message,
                            msg_type = msg_type,
                            chat_id  = chat_id,
                        )
                        if file_path:
                            file_size = os.path.getsize(
                                file_path
                            )
                            file_name = os.path.basename(
                                file_path
                            )
                            stats["total_size"] += file_size
                    except Exception as e:
                        stats["failed"] += 1
                        error_logger.log_exception(
                            e, "download_media", user_id
                        )

                # تحويل صوت لنص
                ai_summary  = None
                ai_category = None

                if (options.get("voice_to_text") and
                        msg_type in ["voice", "audio"] and
                        file_path):
                    try:
                        transcript = await ai_service.transcribe_audio(
                            file_path
                        )
                        if transcript:
                            ai_summary = transcript
                    except Exception as e:
                        error_logger.log_exception(
                            e, "transcribe", user_id
                        )

                # تلخيص AI
                if (options.get("ai_summary") and
                        message.text and
                        len(message.text) > 100):
                    try:
                        ai_summary = await ai_service.summarize_text(
                            message.text
                        )
                    except Exception as e:
                        error_logger.log_exception(
                            e, "summarize", user_id
                        )

                # تصنيف AI
                if (options.get("ai_category") and
                        message.text):
                    try:
                        cat = await ai_service.categorize_text(
                            message.text
                        )
                        if cat:
                            ai_category = cat.get(
                                "category"
                            )
                    except Exception as e:
                        error_logger.log_exception(
                            e, "categorize", user_id
                        )

                # حفظ النص للتصدير
                if message.text:
                    all_texts.append({
                        "text": message.text,
                        "date": str(message.date),
                        "id":   message.id,
                    })

                # معلومات المرسل
                sender_name = None
                sender_id   = None
                if message.sender:
                    sender_id   = message.sender_id
                    sender      = message.sender
                    sender_name = (
                        getattr(sender, "first_name", "") or
                        getattr(sender, "title", "") or ""
                    )

                # حفظ في قاعدة البيانات
                date = message.date
                if (date and hasattr(date, 'tzinfo') and
                        date.tzinfo is not None):
                    date = date.replace(tzinfo=None)

                await db.save_message(
                    archive_id   = archive_id,
                    owner_id     = user_id,
                    chat_id      = chat_id,
                    message_id   = message.id,
                    message_type = msg_type,
                    text         = message.text or "",
                    file_path    = file_path,
                    file_size    = file_size,
                    file_name    = file_name,
                    date         = date,
                    sender_id    = sender_id,
                    sender_name  = sender_name,
                    views        = getattr(
                        message, "views", 0
                    ) or 0,
                    forwards     = getattr(
                        message, "forwards", 0
                    ) or 0,
                    ai_summary   = ai_summary,
                    ai_category  = ai_category,
                )

                # تحديث التقدم
                now     = datetime.now()
                elapsed = (now - last_update).seconds

                if elapsed >= update_interval:
                    last_update = now
                    total       = stats["total"]
                    progress    = (
                        min(
                            int((total / limit) * 100),
                            99
                        )
                        if limit > 0 else 50
                    )

                    await db.update_archive(
                        archive_id,
                        fetched_messages=total,
                        progress=progress,
                    )

                    try:
                        bot.edit_message_text(
                            build_fetch_progress_message(
                                chat_title   = chat_title,
                                current      = total,
                                total        = limit,
                                content_type = content_type,
                                stats        = stats,
                            ),
                            chat_id    = user_id,
                            message_id = progress_msg.message_id,
                            parse_mode = "Markdown"
                        )
                    except Exception:
                        pass

            # اكتملت العملية
            is_cancelled = get_user_data(
                user_id, "is_cancelled"
            ) or False

            final_status = (
                "cancelled" if is_cancelled
                else "completed"
            )

            await db.update_archive(
                archive_id,
                status           = final_status,
                fetched_messages = stats["total"],
                progress         = 100,
                completed_at     = datetime.now(),
            )

            # تصدير TXT إذا مطلوب
            txt_path = None
            if (options.get("save_txt") and all_texts):
                txt_path = await download_manager.export_messages_as_txt(
                    owner_id      = user_id,
                    archive_id    = archive_id,
                    chat_title    = chat_title,
                    messages      = all_texts,
                    extract_smart = options.get(
                        "smart_extract", False
                    ),
                )

            # رسالة الاكتمال
            status_text = (
                "⚠️ **تم إيقاف الجلب**"
                if is_cancelled else
                "✅ **اكتمل الجلب بنجاح!**"
            )

            completion_msg = (
                f"{status_text}\n\n"
                f"📢 القناة: `{chat_title}`\n\n"
                f"{build_stats_message(stats)}"
            )

            try:
                bot.edit_message_text(
                    completion_msg,
                    chat_id    = user_id,
                    message_id = progress_msg.message_id,
                    reply_markup = archive_keyboard(
                        archive_id
                    ),
                    parse_mode = "Markdown"
                )
            except Exception:
                bot.send_message(
                    user_id,
                    completion_msg,
                    reply_markup=archive_keyboard(
                        archive_id
                    ),
                    parse_mode="Markdown"
                )

            # إرسال ملف TXT
            if txt_path and os.path.exists(txt_path):
                with open(txt_path, "rb") as f:
                    bot.send_document(
                        user_id,
                        f,
                        caption=(
                            f"📄 ملف النصوص\n"
                            f"📢 {chat_title}\n"
                            f"💬 {format_number(stats['total'])} رسالة"
                        )
                    )

            activity_logger.log_archive(
                user_id, archive_id, chat_title
            )

        except Exception as e:
            error_logger.log_exception(
                e, "fetch_and_save", user_id
            )
            await db.update_archive(
                archive_id,
                status="failed",
            )
            try:
                bot.edit_message_text(
                    f"❌ **فشل الجلب**\n\n"
                    f"خطأ: `{str(e)[:200]}`",
                    chat_id    = user_id,
                    message_id = progress_msg.message_id,
                    parse_mode = "Markdown"
                )
            except Exception:
                bot.send_message(
                    user_id,
                    f"❌ فشل الجلب: {str(e)[:200]}"
                )

    # ==================== إيقاف الجلب ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "cancel_fetch"
    )
    def cancel_fetch_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(
            call.id, "⚠️ جاري الإيقاف..."
        )

        set_state(user_id, STATE_IDLE, is_cancelled=True)

        task_id = get_user_data(user_id, "current_task_id")
        if task_id:
            asyncio.run(queue_service.cancel_task(task_id))

        bot.send_message(
            user_id,
            "⚠️ **تم طلب الإيقاف**\n\n"
            "سيتوقف الجلب بعد الرسالة الحالية",
            parse_mode="Markdown"
        )

    # ==================== عرض الأرشيفات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "show_archives"
    )
    def show_archives_callback(call: CallbackQuery):
        asyncio.run(_show_archives(bot, call))

    async def _show_archives(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        archives = await db.get_user_archives(
            owner_id=user_id,
            limit=50,
        )

        if not archives:
            bot.send_message(
                user_id,
                "📦 **أرشيفاتك**\n\n"
                "لا توجد أرشيفات بعد\n"
                "ابدأ بجلب محتوى من قناة 👇",
                reply_markup=main_menu_keyboard(
                    is_logged_in=True
                ),
                parse_mode="Markdown"
            )
            return

        archives_list = [dict(a) for a in archives]
        set_state(
            user_id,
            STATE_IDLE,
            archives_list=archives_list,
        )

        bot.send_message(
            user_id,
            f"📦 **أرشيفاتك** ({len(archives_list)})\n\n"
            f"اختر أرشيف لعرض تفاصيله 👇",
            reply_markup=archives_list_keyboard(
                archives_list, page=0
            ),
            parse_mode="Markdown"
        )

    # ==================== صفحات الأرشيفات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("archives_page_")
    )
    def archives_page_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        page = int(
            call.data.replace("archives_page_", "")
        )
        archives_list = get_user_data(
            user_id, "archives_list"
        ) or []

        bot.send_message(
            user_id,
            f"📦 **أرشيفاتك** ({len(archives_list)})\n\n"
            f"اختر أرشيف 👇",
            reply_markup=archives_list_keyboard(
                archives_list, page=page
            ),
            parse_mode="Markdown"
        )

    # ==================== عرض أرشيف ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("view_archive_")
    )
    def view_archive_callback(call: CallbackQuery):
        asyncio.run(_view_archive(bot, call))

    async def _view_archive(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id    = call.from_user.id
        bot.answer_callback_query(call.id)
        archive_id = int(
            call.data.replace("view_archive_", "")
        )

        archive = await db.get_archive(archive_id)
        if not archive:
            bot.send_message(
                user_id, "❌ الأرشيف غير موجود"
            )
            return

        archive_dict = dict(archive)
        msg_count    = await db.count_messages(
            archive_id=archive_id
        )

        status_map = {
            "completed": "✅ مكتمل",
            "pending":   "⏳ في الانتظار",
            "running":   "🔄 جاري",
            "failed":    "❌ فشل",
            "cancelled": "⚠️ ملغي",
        }

        content_name = config.CONTENT_TYPES.get(
            archive_dict.get("content_type", ""),
            "غير معروف"
        )

        msg = (
            f"📦 **تفاصيل الأرشيف**\n\n"
            f"📢 القناة:    `{archive_dict.get('chat_title', '')}`\n"
            f"📌 النوع:     `{content_name}`\n"
            f"📊 الحالة:    "
            f"{status_map.get(archive_dict.get('status', ''), '❓')}\n"
            f"💬 الرسائل:  `{format_number(msg_count)}`\n"
            f"📅 التاريخ:  "
            f"`{format_date(archive_dict.get('started_at'))}`\n"
        )

        bot.send_message(
            user_id,
            msg,
            reply_markup=archive_keyboard(archive_id),
            parse_mode="Markdown"
        )

    # ==================== عمليات الأرشيف ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("arch_")
    )
    def archive_action_callback(call: CallbackQuery):
        asyncio.run(_archive_action(bot, call))

    async def _archive_action(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        parts      = call.data.split("_")
        action     = parts[1]
        archive_id = int(parts[2])

        archive = await db.get_archive(archive_id)
        if not archive:
            bot.send_message(
                user_id, "❌ الأرشيف غير موجود"
            )
            return

        archive_dict = dict(archive)

        if action == "stats":
            await _show_archive_stats(
                bot, user_id, archive_id, archive_dict, db
            )

        elif action == "txt":
            await _export_txt(
                bot, user_id, archive_id, archive_dict, db
            )

        elif action == "zip":
            await _export_zip(
                bot, user_id, archive_dict
            )

        elif action == "extract":
            await _smart_extract(
                bot, user_id, archive_id, archive_dict, db
            )

        elif action == "delete":
            from utils.keyboards import confirm_keyboard
            bot.send_message(
                user_id,
                "⚠️ **هل تريد حذف هذا الأرشيف؟**\n\n"
                "سيتم حذف كل الملفات والبيانات\n"
                "هذا الإجراء لا يمكن التراجع عنه!",
                reply_markup=confirm_keyboard(
                    f"delete_archive_{archive_id}"
                ),
                parse_mode="Markdown"
            )

        elif action == "ai":
            await _analyze_ai(
                bot, user_id, archive_id, archive_dict, db
            )

        elif action in [
            "text", "photos", "videos",
            "files", "audio"
        ]:
            await _show_content(
                bot, user_id, archive_id, action, db
            )

    async def _show_archive_stats(
            bot, user_id, archive_id,
            archive, db):
        """عرض إحصائيات أرشيف"""
        messages = await db.get_archive_messages(
            archive_id=archive_id,
            limit=9999,
        )

        stats = {
            "text":       0,
            "photos":     0,
            "videos":     0,
            "files":      0,
            "audio":      0,
            "voice":      0,
            "stickers":   0,
            "total":      0,
            "total_size": 0,
        }

        for msg in messages:
            msg_type = msg["message_type"]
            stats[msg_type] = stats.get(msg_type, 0) + 1
            stats["total"]  += 1
            stats["total_size"] += msg["file_size"] or 0

        bot.send_message(
            user_id,
            f"📊 **إحصائيات الأرشيف**\n\n"
            f"📢 القناة: `{archive.get('chat_title', '')}`\n\n"
            f"{build_stats_message(stats)}",
            reply_markup=archive_keyboard(archive_id),
            parse_mode="Markdown"
        )

    async def _export_txt(
            bot, user_id, archive_id,
            archive, db):
        """تصدير كـ TXT"""
        wait_msg = bot.send_message(
            user_id,
            "⏳ جاري إنشاء ملف TXT..."
        )

        messages = await db.get_archive_messages(
            archive_id=archive_id,
            limit=9999,
        )

        messages_list = [dict(m) for m in messages]

        txt_path = await download_manager.export_messages_as_txt(
            owner_id   = user_id,
            archive_id = archive_id,
            chat_title = archive.get("chat_title", ""),
            messages   = messages_list,
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if txt_path and os.path.exists(txt_path):
            with open(txt_path, "rb") as f:
                bot.send_document(
                    user_id,
                    f,
                    caption=(
                        f"📄 **ملف النصوص**\n"
                        f"📢 {archive.get('chat_title', '')}\n"
                        f"💬 {format_number(len(messages_list))} رسالة"
                    ),
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                user_id,
                "❌ لا توجد نصوص للتصدير"
            )

    async def _export_zip(
            bot, user_id, archive):
        """تصدير كـ ZIP"""
        wait_msg = bot.send_message(
            user_id,
            "⏳ جاري إنشاء ملف ZIP..."
        )

        zip_path = await download_manager.create_archive_zip(
            owner_id   = user_id,
            chat_id    = archive["chat_id"],
            archive_id = archive["id"],
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if zip_path and os.path.exists(zip_path):
            zip_size = os.path.getsize(zip_path)

            if zip_size < 50 * 1024 * 1024:
                with open(zip_path, "rb") as f:
                    bot.send_document(
                        user_id,
                        f,
                        caption=(
                            f"📦 **ملف الأرشيف**\n"
                            f"📢 {archive.get('chat_title', '')}\n"
                            f"💾 {format_size(zip_size)}"
                        ),
                        parse_mode="Markdown"
                    )
            else:
                bot.send_message(
                    user_id,
                    f"✅ تم إنشاء الملف\n"
                    f"📍 المسار: `{zip_path}`\n"
                    f"💾 الحجم: `{format_size(zip_size)}`\n\n"
                    f"⚠️ الملف كبير للإرسال المباشر",
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                user_id,
                "❌ لا توجد ملفات للتصدير"
            )

    async def _smart_extract(
            bot, user_id, archive_id,
            archive, db):
        """استخراج ذكي"""
        from utils.keyboards import confirm_keyboard

        bot.send_message(
            user_id,
            "💡 **الاستخراج الذكي**\n\n"
            "ماذا تريد استخراج؟",
            reply_markup=_extract_type_keyboard(
                archive_id
            ),
            parse_mode="Markdown"
        )

    async def _analyze_ai(
            bot, user_id, archive_id,
            archive, db):
        """تحليل AI"""
        from services.ai_service import ai_service

        wait_msg = bot.send_message(
            user_id,
            "🤖 جاري التحليل بالذكاء الاصطناعي..."
        )

        messages = await db.get_archive_messages(
            archive_id   = archive_id,
            message_type = "text",
            limit        = 50,
        )

        if not messages:
            try:
                bot.delete_message(
                    user_id, wait_msg.message_id
                )
            except Exception:
                pass
            bot.send_message(
                user_id,
                "❌ لا توجد نصوص للتحليل"
            )
            return

        stats = {
            "total_messages": len(messages),
            "chat_title":     archive.get("chat_title"),
        }

        report = await ai_service.generate_report(
            stats     = stats,
            chat_name = archive.get("chat_title", ""),
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        bot.send_message(
            user_id,
            f"🤖 **تقرير الذكاء الاصطناعي**\n\n"
            f"{report or 'لم يتم توليد التقرير'}",
            reply_markup=archive_keyboard(archive_id),
            parse_mode="Markdown"
        )

    async def _show_content(
            bot, user_id, archive_id,
            content_type, db):
        """عرض محتوى أرشيف"""
        messages = await db.get_archive_messages(
            archive_id   = archive_id,
            message_type = content_type,
            limit        = 20,
        )

        if not messages:
            bot.send_message(
                user_id,
                "❌ لا يوجد محتوى من هذا النوع"
            )
            return

        content_names = {
            "text":   "📝 النصوص",
            "photos": "🖼️ الصور",
            "videos": "🎥 الفيديوهات",
            "files":  "📁 الملفات",
            "audio":  "🎵 الصوتيات",
        }

        content_name = content_names.get(
            content_type, content_type
        )

        msg_text = (
            f"{content_name}\n"
            f"**{len(messages)} رسالة**\n\n"
        )

        for i, msg in enumerate(messages[:10], 1):
            text = msg["text"] or ""
            if content_type == "text":
                preview = (
                    text[:100] + "..."
                    if len(text) > 100
                    else text
                )
                msg_text += f"{i}. {preview}\n\n"
            else:
                file_name = msg["file_name"] or "ملف"
                file_size = format_size(
                    msg["file_size"] or 0
                )
                msg_text += (
                    f"{i}. `{file_name}` "
                    f"({file_size})\n"
                )

        bot.send_message(
            user_id,
            msg_text,
            reply_markup=archive_keyboard(archive_id),
            parse_mode="Markdown"
        )

    def _extract_type_keyboard(archive_id: int):
        """أزرار نوع الاستخراج"""
        from telebot.types import (
            InlineKeyboardMarkup,
            InlineKeyboardButton,
        )
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton(
                "💳 أرقام البطاقات",
                callback_data=f"extract_cards_{archive_id}"
            ),
            InlineKeyboardButton(
                "📱 أرقام الهواتف",
                callback_data=f"extract_phones_{archive_id}"
            ),
        )
        markup.row(
            InlineKeyboardButton(
                "📧 الإيميلات",
                callback_data=f"extract_emails_{archive_id}"
            ),
            InlineKeyboardButton(
                "🔗 الروابط",
                callback_data=f"extract_urls_{archive_id}"
            ),
        )
        markup.row(
            InlineKeyboardButton(
                "📦 استخراج الكل",
                callback_data=f"extract_all_{archive_id}"
            ),
        )
        markup.row(
            InlineKeyboardButton(
                "🔙 رجوع",
                callback_data=f"view_archive_{archive_id}"
            ),
        )
        return markup

    # ==================== استخراج ذكي ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("extract_")
    )
    def extract_callback(call: CallbackQuery):
        asyncio.run(_extract_data(bot, call))

    async def _extract_data(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        parts        = call.data.split("_")
        extract_type = parts[1]
        archive_id   = int(parts[2])

        archive = await db.get_archive(archive_id)
        if not archive:
            bot.send_message(
                user_id, "❌ الأرشيف غير موجود"
            )
            return

        wait_msg = bot.send_message(
            user_id,
            f"⏳ جاري الاستخراج الذكي..."
        )

        messages = await db.get_archive_messages(
            archive_id=archive_id,
            limit=9999,
        )

        messages_list = [dict(m) for m in messages]

        txt_path = await download_manager.extract_and_export(
            owner_id     = user_id,
            archive_id   = archive_id,
            chat_title   = archive["chat_title"],
            messages     = messages_list,
            extract_type = extract_type,
        )

        try:
            bot.delete_message(
                user_id, wait_msg.message_id
            )
        except Exception:
            pass

        if txt_path and os.path.exists(txt_path):
            with open(txt_path, "rb") as f:
                extract_names = {
                    "cards":  "💳 أرقام البطاقات",
                    "phones": "📱 أرقام الهواتف",
                    "emails": "📧 الإيميلات",
                    "urls":   "🔗 الروابط",
                    "all":    "📦 كل البيانات",
                }
                bot.send_document(
                    user_id,
                    f,
                    caption=(
                        f"💡 **الاستخراج الذكي**\n"
                        f"📢 {archive['chat_title']}\n"
                        f"📌 {extract_names.get(extract_type, extract_type)}"
                    ),
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                user_id,
                "❌ لم يتم العثور على بيانات"
            )

    # ==================== حذف الأرشيف ====================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith(
            "confirm_delete_archive_"
        )
    )
    def confirm_delete_archive_callback(
            call: CallbackQuery):
        asyncio.run(_delete_archive(bot, call))

    async def _delete_archive(
            bot: telebot.TeleBot,
            call: CallbackQuery):
        from database import db

        user_id    = call.from_user.id
        bot.answer_callback_query(call.id)
        archive_id = int(
            call.data.replace(
                "confirm_delete_archive_", ""
            )
        )

        archive = await db.get_archive(archive_id)
        if not archive:
            bot.send_message(
                user_id, "❌ الأرشيف غير موجود"
            )
            return

        # حذف الملفات
        await download_manager.delete_archive_files(
            owner_id = archive["owner_id"],
            chat_id  = archive["chat_id"],
        )

        # حذف من قاعدة البيانات
        async with db.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM messages WHERE archive_id = $1",
                archive_id
            )
            await conn.execute(
                "DELETE FROM archives WHERE id = $1",
                archive_id
            )

        bot.send_message(
            user_id,
            "✅ تم حذف الأرشيف بنجاح",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            )
        )

    # ==================== رجوع للخيارات ====================

    @bot.callback_query_handler(
        func=lambda c: c.data == "back_to_options"
    )
    def back_to_options_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        options = get_user_data(user_id, "options") or {}

        bot.send_message(
            user_id,
            "⚙️ **الخيارات الإضافية**",
            reply_markup=extra_options_keyboard(options),
            parse_mode="Markdown"
        )
   
