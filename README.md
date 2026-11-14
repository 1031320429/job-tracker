# 求职追踪器

记录和分析远程实习（或任意岗位）投递情况的小工具。Python + SQLite；核心追踪功能只用标准库，截图自动识别功能需要 `anthropic` 依赖和 API Key。

## 运行

```bash
pip install -r requirements.txt   # 仅截图识别需要
export ANTHROPIC_API_KEY=...      # 仅截图识别需要
python3 app.py
```

然后打开 http://127.0.0.1:8420

数据保存在本地 `data/tracker.db`，简历 PDF 保存在 `data/resume_files/`（都已加入 .gitignore，不会被提交）。

## 功能

- 记录公司、职位、状态（想投 / 已投递 / 笔试 / 面试 / Offer / 被拒 / 已读不回 / 放弃）、渠道、投递途径（邮箱/链接/内推等）、内推人、简历版本、投递日期、下一步时间、备注
- 按状态筛选、按公司/职位搜索
- 顶部统计卡片（总数 + 各状态数量）
- 简历版本管理：可上传 PDF 简历文件，投递记录里关联具体版本，方便回顾"这个岗位投的是哪份简历"

## 截图自动识别（AI Agent）

上传职位截图后，`agent.py` 中的 Claude agent 会依次：提取公司/职位/地点/要求 → 调用工具检查是否已有同公司记录（去重）→ 列出简历版本并匹配最合适的一份 → 生成要点和个性化投递邮件草稿 → 保存或更新记录，最后用中文给出简短总结。

也可以不用 API Key，把职位截图发给 Claude（对话方式），让它直接调用本地接口写入记录：

```bash
curl -X POST http://127.0.0.1:8420/api/applications \
  -H "Content-Type: application/json" \
  -d '{"company":"...", "position":"...", "apply_channel":"...", "notes":"..."}'
```

## 后续可以扩展的方向

- 导出 CSV / 简单的时间趋势图
- 提醒：下一步时间临近时高亮
