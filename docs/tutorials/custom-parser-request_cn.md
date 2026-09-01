# 新增文件名解析器 —— 需求提交文档

> 适用场景:「设置 → 解析器」里内置的 `bilibili` / `anime` / `default` 三个解析器,
> 都清洗不干净你的某一批文件名(比如某个 PT 站、某个下载工具、某个平台的命名习惯),
> 需要开发者新增一个专门的解析器类。
>
> **这份文档不是给你自己改代码用的**,是给你(需求方)填写"我要什么样的解析效果"的模板,
> 开发者拿着这份填好的信息就能直接写代码,不需要来回反复确认细节。

---

## 0. 先确认:真的需要新解析器吗?

在提需求前,先在网页「设置 → 解析器」的**在线测试**框里,把你的文件名丢进去试一下,换几种启用顺序看看效果:

1. 只启用 `default` 试一次
2. 加上 `anime` 再试一次
3. 加上 `bilibili` 再试一次

如果换个顺序或者多勾一个就能出对的结果,直接在设置页保存就行,不需要写新代码。**只有确认现有 3 个解析器排列组合都搞不定,才需要往下走。**

---

## 1. 背景说明(为什么必须由开发者写代码)

Media Manager 的文件名解析不是"填正则表达式配置"的模式,而是**每个解析器都是一段 Python 代码(类)**,像流水线一样按顺序执行:

```
原始文件名 → [解析器1] → [解析器2] → ... → [default 兜底] → 最终标题/年份/季集/清晰度/发布组
```

网页设置页能做的事只有:**选择用哪几个已经写好的解析器、调整顺序、在线测试效果**。没有"自己填规则"的入口。所以如果内置的解析不干净,必须新增一个 Python 类,这一步只能由开发者完成。

你需要做的,是把下面的表格填完整,信息越具体,开发者一次写对的概率越高,来回确认的次数就越少。

---

## 2. 请填写:文件名样本(至少 5~10 个,越多越好)

请提供**真实的**文件名(带扩展名),覆盖这批资源里不同的命名情况(比如有的带集数、有的不带、有的带发布组、有的没有)。

| 序号 | 原始文件名 | 期望解析出的标题 | 期望的年份 | 期望的季/集 | 期望的清晰度 | 期望的发布组 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

**示例(仅供参考格式,不是真实需求)**:

| 序号 | 原始文件名 | 期望解析出的标题 | 期望的年份 | 期望的季/集 | 期望的清晰度 | 期望的发布组 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | `[MyPT][Movie.Title.2021].1080p.mkv` | Movie Title | 2021 | - / - | 1080p | MyPT | 站点固定用 `[MyPT][...]` 开头包裹站点名+标题 |
| 2 | `[MyPT][Series.Name.S02E05].720p.mkv` | Series Name | - | 2 / 5 | 720p | MyPT | 同上,但这次带季集 |
| 3 | `[MyPT]纪录片.地球脉动.2023.4K.mkv` | 地球脉动 | 2023 | - / - | 4K | MyPT | 中文标题,注意"纪录片"这个分类词要被剥掉 |

---

## 3. 请描述:这批文件名的"通用规律"

光给样本还不够,请用文字描述一下**规律**(方便开发者写出能覆盖所有同类文件的规则,而不是针对这几个样本硬编码):

- **来源是什么**:例如"XX PT站下载的种子文件名"、"XX下载工具自动生成的文件名"、"XX相机/录屏软件默认命名"
- **固定的前缀/后缀模式**:例如"开头总是 `[站点名]` 方括号"、"结尾总是跟着 `-上传者ID`"
- **有没有例外/不规律的情况**:例如"大部分文件名规律一致,但有部分老文件是纯中文没有任何标记"
- **哪些内容是"噪声"要剥掉,哪些是"标题"要保留**:比如某个方括号内容是分类标签(要删),另一个方括号内容其实是标题的一部分(要保留)

---

## 4. 请选择:这个新解析器要放在流水线的什么位置

- [ ] 放在最前面(最先执行,比如需要先剥掉一个特殊前缀,再交给后面的解析器处理剩余部分)
- [ ] 放在 `default` 之前、`bilibili`/`anime` 之后(先让通用/平台特化的先跑,这个再做补充清洗)
- [ ] 不确定,让开发者判断

---

## 5. 开发者内部处理流程(供开发者参考,提需求方不需要看)

<details>
<summary>点击展开(仅供开发实现参考)</summary>

1. 阅读需求方填写的表格和规律描述,必要时追加提问确认边界情况
2. 在 `backend/app/providers/parser/` 下新建 `xxx_parser.py`,继承 `FilenameParser`(见 `backend/app/providers/parser/base.py`),参考已有实现:
   - `bilibili_parser.py` —— 剥离固定后缀模式的例子
   - `anime_parser.py` —— 处理方括号前缀+提取字段的例子
   - `default_parser.py` —— 通用噪声词表 + 反复剥离直到稳定的例子
3. 类结构模板:

   ```python
   from __future__ import annotations
   import re
   from app.providers.parser.base import FilenameParser, ParsedName

   class XxxParser(FilenameParser):
       name = "xxx"                      # 唯一标识,前端下拉框显示的 key
       description = "一句话说明这个解析器做什么"

       def parse(self, p: ParsedName) -> ParsedName:
           work = p.working
           # ... 清洗逻辑,只能改 work 字符串和需要提取的字段 ...
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
   ```

4. 在 `backend/app/providers/parser/pipeline.py` 的 `PARSERS` 字典里注册一行(`"xxx": XxxParser`),并根据需求方选择的位置决定是否要调整 `DEFAULT_PIPELINE` 默认顺序
5. 本地用需求方提供的全部样本跑一遍验证:
   ```bash
   cd backend && .venv/bin/python -c "
   from app.providers.parser.pipeline import ParserPipeline
   names = ['xxx', 'default']   # 按需求方选择的位置排列
   pipeline = ParserPipeline.from_config(names)
   samples = ['样本1.mkv', '样本2.mkv', ...]
   for s in samples:
       r = pipeline.parse(s)
       print(s, '->', r.title, r.year, r.season, r.episode, r.quality, r.release_group)
   "
   ```
6. 确认全部样本解析结果与需求方期望一致后,按标准流程 type-check/build → commit → push → CI → 部署
7. 部署后提醒需求方:去「设置 → 解析器」把新解析器加入启用列表并调整到需求方选择的顺序位置,保存配置;如果需要旧资源也生效,再点「重解析全部资源」

</details>

---

## 6. 提交方式

把第 2、3、4 节填好后,发给开发者(或者贴到需求 issue / 聊天里)即可,不需要你自己动代码。
