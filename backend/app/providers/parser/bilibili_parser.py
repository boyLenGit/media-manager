"""B 站下载文件名解析器。

B 站客户端/第三方工具下载的文件名典型特征:
- (Av10285316,P1) 或 (BV1xxxxxx,P1)  — av/bv 号 + 分 P
- (BV1xxxxxx)
- " - 1.正片"  / " - 1.改" / " - 1.未命名项目-顺丰第三版"  — 分 P 标题
- 「未命名项目」「未命名项目-顺丰第三版」 — 投稿人偷懒留下的默认名
- "Av6197763" / "BV1xx411c7mu"  — 裸 BV 号
- 「P1」「P10」  — 分 P 序号

我们的策略是把这些后缀都先剥掉,把"主标题"留给后面的 default parser。

Demo 测试样本(verified):
- "我们其实是未出道的女团W&M2 - 1.我们其实是女团(Av10285316,P1)"
  → "我们其实是未出道的女团W&M2"
- "「测评」顺丰快递寄丢，up主被逼上法院？物流一哥，就这？ - 1.未命名项目-顺丰第三版"
  → "「测评」顺丰快递寄丢，up主被逼上法院？物流一哥，就这？"
- "1.【苹果发布会】107秒！Apple发布会快闪版(Av6197763,P1)"
  → "【苹果发布会】107秒！Apple发布会快闪版"
"""
from __future__ import annotations

import re

from app.providers.parser.base import FilenameParser, ParsedName


# B 站 av/bv 号 + 可选分 P,放在末尾括号里
_BV_AV_TAIL = re.compile(
    r"\s*[\(\[（【][\s,，]*(?:[Aa][Vv]\d+|[Bb][Vv][A-Za-z0-9]+)\b(?:[,，]\s*[Pp]\d+)?\s*[\)\]）】]\s*$"
)
# 也可能是没括号的裸 BV/AV
_BV_AV_NAKED = re.compile(r"\s+(?:[Aa][Vv]\d+|[Bb][Vv][A-Za-z0-9]+)\s*$")

# 「 - 1.xxx」「 - 23.正片」 这种分 P 后缀
# 后面的 .xxx 标题部分允许任何字符(包括空格、汉字),只要不是开头才有的「 - N」格式
# 注意:必须是中划线-空格-数字-(可选 .标题),避免把正常标题里的 "-1" 误剥
_PART_TITLE_TAIL = re.compile(
    r"\s+-\s+\d+(?:\.[^\(\)\[\]]+)?\s*$"
)

# 「未命名项目」类无意义后缀(投稿者偷懒)
_UNNAMED_TAIL = re.compile(
    r"\s+(?:未命名项目|未命名|新建项目|临时|test|TEST|默认)[^\s]*\s*$"
)

# 单纯的分 P 序号「P1」「p2」等
_PURE_P_TAIL = re.compile(r"\s+[Pp]\d+\s*$")

# 文件开头的纯数字编号「1.xxx」「01.xxx」(常见于 B 站合集下载,自动加序号)
_LEADING_INDEX = re.compile(r"^(?:\d{1,3})[.\s]+")


class BilibiliParser(FilenameParser):
    name = "bilibili"
    description = "B 站特化:剥离 (Av/BV 号,P1)、未命名项目、分P序号等"

    def parse(self, p: ParsedName) -> ParsedName:
        work = p.working

        # 反复剥离尾部噪声直到稳定
        for _ in range(5):
            before = work
            work = _BV_AV_TAIL.sub("", work)
            work = _BV_AV_NAKED.sub("", work)
            work = _PART_TITLE_TAIL.sub("", work)
            work = _UNNAMED_TAIL.sub("", work)
            work = _PURE_P_TAIL.sub("", work)
            work = work.rstrip(" .-_")
            if work == before:
                break

        # 剥头部的"1." "01." 编号 — 仅当剥完后剩余内容仍 >= 2 字符,
        # 避免把"3.21" 这种本身就是标题的剥成空
        stripped = _LEADING_INDEX.sub("", work, count=1)
        if len(stripped.strip()) >= 2:
            work = stripped

        return ParsedName(
            raw=p.raw,
            working=work,
            title=p.title,
            normalized_title=p.normalized_title,
            year=p.year,
            season=p.season,
            episode=p.episode,
            quality=p.quality,
            release_group=p.release_group,
            language_tags=p.language_tags,
            applied=p.applied + [self.name],
        )
