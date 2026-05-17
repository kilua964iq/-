import os
import asyncio
import json
from typing import Optional, List
from openai import AsyncOpenAI
from config import config
from utils.logger import bot_logger, error_logger


class AIService:

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

            return response.choices[0].message.content

        except Exception as e:
            error_logger.log_exception(
                e, "summarize_text"
            )
            return None

    # ==================== تصنيف ====================

    async def categorize_text(
            self,
            text: str) -> Optional[dict]:
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

            return json.loads(
                response.choices[0].message.content
            )

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

            return response

        except Exception as e:
            error_logger.log_exception(
                e, "transcribe_audio"
            )
            return None

    # ==================== تحليل صور ====================

    async def analyze_image(
            self,
            image_path: str) -> Optional[dict]:
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

            return json.loads(
                response.choices[0].message.content
            )

        except Exception as e:
            error_logger.log_exception(
                e, "analyze_image"
            )
            return None

    # ==================== تقرير ====================

    async def generate_report(
            self,
            stats: dict,
            chat_name: str) -> Optional[str]:
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

    async def check_service(self) -> bool:
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
