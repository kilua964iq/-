import asyncio
from typing import Optional, Dict, Callable
from datetime import datetime
from enum import Enum
from config import config
from utils.logger import bot_logger, error_logger


# ==================== حالات المهمة ====================

class TaskStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    PAUSED    = "paused"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW    = 0
    NORMAL = 1
    HIGH   = 2
    URGENT = 3


# ==================== المهمة ====================

class Task:
    """تمثيل مهمة واحدة"""

    def __init__(
            self,
            task_id: int,
            owner_id: int,
            task_type: str,
            coroutine,
            priority: TaskPriority = TaskPriority.NORMAL,
            data: dict = None):

        self.task_id    = task_id
        self.owner_id   = owner_id
        self.task_type  = task_type
        self.coroutine  = coroutine
        self.priority   = priority
        self.data       = data or {}

        self.status     = TaskStatus.PENDING
        self.progress   = 0
        self.result     = None
        self.error      = None

        self.created_at   = datetime.now()
        self.started_at   = None
        self.completed_at = None

        self._task        = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._cancel_flag = False

    def to_dict(self) -> dict:
        return {
            "task_id":      self.task_id,
            "owner_id":     self.owner_id,
            "task_type":    self.task_type,
            "status":       self.status.value,
            "priority":     self.priority.value,
            "progress":     self.progress,
            "error":        self.error,
            "created_at":   str(self.created_at),
            "started_at":   str(self.started_at),
            "completed_at": str(self.completed_at),
            "data":         self.data,
        }


# ==================== الطابور ====================

