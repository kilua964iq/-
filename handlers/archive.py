import asyncio
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
)
from utils.helpers import (
    format_number,
    format_size,
    build_stats_message,
    build_fetch_progress_message,
    build_archive_summary,
    safe_edit_message,
    safe_delete_message,
    classify_message,
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
    """اختيار نوع المحتوى"""
    query   = update.callback_query
    await query.answer()

    # pattern: content_{type}
    content_type = query.data.replace("content_", "")
    context.user_data["content_type"] = content_type

    content_names = config.CONTENT_TYPES
    content_name  = content_names.get(
        content_type, content_type
    )

    await query.message.reply_text(
        f"✅ النوع المختار: **{content_name}**\n\n"
        f"🔢 **كم رسالة تريد جلبها؟**",
        reply_markup=fetch_limit_keyboard(),
        parse_mode="Markdown",
    )


# ==================== اختيار الحد ====================

async def fetch_limit_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """اختيار حد الجلب"""
    query = update.callback_query
    await query.answer()

    # pattern: limit_{number}
    limit = int(query.data.replace("limit_", ""))
    context.user_data["fetch_limit"] = limit

    content_type = context.user_data.get(
        "content_type", "all"
    )
    content_name = config.CONTENT_TYPES.get(
        content_type, content_type
    )

    limit_text = (
        f"آخر {format_number(limit)}"
        if limit > 0 else "كل المحتوى"
    )

    chat = context.user_data.get("selected_chat", {})

    await query.message.reply_text(
        f"✅ **ملخص الاختيارات**\n\n"
        f"📢 القناة:   `{chat.get('title', '')}`\n"
        f"📌 النوع:    `{content_name}`\n"
        f"🔢 الكمية:   `{limit_text}`\n\n"
        f"⚙️ **خيارات إضافية؟**",
        reply_markup=extra_options_keyboard(),
        parse_mode="Markdown",
    )


# ==================== الخيارات الإضافية ====================

async def toggle_option_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """تفعيل/إيقاف خيار"""
    query  = update.callback_query
    await query.answer()

    option  = query.data.replace("opt_", "")
    options = context.user_data.get("options", {})

    # تبديل الخيار
    options[option] = not options.get(option, False)
    context.user_data["options"] = options

    status = "✅" if options[option] else "❌"

    option_names = {
        "ai_summary":    "تلخيص AI",
        "ai_category":   "تصنيف AI",
        "voice_to_text": "تحويل صوت لنص",
        "no_duplicate":  "تجنب التكرار",
        "date_filter":   "تصفية بالتاريخ",
        "keyword_filter": "تصفية بكلمة",
    }

    name = option_names.get(option, option)
    await query.answer(
        f"{status} {name}",
        show_alert=False
    )


async def start_fetch_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية الجلب"""
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    chat         = context.user_data.get("selected_chat", {})
    content_type = context.user_data.get("content_type", "all")
    limit        = context.user_data.get("fetch_limit", 100)
    options      = context.user_data.get("options", {})

    if not chat:
        await query.message.reply_text(
            "❌ لم يتم اختيار قناة\n"
            "ابدأ من جديد"
        )
        return

    content_name = config.CONTENT_TYPES.get(
        content_type, content_type
    )
    limit_text = (
        f"آخر {format_number(limit)}"
        if limit > 0 else "كل المحتوى"
    )

    # عرض ملخص نهائي
    options_text = ""
    if options.get("ai_summary"):
        options_text += "🤖 تلخيص AI\n"
    if options.get("ai_category"):
        options_text += "🏷️ تصنيف AI\n"
    if options.get("voice_to_text"):
        options_text += "🎙️ تحويل صوت لنص\n"
    if options.get("no_duplicate"):
        options_text += "🔍 تجنب التكرار\n"

    stats = {
        "text": 0, "photos": 0,
        "videos": 0, "files": 0,
    }

    await query.message.reply_text(
        f"📋 **تأكيد الجلب**\n\n"
        f"📢 القناة:  `{chat.get('title', '')}`\n"
        f"📌 النوع:   `{content_name}`\n"
        f"🔢 الكمية:  `{limit_text}`\n"
        f"{options_text}\n"
        f"هل تريد البدء؟",
        reply_markup=confirm_fetch_keyboard(stats),
        parse_mode="Markdown",
    )


# ==================== تأكيد الجلب ====================

async def confirm_save_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """تأكيد وبدء الجلب"""
    from database import db

    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    chat         = context.user_data.get("selected_chat", {})
    content_type = context.user_data.get("content_type", "all")
    limit        = context.user_data.get("fetch_limit", 100)
    options      = context.user_data.get("options", {})

    # إنشاء أرشيف في قاعدة البيانات
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
    progress_msg = await query.message.reply_text(
        f"🚀 **بدأ الجلب...**\n\n"
        f"📢 {chat.get('title', '')}\n\n"
        f"⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\n"
        f"`0` رسالة",
        parse_mode="Markdown",
    )

    context.user_data["progress_msg"]  = progress_msg
    context.user_data["archive_id"]    = archive_id
    context.user_data["is_cancelled"]  = False

    # إضافة للطابور
    task = await queue_service.add_task(
        owner_id  = user_id,
        task_type = "fetch",
        coroutine = _fetch_and_save(
            user_id      = user_id,
            archive_id   = archive_id,
            chat         = chat,
            content_type = content_type,
            limit        = limit,
            options      = options,
            progress_msg = progress_msg,
            context      = context,
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

    bot_logger.info(
        f"▶️ بدأ الجلب للمستخدم {user_id} "
        f"archive={archive_id}"
    )


# ==================== عملية الجلب الرئيسية ====================

async def _fetch_and_save(
        user_id: int,
        archive_id: int,
        chat: dict,
        content_type: str,
        limit: int,
        options: dict,
        progress_msg,
        context: ContextTypes.DEFAULT_TYPE):
    """عملية الجلب والحفظ الكاملة"""
    from database import db
    from services.ai_service import ai_service

    chat_id    = chat.get("id")
    chat_title = chat.get("title", "")
    entity     = chat.get("entity")

    stats = {
        "text":     0,
        "photos":   0,
        "videos":   0,
        "files":    0,
        "audio":    0,
        "voice":    0,
        "stickers": 0,
        "total":    0,
        "failed":   0,
        "total_size": 0,
    }

    last_update  = datetime.now()
    update_interval = 5  # تحديث كل 5 ثوانٍ

    try:
        await db.update_archive(
            archive_id,
            status = "running"
        )

        # جلب الرسائل
        async for msg_data in telegram_service.fetch_messages(
            user_id      = user_id,
            entity       = entity,
            content_type = content_type,
            limit        = limit,
        ):
            # التحقق من الإلغاء
            if context.user_data.get("is_cancelled"):
                break

            message  = msg_data["message"]
            msg_type = msg_data["type"]
            stats    = msg_data["stats"]

            file_path = None
            file_size = 0
            file_name = None

            # تحميل الملف إذا كان ميديا
            if (message.media and
                    msg_type != "text" and
                    msg_type != "stickers"):
                try:
                    file_path = await telegram_service.download_media(
                        user_id  = user_id,
                        message  = message,
                        msg_type = msg_type,
                        chat_id  = chat_id,
                    )
                    if file_path:
                        import os
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
                    from services.ai_service import ai_service
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
                    cat_result = await ai_service.categorize_text(
                        message.text
                    )
                    if cat_result:
                        ai_category = cat_result.get(
                            "category"
                        )
                except Exception as e:
                    error_logger.log_exception(
                        e, "categorize", user_id
                    )

            # حفظ في قاعدة البيانات
            sender_name = None
            sender_id   = None
            if message.sender:
                sender_id   = message.sender_id
                sender      = message.sender
                sender_name = (
                    getattr(sender, "first_name", "") or
                    getattr(sender, "title", "") or
                    ""
                )

            await db.save_message(
                archive_id  = archive_id,
                owner_id    = user_id,
                chat_id     = chat_id,
                message_id  = message.id,
                message_type = msg_type,
                text        = message.text or "",
                file_path   = file_path,
                file_size   = file_size,
                file_name   = file_name,
                date        = message.date,
                sender_id   = sender_id,
                sender_name = sender_name,
                views       = getattr(message, "views", 0) or 0,
                forwards    = getattr(message, "forwards", 0) or 0,
                ai_summary  = ai_summary,
                ai_category = ai_category,
            )

            # تحديث التقدم
            now = datetime.now()
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
                        parse_mode = "Markdown",
                    )
                except Exception:
                    pass

        # اكتملت العملية
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

        # رسالة النهاية
        await _send_completion_message(
            progress_msg = progress_msg,
            chat_title   = chat_title,
            archive_id   = archive_id,
            stats        = stats,
            is_cancelled = is_cancelled,
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
            status = "failed",
        )
        try:
            await progress_msg.edit_text(
                f"❌ **فشل الجلب**\n\n"
                f"خطأ: `{str(e)[:200]}`",
                parse_mode = "Markdown",
            )
        except Exception:
            pass


async def _send_completion_message(
        progress_msg,
        chat_title: str,
        archive_id: int,
        stats: dict,
        is_cancelled: bool = False):
    """إرسال رسالة اكتمال الجلب"""

    if is_cancelled:
        status_text = "⚠️ **تم إيقاف الجلب**"
    else:
        status_text = "✅ **اكتمل الجلب بنجاح!**"

    msg = (
        f"{status_text}\n\n"
        f"📢 القناة: `{chat_title}`\n\n"
        f"{build_stats_message(stats)}"
    )

    try:
        await progress_msg.edit_text(
            msg,
            reply_markup = archive_keyboard(archive_id),
            parse_mode   = "Markdown",
        )
    except Exception:
        try:
            await progress_msg.reply_text(
                msg,
                reply_markup = archive_keyboard(archive_id),
                parse_mode   = "Markdown",
            )
        except Exception:
            pass


# ==================== إيقاف الجلب ====================

async def cancel_fetch_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """إيقاف عملية الجلب"""
    query = update.callback_query
    await query.answer("⚠️ جاري الإيقاف...")

    context.user_data["is_cancelled"] = True

    task_id = context.user_data.get("current_task_id")
    if task_id:
        await queue_service.cancel_task(task_id)

    await query.message.reply_text(
        "⚠️ **تم طلب الإيقاف**\n\n"
        "سيتوقف الجلب بعد الرسالة الحالية",
        parse_mode = "Markdown",
    )


# ==================== عرض الأرشيفات ====================

async def show_archives_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الأرشيفات"""
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
            reply_markup = main_menu_keyboard(
                is_logged_in=True
            ),
            parse_mode = "Markdown",
        )
        return

    archives_list = [dict(a) for a in archives]
    context.user_data["archives_list"] = archives_list

    await query.message.reply_text(
        f"📦 **أرشيفاتك** ({len(archives_list)})\n\n"
        f"اختر أرشيف لعرض تفاصيله 👇",
        reply_markup = archives_list_keyboard(
            archives_list, page=0
        ),
        parse_mode = "Markdown",
    )


