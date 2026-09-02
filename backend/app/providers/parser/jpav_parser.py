"""FC2-PPV 番号格式归一化解析器。

背景:
- FC2-PPV-数字 这种番号格式,default_parser.py 已经能正确处理并保持独立
  (不会像旧 bug 那样被误剥成裸数字导致大量番号合并成同一个标题,
  见 commit cd3a52e 的修复)。
- 但用户/上传者写法不统一,同一个视频可能出现:
    FC2-PPV-3180681 / FC2_PPV_3180681 / fc2ppv3180681 / FC2PPV-3180681
  这些写法在 default parser 里会生成不同的 normalized_title,导致
  同一视频的不同来源文件无法被识别为同一份资源(重复扫描/去重会漏判)。

策略:
- 只做"归一化",不改变番号本身的数字内容,不剥掉番号(不重复破坏已经修好
  的 FC2-PPV 完整保留逻辑)。
- 只在明确匹配到 FC2-PPV 变体写法时才动手,不匹配的文件名(绝大多数普通
  影视/番剧/B站视频)完全不受影响,原样传给下一个 parser。
- 把归一化后的番号顺带存进 release_group,方便前端展示/筛选。
"""
from __future__ import annotations

import re

from app.providers.parser.base import FilenameParser, ParsedName

# 匹配 FC2-PPV 的各种分隔符/大小写变体:
# FC2-PPV-123456 / FC2_PPV_123456 / fc2ppv123456 / FC2PPV-123456 ...
# 前后用负向断言避免匹配到更长的字母数字串中间的一部分(比如 XFC2-PPV-123456X)。
_FC2_PPV_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])[Ff][Cc]2[-_]?[Pp][Pp][Vv][-_]?(\d{6,10})(?![0-9])"
)


class JPAVParser(FilenameParser):
    name = "jpav"
    description = "FC2-PPV 番号写法归一化(不同分隔符/大小写统一识别为同一番号)"

    def parse(self, p: ParsedName) -> ParsedName:
        work = p.working
        release_group = p.release_group

        m = _FC2_PPV_PATTERN.search(work)
        if m:
            code = m.group(1)
            canonical = f"FC2-PPV-{code}"
            # 只替换匹配到的这一段,归一化成统一写法,不改动其余文件名内容
            # (标题清洗/年份季集提取等都留给后面的 default parser 处理)。
            work = _FC2_PPV_PATTERN.sub(canonical, work, count=1)
            if release_group is None:
                release_group = canonical

        return ParsedName(
            raw=p.raw,
            working=work,
            title=p.title,
            normalized_title=p.normalized_title,
            year=p.year,
            season=p.season,
            episode=p.episode,
            quality=p.quality,
            release_group=release_group,
            language_tags=p.language_tags,
            applied=p.applied + [self.name],
        )
