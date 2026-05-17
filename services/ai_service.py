import os
import asyncio
import json
import re
from typing import Optional, List, Dict
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
        self.embed_model   = "text-embedding-3-small"

    # ==================== تلخيص ====================

    async def summarize_text(
            self,
            text: str,
            max_length: int = 200,
            language: str = "ar") -> Optional[str]:
        """تلخيص نص بشكل ذكي"""
        try:
            if not text or len(text) < 50:
                return text

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت خبير في تلخيص النصوص. "
                            "لخص بدقة واحتفظ بالمعلومات المهمة."
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
                max_tokens=600,
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
        """تصنيف نص تلقائياً"""
        try:
            if not text or len(text) < 10:
                return {
                    "category":   "عام",
                    "confidence": 0.5,
                    "keywords":   [],
                    "sentiment":  "محايد",
                    "language":   "ar",
                }

            categories = [
                "أخبار", "تقنية", "رياضة",
                "ترفيه", "سياسة", "اقتصاد",
                "صحة", "علوم", "ثقافة",
                "دين", "إعلانات", "تعليم",
                "سفر", "طعام", "فن", "عام"
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت مصنف نصوص متخصص. "
                            "أجب بـ JSON فقط بدون أي نص إضافي."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"صنف النص في إحدى الفئات: "
                            f"{', '.join(categories)}\n\n"
                            f"النص: {text[:1000]}\n\n"
                            f"أجب بـ JSON:\n"
                            f'{{"category": "الفئة",'
                            f'"confidence": 0.0-1.0,'
                            f'"keywords": ["كلمة1","كلمة2"],'
                            f'"sentiment": "إيجابي/سلبي/محايد",'
                            f'"language": "ar/en/other"}}'
                        )
                    }
                ],
                max_tokens=200,
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
            return {
                "category":   "عام",
                "confidence": 0.0,
                "keywords":   [],
                "sentiment":  "محايد",
                "language":   "ar",
            }

    # ==================== تحليل المشاعر ====================

    async def analyze_sentiment(
            self,
            text: str) -> Optional[dict]:
        """تحليل مشاعر النص"""
        try:
            if not text:
                return None

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت محلل مشاعر متخصص. "
                            "أجب بـ JSON فقط."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"حلل مشاعر النص التالي:\n"
                            f"{text[:500]}\n\n"
                            f"أجب بـ JSON:\n"
                            f'{{"sentiment": "إيجابي/سلبي/محايد",'
                            f'"score": 0.0-1.0,'
                            f'"emotions": ["فرح","حزن","غضب","خوف","مفاجأة"],'
                            f'"explanation": "شرح قصير"}}'
                        )
                    }
                ],
                max_tokens=200,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            return json.loads(
                response.choices[0].message.content
            )

        except Exception as e:
            error_logger.log_exception(
                e, "analyze_sentiment"
            )
            return None

    # ==================== ترجمة ====================

    async def translate_text(
            self,
            text: str,
            target_language: str = "ar") -> Optional[str]:
        """ترجمة نص لأي لغة"""
        try:
            if not text:
                return None

            lang_names = {
                "ar": "العربية",
                "en": "الإنجليزية",
                "fr": "الفرنسية",
                "de": "الألمانية",
                "es": "الإسبانية",
                "tr": "التركية",
                "fa": "الفارسية",
            }

            lang_name = lang_names.get(
                target_language, target_language
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"أنت مترجم محترف. "
                            f"ترجم النص إلى {lang_name} "
                            f"بدون أي تعليق إضافي."
                        )
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=1000,
                temperature=0.1,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_logger.log_exception(
                e, "translate_text"
            )
            return None

    # ==================== كشف اللغة ====================

    async def detect_language(
            self, text: str) -> Optional[str]:
        """كشف لغة النص"""
        try:
            if not text:
                return None

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"ما لغة هذا النص؟ "
                            f"أجب بكود اللغة فقط مثل ar/en/fr:\n"
                            f"{text[:200]}"
                        )
                    }
                ],
                max_tokens=10,
                temperature=0.1,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            error_logger.log_exception(
                e, "detect_language"
            )
            return None

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
        """تحليل محتوى صورة بالتفصيل"""
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
                                    "حلل هذه الصورة بالتفصيل:\n"
                                    "1. ماذا تحتوي؟\n"
                                    "2. هل فيها نصوص؟ استخرجها\n"
                                    "3. الفئة\n"
                                    "4. كلمات مفتاحية\n"
                                    "5. هل فيها معلومات حساسة؟\n\n"
                                    "أجب بـ JSON:\n"
                                    '{"description": "",'
                                    '"extracted_text": "",'
                                    '"category": "",'
                                    '"keywords": [],'
                                    '"is_sensitive": false,'
                                    '"sensitive_type": ""}'
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
                max_tokens=500,
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

    # ==================== OCR من الصور ====================

    async def extract_text_from_image(
            self,
            image_path: str) -> Optional[str]:
        """استخراج النص من صورة OCR"""
        try:
            result = await self.analyze_image(image_path)
            if result:
                return result.get("extracted_text", "")
            return None
        except Exception as e:
            error_logger.log_exception(
                e, "extract_text_from_image"
            )
            return None

    # ==================== بحث ذكي ====================

    async def smart_search(
            self,
            query: str,
            messages: List[dict],
            top_k: int = 10) -> List[dict]:
        """بحث ذكي بالمعنى وليس بالكلمة"""
        try:
            if not messages:
                return []

            # الحصول على embedding للبحث
            query_embedding = await self._get_embedding(query)
            if not query_embedding:
                # بحث عادي إذا فشل الـ embedding
                return [
                    m for m in messages
                    if query.lower() in
                    (m.get("text", "") or "").lower()
                ][:top_k]

            # حساب التشابه لكل رسالة
            scored = []
            for msg in messages:
                text = msg.get("text", "") or ""
                if not text:
                    continue

                msg_embedding = await self._get_embedding(
                    text[:500]
                )
                if msg_embedding:
                    score = self._cosine_similarity(
                        query_embedding, msg_embedding
                    )
                    scored.append({
                        **msg,
                        "relevance_score": score
                    })
                    await asyncio.sleep(0.1)

            # ترتيب حسب التشابه
            scored.sort(
                key=lambda x: x.get("relevance_score", 0),
                reverse=True
            )

            return scored[:top_k]

        except Exception as e:
            error_logger.log_exception(
                e, "smart_search"
            )
            return []

    # ==================== أوامر طبيعية ====================

    async def process_natural_command(
            self,
            command: str,
            context: dict = None) -> dict:
        """معالجة أوامر طبيعية بالعربي"""
        try:
            system_prompt = """
أنت مساعد ذكي لبوت أرشفة تيليغرام.
المستخدم يعطيك أمراً بالعربي وأنت تحوله لعملية محددة.

الأوامر المتاحة:
- search: بحث في المحتوى
- summarize: تلخيص
- extract: استخراج بيانات (cards/phones/emails/urls)
- analyze: تحليل
- translate: ترجمة
- stats: إحصائيات

أجب بـ JSON:
{
  "action": "search/summarize/extract/analyze/translate/stats",
  "params": {
    "query": "نص البحث إذا كان بحث",
    "extract_type": "cards/phones/emails/urls/all",
    "target_language": "ar/en",
    "chat_filter": "اسم القناة إذا ذكر"
  },
  "response": "رد طبيعي للمستخدم"
}
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": command}
            ]

            if context:
                messages.insert(1, {
                    "role": "system",
                    "content": f"السياق: {json.dumps(context, ensure_ascii=False)}"
                })

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            return json.loads(
                response.choices[0].message.content
            )

        except Exception as e:
            error_logger.log_exception(
                e, "process_natural_command"
            )
            return {
                "action":   "unknown",
                "params":   {},
                "response": "لم أفهم الأمر، حاول مجدداً"
            }

    # ==================== كشف الأخبار المزيفة ====================

    async def detect_fake_news(
            self,
            text: str) -> Optional[dict]:
        """كشف الأخبار المزيفة أو المضللة"""
        try:
            if not text or len(text) < 50:
                return None

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت محلل أخبار متخصص في كشف "
                            "المعلومات المضللة. أجب بـ JSON فقط."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"حلل هذا النص وحدد:\n"
                            f"1. هل يحتوي على معلومات مضللة؟\n"
                            f"2. مستوى الموثوقية\n"
                            f"3. الأسباب\n\n"
                            f"النص: {text[:1000]}\n\n"
                            f"أجب بـ JSON:\n"
                            f'{{"is_misleading": false,'
                            f'"reliability_score": 0.0-1.0,'
                            f'"reasons": [],'
                            f'"recommendation": ""}}'
                        )
                    }
                ],
                max_tokens=300,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            return json.loads(
                response.choices[0].message.content
            )

        except Exception as e:
            error_logger.log_exception(
                e, "detect_fake_news"
            )
            return None

    # ==================== استخراج الأحداث ====================

    async def extract_events(
            self,
            text: str) -> Optional[dict]:
        """استخراج الأحداث والتواريخ من النص"""
        try:
            if not text:
                return None

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت متخصص في استخراج "
                            "الأحداث والتواريخ. "
                            "أجب بـ JSON فقط."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"استخرج الأحداث والتواريخ "
                            f"من النص:\n{text[:1000]}\n\n"
                            f"أجب بـ JSON:\n"
                            f'{{"events": ['
                            f'{{"date": "",'
                            f'"event": "",'
                            f'"location": "",'
                            f'"importance": "high/medium/low"}}],'
                            f'"timeline": "وصف الجدول الزمني"}}'
                        )
                    }
                ],
                max_tokens=400,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            return json.loads(
                response.choices[0].message.content
            )

        except Exception as e:
            error_logger.log_exception(
                e, "extract_events"
            )
            return None

    # ==================== مقارنة قناتين ====================

    async def compare_channels(
            self,
            channel1_stats: dict,
            channel2_stats: dict,
            channel1_name: str,
            channel2_name: str) -> Optional[str]:
        """مقارنة تحليلية بين قناتين"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت محلل قنوات تيليغرام متخصص."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"قارن بين هاتين القناتين:\n\n"
                            f"القناة 1 - {channel1_name}:\n"
                            f"{json.dumps(channel1_stats, ensure_ascii=False)}\n\n"
                            f"القناة 2 - {channel2_name}:\n"
                            f"{json.dumps(channel2_stats, ensure_ascii=False)}\n\n"
                            f"اكتب تقرير مقارنة شامل يشمل:\n"
                            f"1. الفروقات الرئيسية\n"
                            f"2. نقاط القوة لكل قناة\n"
                            f"3. التوصيات\n"
                        )
                    }
                ],
                max_tokens=800,
                temperature=0.5,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_logger.log_exception(
                e, "compare_channels"
            )
            return None

    # ==================== تحليل الأنماط ====================

    async def analyze_patterns(
            self,
            messages: List[dict]) -> Optional[dict]:
        """تحليل أنماط المحتوى وتوقعات مستقبلية"""
        try:
            if not messages or len(messages) < 5:
                return None

            # تحضير ملخص للرسائل
            sample = messages[:50]
            texts  = [
                m.get("text", "")[:200]
                for m in sample
                if m.get("text")
            ]

            if not texts:
                return None

            combined = "\n---\n".join(texts[:20])

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت محلل بيانات متخصص في "
                            "تحليل أنماط المحتوى. "
                            "أجب بـ JSON فقط."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"حلل أنماط هذا المحتوى:\n"
                            f"{combined}\n\n"
                            f"أجب بـ JSON:\n"
                            f'{{"main_topics": [],'
                            f'"posting_pattern": "",'
                            f'"audience_type": "",'
                            f'"content_quality": "high/medium/low",'
                            f'"predictions": [],'
                            f'"best_posting_time": "",'
                            f'"recommendations": []}}'
                        )
                    }
                ],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            return json.loads(
                response.choices[0].message.content
            )

        except Exception as e:
            error_logger.log_exception(
                e, "analyze_patterns"
            )
            return None

    # ==================== تحليل الروابط ====================

    async def analyze_url(
            self, url: str) -> Optional[dict]:
        """تحليل رابط واستخراج معلوماته"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        # استخراج العنوان والوصف
                        title = re.search(
                            r'<title>(.*?)</title>',
                            html, re.IGNORECASE
                        )
                        desc = re.search(
                            r'<meta name="description" content="(.*?)"',
                            html, re.IGNORECASE
                        )

                        title_text = (
                            title.group(1) if title else ""
                        )
                        desc_text = (
                            desc.group(1) if desc else ""
                        )

                        # تحليل AI للمحتوى
                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {
                                    "role": "user",
                                    "content": (
                                        f"حلل هذا الرابط:\n"
                                        f"URL: {url}\n"
                                        f"العنوان: {title_text}\n"
                                        f"الوصف: {desc_text}\n\n"
                                        f"أجب بـ JSON:\n"
                                        f'{{"title": "",'
                                        f'"summary": "",'
                                        f'"category": "",'
                                        f'"is_safe": true,'
                                        f'"language": ""}}'
                                    )
                                }
                            ],
                            max_tokens=200,
                            response_format={"type": "json_object"},
                        )

                        return json.loads(
                            response.choices[0].message.content
                        )

        except Exception as e:
            error_logger.log_exception(
                e, "analyze_url"
            )
            return None

    # ==================== تقرير شامل ====================

    async def generate_report(
            self,
            stats: dict,
            chat_name: str) -> Optional[str]:
        """توليد تقرير تحليلي شامل"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت محلل بيانات متخصص "
                            "في تحليل محتوى تيليغرام. "
                            "اكتب تقارير احترافية ومفصلة."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"اكتب تقريراً شاملاً لقناة "
                            f"'{chat_name}':\n\n"
                            f"الإحصائيات:\n"
                            f"{json.dumps(stats, ensure_ascii=False, indent=2)}\n\n"
                            f"التقرير يشمل:\n"
                            f"1. ملخص تنفيذي\n"
                            f"2. تحليل المحتوى\n"
                            f"3. نقاط القوة والضعف\n"
                            f"4. التوصيات\n"
                            f"5. التوقعات المستقبلية\n"
                        )
                    }
                ],
                max_tokens=1000,
                temperature=0.5,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_logger.log_exception(
                e, "generate_report"
            )
            return None

    # ==================== تحليل شامل ====================

    async def analyze_content(
            self,
            text: str,
            include_summary: bool = True,
            include_category: bool = True,
            include_sentiment: bool = True,
            include_events: bool = False) -> dict:
        """تحليل شامل للمحتوى"""
        result = {
            "summary":   None,
            "category":  None,
            "keywords":  [],
            "sentiment": None,
            "events":    None,
            "language":  None,
        }

        if not text:
            return result

        tasks = []

        if include_summary:
            tasks.append(
                ("summary", self.summarize_text(text))
            )

        if include_category:
            tasks.append(
                ("category", self.categorize_text(text))
            )

        if include_sentiment:
            tasks.append(
                ("sentiment", self.analyze_sentiment(text))
            )

        if include_events:
            tasks.append(
                ("events", self.extract_events(text))
            )

        # تنفيذ متوازي
        for key, task in tasks:
            try:
                value = await task
                if key == "category" and value:
                    result["category"] = value.get("category")
                    result["keywords"] = value.get("keywords", [])
                    result["language"] = value.get("language")
                elif key == "sentiment" and value:
                    result["sentiment"] = value.get("sentiment")
                else:
                    result[key] = value
            except Exception as e:
                error_logger.log_exception(
                    e, f"analyze_content_{key}"
                )

        return result

    # ==================== كشف التكرار ====================

    async def is_duplicate(
            self,
            text1: str,
            text2: str,
            threshold: float = 0.92) -> bool:
        """كشف التكرار بين نصين"""
        try:
            if text1 == text2:
                return True

            if not text1 or not text2:
                return False

            emb1 = await self._get_embedding(text1)
            emb2 = await self._get_embedding(text2)

            if not emb1 or not emb2:
                return False

            similarity = self._cosine_similarity(emb1, emb2)
            return similarity >= threshold

        except Exception as e:
            error_logger.log_exception(
                e, "is_duplicate"
            )
            return False

    # ==================== دوال مساعدة ====================

    async def _get_embedding(
            self,
            text: str) -> Optional[List[float]]:
        """استخراج embedding للنص"""
        try:
            if not text:
                return None

            response = await self.client.embeddings.create(
                model=self.embed_model,
                input=text[:8000],
            )
            return response.data[0].embedding

        except Exception as e:
            error_logger.log_exception(
                e, "_get_embedding"
            )
            return None

    def _cosine_similarity(
            self,
            vec1: List[float],
            vec2: List[float]) -> float:
        """حساب التشابه بين متجهين"""
        try:
            import math
            dot     = sum(a * b for a, b in zip(vec1, vec2))
            mag1    = math.sqrt(sum(a**2 for a in vec1))
            mag2    = math.sqrt(sum(b**2 for b in vec2))

            if mag1 == 0 or mag2 == 0:
                return 0.0

            return dot / (mag1 * mag2)

        except Exception:
            return 0.0

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