async def archives_page_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """التنقل بين صفحات الأرشيفات"""
    query = update.callback_query
    await query.answer()

    page = int(query.data.replace("archives_page_", ""))
    archives_list = context.user_data.get(
        "archives_list", []
    )

    await safe_edit_message(
        query.message,
        f"📦 **أرشيفاتك** ({len(archives_list)})\n\n"
        f"اختر أرشيف 👇",
        reply_markup = archives_list_keyboard(
            archives_list, page=page
        ),
        parse_mode = "Markdown",
    )


async def view_archive_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل أرشيف"""
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

    archive_dict = dict(archive)

    # إحصائيات الأرشيف
    msg_count = await db.count_messages(
        archive_id=archive_id
    )

    storage = download_manager.get_user_storage(
        archive_dict["owner_id"]
    )

    summary = build_archive_summary(archive_dict)
    summary += (
        f"💬 الرسائل المحفوظة: `{format_number(msg_count)}`\n"
    )

    await query.message.reply_text(
        summary,
        reply_markup = archive_keyboard(archive_id),
        parse_mode   = "Markdown",
    )


# ==================== عمليات الأرشيف ====================

async def archive_action_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """عمليات على الأرشيف"""
    from database import db

    query  = update.callback_query
    await query.answer()

    # pattern: arch_{action}_{archive_id}
    parts      = query.data.split("_")
    action     = parts[1]
    archive_id = int(parts[2])

    archive = await db.get_archive(archive_id)
    if not archive:
        await query.message.reply_text(
            "❌ الأرشيف غير موجود"
        )
        return

    archive_dict = dict(archive)

    if action == "stats":
        await _show_archive_stats(
            query, archive_id, archive_dict
        )

    elif action == "export":
        await _export_archive(
            query, archive_dict
        )

    elif action == "delete":
        await _confirm_delete_archive(
            query, archive_id
        )

    elif action == "ai":
        await _analyze_archive_ai(
            query, archive_id, archive_dict
        )

    elif action in [
        "text", "photos", "videos",
        "files", "audio"
    ]:
        await _show_archive_content(
            query, archive_id, action, db
        )


async def _show_archive_stats(
        query,
        archive_id: int,
        archive: dict):
    """عرض إحصائيات أرشيف"""
    from database import db

    messages = await db.get_archive_messages(
        archive_id = archive_id,
        limit      = 9999,
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
        reply_markup = archive_keyboard(archive_id),
        parse_mode   = "Markdown",
    )


async def _export_archive(query, archive: dict):
    """تصدير أرشيف كـ ZIP"""
    user_id    = archive["owner_id"]
    chat_id    = archive["chat_id"]
    archive_id = archive["id"]

    wait_msg = await query.message.reply_text(
        "⏳ جاري إنشاء ملف ZIP..."
    )

    zip_path = await download_manager.create_archive_zip(
        owner_id   = user_id,
        chat_id    = chat_id,
        archive_id = archive_id,
    )

    await safe_delete_message(wait_msg)

    if zip_path:
        import os
        zip_size = os.path.getsize(zip_path)

        if zip_size < 50 * 1024 * 1024:  # أقل من 50MB
            with open(zip_path, "rb") as f:
                await query.message.reply_document(
                    document = f,
                    caption  = (
                        f"📦 أرشيف: "
                        f"{archive.get('chat_title', '')}\n"
                        f"💾 الحجم: {format_size(zip_size)}"
                    ),
                )
        else:
            await query.message.reply_text(
                f"✅ تم إنشاء الملف\n"
                f"📍 المسار: `{zip_path}`\n"
                f"💾 الحجم: `{format_size(zip_size)}`\n\n"
                f"⚠️ الملف كبير جداً للإرسال المباشر",
                parse_mode = "Markdown",
            )
    else:
        await query.message.reply_text(
            "❌ لا توجد ملفات للتصدير"
        )


async def _confirm_delete_archive(
        query, archive_id: int):
    """تأكيد حذف أرشيف"""
    from utils.keyboards import confirm_keyboard

    await query.message.reply_text(
        "⚠️ **هل تريد حذف هذا الأرشيف؟**\n\n"
        "سيتم حذف كل الملفات والبيانات\n"
        "هذا الإجراء لا يمكن التراجع عنه!",
        reply_markup = confirm_keyboard(
            f"delete_archive_{archive_id}"
        ),
        parse_mode = "Markdown",
    )


async def confirm_delete_archive_callback(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ حذف الأرشيف"""
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

    # حذف الملفات
    await download_manager.delete_archive_files(
        owner_id = archive["owner_id"],
        chat_id  = archive["chat_id"],
    )

    # حذف من قاعدة البيانات
    async with (await __import__(
        "database", fromlist=["db"]
    ).db.pool.acquire()) as conn:
        await conn.execute(
            "DELETE FROM messages WHERE archive_id = $1",
            archive_id
        )
        await conn.execute(
            "DELETE FROM archives WHERE id = $1",
            archive_id
        )

    await query.message.reply_text(
        "✅ تم حذف الأرشيف بنجاح",
        reply_markup = main_menu_keyboard(
            is_logged_in=True
        ),
    )


