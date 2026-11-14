import json
import os
from typing import Optional

import anthropic
from anthropic import beta_tool

from db import get_connection

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """你是一个求职投递助手。用户会给你一张职位截图。你需要：
1. 从截图中提取：公司名称、职位名称、工作地点、任职要求/条件要点、投递邮箱或投递链接、招聘渠道（如果能判断，比如 LinkedIn/官网/内推）。
2. 调用 check_existing_application 检查这家公司是否已经有记录，避免重复创建。
3. 调用 list_resume_versions 查看现有简历版本，如果某个版本的备注和这个岗位的要求明显匹配，就使用它的 id；如果都不匹配或者没有任何简历，resume_id 留空，不要瞎猜。
4. 把职位关键要求整理成几句话，再加一段简短、可直接使用的个性化投递邮件草稿（称呼、一两句为什么合适、结尾），一起放进 notes 字段。
5. 调用 save_application 保存记录：如果第 2 步发现了同公司的记录，用 application_id 更新它；否则新建一条。
6. 最后用中文给用户一段简短总结（3-5 句话）：识别到了什么岗位、是否发现重复记录、推荐了哪个简历版本（如果有）、备注里写了什么要点。不要整段重复输出简历原文或邮件全文。
"""


def _row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


def _build_tools(result_holder):
    @beta_tool
    def check_existing_application(company: str) -> str:
        """Search the tracker for existing records from a given company, to avoid creating duplicates.

        Args:
            company: The company name to search for.
        """
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, company, position, status FROM applications WHERE company LIKE ?",
            (f"%{company}%",),
        ).fetchall()
        conn.close()
        return json.dumps([_row_to_dict(r) for r in rows], ensure_ascii=False)

    @beta_tool
    def list_resume_versions() -> str:
        """List all resume versions on file, with their name and notes, to help pick the best match for a job posting."""
        conn = get_connection()
        rows = conn.execute("SELECT id, name, notes FROM resumes").fetchall()
        conn.close()
        return json.dumps([_row_to_dict(r) for r in rows], ensure_ascii=False)

    @beta_tool
    def save_application(
        company: str,
        position: str,
        apply_channel: Optional[str] = None,
        location: Optional[str] = None,
        source: Optional[str] = None,
        resume_id: Optional[int] = None,
        notes: Optional[str] = None,
        application_id: Optional[int] = None,
    ) -> str:
        """Create a new application record, or update an existing one if application_id is given.

        Args:
            company: Company name.
            position: Job title / position name.
            apply_channel: Email address, application URL, or method to apply.
            location: Job location (e.g. Remote, city name).
            source: Where the posting was found (e.g. LinkedIn, referral, official site).
            resume_id: The id of a matching resume version found via list_resume_versions. Omit if no good match.
            notes: A short summary of key requirements plus a brief personalized outreach email draft.
            application_id: If updating a record found via check_existing_application, its id. Omit to create a new record.
        """
        conn = get_connection()
        if application_id:
            fields = {
                "company": company, "position": position, "apply_channel": apply_channel,
                "location": location, "source": source, "resume_id": resume_id, "notes": notes,
            }
            fields = {k: v for k, v in fields.items() if v is not None}
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE applications SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                list(fields.values()) + [application_id],
            )
            saved_id = application_id
        else:
            cur = conn.execute(
                """
                INSERT INTO applications (company, position, apply_channel, location, source, resume_id, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'wishlist')
                """,
                (company, position, apply_channel, location, source, resume_id, notes),
            )
            saved_id = cur.lastrowid
            conn.execute(
                "INSERT INTO status_history (application_id, status) VALUES (?, 'wishlist')",
                (saved_id,),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (saved_id,)).fetchone()
        conn.close()
        result_holder["application_id"] = saved_id
        return json.dumps(_row_to_dict(row), ensure_ascii=False)

    return [check_existing_application, list_resume_versions, save_application]


def process_screenshot(image_base64: str, media_type: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "尚未配置 ANTHROPIC_API_KEY，无法使用截图识别功能。"}

    result_holder = {"application_id": None}
    client = anthropic.Anthropic(api_key=api_key)

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=_build_tools(result_holder),
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                {"type": "text", "text": "这是一张职位截图，请按流程处理。"},
            ],
        }],
    )

    final_message = None
    for message in runner:
        final_message = message

    summary = ""
    if final_message:
        summary = "".join(b.text for b in final_message.content if b.type == "text")

    return {"summary": summary, "application_id": result_holder["application_id"]}
