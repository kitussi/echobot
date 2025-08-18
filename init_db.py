import sqlite3

# Conexión a la base de datos (si no existe, se crea automáticamente)
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Tabla para almacenar configuración de grupos
cursor.execute("""
CREATE TABLE IF NOT EXISTS groups (
    group_id TEXT PRIMARY KEY,
    alert_chat TEXT
)
""")

# Tabla para usuarios vigilados
cursor.execute("""
CREATE TABLE IF NOT EXISTS watch_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT,
    user_id INTEGER,
    username TEXT,
    FOREIGN KEY (group_id) REFERENCES groups (group_id)
)
""")

conn.commit()
conn.close()

print("✅ Base de datos inicializada correctamente.")

from db_utils import create_tables

create_tables()
print("Tablas creadas correctamente.")
