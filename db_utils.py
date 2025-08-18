# db_utils.py

import sqlite3

DB_FILE = "multi_user_bot.db"

def get_db_connection():
    """Crea y devuelve una conexión a la base de datos."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    """Crea las tablas de la base de datos si no existen."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla para guardar la configuración de cada usuario (su chat de destino)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        destination_chat_id TEXT NOT NULL
    )
    """)

    # Tabla para usuarios y grupos vigilados, vinculada al usuario que vigila
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

    conn.commit()
    conn.close()
    print("✅ Base de datos multiusuario lista.")

# --- Funciones de configuración de usuario ---

def set_user_destination(user_id: int, destination_chat_id: str):
    """Guarda o actualiza el chat de destino para un usuario específico."""
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO user_settings (user_id, destination_chat_id) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET destination_chat_id = excluded.destination_chat_id",
        (user_id, destination_chat_id)
    )
    conn.commit()
    conn.close()

def get_user_destination(user_id: int) -> str | None:
    """Obtiene el chat de destino de un usuario."""
    conn = get_db_connection()
    row = conn.execute("SELECT destination_chat_id FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row['destination_chat_id'] if row else None

# --- Funciones de la lista de vigilancia ---

def add_watched_target(watcher_user_id: int, source_group_id: str, target_user_id: int, target_username: str) -> bool:
    """Añade un objetivo a la lista de vigilancia de un usuario."""
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
        return False # Ya existía

def remove_watched_target(watcher_user_id: int, target_user_id: int, source_group_id: str) -> bool:
    """Elimina un objetivo de la lista de vigilancia de un usuario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM watched_targets WHERE watcher_user_id = ? AND target_user_id = ? AND source_group_id = ?",
        (watcher_user_id, target_user_id, source_group_id)
    )
    changes = cursor.rowcount
    conn.commit()
    conn.close()
    return changes > 0

def get_user_watched_targets(watcher_user_id: int) -> list:
    """Obtiene toda la lista de objetivos de un usuario."""
    conn = get_db_connection()
    targets = conn.execute("SELECT source_group_id, target_user_id, target_username FROM watched_targets WHERE watcher_user_id = ?", (watcher_user_id,)).fetchall()
    conn.close()
    return targets

def find_watchers_for_target(source_group_id: str, target_user_id: int) -> list:
    """Encuentra todos los usuarios que están vigilando a un objetivo específico en un grupo."""
    conn = get_db_connection()
    watchers = conn.execute(
        "SELECT watcher_user_id FROM watched_targets WHERE source_group_id = ? AND target_user_id = ?",
        (source_group_id, target_user_id)
    ).fetchall()
    conn.close()
    # Devuelve una lista de IDs de los vigilantes
    return [row['watcher_user_id'] for row in watchers]