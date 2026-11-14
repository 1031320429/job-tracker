# Job Tracker · 求职追踪器

[中文说明在下方 / Chinese version below](#求职追踪器-1)

A small web app for tracking internship and job applications, with an AI agent that turns a screenshot of a job posting into a structured record.

<!-- TODO: add a screenshot of the app, e.g. ![Job Tracker screenshot](docs/screenshot.png) -->

## Features

- Track company, position, status (wishlist / applied / test / interview / offer / rejected / ghosted / dropped), channel, contact, resume version, dates and notes
- Filter by status, search by company or position, and see summary stat cards
- Resume version management: upload PDF resumes and link each application to the version you used
- Basic-auth login, SQLite storage, Dockerfile and `fly.toml` for deployment to Fly.io

## AI screenshot agent

Upload a screenshot of a job posting and the agent in `agent.py` (built on the Anthropic SDK with tool calling) will:

1. Extract the company, position, location, requirements and how to apply
2. Check the tracker for an existing record from the same company to avoid duplicates
3. Look through your resume versions and pick the best match, or leave it empty if none fits
4. Write a short summary of the requirements and a personalized outreach email draft
5. Create or update the record and reply with a short summary

## Run locally

```bash
pip install -r requirements.txt   # only needed for the screenshot agent
export ANTHROPIC_API_KEY=...      # only needed for the screenshot agent
python3 app.py
```

Open http://127.0.0.1:8420. On first run a random password for the user `admin` is generated, printed once and saved to `data/auth.json`. You can also set `AUTH_USERNAME` and `AUTH_PASSWORD` as environment variables. Your data stays in `data/` and is git-ignored.

---

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
