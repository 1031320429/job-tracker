import sqlite3

from paths import DATA_DIR

DB_PATH = DATA_DIR / "tracker.db"
RESUME_FILES_DIR = DATA_DIR / "resume_files"

STATUSES = [
    "wishlist",   # 想投，还没投
    "applied",    # 已投递
    "oa",         # 笔试/测评
    "interview",  # 面试中
    "offer",      # 拿到 offer
    "rejected",   # 被拒
    "ghosted",    # 已投很久无回音
    "withdrawn",  # 主动放弃
]


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_names(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn):
    app_cols = _column_names(conn, "applications")
    if "job_url" in app_cols and "apply_channel" not in app_cols:
        conn.execute("ALTER TABLE applications RENAME COLUMN job_url TO apply_channel")

    resume_cols = _column_names(conn, "resumes")
    if "file_name" not in resume_cols:
        conn.execute("ALTER TABLE resumes ADD COLUMN file_name TEXT")
    if "file_path" not in resume_cols:
        conn.execute("ALTER TABLE resumes ADD COLUMN file_path TEXT")


def init_db():
    RESUME_FILES_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            notes TEXT,
            file_name TEXT,
            file_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            position TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'wishlist',
            location TEXT,
            source TEXT,
            apply_channel TEXT,
            resume_id INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
            referral TEXT,
            applied_date TEXT,
            next_step_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS checkins (
            date TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS sticky_note (
            id INTEGER PRIMARY KEY,
            content TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    _migrate(conn)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
