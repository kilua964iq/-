import logging
import colorlog
import os
from datetime import datetime
from config import config


# ==================== إعداد السجلات ====================

def setup_logger(name: str = "bot") -> logging.Logger:
    """إعداد نظام السجلات الكامل"""

    os.makedirs(config.LOG_PATH, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # تجنب تكرار الهاندلرز
    if logger.handlers:
        return logger

    # ===== هاندلر الكونسول الملون =====
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

    # ===== هاندلر ملف السجل العام =====
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    log_file = os.path.join(
        config.LOG_PATH,
        f"bot_{datetime.now().strftime('%Y_%m_%d')}.log"
    )
    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # ===== هاندلر ملف الأخطاء =====
    error_file = os.path.join(
        config.LOG_PATH,
        f"errors_{datetime.now().strftime('%Y_%m_%d')}.log"
    )
    error_handler = logging.FileHandler(
        error_file,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)

    # إضافة الهاندلرز
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger


# ==================== سجل النشاط ====================

class ActivityLogger:
    """سجل نشاط المستخدمين"""

    def __init__(self):
        self.logger = setup_logger("activity")
        self.log_file = os.path.join(
            config.LOG_PATH,
            f"activity_{datetime.now().strftime('%Y_%m_%d')}.log"
        )
        self._setup_file()

    def _setup_file(self):
        """إعداد ملف النشاط"""
        handler = logging.FileHandler(
            self.log_file,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self.logger.addHandler(handler)

    def log(self, user_id: int, action: str,
            details: str = ""):
        """تسجيل نشاط مستخدم"""
        self.logger.info(
            f"USER:{user_id} | ACTION:{action} | {details}"
        )

    def log_login(self, user_id: int, phone: str):
        self.log(user_id, "LOGIN", f"phone={phone}")

    def log_logout(self, user_id: int):
        self.log(user_id, "LOGOUT")

    def log_fetch(self, user_id: int, chat_id: int,
                  content_type: str, count: int):
        self.log(
            user_id, "FETCH",
            f"chat={chat_id} type={content_type} count={count}"
        )

    def log_archive(self, user_id: int, archive_id: int,
                    chat_name: str):
        self.log(
            user_id, "ARCHIVE",
            f"archive_id={archive_id} chat={chat_name}"
        )

    def log_ai_request(self, user_id: int,
                       request_type: str):
        self.log(
            user_id, "AI_REQUEST",
            f"type={request_type}"
        )

    def log_error(self, user_id: int, error: str):
        self.log(user_id, "ERROR", f"error={error}")

    def log_admin_action(self, admin_id: int,
                         action: str, target_id: int = None):
        details = f"target={target_id}" if target_id else ""
        self.log(admin_id, f"ADMIN_{action}", details)


# ==================== سجل الأداء ====================

class PerformanceLogger:
    """سجل أداء العمليات"""

    def __init__(self):
        self.logger = setup_logger("performance")
        self.log_file = os.path.join(
            config.LOG_PATH,
            f"performance_{datetime.now().strftime('%Y_%m_%d')}.log"
        )
        self._setup_file()

    def _setup_file(self):
        handler = logging.FileHandler(
            self.log_file,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self.logger.addHandler(handler)

    def log_operation(self, operation: str,
                      duration: float,
                      details: str = ""):
        self.logger.info(
            f"OP:{operation} | "
            f"DURATION:{duration:.2f}s | {details}"
        )

    def log_fetch_speed(self, messages: int,
                        duration: float):
        speed = messages / duration if duration > 0 else 0
        self.logger.info(
            f"FETCH_SPEED: {speed:.1f} msg/s | "
            f"total={messages} duration={duration:.2f}s"
        )

    def log_download_speed(self, size_bytes: int,
                           duration: float):
        speed = size_bytes / duration if duration > 0 else 0
        speed_mb = speed / (1024 * 1024)
        self.logger.info(
            f"DOWNLOAD_SPEED: {speed_mb:.2f} MB/s | "
            f"size={size_bytes} duration={duration:.2f}s"
        )


# ==================== سجل الأخطاء ====================

class ErrorLogger:
    """سجل الأخطاء التفصيلي"""

    def __init__(self):
        self.logger = setup_logger("errors")

    def log_exception(self, error: Exception,
                      context: str = "",
                      user_id: int = None):
        """تسجيل استثناء مع التفاصيل"""
        import traceback
        tb = traceback.format_exc()
        self.logger.error(
            f"EXCEPTION in {context} | "
            f"user={user_id} | "
            f"error={str(error)}\n{tb}"
        )

    def log_flood_wait(self, seconds: int,
                       user_id: int = None):
        self.logger.warning(
            f"FLOOD_WAIT: {seconds}s | user={user_id}"
        )

    def log_auth_error(self, user_id: int, error: str):
        self.logger.error(
            f"AUTH_ERROR: user={user_id} | {error}"
        )

    def log_download_error(self, user_id: int,
                           file_name: str, error: str):
        self.logger.error(
            f"DOWNLOAD_ERROR: user={user_id} | "
            f"file={file_name} | {error}"
        )


# ==================== Instances ====================

bot_logger = setup_logger("bot")
activity_logger = ActivityLogger()
performance_logger = PerformanceLogger()
error_logger = ErrorLogger()
