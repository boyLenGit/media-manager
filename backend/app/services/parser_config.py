"""解析器激活配置。

存储在 app_setting 表的 key="parser_pipeline" 下,值为 JSON 字符串列表。
默认 ["bilibili", "anime", "default"]。
"""
import json
import logging

from sqlmodel import Session, select

from app.db.session import engine
from app.models import AppSetting
from app.providers.parser.pipeline import DEFAULT_PIPELINE

logger = logging.getLogger(__name__)

SETTING_KEY = "parser_pipeline"


def get_active_parser_names() -> list[str]:
    """返回当前激活的 parser 名称列表(按顺序)。"""
    with Session(engine) as session:
        s = session.exec(select(AppSetting).where(AppSetting.key == SETTING_KEY)).first()
    if s and s.value:
        try:
            data = json.loads(s.value)
            if isinstance(data, list) and all(isinstance(x, str) for x in data):
                return data
        except json.JSONDecodeError:
            logger.warning("parser_pipeline setting is invalid json, fallback to default")
    return list(DEFAULT_PIPELINE)


def set_active_parser_names(names: list[str]) -> None:
    """更新激活的 parser 列表。"""
    payload = json.dumps(names, ensure_ascii=False)
    with Session(engine) as session:
        s = session.exec(select(AppSetting).where(AppSetting.key == SETTING_KEY)).first()
        if s:
            s.value = payload
            s.value_type = "json"
        else:
            s = AppSetting(
                key=SETTING_KEY,
                value=payload,
                value_type="json",
                description="启用的文件名解析器顺序",
            )
            session.add(s)
        session.commit()

    # 失效缓存,下次解析使用新配置
    from app.services.filename_parser import reset_pipeline_cache

    reset_pipeline_cache()
