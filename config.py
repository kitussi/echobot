# config.py (Versión Final Verificada)

import os
from dotenv import load_dotenv

# Esta función carga las variables del archivo .env a nuestro entorno
load_dotenv()

# Ahora, leemos las variables desde el entorno
TELEGRAM_TOKEN = os.environ.get("BOT_TOKEN")

# Leemos la variable de entorno. Si no existe, por defecto será "production".
# Esto asegura que config.ENVIRONMENT siempre exista.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production") 