# =============================================================
# config/settings.py — Configurações da Evolution API
# =============================================================
# Edite este arquivo com os dados da sua instância.

EVOLUTION_API_URL = "http://localhost:8080"   # URL da Evolution API (Docker local)
EVOLUTION_API_KEY = "evolution-key-2024"      # Mesma chave do docker-compose.yml
INSTANCE_NAME    = "meu-whatsapp"             # Nome da instância

# Cabeçalhos padrão usados em todas as requisições
HEADERS = {
    "Content-Type": "application/json",
    "apikey": EVOLUTION_API_KEY,
}
