# =============================================================
# utils/logger.py — Log no terminal e em arquivo
# =============================================================
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


def log(mensagem: str):
    """Imprime no terminal e salva em arquivo de log diário."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] {mensagem}"
    print(linha)

    os.makedirs(LOG_DIR, exist_ok=True)
    nome_arquivo = datetime.now().strftime("%Y-%m-%d") + ".log"
    with open(os.path.join(LOG_DIR, nome_arquivo), "a", encoding="utf-8") as f:
        f.write(linha + "\n")
