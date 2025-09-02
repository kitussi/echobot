import sqlite3

DB_FILE = "multi_user_bot.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        destination_chat_id TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watched_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        watcher_user_id INTEGER NOT NULL,
        source_group_id TEXT NOT NULL,
        target_user_id INTEGER NOT NULL,
        target_username TEXT,
        UNIQUE(watcher_user_id, source_group_id, target_user_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS filters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        filter_type TEXT NOT NULL, -- 'keyword_include', 'keyword_exclude', 'content_type'
        filter_value TEXT NOT NULL,
        FOREIGN KEY (target_id) REFERENCES watched_targets (id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Base de datos con filtros lista.")

def set_user_destination(user_id: int, destination_chat_id: str):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO user_settings (user_id, destination_chat_id) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET destination_chat_id = excluded.destination_chat_id",
        (user_id, destination_chat_id)
    )
    conn.commit()
    conn.close()

def get_user_destination(user_id: int) -> str | None:
    conn = get_db_connection()
    row = conn.execute("SELECT destination_chat_id FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row['destination_chat_id'] if row else None

def add_watched_target(watcher_user_id: int, source_group_id: str, target_user_id: int, target_username: str) -> bool:
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO watched_targets (watcher_user_id, source_group_id, target_user_id, target_username) VALUES (?, ?, ?, ?)",
            (watcher_user_id, source_group_id, target_user_id, target_username)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def remove_watched_target_by_id(target_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watched_targets WHERE id = ?", (target_id,))
    changes = cursor.rowcount
    conn.commit()
    conn.close()
    return changes > 0

def get_user_watched_targets(watcher_user_id: int) -> list:
    conn = get_db_connection()
    targets = conn.execute("SELECT id, source_group_id, target_user_id, target_username FROM watched_targets WHERE watcher_user_id = ?", (watcher_user_id,)).fetchall()
    conn.close()
    return targets

def find_watchers_for_target(source_group_id: str, target_user_id: int) -> list:
    conn = get_db_connection()
    watchers = conn.execute(
        "SELECT id, watcher_user_id FROM watched_targets WHERE source_group_id = ? AND target_user_id = ?",
        (source_group_id, str(target_user_id))
    ).fetchall()
    conn.close()
    return watchers

def add_filter(target_id: int, filter_type: str, filter_value: str):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO filters (target_id, filter_type, filter_value) VALUES (?, ?, ?)",
        (target_id, filter_type, filter_value)
    )
    conn.commit()
    conn.close()

def get_filters_for_target(target_id: int) -> list:
    conn = get_db_connection()
    filters_list = conn.execute("SELECT id, filter_type, filter_value FROM filters WHERE target_id = ?", (target_id,)).fetchall()
    conn.close()
    return filters_list

def remove_filter_by_id(filter_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM filters WHERE id = ?", (filter_id,))
    conn.commit()
    conn.close()

def remove_user_destination(user_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_migrated_group_id(old_group_id: str, new_group_id: str):
    """Updates all occurrences of an old group ID to a new one after a migration."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE watched_targets SET source_group_id = ? WHERE source_group_id = ?",
        (new_group_id, old_group_id)
    )
    conn.commit()
    conn.close()
    print(f"Database updated: Group ID {old_group_id} migrated to {new_group_id}")