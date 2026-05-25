"""旧版 filename_parser 兼容层。

实际逻辑已迁移到 app.providers.parser/。
保留这个模块只是为了不破坏现有 import。

新代码请用:
    from app.providers.parser.pipeline import ParserPipeline
    pipeline = ParserPipeline.from_config()  # 或自定义列表
    result = pipeline.parse("文件名.mp4")
"""
from __future__ import annotations

from functools import lru_cache

from app.providers.parser.base import ParsedName  # noqa: F401  re-export
from app.providers.parser.pipeline import ParserPipeline


@lru_cache(maxsize=1)
def _default_pipeline() -> ParserPipeline:
    """缓存默认 pipeline,避免每次调用都重新构造解析器实例。"""
    from app.services.parser_config import get_active_parser_names

    return ParserPipeline.from_config(get_active_parser_names())


def parse_filename(filename_no_ext: str) -> ParsedName:
    """向后兼容的入口。使用当前激活的 pipeline 解析。"""
    return _default_pipeline().parse(filename_no_ext)


def reset_pipeline_cache() -> None:
    """配置改了之后调一下,让下次解析重新构造 pipeline。"""
    _default_pipeline.cache_clear()
