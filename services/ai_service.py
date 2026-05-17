import os
import asyncio
import json
from typing import Optional, List
from openai import AsyncOpenAI
from config import config
from utils.logger import bot_logger, error_logger


# ==================== خدمة الذكاء الاصطناعي ====================

class AIService:
    """خدمة الذكاء الاصطناعي الكاملة"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY
        )
        self.model         = "gpt-4-turbo-preview"
        self.whisper_model = "whisper-1"

    # ==================== تلخيص ====================

    async def summarize_text(
            self,
            text: str,
            max_length: int = 200) -> Optional[str]:
        """تلخيص نص"""
        try:
            if not text or len(text) < 50:
                return text

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت مساعد متخصص في تلخيص "
                            "النصوص بشكل دقيق ومختصر."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"لخص النص التالي بحد أقصى "
                            f"{max_length} كلمة "
                            f"باللغة العربية:\n\n{text}"
                        )
                    }
                ],
                max_tokens=500,
                temperature=0.3,
            )

            summary = response.choices[0].message.content
            bot_logger.debug("✅ تم تلخيص نص")
            return summary

        except Exception as e:
            error_logger.log_exception(
                e, "summarize_text"
            )
            return None

    async def summarize_batch(
            self,
            texts: List[str],
            progress_callback=None) -> List[Optional[str]]:
        """تلخيص مجموعة نصوص"""
        results = []
        for i, text in enumerate(texts):
            summary = await self.summarize_text(text)
            results.append(summary)

            if progress_callback:
                await progress_callback(i + 1, len(texts))

            await asyncio.sleep(0.5)

        return results

    # ==================== تصنيف ====================

    async def categorize_text(
            self,
            text: str) -> Optional[dict]:
        """تصنيف نص تلقائياً"""
        try:
            if not text or len(text) < 10:
                return {
                    "category":   "عام",
                    "confidence": 0.5
                }

            categories = [
                "أخبار", "تقنية", "رياضة",
                "ترفيه", "سياسة", "اقتصاد",
                "صحة", "علوم", "ثقافة",
                "دين", "إعلانات", "عام"
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت مصنف نصوص متخصص. "
                            "أجب بـ JSON فقط."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"صنف النص في إحدى الفئات: "
                            f"{', '.join(categories)}\n\n"
                            f"النص: {text[:500]}\n\n"
                            f"أجب بـ JSON:\n"
                            f'{{"category": "الفئة", '
                            f'"confidence": 0.0-1.0, '
                            f'"keywords": []}}'
                        )
                    }
                ],
                max_tokens=150,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            result = json.loads(
                response.choices[0].message.content
            )
            return result

        except Exception as e:
            error_logger.log_exception(
                e, "categorize_text"
            )
            return {"category": "عام", "confidence": 0.0}

    # ==================== تحويل صوت ====================

    async def transcribe_audio(
            self,
            file_path: str,
            language: str = "ar") -> Optional[str]:
        """تحويل ملف صوتي لنص"""
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model=self.whisper_model,
                    file=audio_file,
                    language=language,
                    response_format="text",
                )

            bot_logger.debug(
                f"✅ تم تحويل الصوت: {file_path}"
            )
            return response

        except Exception as e:
            error_logger.log_exception(
                e, "transcribe_audio"
            )
            return None

    async def transcribe_batch(
            self,
            file_paths: List[str],
            language: str = "ar",
            progress_callback=None) -> List[Optional[str]]:
        """تحويل مجموعة ملفات صوتية"""
        results = []
        for i, file_path in enumerate(file_paths):
            text = await self.transcribe_audio(
                file_path, language
            )
            results.append(text)

            if progress_callback:
                await progress_callback(
                    i + 1, len(file_paths)
                )

            await asyncio.sleep(0.3)

        return results

    # ==================== تحليل صور ====================

    async def analyze_image(
            self,
            image_path: str) -> Optional[dict]:
        """تحليل محتوى صورة"""
        try:
            if not os.path.exists(image_path):
                return None

            import base64
            with open(image_path, "rb") as img_file:
                image_data = base64.b64encode(
                    img_file.read()
                ).decode("utf-8")

            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {
                ".jpg":  "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png":  "image/png",
                ".gif":  "image/gif",
                ".webp": "image/webp",
            }
            mime_type = mime_map.get(ext, "image/jpeg")

            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "حلل هذه الصورة:\n"
                                    "1. ماذا تحتوي؟\n"
                                    "2. الفئة؟\n"
                                    "3. كلمات مفتاحية\n\n"
                                    "أجب بـ JSON:\n"
                                    '{"description": "",'
                                    '"category": "",'
                                    '"keywords": []}'
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        f"data:{mime_type};"
                                        f"base64,{image_data}"
                                    )
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300,
                response_format={"type": "json_object"},
            )

            result = json.loads(
                response.choices[0].message.content
            )
            return result

        except Exception as e:
            error_logger.log_exception(
                e, "analyze_image"
            )
            return None

    # ==================== كشف التكرار ====================

    async def get_embedding(
            self,
            text: str) -> Optional[List[float]]:
        """استخراج embedding للنص"""
        try:
            if not text:
                return None

            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],
            )
            return response.data[0].embedding

        except Exception as e:
            error_logger.log_exception(
                e, "get_embedding"
            )
            return None

    def calculate_similarity(
            self,
            emb1: List[float],
            emb2: List[float]) -> float:
        """حساب التشابه بين نصين"""
        try:
            import math
            dot = sum(
                a * b for a, b in zip(emb1, emb2)
            )
            mag1 = math.sqrt(sum(a**2 for a in emb1))
            mag2 = math.sqrt(sum(b**2 for b in emb2))

            if mag1 == 0 or mag2 == 0:
                return 0.0

            return dot / (mag1 * mag2)

        except Exception:
            return 0.0

    async def is_duplicate(
            self,
            text1: str,
            text2: str,
            threshold: float = 0.95) -> bool:
        """كشف التكرار"""
        try:
            if text1 == text2:
                return True

            emb1 = await self.get_embedding(text1)
            emb2 = await self.get_embedding(text2)

            if not emb1 or not emb2:
                return False

            similarity = self.calculate_similarity(
                emb1, emb2
            )
            return similarity >= threshold

        except Exception as e:
            error_logger.log_exception(
                e, "is_duplicate"
            )
            return False

    # ==================== تحليل شامل ====================

    async def analyze_content(
            self,
            text: str,
            include_summary: bool = True,
            include_category: bool = True) -> dict:
        """تحليل شامل للمحتوى"""
        result = {
            "summary":  None,
            "category": None,
            "keywords": [],
        }

        if include_summary and text:
            try:
                result["summary"] = (
                    await self.summarize_text(text)
                )
            except Exception as e:
                error_logger.log_exception(
                    e, "analyze_content_summary"
                )

        if include_category and text:
            try:
                cat = await self.categorize_text(text)
                if cat:
                    result["category"] = cat.get(
                        "category"
                    )
                    result["keywords"] = cat.get(
                        "keywords", []
                    )
            except Exception as e:
                error_logger.log_exception(
                    e, "analyze_content_category"
                )

        return result

    # ==================== تقرير ====================

    async def generate_report(
            self,
            stats: dict,
            chat_name: str) -> Optional[str]:
        """توليد تقرير تحليلي"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت محلل بيانات متخصص "
                            "في تحليل محتوى تيليغرام."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"بناءً على إحصائيات "
                            f"قناة '{chat_name}':\n"
                            f"{json.dumps(stats, ensure_ascii=False, indent=2)}\n\n"
                            f"اكتب تقريراً مختصراً يشمل:\n"
                            f"1. ملخص النشاط\n"
                            f"2. أبرز الملاحظات\n"
                            f"3. توصيات\n"
                        )
                    }
                ],
                max_tokens=800,
                temperature=0.5,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_logger.log_exception(
                e, "generate_report"
            )
            return None

    # ==================== فحص الخدمة ====================

    async def check_service(self) -> bool:
        """التحقق من عمل الخدمة"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": "قل نعم"}
                ],
                max_tokens=5,
            )
            return bool(
                response.choices[0].message.content
            )
        except Exception:
            return False


# ==================== Instance ====================

ai_service = AIService()
