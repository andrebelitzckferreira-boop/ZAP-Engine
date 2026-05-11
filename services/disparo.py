import time
import random
import json
from datetime import datetime

from database import (
    get_pending_contacts, update_contact_status,
    create_campaign, update_campaign_status,
    log_message, get_antiban_settings,
    get_today_count, increment_today_count
)
from services.evolution_api import send_text_message, send_image_message, send_audio_message
from utils.logger import log
from utils.formatter import formatar_telefone


def get_saudacao():
    hora = datetime.now().hour
    if 5 <= hora < 12:  return "Bom dia"
    if 12 <= hora < 18: return "Boa tarde"
    return "Boa noite"


def _delay_humano(seg):
    v = seg * 0.25
    return max(seg + random.uniform(-v, v), 0.5)


def executar_campanha(nome, mensagens, lote_tamanho, delay_lote_seg, delay_msg_seg,
                      media_url=None, media_type=None, daily_limit=0):
    """
    mensagens: lista de strings (até 5). Para cada contato escolhe 1 aleatório.
    Suporta variáveis: {nome}, {saudacao}
    media_type: 'image' | 'audio' | None
    """
    if isinstance(mensagens, str):
        mensagens = [mensagens]

    campaign_id = create_campaign(
        nome, mensagens, lote_tamanho, delay_lote_seg, delay_msg_seg,
        media_url=media_url, media_type=media_type, daily_limit=daily_limit
    )
    update_campaign_status(campaign_id, "em_andamento")

    antiban = get_antiban_settings()
    limite_dia = daily_limit or antiban.get("daily_limit", 0)
    warmup = antiban.get("warmup_mode", 0)

    if warmup:
        dia = antiban.get("warmup_day", 1)
        limite_dia = min(20 * dia, limite_dia or 9999)
        log(f"🔥 Modo aquecimento ativo — limite hoje: {limite_dia} msgs")

    contatos = get_pending_contacts()
    total = len(contatos)
    if total == 0:
        log("⚠️  Nenhum contato pendente.")
        update_campaign_status(campaign_id, "concluida")
        return campaign_id

    log(f"\n🚀 Campanha '{nome}' — {total} contatos | lote {lote_tamanho} | delay {delay_msg_seg}s/{delay_lote_seg}s")

    enviados = erros = 0
    lote_num = 0
    saudacao = get_saudacao()

    for i in range(0, total, lote_tamanho):
        lote = contatos[i: i + lote_tamanho]
        lote_num += 1
        log(f"\n── Lote {lote_num} ──────────────────────────────")

        for idx, contato in enumerate(lote):
            # Anti-ban: limite diário
            if limite_dia > 0 and get_today_count() >= limite_dia:
                log(f"⛔ Limite diário de {limite_dia} msgs atingido. Pausando campanha.")
                update_campaign_status(campaign_id, "pausada")
                return campaign_id

            telefone = formatar_telefone(contato["telefone"])
            nome_c = contato["nome"] or "cliente"
            msg = random.choice(mensagens)
            msg = msg.replace("{nome}", nome_c).replace("{saudacao}", saudacao)

            log(f"  📤 {nome_c} ({telefone})")

            # Envia mídia primeiro se houver
            if media_url and media_type == "image":
                res = send_image_message(telefone, media_url, msg)
            elif media_url and media_type == "audio":
                send_text_message(telefone, msg)  # texto + áudio
                res = send_audio_message(telefone, media_url)
            else:
                res = send_text_message(telefone, msg)

            if res["success"]:
                update_contact_status(contato["id"], "enviado")
                log_message(campaign_id, contato["id"], "enviado")
                increment_today_count()
                enviados += 1
                log(f"  ✅ OK")
            else:
                update_contact_status(contato["id"], "erro")
                log_message(campaign_id, contato["id"], "erro", res["error"])
                erros += 1
                log(f"  ❌ {res['error']}")

            if idx < len(lote) - 1:
                espera = _delay_humano(delay_msg_seg)
                log(f"  ⏳ {espera:.1f}s...")
                time.sleep(espera)

        if i + lote_tamanho < total:
            log(f"\n⏸️  Lote {lote_num} concluído. Pausa de {delay_lote_seg}s...")
            for r in range(delay_lote_seg, 0, -1):
                print(f"\r  ⏳ {r}s...   ", end="", flush=True)
                time.sleep(1)
            print()

    update_campaign_status(campaign_id, "concluida")
    log(f"\n🏁 Concluída! ✅ {enviados} enviados | ❌ {erros} erros")
    return campaign_id
