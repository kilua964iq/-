import logging
import colorlog
import os
from datetime import datetime
from config import config


def setup_logger(name: str = "bot") -> logging.Logger:
    os.makedirs(config.LOG_PATH, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # ===== كونسول ملون =====
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s]%(reset)s "
        "%(blue)s%(name)s%(reset)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "red,bg_white",
        }
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # ===== ملف السجل =====
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    log_file = os.path.join(
        config.LOG_PATH,
        f"bot_{datetime.now().strftime('%Y_%m_%d')}.log"
    )
    file_handler = logging.FileHandler(
        log_file, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # ===== ملف الأخطاء =====
    error_file = os.path.join(
        config.LOG_PATH,
        f"errors_{datetime.now().strftime('%Y_%m_%d')}.log"
    )
    error_handler = logging.FileHandler(
        error_file, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger


# ==================== سجل النشاط ====================

class ActivityLogger:
    def __init__(self):
        self.logger = setup_logger("activity")

    def log(self, user_id: int,
            action: str, details: str = ""):
        self.logger.info(
            f"USER:{user_id} | "
            f"ACTION:{action} | {details}"
        )

    def log_login(self, user_id: int, phone: str):
        self.log(user_id, "LOGIN", f"phone={phone}")

    def log_logout(self, user_id: int):
        self.log(user_id, "LOGOUT")

    def log_fetch(self, user_id: int, chat_id: int,
                  content_type: str, count: int):
        self.log(
            user_id, "FETCH",
            f"chat={chat_id} "
            f"type={content_type} "
            f"count={count}"
        )

    def log_archive(self, user_id: int,
                    archive_id: int, chat_name: str):
        self.log(
            user_id, "ARCHIVE",
            f"archive_id={archive_id} chat={chat_name}"
        )

    def log_search(self, user_id: int,
                   query: str, results: int):
        self.log(
            user_id, "SEARCH",
            f"query={query} results={results}"
        )

    def log_admin_action(self, admin_id: int,
                         action: str,
                         target_id: int = None):
        details = (
            f"target={target_id}" if target_id else ""
        )
        self.log(admin_id, f"ADMIN_{action}", details)


# ==================== سجل الأخطاء ====================

class ErrorLogger:
    def __init__(self):
        self.logger = setup_logger("errors")

    def log_exception(self, error: Exception,
                      context: str = "",
                      user_id: int = None):
        import traceback
        tb = traceback.format_exc()
        self.logger.error(
            f"EXCEPTION in {context} | "
            f"user={user_id} | "
            f"error={str(error)}\n{tb}"
        )
        print(
            f"❌ خطأ في {context}: {error}",
            flush=True
        )

    def log_flood_wait(self, seconds: int,
                       user_id: int = None):
        self.logger.warning(
            f"FLOOD_WAIT: {seconds}s | user={user_id}"
        )

    def log_download_error(self, user_id: int,
                           file_name: str, error: str):
        self.logger.error(
            f"DOWNLOAD_ERROR: user={user_id} | "
            f"file={file_name} | {error}"
        )


# ==================== Instances ====================

bot_logger       = setup_logger("bot")
activity_logger  = ActivityLogger()
error_logger     = ErrorLogger()
