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
