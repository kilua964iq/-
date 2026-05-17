import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
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
    confirm_keyboard,
)
from utils.helpers import (
    format_number,
    format_size,
    format_date,
    build_stats_message,
    build_fetch_progress_message,
    build_progress_bar,
    classify_message,
    smart_extract,
    format_extracted_data,
    clean_text,
)
from utils.logger import (
    bot_logger,
    activity_logger,
    error_logger,
)


# ==================== اختيار المحتوى ====================

async def content_type_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query        = update.callback_query
    await query.answer()
    content_type = query.data.replace("content_", "")

    context.user_data["content_type"] = content_type

    content_name = config.CONTENT_TYPES.get(
        content_type, content_type
    )

    await query.message.reply_text(
        f"✅ النوع المختار: **{content_name}**\n\n"
        f"🔢 **كم رسالة تريد جلبها؟**",
        reply_markup=fetch_limit_keyboard(),
        parse_mode="Markdown"
    )


# ==================== اختيار الحد ====================

async def fetch_limit_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    limit = int(query.data.replace("limit_", ""))
    context.user_data["fetch_limit"] = limit

    content_type = context.user_data.get(
        "content_type", "all"
    )
    content_name = config.CONTENT_TYPES.get(
        content_type, content_type
    )
    chat    = context.user_data.get("selected_chat", {})
    options = context.user_data.get("options", {})

    limit_text = (
        f"آخر {format_number(limit)}"
        if limit > 0 else "كل المحتوى"
    )

    await query.message.reply_text(
        f"✅ **ملخص الاختيارات**\n\n"
        f"📢 القناة:  `{chat.get('title', '')}`\n"
        f"📌 النوع:   `{content_name}`\n"
        f"🔢 الكمية:  `{limit_text}`\n\n"
        f"⚙️ **خيارات إضافية؟**",
        reply_markup=extra_options_keyboard(options),
        parse_mode="Markdown"
    )


# ==================== الخيارات الإضافية ====================

async def toggle_option_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    option  = query.data.replace("opt_", "")
    options = context.user_data.get("options", {})

    options[option] = not options.get(option, False)
    context.user_data["options"] = options

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

    await query.answer(
        f"{status} {name}",
        show_alert=False
    )

    try:
        await query.edit_message_reply_markup(
            reply_markup=extra_options_keyboard(options)
        )
    except Exception:
        pass


# ==================== بدء الجلب ====================

