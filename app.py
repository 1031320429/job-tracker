import base64
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from auth import check_auth
from db import get_connection, init_db, STATUSES, RESUME_FILES_DIR

STATIC_DIR = Path(__file__).parent / "static"

APPLICATION_FIELDS = [
    "company", "position", "status", "location", "source", "apply_channel",
    "resume_id", "referral", "applied_date", "next_step_date", "notes",
]


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


class Handler(BaseHTTPRequestHandler):
    def _authorized(self):
        if check_auth(self.headers.get("Authorization")):
            return True
        body = b"401 Unauthorized"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Job Tracker"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        file_path = (STATIC_DIR / path.lstrip("/")).resolve()
        if STATIC_DIR not in file_path.parents and file_path != STATIC_DIR:
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        content_type = "text/html"
        if file_path.suffix == ".css":
            content_type = "text/css"
        elif file_path.suffix == ".js":
            content_type = "application/javascript"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

    # ---- routing ----
    def do_GET(self):
        if not self._authorized():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/applications":
            return self.handle_list_applications(query)
        if path == "/api/stats":
            return self.handle_stats()
        if path == "/api/resumes":
            return self.handle_list_resumes()
        if path == "/api/checkins":
            return self.handle_list_checkins(query)
        if path == "/api/note":
            return self.handle_get_note()
        m = re.match(r"^/api/applications/(\d+)$", path)
        if m:
            return self.handle_get_application(int(m.group(1)))
        m = re.match(r"^/api/resumes/(\d+)/file$", path)
        if m:
            return self.handle_get_resume_file(int(m.group(1)))
        return self._serve_static(path)

    def do_POST(self):
        if not self._authorized():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/applications":
            return self.handle_create_application()
        if path == "/api/resumes":
            return self.handle_create_resume()
        if path == "/api/checkins":
            return self.handle_create_checkin()
        if path == "/api/agent/process_screenshot":
            return self.handle_process_screenshot()
        self.send_error(404)

    def do_PUT(self):
        if not self._authorized():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/note":
            return self.handle_update_note()
        m = re.match(r"^/api/applications/(\d+)$", parsed.path)
        if m:
            return self.handle_update_application(int(m.group(1)))
        self.send_error(404)

    def do_DELETE(self):
        if not self._authorized():
            return
        parsed = urlparse(self.path)
        m = re.match(r"^/api/applications/(\d+)$", parsed.path)
        if m:
            return self.handle_delete_application(int(m.group(1)))
        m = re.match(r"^/api/resumes/(\d+)$", parsed.path)
        if m:
            return self.handle_delete_resume(int(m.group(1)))
        m = re.match(r"^/api/checkins/(\d{4}-\d{2}-\d{2})$", parsed.path)
        if m:
            return self.handle_delete_checkin(m.group(1))
        self.send_error(404)

    # ---- applications ----
    def handle_list_applications(self, query):
        conn = get_connection()
        sql = """
            SELECT a.*, r.name AS resume_name
            FROM applications a
            LEFT JOIN resumes r ON r.id = a.resume_id
        """
        clauses = []
        params = []
        if "status" in query and query["status"][0]:
            clauses.append("a.status = ?")
            params.append(query["status"][0])
        if "q" in query and query["q"][0]:
            clauses.append("(a.company LIKE ? OR a.position LIKE ?)")
            like = f"%{query['q'][0]}%"
            params.extend([like, like])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY COALESCE(a.applied_date, a.created_at) DESC, a.id DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        self._send_json([row_to_dict(r) for r in rows])

    def handle_get_application(self, app_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        history = conn.execute(
            "SELECT status, changed_at FROM status_history WHERE application_id = ? ORDER BY changed_at",
            (app_id,),
        ).fetchall()
        conn.close()
        if not row:
            return self.send_error(404)
        data = row_to_dict(row)
        data["history"] = [row_to_dict(h) for h in history]
        self._send_json(data)

    def handle_create_application(self):
        body = self._read_json_body()
        company = (body.get("company") or "").strip()
        position = (body.get("position") or "").strip()
        if not company or not position:
            return self._send_json({"error": "company and position are required"}, 400)
        status = body.get("status") or "wishlist"
        if status not in STATUSES:
            return self._send_json({"error": f"invalid status: {status}"}, 400)

        fields = {k: body.get(k) for k in APPLICATION_FIELDS}
        fields["company"] = company
        fields["position"] = position
        fields["status"] = status

        conn = get_connection()
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        cur = conn.execute(
            f"INSERT INTO applications ({cols}) VALUES ({placeholders})",
            list(fields.values()),
        )
        app_id = cur.lastrowid
        conn.execute(
            "INSERT INTO status_history (application_id, status) VALUES (?, ?)",
            (app_id, status),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        conn.close()
        self._send_json(row_to_dict(row), 201)

    def handle_update_application(self, app_id):
        body = self._read_json_body()
        conn = get_connection()
        existing = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        if not existing:
            conn.close()
            return self.send_error(404)

        if "status" in body and body["status"] not in STATUSES:
            conn.close()
            return self._send_json({"error": f"invalid status: {body['status']}"}, 400)

        updates = {k: body[k] for k in APPLICATION_FIELDS if k in body}
        if not updates:
            conn.close()
            return self._send_json({"error": "no fields to update"}, 400)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [app_id]
        conn.execute(
            f"UPDATE applications SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            params,
        )
        if "status" in updates and updates["status"] != existing["status"]:
            conn.execute(
                "INSERT INTO status_history (application_id, status) VALUES (?, ?)",
                (app_id, updates["status"]),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        conn.close()
        self._send_json(row_to_dict(row))

    def handle_delete_application(self, app_id):
        conn = get_connection()
        conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.commit()
        conn.close()
        self._send_json({"ok": True})

    # ---- resumes ----
    def handle_list_resumes(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM resumes ORDER BY created_at DESC").fetchall()
        conn.close()
        self._send_json([row_to_dict(r) for r in rows])

    def handle_create_resume(self):
        body = self._read_json_body()
        name = (body.get("name") or "").strip()
        if not name:
            return self._send_json({"error": "name is required"}, 400)

        file_data = body.get("file_data")
        file_name = body.get("file_name")
        if file_data and not (file_name or "").lower().endswith(".pdf"):
            return self._send_json({"error": "only PDF files are supported"}, 400)

        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO resumes (name, notes) VALUES (?, ?)",
            (name, body.get("notes")),
        )
        resume_id = cur.lastrowid

        if file_data:
            dest = RESUME_FILES_DIR / f"{resume_id}.pdf"
            dest.write_bytes(base64.b64decode(file_data))
            conn.execute(
                "UPDATE resumes SET file_name = ?, file_path = ? WHERE id = ?",
                (file_name, dest.name, resume_id),
            )

        conn.commit()
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        conn.close()
        self._send_json(row_to_dict(row), 201)

    def handle_get_resume_file(self, resume_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        conn.close()
        if not row or not row["file_path"]:
            return self.send_error(404)
        file_path = RESUME_FILES_DIR / row["file_path"]
        if not file_path.is_file():
            return self.send_error(404)
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Content-Disposition",
            f'inline; filename="{row["file_name"] or "resume.pdf"}"',
        )
        self.end_headers()
        self.wfile.write(body)

    def handle_delete_resume(self, resume_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        conn.commit()
        conn.close()
        if row and row["file_path"]:
            file_path = RESUME_FILES_DIR / row["file_path"]
            file_path.unlink(missing_ok=True)
        self._send_json({"ok": True})

    # ---- checkins ----
    def handle_list_checkins(self, query):
        month = query.get("month", [None])[0]
        conn = get_connection()
        if month and re.match(r"^\d{4}-\d{2}$", month):
            rows = conn.execute(
                "SELECT date FROM checkins WHERE date LIKE ? ORDER BY date", (f"{month}-%",)
            ).fetchall()
        else:
            rows = conn.execute("SELECT date FROM checkins ORDER BY date").fetchall()
        conn.close()
        self._send_json({"dates": [r["date"] for r in rows]})

    def handle_create_checkin(self):
        body = self._read_json_body()
        date = body.get("date")
        if not date or not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            return self._send_json({"error": "date must be YYYY-MM-DD"}, 400)
        conn = get_connection()
        conn.execute("INSERT OR IGNORE INTO checkins (date) VALUES (?)", (date,))
        conn.commit()
        conn.close()
        self._send_json({"date": date, "checked": True}, 201)

    def handle_delete_checkin(self, date):
        conn = get_connection()
        conn.execute("DELETE FROM checkins WHERE date = ?", (date,))
        conn.commit()
        conn.close()
        self._send_json({"date": date, "checked": False})

    # ---- AI agent ----
    def handle_process_screenshot(self):
        body = self._read_json_body()
        image_data = body.get("image_data")
        media_type = body.get("media_type")
        if not image_data or not media_type:
            return self._send_json({"error": "image_data and media_type are required"}, 400)
        try:
            import agent
        except ImportError:
            return self._send_json(
                {"error": "服务器尚未安装 anthropic 依赖，运行 `pip install anthropic` 后重启服务。"}, 500
            )
        result = agent.process_screenshot(image_data, media_type)
        if "error" in result:
            return self._send_json(result, 400)
        self._send_json(result)

    # ---- sticky note ----
    def handle_get_note(self):
        conn = get_connection()
        row = conn.execute("SELECT content, updated_at FROM sticky_note WHERE id = 1").fetchone()
        conn.close()
        if row:
            self._send_json(row_to_dict(row))
        else:
            self._send_json({"content": "", "updated_at": None})

    def handle_update_note(self):
        body = self._read_json_body()
        content = body.get("content", "")
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO sticky_note (id, content, updated_at) VALUES (1, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
            """,
            (content,),
        )
        conn.commit()
        row = conn.execute("SELECT content, updated_at FROM sticky_note WHERE id = 1").fetchone()
        conn.close()
        self._send_json(row_to_dict(row))

    # ---- stats ----
    def handle_stats(self):
        conn = get_connection()
        by_status = conn.execute(
            "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS n FROM applications").fetchone()["n"]
        by_week = conn.execute(
            """
            SELECT strftime('%Y-W%W', COALESCE(applied_date, created_at)) AS week, COUNT(*) AS n
            FROM applications
            WHERE status != 'wishlist'
            GROUP BY week
            ORDER BY week
            """
        ).fetchall()
        conn.close()
        self._send_json({
            "total": total,
            "by_status": {r["status"]: r["n"] for r in by_status},
            "by_week": [row_to_dict(r) for r in by_week],
        })


def main():
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8420))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Job tracker running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