class QueueService:
    """نظام طابور المهام الكامل"""

    def __init__(self):
        self._tasks: Dict[int, Task]     = {}
        self._queue: asyncio.PriorityQueue = (
            asyncio.PriorityQueue()
        )
        self._workers: list              = []
        self._running                    = False
        self._callbacks: Dict[str, list] = {
            "on_start":    [],
            "on_progress": [],
            "on_complete": [],
            "on_error":    [],
            "on_cancel":   [],
        }
        self._task_counter = 0

    # ==================== تشغيل الطابور ====================

    async def start(
            self,
            num_workers: int = None):
        """تشغيل الطابور"""
        if self._running:
            return

        self._running = True
        num_workers = num_workers or config.MAX_CONCURRENT_TASKS

        for i in range(num_workers):
            worker = asyncio.create_task(
                self._worker(f"worker_{i}")
            )
            self._workers.append(worker)

        bot_logger.info(
            f"✅ تم تشغيل الطابور بـ {num_workers} عمال"
        )

    async def stop(self):
        """إيقاف الطابور"""
        self._running = False

        for worker in self._workers:
            worker.cancel()

        self._workers.clear()
        bot_logger.info("⛔ تم إيقاف الطابور")

    async def _worker(self, worker_name: str):
        """عامل معالجة المهام"""
        bot_logger.debug(f"🔄 {worker_name} جاهز")

        while self._running:
            try:
                # جلب مهمة من الطابور
                priority, task_id = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )

                task = self._tasks.get(task_id)
                if not task:
                    continue

                if task.status == TaskStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                await self._execute_task(task, worker_name)
                self._queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                error_logger.log_exception(
                    e, f"worker_{worker_name}"
                )

    async def _execute_task(
            self,
            task: Task,
            worker_name: str):
        """تنفيذ مهمة"""
        task.status     = TaskStatus.RUNNING
        task.started_at = datetime.now()

        bot_logger.info(
            f"▶️ {worker_name} يعالج مهمة "
            f"{task.task_id} ({task.task_type})"
        )

        await self._trigger_callback("on_start", task)

        try:
            result = await task.coroutine

            if task._cancel_flag:
                task.status = TaskStatus.CANCELLED
                await self._trigger_callback(
                    "on_cancel", task
                )
            else:
                task.status       = TaskStatus.COMPLETED
                task.result       = result
                task.progress     = 100
                task.completed_at = datetime.now()

                bot_logger.info(
                    f"✅ مهمة {task.task_id} مكتملة"
                )
                await self._trigger_callback(
                    "on_complete", task
                )

        except asyncio.CancelledError:
            task.status       = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            await self._trigger_callback("on_cancel", task)

        except Exception as e:
            task.status       = TaskStatus.FAILED
            task.error        = str(e)
            task.completed_at = datetime.now()

            error_logger.log_exception(
                e, f"task_{task.task_id}"
            )
            await self._trigger_callback("on_error", task)

    # ==================== إدارة المهام ====================

    async def add_task(
            self,
            owner_id: int,
            task_type: str,
            coroutine,
            priority: TaskPriority = TaskPriority.NORMAL,
            data: dict = None) -> Task:
        """إضافة مهمة للطابور"""

        self._task_counter += 1
        task = Task(
            task_id   = self._task_counter,
            owner_id  = owner_id,
            task_type = task_type,
            coroutine = coroutine,
            priority  = priority,
            data      = data or {},
        )

        self._tasks[task.task_id] = task

        # الأولوية معكوسة (أصغر = أعلى)
        await self._queue.put(
            (-priority.value, task.task_id)
        )

        bot_logger.info(
            f"➕ مهمة جديدة {task.task_id} "
            f"({task_type}) للمستخدم {owner_id}"
        )

        return task

    async def cancel_task(
            self, task_id: int) -> bool:
        """إلغاء مهمة"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.RUNNING:
            task._cancel_flag = True
            if task._task:
                task._task.cancel()
        else:
            task.status = TaskStatus.CANCELLED

        bot_logger.info(f"❌ تم إلغاء مهمة {task_id}")
        return True

    async def pause_task(
            self, task_id: int) -> bool:
        """إيقاف مهمة مؤقتاً"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.PAUSED
            task._pause_event.clear()
            bot_logger.info(
                f"⏸️ تم إيقاف مهمة {task_id} مؤقتاً"
            )
            return True

        return False

    async def resume_task(
            self, task_id: int) -> bool:
        """استكمال مهمة موقوفة"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.PAUSED:
            task.status = TaskStatus.RUNNING
            task._pause_event.set()
            bot_logger.info(
                f"▶️ تم استكمال مهمة {task_id}"
            )
            return True

        return False

    async def retry_task(
            self, task_id: int) -> bool:
        """إعادة محاولة مهمة فاشلة"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.FAILED:
            task.status   = TaskStatus.PENDING
            task.error    = None
            task.progress = 0

            await self._queue.put(
                (-task.priority.value, task.task_id)
            )

            bot_logger.info(
                f"🔄 إعادة محاولة مهمة {task_id}"
            )
            return True

        return False

    def update_progress(
            self,
            task_id: int,
            progress: int):
        """تحديث تقدم مهمة"""
        task = self._tasks.get(task_id)
        if task:
            task.progress = min(max(progress, 0), 100)

    # ==================== استعلامات ====================

    def get_task(
            self, task_id: int) -> Optional[Task]:
        """جلب مهمة"""
        return self._tasks.get(task_id)

    def get_user_tasks(
            self,
            owner_id: int,
            status: TaskStatus = None) -> list:
        """جلب مهام مستخدم"""
        tasks = [
            t for t in self._tasks.values()
            if t.owner_id == owner_id
        ]
        if status:
            tasks = [
                t for t in tasks
                if t.status == status
            ]
        return sorted(
            tasks,
            key=lambda x: x.created_at,
            reverse=True
        )

    def get_active_tasks(
            self,
            owner_id: int = None) -> list:
        """جلب المهام النشطة"""
        active_statuses = [
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
        ]
        tasks = [
            t for t in self._tasks.values()
            if t.status in active_statuses
        ]
        if owner_id:
            tasks = [
                t for t in tasks
                if t.owner_id == owner_id
            ]
        return tasks

    def get_queue_stats(self) -> dict:
        """إحصائيات الطابور"""
        all_tasks = list(self._tasks.values())
        return {
            "total":     len(all_tasks),
            "pending":   sum(
                1 for t in all_tasks
                if t.status == TaskStatus.PENDING
            ),
            "running":   sum(
                1 for t in all_tasks
                if t.status == TaskStatus.RUNNING
            ),
            "paused":    sum(
                1 for t in all_tasks
                if t.status == TaskStatus.PAUSED
            ),
            "completed": sum(
                1 for t in all_tasks
                if t.status == TaskStatus.COMPLETED
            ),
            "failed":    sum(
                1 for t in all_tasks
                if t.status == TaskStatus.FAILED
            ),
            "cancelled": sum(
                1 for t in all_tasks
                if t.status == TaskStatus.CANCELLED
            ),
            "workers":   len(self._workers),
            "queue_size": self._queue.qsize(),
        }

    # ==================== Callbacks ====================

    def on_start(self, callback: Callable):
        """callback عند بدء مهمة"""
        self._callbacks["on_start"].append(callback)

    def on_progress(self, callback: Callable):
        """callback عند تحديث التقدم"""
        self._callbacks["on_progress"].append(callback)

    def on_complete(self, callback: Callable):
        """callback عند اكتمال مهمة"""
        self._callbacks["on_complete"].append(callback)

    def on_error(self, callback: Callable):
        """callback عند فشل مهمة"""
        self._callbacks["on_error"].append(callback)

    def on_cancel(self, callback: Callable):
        """callback عند إلغاء مهمة"""
        self._callbacks["on_cancel"].append(callback)

    async def _trigger_callback(
            self,
            event: str,
            task: Task):
        """تشغيل callbacks"""
        for callback in self._callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception as e:
                error_logger.log_exception(
                    e, f"callback_{event}"
                )

    # ==================== تنظيف ====================

    def cleanup_completed(
            self,
            keep_last: int = 100):
        """تنظيف المهام المكتملة القديمة"""
        completed = [
            t for t in self._tasks.values()
            if t.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ]
        ]

        completed.sort(
            key=lambda x: x.completed_at or datetime.min
        )

        to_remove = completed[:-keep_last]
        for task in to_remove:
            del self._tasks[task.task_id]

        if to_remove:
            bot_logger.debug(
                f"🗑️ تم حذف {len(to_remove)} "
                f"مهمة قديمة"
            )


# ==================== Instance ====================

queue_service = QueueService()