async def start_fetch_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    chat         = context.user_data.get("selected_chat", {})
    content_type = context.user_data.get("content_type", "all")
    limit        = context.user_data.get("fetch_limit", 100)
    options      = context.user_data.get("options", {})

    if not chat:
        await query.message.reply_text(
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

    await query.message.reply_text(
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

async def confirm_save_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    chat         = context.user_data.get("selected_chat", {})
    content_type = context.user_data.get("content_type", "all")
    limit        = context.user_data.get("fetch_limit", 100)
    options      = context.user_data.get("options", {})

    if not chat:
        await query.message.reply_text(
            "❌ لم يتم اختيار قناة"
        )
        return

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

    progress_msg = await query.message.reply_text(
        f"🚀 **بدأ الجلب...**\n\n"
        f"📢 {chat.get('title', '')}\n\n"
        f"⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\n"
        f"`0` رسالة",
        parse_mode="Markdown"
    )

    context.user_data["progress_msg_id"] = (
        progress_msg.message_id
    )
    context.user_data["archive_id"]   = archive_id
    context.user_data["is_cancelled"] = False

    task = await queue_service.add_task(
        owner_id  = user_id,
        task_type = "fetch",
        coroutine = _fetch_and_save(
            context      = context,
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

    context.user_data["current_task_id"] = task.task_id


# ==================== عملية الجلب ====================

async def _fetch_and_save(
        context,
        user_id: int,
        archive_id: int,
        chat: dict,
        content_type: str,
        limit: int,
        options: dict,
        progress_msg):
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
    seen_texts      = set()

    try:
        await db.update_archive(
            archive_id, status="running"
        )

        async for msg_data in telegram_service.fetch_messages(
            user_id      = user_id,
            entity       = entity,
            content_type = content_type,
            limit        = limit,
        ):
            if context.user_data.get("is_cancelled"):
                break

            message  = msg_data["message"]
            msg_type = msg_data["type"]
            stats    = msg_data["stats"]

            if options.get("no_duplicate") and message.text:
                if message.text in seen_texts:
                    continue
                seen_texts.add(message.text)

            file_path = None
            file_size = 0
            file_name = None

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
                        file_size = os.path.getsize(file_path)
                        file_name = os.path.basename(file_path)
                        stats["total_size"] += file_size
                except Exception as e:
                    stats["failed"] += 1
                    error_logger.log_exception(
                        e, "download_media", user_id
                    )

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

            if (options.get("ai_category") and
                    message.text):
                try:
                    cat = await ai_service.categorize_text(
                        message.text
                    )
                    if cat:
                        ai_category = cat.get("category")
                except Exception as e:
                    error_logger.log_exception(
                        e, "categorize", user_id
                    )

            if message.text:
                all_texts.append({
                    "text": message.text,
                    "date": str(message.date),
                    "id":   message.id,
                })

            sender_name = None
            sender_id   = None
            if message.sender:
                sender_id   = message.sender_id
                sender      = message.sender
                sender_name = (
                    getattr(sender, "first_name", "") or
                    getattr(sender, "title", "") or ""
                )

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

            now     = datetime.now()
            elapsed = (now - last_update).seconds

            if elapsed >= update_interval:
                last_update = now
                total       = stats["total"]
                progress    = (
                    min(int((total / limit) * 100), 99)
                    if limit > 0 else 50
                )

                await db.update_archive(
                    archive_id,
                    fetched_messages = total,
                    progress         = progress,
                )

                try:
                    await progress_msg.edit_text(
                        build_fetch_progress_message(
                            chat_title   = chat_title,
                            current      = total,
                            total        = limit,
                            content_type = content_type,
                            stats        = stats,
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

        is_cancelled = context.user_data.get(
            "is_cancelled", False
        )

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

        txt_path = None
        if options.get("save_txt") and all_texts:
            txt_path = await download_manager.export_messages_as_txt(
                owner_id      = user_id,
                archive_id    = archive_id,
                chat_title    = chat_title,
                messages      = all_texts,
                extract_smart = options.get(
                    "smart_extract", False
                ),
            )

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
            await progress_msg.edit_text(
                completion_msg,
                reply_markup = archive_keyboard(archive_id),
                parse_mode   = "Markdown"
            )
        except Exception:
            await progress_msg.reply_text(
                completion_msg,
                reply_markup = archive_keyboard(archive_id),
                parse_mode   = "Markdown"
            )

        if txt_path and os.path.exists(txt_path):
            with open(txt_path, "rb") as f:
                await progress_msg.reply_document(
                    document = f,
                    caption  = (
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
            archive_id, status="failed"
        )
        try:
            await progress_msg.edit_text(
                f"❌ **فشل الجلب**\n\n"
                f"خطأ: `{str(e)[:200]}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ==================== إيقاف الجلب ====================

async def cancel_fetch_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⚠️ جاري الإيقاف...")

    context.user_data["is_cancelled"] = True

    task_id = context.user_data.get("current_task_id")
    if task_id:
        await queue_service.cancel_task(task_id)

    await query.message.reply_text(
        "⚠️ **تم طلب الإيقاف**\n\n"
        "سيتوقف الجلب بعد الرسالة الحالية",
        parse_mode="Markdown"
    )


# ==================== عرض الأرشيفات ====================

async def show_archives_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    archives = await db.get_user_archives(
        owner_id = user_id,
        limit    = 50,
    )

    if not archives:
        await query.message.reply_text(
            "📦 **أرشيفاتك**\n\n"
            "لا توجد أرشيفات بعد\n"
            "ابدأ بجلب محتوى من قناة 👇",
            reply_markup=main_menu_keyboard(
                is_logged_in=True
            ),
            parse_mode="Markdown"
        )
        return

    context.user_data["archives_list"] = archives

    await query.message.reply_text(
        f"📦 **أرشيفاتك** ({len(archives)})\n\n"
        f"اختر أرشيف لعرض تفاصيله 👇",
        reply_markup=archives_list_keyboard(
            archives, page=0
        ),
        parse_mode="Markdown"
    )


# ==================== صفحات الأرشيفات ====================

async def archives_page_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = int(
        query.data.replace("archives_page_", "")
    )
    archives_list = context.user_data.get(
        "archives_list", []
    )

    await query.message.reply_text(
        f"📦 **أرشيفاتك** ({len(archives_list)})\n\n"
        f"اختر أرشيف 👇",
        reply_markup=archives_list_keyboard(
            archives_list, page=page
        ),
        parse_mode="Markdown"
    )


# ==================== عرض أرشيف ====================

async def view_archive_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query      = update.callback_query
    await query.answer()
    archive_id = int(
        query.data.replace("view_archive_", "")
    )

    archive = await db.get_archive(archive_id)
    if not archive:
        await query.message.reply_text(
            "❌ الأرشيف غير موجود"
        )
        return

    msg_count = await db.count_messages(
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
        archive.get("content_type", ""),
        "غير معروف"
    )

    msg = (
        f"📦 **تفاصيل الأرشيف**\n\n"
        f"📢 القناة:    `{archive.get('chat_title', '')}`\n"
        f"📌 النوع:     `{content_name}`\n"
        f"📊 الحالة:    "
        f"{status_map.get(archive.get('status', ''), '❓')}\n"
        f"💬 الرسائل:  `{format_number(msg_count)}`\n"
        f"📅 التاريخ:  "
        f"`{archive.get('started_at', '')}`\n"
    )

    await query.message.reply_text(
        msg,
        reply_markup=archive_keyboard(archive_id),
        parse_mode="Markdown"
    )


# ==================== عمليات الأرشيف ====================

async def archive_action_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query      = update.callback_query
    await query.answer()
    user_id    = update.effective_user.id

    parts      = query.data.split("_")
    action     = parts[1]
    archive_id = int(parts[2])

    archive = await db.get_archive(archive_id)
    if not archive:
        await query.message.reply_text(
            "❌ الأرشيف غير موجود"
        )
        return

    if action == "stats":
        await _show_archive_stats(
            query, archive_id, archive, db
        )

    elif action == "txt":
        await _export_txt(
            query, user_id, archive_id, archive, db
        )

    elif action == "zip":
        await _export_zip(
            query, user_id, archive
        )

    elif action == "extract":
        await query.message.reply_text(
            "💡 **الاستخراج الذكي**\n\n"
            "ماذا تريد استخراج؟",
            reply_markup=_extract_type_keyboard(archive_id),
            parse_mode="Markdown"
        )

    elif action == "ai":
        await _analyze_ai(
            query, user_id, archive_id, archive, db
        )

    elif action == "delete":
        await query.message.reply_text(
            "⚠️ **هل تريد حذف هذا الأرشيف؟**\n\n"
            "سيتم حذف كل الملفات والبيانات!\n"
            "هذا الإجراء لا يمكن التراجع عنه!",
            reply_markup=confirm_keyboard(
                f"delete_archive_{archive_id}"
            ),
            parse_mode="Markdown"
        )

    elif action in [
        "text", "photos", "videos",
        "files", "audio"
    ]:
        await _show_content(
            query, archive_id, action, db
        )


async def _show_archive_stats(
        query, archive_id, archive, db):
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

    await query.message.reply_text(
        f"📊 **إحصائيات الأرشيف**\n\n"
        f"📢 القناة: `{archive.get('chat_title', '')}`\n\n"
        f"{build_stats_message(stats)}",
        reply_markup=archive_keyboard(archive_id),
        parse_mode="Markdown"
    )


async def _export_txt(
        query, user_id, archive_id, archive, db):
    wait_msg = await query.message.reply_text(
        "⏳ جاري إنشاء ملف TXT..."
    )

    messages = await db.get_archive_messages(
        archive_id=archive_id,
        limit=9999,
    )

    txt_path = await download_manager.export_messages_as_txt(
        owner_id   = user_id,
        archive_id = archive_id,
        chat_title = archive.get("chat_title", ""),
        messages   = messages,
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if txt_path and os.path.exists(txt_path):
        with open(txt_path, "rb") as f:
            await query.message.reply_document(
                document = f,
                caption  = (
                    f"📄 **ملف النصوص**\n"
                    f"📢 {archive.get('chat_title', '')}\n"
                    f"💬 {format_number(len(messages))} رسالة"
                ),
                parse_mode="Markdown"
            )
    else:
        await query.message.reply_text(
            "❌ لا توجد نصوص للتصدير"
        )


async def _export_zip(query, user_id, archive):
    wait_msg = await query.message.reply_text(
        "⏳ جاري إنشاء ملف ZIP..."
    )

    zip_path = await download_manager.create_archive_zip(
        owner_id   = user_id,
        chat_id    = archive["chat_id"],
        archive_id = archive["id"],
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if zip_path and os.path.exists(zip_path):
        zip_size = os.path.getsize(zip_path)

        if zip_size < 50 * 1024 * 1024:
            with open(zip_path, "rb") as f:
                await query.message.reply_document(
                    document = f,
                    caption  = (
                        f"📦 **ملف الأرشيف**\n"
                        f"📢 {archive.get('chat_title', '')}\n"
                        f"💾 {format_size(zip_size)}"
                    ),
                    parse_mode="Markdown"
                )
        else:
            await query.message.reply_text(
                f"✅ تم إنشاء الملف\n"
                f"💾 الحجم: `{format_size(zip_size)}`\n\n"
                f"⚠️ الملف كبير للإرسال المباشر",
                parse_mode="Markdown"
            )
    else:
        await query.message.reply_text(
            "❌ لا توجد ملفات للتصدير"
        )


async def _analyze_ai(
        query, user_id, archive_id, archive, db):
    from services.ai_service import ai_service

    wait_msg = await query.message.reply_text(
        "🤖 جاري التحليل بالذكاء الاصطناعي..."
    )

    messages = await db.get_archive_messages(
        archive_id   = archive_id,
        message_type = "text",
        limit        = 50,
    )

    if not messages:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await query.message.reply_text(
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
        await wait_msg.delete()
    except Exception:
        pass

    await query.message.reply_text(
        f"🤖 **تقرير الذكاء الاصطناعي**\n\n"
        f"{report or 'لم يتم توليد التقرير'}",
        reply_markup=archive_keyboard(archive_id),
        parse_mode="Markdown"
    )

async def _show_content(
        query, archive_id, content_type, db):
    messages = await db.get_archive_messages(
        archive_id   = archive_id,
        message_type = content_type,
        limit        = 20,
    )

    if not messages:
        await query.message.reply_text(
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

    await query.message.reply_text(
        msg_text,
        reply_markup=archive_keyboard(archive_id),
        parse_mode="Markdown"
    )


def _extract_type_keyboard(archive_id: int):
    from telegram import (
        InlineKeyboardMarkup,
        InlineKeyboardButton,
    )
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💳 أرقام البطاقات",
                callback_data=f"extract_cards_{archive_id}"
            ),
            InlineKeyboardButton(
                "📱 أرقام الهواتف",
                callback_data=f"extract_phones_{archive_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "📧 الإيميلات",
                callback_data=f"extract_emails_{archive_id}"
            ),
            InlineKeyboardButton(
                "🔗 الروابط",
                callback_data=f"extract_urls_{archive_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "📦 استخراج الكل",
                callback_data=f"extract_all_{archive_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 رجوع",
                callback_data=f"view_archive_{archive_id}"
            ),
        ],
    ])


# ==================== استخراج ذكي ====================

async def extract_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query      = update.callback_query
    await query.answer()
    user_id    = update.effective_user.id

    parts        = query.data.split("_")
    extract_type = parts[1]
    archive_id   = int(parts[2])

    archive = await db.get_archive(archive_id)
    if not archive:
        await query.message.reply_text(
            "❌ الأرشيف غير موجود"
        )
        return

    wait_msg = await query.message.reply_text(
        "⏳ جاري الاستخراج الذكي..."
    )

    messages = await db.get_archive_messages(
        archive_id=archive_id,
        limit=9999,
    )

    txt_path = await download_manager.extract_and_export(
        owner_id     = user_id,
        archive_id   = archive_id,
        chat_title   = archive["chat_title"],
        messages     = messages,
        extract_type = extract_type,
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if txt_path and os.path.exists(txt_path):
        extract_names = {
            "cards":  "💳 أرقام البطاقات",
            "phones": "📱 أرقام الهواتف",
            "emails": "📧 الإيميلات",
            "urls":   "🔗 الروابط",
            "all":    "📦 كل البيانات",
        }
        with open(txt_path, "rb") as f:
            await query.message.reply_document(
                document = f,
                caption  = (
                    f"💡 **الاستخراج الذكي**\n"
                    f"📢 {archive['chat_title']}\n"
                    f"📌 {extract_names.get(extract_type, extract_type)}"
                ),
                parse_mode="Markdown"
            )
    else:
        await query.message.reply_text(
            "❌ لم يتم العثور على بيانات"
        )


# ==================== حذف الأرشيف ====================

async def confirm_delete_archive_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    from database import db

    query      = update.callback_query
    await query.answer()
    archive_id = int(
        query.data.replace("confirm_delete_archive_", "")
    )

    archive = await db.get_archive(archive_id)
    if not archive:
        await query.message.reply_text(
            "❌ الأرشيف غير موجود"
        )
        return

    await download_manager.delete_archive_files(
        owner_id = archive["owner_id"],
        chat_id  = archive["chat_id"],
    )

    await db.delete_archive_data(archive_id)

    await query.message.reply_text(
        "✅ تم حذف الأرشيف بنجاح",
        reply_markup=main_menu_keyboard(
            is_logged_in=True
        )
    )


# ==================== رجوع للخيارات ====================

async def back_to_options_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    options = context.user_data.get("options", {})

    await query.message.reply_text(
        "⚙️ **الخيارات الإضافية**",
        reply_markup=extra_options_keyboard(options),
        parse_mode="Markdown"
    )


# ==================== تسجيل الهاندلرز ====================

def register_archive_handlers(app):
    app.add_handler(CallbackQueryHandler(
        content_type_callback,
        pattern="^content_"
    ))
    app.add_handler(CallbackQueryHandler(
        fetch_limit_callback,
        pattern="^limit_"
    ))
    app.add_handler(CallbackQueryHandler(
        toggle_option_callback,
        pattern="^opt_"
    ))
    app.add_handler(CallbackQueryHandler(
        start_fetch_callback,
        pattern="^start_fetch$"
    ))
    app.add_handler(CallbackQueryHandler(
        confirm_save_callback,
        pattern="^confirm_save$"
    ))
    app.add_handler(CallbackQueryHandler(
        cancel_fetch_callback,
        pattern="^cancel_fetch$"
    ))
    app.add_handler(CallbackQueryHandler(
        show_archives_callback,
        pattern="^show_archives$"
    ))
    app.add_handler(CallbackQueryHandler(
        archives_page_callback,
        pattern="^archives_page_"
    ))
    app.add_handler(CallbackQueryHandler(
        view_archive_callback,
        pattern="^view_archive_"
    ))
    app.add_handler(CallbackQueryHandler(
        archive_action_callback,
        pattern="^arch_"
    ))
    app.add_handler(CallbackQueryHandler(
        extract_callback,
        pattern="^extract_"
    ))
    app.add_handler(CallbackQueryHandler(
        confirm_delete_archive_callback,
        pattern="^confirm_delete_archive_"
    ))
    app.add_handler(CallbackQueryHandler(
        back_to_options_callback,
        pattern="^back_to_options$"
    ))