async def _analyze_archive_ai(
        query,
        archive_id: int,
        archive: dict):
    """تحليل أرشيف بالذكاء الاصطناعي"""
    from database import db
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
        await safe_delete_message(wait_msg)
        await query.message.reply_text(
            "❌ لا توجد نصوص للتحليل"
        )
        return

    texts = [
        m["text"] for m in messages
        if m["text"]
    ]
    combined = "\n\n".join(texts[:20])

    stats = {
        "total_messages": len(messages),
        "chat_title":     archive.get("chat_title"),
    }

    report = await ai_service.generate_report(
        stats     = stats,
        chat_name = archive.get("chat_title", ""),
    )

    await safe_delete_message(wait_msg)

    await query.message.reply_text(
        f"🤖 **تقرير الذكاء الاصطناعي**\n\n"
        f"{report or 'لم يتم توليد التقرير'}",

        reply_markup = archive_keyboard(archive_id),
        parse_mode   = "Markdown",
    )


async def _show_archive_content(
        query,
        archive_id: int,
        content_type: str,
        db):
    """عرض محتوى أرشيف حسب النوع"""

    messages = await db.get_archive_messages(
        archive_id   = archive_id,
        message_type = content_type,
        limit        = 20,
    )

    if not messages:
        await query.message.reply_text(
            f"❌ لا يوجد محتوى من هذا النوع"
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
        date = msg["date"]
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
        reply_markup = archive_keyboard(archive_id),
        parse_mode   = "Markdown",
    )


