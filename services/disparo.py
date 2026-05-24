import random
import threading
import time
from datetime import datetime, timedelta

from config.settings import (
    DEFAULT_BATCH_PAUSE_MAX_SECONDS,
    DEFAULT_BATCH_PAUSE_MIN_SECONDS,
    DEFAULT_DELAY_MAX_SECONDS,
    DEFAULT_DELAY_MIN_SECONDS,
    DEFAULT_HOURLY_LIMIT,
    DUPLICATE_COOLDOWN_HOURS,
    SEND_WINDOW_END,
    SEND_WINDOW_START,
)
from database import (
    create_campaign,
    get_antiban_settings,
    get_current_hour_count,
    get_pending_contacts,
    get_today_count,
    increment_today_count,
    log_message,
    update_campaign_status,
    update_contact_status,
    was_sent_recently,
)
from services.evolution_api import (
    check_instance,
    send_audio_message,
    send_image_message,
    send_text_message,
)
from utils.formatter import formatar_telefone
from utils.logger import log


class CampaignControl:
    def __init__(self):
        self._lock = threading.Lock()
        self.paused = False
        self.stopped = False
        self.current_campaign_id = None

    def reset(self, campaign_id=None):
        with self._lock:
            self.paused = False
            self.stopped = False
            self.current_campaign_id = campaign_id

    def pause(self):
        with self._lock:
            self.paused = True

    def resume(self):
        with self._lock:
            self.paused = False

    def stop(self):
        with self._lock:
            self.stopped = True
            self.paused = False

    def snapshot(self):
        with self._lock:
            return {
                "paused": self.paused,
                "stopped": self.stopped,
                "campaign_id": self.current_campaign_id,
            }


def get_saudacao():
    hora = datetime.now().hour
    if 5 <= hora < 12:
        return "Bom dia"
    if 12 <= hora < 18:
        return "Boa tarde"
    return "Boa noite"


def _random_delay(min_seconds: int, max_seconds: int) -> float:
    min_seconds = max(int(min_seconds), 1)
    max_seconds = max(int(max_seconds), min_seconds)
    mode = min_seconds + (max_seconds - min_seconds) * random.uniform(0.35, 0.65)
    return random.triangular(min_seconds, max_seconds, mode)


def _parse_hhmm(value: str, fallback: str):
    try:
        hour, minute = (value or fallback).split(":")[:2]
        return int(hour), int(minute)
    except Exception:
        hour, minute = fallback.split(":")
        return int(hour), int(minute)


def _seconds_until_send_window() -> int:
    start_h, start_m = _parse_hhmm(SEND_WINDOW_START, "08:00")
    end_h, end_m = _parse_hhmm(SEND_WINDOW_END, "18:00")
    now = datetime.now()
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if start <= now <= end:
        return 0
    if now < start:
        return int((start - now).total_seconds())
    tomorrow_start = start + timedelta(days=1)
    return int((tomorrow_start - now).total_seconds())


def _sleep_interruptible(seconds: float, control: CampaignControl | None, campaign_id: int | None = None) -> bool:
    end = time.time() + max(float(seconds), 0)
    while time.time() < end:
        if control:
            state = control.snapshot()
            if state["stopped"]:
                if campaign_id:
                    update_campaign_status(campaign_id, "parada")
                return False
            while state["paused"]:
                if campaign_id:
                    update_campaign_status(campaign_id, "pausada")
                time.sleep(1)
                state = control.snapshot()
                if state["stopped"]:
                    if campaign_id:
                        update_campaign_status(campaign_id, "parada")
                    return False
            if campaign_id:
                update_campaign_status(campaign_id, "em_andamento")
        remaining = end - time.time()
        if remaining > 0:
            time.sleep(min(1, remaining))
    return True


