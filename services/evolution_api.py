import random
import time
import json

import requests

from config.settings import (
    EVOLUTION_API_URL,
    EVOLUTION_TYPING_ENABLED,
    HEADERS,
    INSTANCE_NAME,
)
from database import create_outbound_message, update_outbound_message, get_outbound_by_message_id


def _url(path: str) -> str:
    return f"{EVOLUTION_API_URL}{path}"


def _parse_json(resp):
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def resolve_whatsapp_number(telefone: str):
    payload = {"numbers": [telefone]}
    try:
        resp = requests.post(
            _url(f"/chat/whatsappNumbers/{INSTANCE_NAME}"),
            json=payload,
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = _parse_json(resp)
        if isinstance(data, list) and data:
            item = data[0] if isinstance(data[0], dict) else {}
            jid = str(item.get("jid") or "").strip()
            number = str(item.get("number") or "").strip()
            exists = bool(item.get("exists"))
            return {
                "success": True,
                "exists": exists,
                "jid": jid,
                "number": number,
                "raw": data,
            }
        return {"success": False, "error": "Resposta inesperada ao validar numero", "raw": data}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def check_instance():
    url = _url(f"/instance/connectionState/{INSTANCE_NAME}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = _parse_json(resp)
        state = data.get("instance", {}).get("state") or data.get("state") or "close"
        return {"state": state, "instance": {"state": state}, "raw": data}
    except Exception as exc:
        return {"state": "error", "error": str(exc), "instance": {"state": "error"}}


def send_presence(telefone: str, presence: str = "composing", delay_ms: int = 1200):
    if not EVOLUTION_TYPING_ENABLED:
        return {"success": False, "ignored": True}

    payload = {
        "number": telefone,
        "presence": presence,
        "delay": max(int(delay_ms), 0),
    }
    try:
        resp = requests.post(
            _url(f"/chat/sendPresence/{INSTANCE_NAME}"),
            json=payload,
            headers=HEADERS,
            timeout=8,
        )
        if resp.status_code == 404:
            return {"success": False, "ignored": True, "error": "Endpoint nao disponivel"}
        resp.raise_for_status()
        return {"success": True, "data": _parse_json(resp)}
    except Exception as exc:
        return {"success": False, "ignored": True, "error": str(exc)}


def simulate_typing(telefone: str, texto: str):
    delay_ms = min(max(len(texto) * random.randint(28, 42) + random.randint(600, 1400), 1200), 9000)
    send_presence(telefone, "composing", delay_ms)
    time.sleep(delay_ms / 1000)


def send_text_message(telefone, mensagem, typing: bool = False):
    if typing:
        simulate_typing(telefone, mensagem)

    url = _url(f"/message/sendText/{INSTANCE_NAME}")
    payloads = [
        {"number": telefone, "textMessage": {"text": mensagem}},
        {"number": telefone, "text": mensagem},
    ]
    last_error = None

    for payload in payloads:
        try:
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=20)
            data = _parse_json(resp)
            if resp.ok:
                tracking_id = None
                message_id = ""
                remote_jid = ""
                provider_status = ""
                if isinstance(data, dict):
                    message_id = str(data.get("key", {}).get("id") or data.get("id") or "").strip()
                    remote_jid = str(data.get("key", {}).get("remoteJid") or data.get("remoteJid") or "").strip()
                    provider_status = str(data.get("status") or "").strip()
                if message_id or remote_jid:
                    tracking_id = create_outbound_message(
                        telefone=telefone,
                        mensagem=mensagem,
                        origin="send_text",
                        provider_message_id=message_id,
                        provider_status=provider_status or "PENDING",
                        remote_jid=remote_jid,
                        provider_raw=data,
                    )
                return {"success": True, "data": data, "payload": payload, "tracking_id": tracking_id}
            last_error = f"HTTP {resp.status_code}: {str(data)[:500]}"
        except Exception as exc:
            last_error = str(exc)

    return {"success": False, "error": last_error or "Falha ao enviar mensagem"}


def send_image_message(telefone, url_imagem, legenda="", typing: bool = False):
    if typing and legenda:
        simulate_typing(telefone, legenda)

    payload = {
        "number": telefone,
        "mediatype": "image",
        "media": url_imagem,
        "caption": legenda,
    }
    try:
        resp = requests.post(
            _url(f"/message/sendMedia/{INSTANCE_NAME}"),
            json=payload,
            headers=HEADERS,
            timeout=25,
        )
        data = _parse_json(resp)
        resp.raise_for_status()
        if isinstance(data, dict):
            create_outbound_message(
                telefone=telefone,
                mensagem=legenda,
                origin="send_media",
                provider_message_id=str(data.get("key", {}).get("id") or data.get("id") or "").strip(),
                provider_status=str(data.get("status") or "PENDING").strip() or "PENDING",
                remote_jid=str(data.get("key", {}).get("remoteJid") or data.get("remoteJid") or "").strip(),
                provider_raw=data,
            )
        return {"success": True, "data": data}
    except requests.exceptions.HTTPError:
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def send_audio_message(telefone, url_audio):
    payload = {"number": telefone, "audio": url_audio}
    try:
        resp = requests.post(
            _url(f"/message/sendWhatsAppAudio/{INSTANCE_NAME}"),
            json=payload,
            headers=HEADERS,
            timeout=25,
        )
        data = _parse_json(resp)
        resp.raise_for_status()
        if isinstance(data, dict):
            create_outbound_message(
                telefone=telefone,
                mensagem="",
                origin="send_audio",
                provider_message_id=str(data.get("key", {}).get("id") or data.get("id") or "").strip(),
                provider_status=str(data.get("status") or "PENDING").strip() or "PENDING",
                remote_jid=str(data.get("key", {}).get("remoteJid") or data.get("remoteJid") or "").strip(),
                provider_raw=data,
            )
        return {"success": True, "data": data}
    except requests.exceptions.HTTPError:
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def fetch_conversations():
    try:
        resp = requests.post(_url(f"/chat/findMessages/{INSTANCE_NAME}"), json={}, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        msgs = _parse_json(resp)
        if not isinstance(msgs, list):
            msgs = msgs.get("messages", {}).get("records", []) if isinstance(msgs, dict) else []

        seen = {}
        for message in msgs:
            jid = message.get("key", {}).get("remoteJid", "")
            if not jid or "@g.us" in jid:
                continue
            if jid not in seen:
                numero = jid.replace("@s.whatsapp.net", "")
                timestamp = message.get("messageTimestamp", 0)
                if isinstance(timestamp, dict):
                    timestamp = timestamp.get("low", 0)
                seen[jid] = {
                    "id": jid,
                    "numero": numero,
                    "nome": message.get("pushName") or numero,
                    "nao_lidas": 0,
                    "ultimo": timestamp,
                }
        return list(seen.values())
    except Exception:
        return []


def fetch_messages(remote_jid, limit=30):
    payload = {"where": {"key": {"remoteJid": remote_jid}}, "limit": limit}
    try:
        resp = requests.post(_url(f"/chat/findMessages/{INSTANCE_NAME}"), json=payload, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = _parse_json(resp)
        if isinstance(data, list):
            return data
        return data.get("messages", {}).get("records", []) if isinstance(data, dict) else []
    except Exception:
        return []


def fetch_all_messages(filter_jid=None, limit=50):
    payload = {"where": {"key": {"remoteJid": filter_jid}}} if filter_jid else {}
    try:
        resp = requests.post(_url(f"/chat/findMessages/{INSTANCE_NAME}"), json=payload, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = _parse_json(resp)
        if isinstance(data, list):
            msgs = data
        elif isinstance(data, dict):
            msgs = data.get("messages", {}).get("records", []) or data.get("records", []) or []
        else:
            msgs = []
        if filter_jid:
            msgs = [m for m in msgs if m.get("key", {}).get("remoteJid", "") == filter_jid]
        return msgs[:limit]
    except Exception:
        return []
