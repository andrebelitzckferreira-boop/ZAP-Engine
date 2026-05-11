import requests
from config.settings import EVOLUTION_API_URL, INSTANCE_NAME, HEADERS

def check_instance():
    url = f"{EVOLUTION_API_URL}/instance/fetchInstances"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        for inst in resp.json():
            if inst.get("instance", {}).get("instanceName") == INSTANCE_NAME:
                return {"state": "open"}
        return {"state": "close"}
    except Exception as e:
        return {"error": str(e)}

def send_text_message(telefone, mensagem):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    payload = {"number": telefone, "textMessage": {"text": mensagem}}
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except requests.exceptions.HTTPError:
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_image_message(telefone, url_imagem, legenda=""):
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{INSTANCE_NAME}"
    payload = {
        "number": telefone,
        "mediatype": "image",
        "media": url_imagem,
        "caption": legenda,
    }
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except requests.exceptions.HTTPError:
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_audio_message(telefone, url_audio):
    url = f"{EVOLUTION_API_URL}/message/sendWhatsAppAudio/{INSTANCE_NAME}"
    payload = {"number": telefone, "audio": url_audio}
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except requests.exceptions.HTTPError:
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def fetch_conversations():
    url = f"{EVOLUTION_API_URL}/chat/findChats/{INSTANCE_NAME}"
    try:
        resp = requests.post(url, json={}, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return []

def fetch_messages(remote_jid, limit=30):
    url = f"{EVOLUTION_API_URL}/chat/findMessages/{INSTANCE_NAME}"
    payload = {"where": {"key": {"remoteJid": remote_jid}}, "limit": limit}
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return []