def _wait_for_limits(policy: dict, campaign_id: int, control: CampaignControl | None) -> bool:
    wait_window = _seconds_until_send_window()
    if wait_window > 0:
        log(f"Fora do horario de envio. Aguardando {wait_window // 60} min.")
        if not _sleep_interruptible(wait_window, control, campaign_id):
            return False

    hourly_limit = int(policy.get("hourly_limit") or 0)
    if hourly_limit > 0 and get_current_hour_count() >= hourly_limit:
        now = datetime.now()
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        wait = max(int((next_hour - now).total_seconds()), 60)
        log(f"Limite horario de {hourly_limit} envios atingido. Retomando na proxima hora.")
        return _sleep_interruptible(wait, control, campaign_id)
    return True


def _choose_message(mensagens: list[str], last_message: str | None) -> str:
    if len(mensagens) <= 1:
        return mensagens[0]
    choices = [m for m in mensagens if m != last_message] or mensagens
    return random.choice(choices)


def executar_campanha(
    nome,
    mensagens=None,
    lote_tamanho=10,
    delay_lote_seg=1800,
    delay_msg_seg=45,
    media_url=None,
    media_type=None,
    daily_limit=0,
    hourly_limit=None,
    delay_min_seg=None,
    delay_max_seg=None,
    pause_every=None,
    pause_min_seg=None,
    pause_max_seg=None,
    duplicate_cooldown_hours=None,
    control: CampaignControl | None = None,
    mensagem=None,
):
    if mensagens is None:
        mensagens = [mensagem] if mensagem else []
    if isinstance(mensagens, str):
        mensagens = [mensagens]
    mensagens = [m.strip() for m in mensagens if str(m or "").strip()]
    if not mensagens:
        raise ValueError("Informe pelo menos uma mensagem.")

    antiban = get_antiban_settings()
    delay_min = int(delay_min_seg or antiban.get("delay_min_seg") or DEFAULT_DELAY_MIN_SECONDS)
    delay_max = int(delay_max_seg or antiban.get("delay_max_seg") or DEFAULT_DELAY_MAX_SECONDS)
    if delay_max < delay_min:
        delay_min, delay_max = delay_max, delay_min

    policy = {
        "daily_limit": int(daily_limit or antiban.get("daily_limit") or 0),
        "hourly_limit": int(hourly_limit or antiban.get("hourly_limit") or DEFAULT_HOURLY_LIMIT),
        "delay_min_seg": delay_min,
        "delay_max_seg": delay_max,
        "pause_every": int(pause_every or antiban.get("pause_every") or lote_tamanho or 10),
        "pause_min_seg": int(pause_min_seg or antiban.get("pause_min_seg") or DEFAULT_BATCH_PAUSE_MIN_SECONDS),
        "pause_max_seg": int(pause_max_seg or antiban.get("pause_max_seg") or DEFAULT_BATCH_PAUSE_MAX_SECONDS),
        "duplicate_cooldown_hours": int(
            duplicate_cooldown_hours
            or antiban.get("duplicate_cooldown_hours")
            or DUPLICATE_COOLDOWN_HOURS
        ),
    }

    if antiban.get("warmup_mode"):
        warmup_day = int(antiban.get("warmup_day") or 1)
        warmup_limit = min(max(warmup_day, 1) * 20, policy["daily_limit"] or 9999)
        policy["daily_limit"] = warmup_limit
        log(f"Modo aquecimento ativo. Limite de hoje: {warmup_limit} mensagens.")

    campaign_id = create_campaign(
        nome,
        mensagens,
        lote_tamanho,
        delay_lote_seg,
        delay_msg_seg,
        media_url=media_url,
        media_type=media_type,
        daily_limit=policy["daily_limit"],
        hourly_limit=policy["hourly_limit"],
        delay_min_seg=policy["delay_min_seg"],
        delay_max_seg=policy["delay_max_seg"],
        pause_every=policy["pause_every"],
        pause_min_seg=policy["pause_min_seg"],
        pause_max_seg=policy["pause_max_seg"],
        duplicate_cooldown_hours=policy["duplicate_cooldown_hours"],
    )
    if control:
        control.reset(campaign_id)
    update_campaign_status(campaign_id, "em_andamento")

    contatos = [dict(c) for c in get_pending_contacts()]
    total = len(contatos)
    if not total:
        log("Nenhum contato pendente.")
        update_campaign_status(campaign_id, "concluida")
        return campaign_id

    log(
        f"Campanha '{nome}' iniciada: {total} contatos, "
        f"delay {delay_min}-{delay_max}s, limite/h {policy['hourly_limit']}, "
        f"limite/dia {policy['daily_limit'] or 'ilimitado'}."
    )

    enviados = erros = ignorados = 0
    sent_since_pause = 0
    last_message = None
    saudacao = get_saudacao()

    for index, contato in enumerate(contatos, start=1):
        if control and control.snapshot()["stopped"]:
            update_campaign_status(campaign_id, "parada")
            log("Campanha parada pelo painel.")
            return campaign_id

        if not _wait_for_limits(policy, campaign_id, control):
            return campaign_id

        if policy["daily_limit"] > 0 and get_today_count() >= policy["daily_limit"]:
            log(f"Limite diario de {policy['daily_limit']} envios atingido. Campanha pausada.")
            update_campaign_status(campaign_id, "pausada")
            if control:
                control.pause()
            return campaign_id

        if was_sent_recently(contato, policy["duplicate_cooldown_hours"]):
            update_contact_status(contato["id"], "ignorado")
            log_message(campaign_id, contato["id"], "ignorado", "cooldown de reenvio ativo")
            ignorados += 1
            log(f"Ignorado por cooldown: {contato.get('nome') or contato['telefone']}")
            continue

        telefone = formatar_telefone(contato["telefone"])
        nome_contato = contato.get("nome") or "cliente"
        msg = _choose_message(mensagens, last_message)
        last_message = msg
        msg = msg.replace("{nome}", nome_contato).replace("{saudacao}", saudacao)
        if contato.get("cidade"):
            msg = msg.replace("{cidade}", contato["cidade"])

        log(f"Enviando {index}/{total}: {nome_contato} ({telefone})")

        state = check_instance()
        if state.get("state") != "open":
            log(f"WhatsApp desconectado ({state.get('state')}). Campanha pausada.")
            update_campaign_status(campaign_id, "pausada")
            if control:
                control.pause()
            return campaign_id

        if media_url and media_type == "image":
            result = send_image_message(telefone, media_url, msg, typing=True)
        elif media_url and media_type == "audio":
            text_result = send_text_message(telefone, msg, typing=True)
            result = send_audio_message(telefone, media_url) if text_result.get("success") else text_result
        else:
            result = send_text_message(telefone, msg, typing=True)

        if result.get("success"):
            update_contact_status(contato["id"], "enviado")
            log_message(campaign_id, contato["id"], "enviado", mensagem=msg)
            increment_today_count()
            enviados += 1
            sent_since_pause += 1
            log("OK")
        else:
            error = result.get("error", "erro desconhecido")
            update_contact_status(contato["id"], "erro", last_error=error)
            log_message(campaign_id, contato["id"], "erro", error, mensagem=msg)
            erros += 1
            log(f"Erro: {error}")

        remaining = index < total
        if remaining and sent_since_pause >= policy["pause_every"]:
            pause = _random_delay(policy["pause_min_seg"], policy["pause_max_seg"])
            sent_since_pause = 0
            log(f"Pausa longa apos bloco: {pause / 60:.1f} min.")
            if not _sleep_interruptible(pause, control, campaign_id):
                return campaign_id
        elif remaining:
            delay = _random_delay(policy["delay_min_seg"], policy["delay_max_seg"])
            log(f"Aguardando {delay:.1f}s antes do proximo contato.")
            if not _sleep_interruptible(delay, control, campaign_id):
                return campaign_id

    update_campaign_status(campaign_id, "concluida")
    log(f"Campanha concluida. Enviados: {enviados} | Erros: {erros} | Ignorados: {ignorados}")
    return campaign_id
