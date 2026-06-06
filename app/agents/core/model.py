from __future__ import annotations

from agno.models.openai.like import OpenAILike

from app.core.config import settings


class TgModel(OpenAILike):
    """项目自定义模型"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            id=settings.llm_model_id,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            provider=settings.llm_provider,
            *args,
            **kwargs,
        )
        self.supports_native_structured_outputs = False


class TgVisionModel(OpenAILike):
    """项目自定义视觉模型"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            id=settings.vision_llm_model_id,
            api_key=settings.vision_llm_api_key,
            base_url=settings.vision_llm_base_url,
            provider=settings.vision_llm_provider,
            *args,
            **kwargs,
        )
