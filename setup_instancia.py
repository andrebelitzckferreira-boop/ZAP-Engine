#!/usr/bin/env python3
# =============================================================
# setup_instancia.py — Cria a instância e exibe o QR Code
# Rode UMA VEZ após subir o Docker
# =============================================================
import sys
import os
import time
import requests
import base64

sys.path.insert(0, os.path.dirname(__file__))

from config.settings import EVOLUTION_API_URL, EVOLUTION_API_KEY, INSTANCE_NAME, HEADERS

QR_HTML_PATH = os.path.join(os.path.dirname(__file__), "qrcode.html")


def aguardar_api(tentativas=10):
    print("⏳ Aguardando a Evolution API iniciar...")
    for i in range(tentativas):
        try:
            r = requests.get(f"{EVOLUTION_API_URL}/", timeout=3)
            print("✅ API respondendo!\n")
            return True
        except Exception:
            print(f"   Tentativa {i+1}/{tentativas}...")
            time.sleep(3)
    return False


def criar_instancia():
    print(f"📱 Criando instância '{INSTANCE_NAME}'...")
    url = f"{EVOLUTION_API_URL}/instance/create"
    payload = {
        "instanceName": INSTANCE_NAME,
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS"
    }
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        data = r.json()

        # Instância já existe? tenta conectar direto
        if r.status_code == 403 or "already" in str(data).lower():
            print(f"  ℹ️  Instância já existe, buscando QR Code...")
            return obter_qrcode()

        r.raise_for_status()
        return data
    except Exception as e:
        print(f"❌ Erro ao criar instância: {e}")
        return None


def obter_qrcode():
    url = f"{EVOLUTION_API_URL}/instance/connect/{INSTANCE_NAME}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ Erro ao obter QR Code: {e}")
        return None


def salvar_qrcode_html(base64_qr: str):
    """Salva um HTML com o QR Code para abrir no navegador."""
    # Remove prefixo data:image/... se houver
    if "," in base64_qr:
        base64_qr = base64_qr.split(",")[1]

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>QR Code — WhatsApp</title>
  <style>
    body {{
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      min-height: 100vh; margin: 0;
      background: #111; color: #fff;
      font-family: sans-serif;
    }}
    img {{ width: 300px; height: 300px; background: white; padding: 16px; border-radius: 12px; }}
    h2 {{ margin-bottom: 8px; }}
    p {{ color: #aaa; font-size: 14px; }}
  </style>
</head>
<body>
  <h2>📲 Escaneie com o WhatsApp</h2>
  <p>Abra o WhatsApp → Menu → Dispositivos Conectados → Conectar dispositivo</p>
  <img src="data:image/png;base64,{base64_qr}" alt="QR Code"/>
  <p style="margin-top:16px; color:#666;">Após escanear, feche esta janela e rode: <code>python main.py</code></p>
</body>
</html>"""

    with open(QR_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)


def verificar_conexao():
    url = f"{EVOLUTION_API_URL}/instance/connectionState/{INSTANCE_NAME}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        return data.get("instance", {}).get("state", "unknown")
    except Exception:
        return "unknown"


def main():
    print("="*55)
    print("  🔧  SETUP — Evolution API + WhatsApp")
    print("="*55 + "\n")

    # 1. Aguarda API
    if not aguardar_api():
        print("❌ API não respondeu. Verifique se o Docker está rodando:")
        print("   docker compose up -d")
        sys.exit(1)

    # 2. Cria instância e pega QR
    data = criar_instancia()
    if not data:
        sys.exit(1)

    # Tenta extrair o QR Code de diferentes estruturas de resposta
    base64_qr = (
        data.get("qrcode", {}).get("base64") or
        data.get("base64") or
        data.get("qr") or
        ""
    )

    if not base64_qr:
        print("⚠️  QR Code não retornado automaticamente.")
        print(f"   Acesse manualmente: {EVOLUTION_API_URL}/docs")
        print(f"   Endpoint: GET /instance/connect/{INSTANCE_NAME}")
    else:
        salvar_qrcode_html(base64_qr)
        print(f"✅ QR Code salvo em: qrcode.html")
        print("   Abra esse arquivo no navegador e escaneie com o WhatsApp!\n")

        # Abre automaticamente no navegador
        import webbrowser
        webbrowser.open(f"file:///{os.path.abspath(QR_HTML_PATH)}")

    # 3. Aguarda conexão
    print("⏳ Aguardando você escanear o QR Code...")
    print("   (verificando a cada 5 segundos)\n")
    for _ in range(24):   # até 2 minutos
        time.sleep(5)
        estado = verificar_conexao()
        print(f"   Estado atual: {estado}")
        if estado == "open":
            print("\n✅ WhatsApp conectado com sucesso!")
            print("   Agora rode: python main.py")
            break
    else:
        print("\n⚠️  Tempo esgotado. Se já escaneou, tente: python main.py mesmo assim.")


if __name__ == "__main__":
    main()