# ==================== تسجيل الهاندلرز ====================

def register_archive_handlers(app):
    """تسجيل كل هاندلرز الأرشيف"""

    # اختيار المحتوى
    app.add_handler(CallbackQueryHandler(
        content_type_callback,
        pattern = "^content_"
    ))

    # حد الجلب
    app.add_handler(CallbackQueryHandler(
        fetch_limit_callback,
        pattern = "^limit_"
    ))

    # الخيارات الإضافية
    app.add_handler(CallbackQueryHandler(
        toggle_option_callback,
        pattern = "^opt_"
    ))

    # بدء الجلب
    app.add_handler(CallbackQueryHandler(
        start_fetch_callback,
        pattern = "^start_fetch$"
    ))

    # تأكيد الحفظ
    app.add_handler(CallbackQueryHandler(
        confirm_save_callback,
        pattern = "^confirm_save$"
    ))

    # إلغاء الجلب
    app.add_handler(CallbackQueryHandler(
        cancel_fetch_callback,
        pattern = "^cancel_fetch$"
    ))

    # عرض الأرشيفات
    app.add_handler(CallbackQueryHandler(
        show_archives_callback,
        pattern = "^show_archives$"
    ))

    # صفحات الأرشيفات
    app.add_handler(CallbackQueryHandler(
        archives_page_callback,
        pattern = "^archives_page_"
    ))

    # عرض أرشيف
    app.add_handler(CallbackQueryHandler(
        view_archive_callback,
        pattern = "^view_archive_"
    ))

    # عمليات الأرشيف
    app.add_handler(CallbackQueryHandler(
        archive_action_callback,
        pattern = "^arch_"
    ))

    # تأكيد الحذف
    app.add_handler(CallbackQueryHandler(
        confirm_delete_archive_callback,
        pattern = "^confirm_delete_archive_"
    ))

    # الرجوع لخيارات الجلب
    app.add_handler(CallbackQueryHandler(
        start_fetch_callback,
        pattern = "^back_to_options$"
    ))
