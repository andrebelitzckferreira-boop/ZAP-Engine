import hashlib
import json
import os
import random
import re
import unicodedata
from functools import lru_cache
from datetime import datetime, timedelta
from pathlib import Path

import requests

from config.settings import APP_DIR, GROQ_API_KEY, GROQ_MODEL

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
COMERCIAL_CONFIG_PATH = Path(APP_DIR) / "data" / "ia_comercial_config.json"


@lru_cache(maxsize=1)
def _carregar_config_comercial() -> dict:
    try:
        with open(COMERCIAL_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _cfg(secao: str, chave: str, default=None):
    valor = _carregar_config_comercial().get(secao, {}).get(chave, default)
    return default if valor in ("", None) else valor


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9@.#/+\- ]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _indice_estavel(chave: str, tamanho: int) -> int:
    if tamanho <= 1:
        return 0
    digest = hashlib.sha1(chave.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % tamanho


def _escolher_variante(itens: list[str], chave: str, ultimo_texto: str = "") -> str:
    opcoes = [str(item).strip() for item in (itens or []) if str(item).strip()]
    if not opcoes:
        return ""
    if ultimo_texto:
        ultimo_norm = _normalizar_texto(ultimo_texto)
        opcoes_sem_repeticao = [item for item in opcoes if _normalizar_texto(item) != ultimo_norm]
        if opcoes_sem_repeticao:
            opcoes = opcoes_sem_repeticao
    return opcoes[_indice_estavel(chave, len(opcoes))]

PROMPT_MESTRE = """Voce atende pelo WhatsApp como consultor comercial de protecao veicular no Brasil.

Objetivo: conversar de forma natural, curta e consultiva, entender o veiculo, comparar seguro/protecao quando fizer sentido e conduzir para o proximo passo.

Regras de estilo:
- Portugues brasileiro simples, educado e direto.
- Respostas curtas, normalmente 1 a 3 linhas.
- Uma pergunta por vez.
- Sem texto grande, sem lista longa e sem tom de robo.
- Nunca responda de forma engessada ou com a mesma abertura repetida.
- Se fizer sentido, use respostas em duas partes curtas, nao textao unico.
- Nao pressionar. Se a pessoa disser que nao tem interesse, respeite e deixe a porta aberta.
- Nao prometa valor fechado sem modelo, ano, versao e cidade.
- Quando pedirem valor, peca dados do veiculo ou diga que depende da FIPE/perfil.
- Se o lead estiver frio, seja leve e curioso.
- Se o lead estiver morno, construa confianca.
- Se o lead estiver quente, seja objetivo e conduza para simulacao e fechamento.
- Se surgir "caro", responda com empatia e ofereca uma opcao mais enxuta.
- Se surgir "vou pensar", respeite e ofereca um resumo curto sem pressionar.

Fluxo comercial:
1. Primeiro contato: cumprimente e pergunte se ja usa seguro/protecao.
2. Se ja possui: pergunte se esta satisfeito com valor e cobertura.
3. Se nao possui: explique em uma frase que a protecao costuma ser mais acessivel e ajuda em roubo, furto, colisao e assistencia.
4. Coleta: pedir modelo, ano, versao e cidade.
4. Se houver placa, peça a placa primeiro para consultar o veículo correto.
5. Se a placa não vier, peça modelo, ano, versão e cidade.
6. Com veiculo informado: diga que vai consultar pela FIPE e preparar uma condicao.
7. Sempre conduza para um proximo passo claro.
8. Sempre ofereca caminho simples com 1, 2 ou 3 quando isso aumentar resposta.
9. Mantenha tom de consultor real, nao de robo.

Estagios esperados:
- lead_frio: abrir conversa leve.
- interessado: pedir veiculo ou confirmar dados.
- ja_possui_seguro: comparar valor/cobertura sem atacar concorrente.
- sem_interesse: agradecer e encerrar com abertura.
- caro: acolher objeção e oferecer versão mais enxuta.
- vou_pensar: respeitar e deixar um resumo curto.
- pediu_valor: pedir dados para cotar.
- informou_veiculo: confirmar dados e preparar FIPE/proposta.
- parado: reengajar com leveza.

Se a pessoa pedir humano, atendente, suporte ou consultor, responda apenas ##HUMANO##.
"""

MSG_BOAS_VINDAS = (
    "Oi, tudo bem?\n"
    "Sou da equipe comercial de protecao veicular. Posso te ajudar com uma cotacao?"
)

MSG_REENGAJAMENTO_TEMPLATES = [
    "Oi {nome}, tudo bem? Ficou alguma duvida sobre a protecao?",
    "{nome}, passando rapidinho: ainda quer que eu veja uma condicao pro seu veiculo?",
    "Oi {nome}! Posso te ajudar a comparar valor e cobertura sem compromisso.",
    "Tudo certo por ai? Se quiser, ainda consigo consultar uma cotacao pra voce.",
]

PALAVRAS_HUMANO = [
    "humano",
    "atendente",
    "consultor",
    "falar com andre",
    "falar com andré",
    "suporte",
    "transferir",
    "pessoa real",
]


def get_msg_reengajamento(nome: str = "") -> str:
    template = random.choice(MSG_REENGAJAMENTO_TEMPLATES)
    return template.replace("{nome}", nome or "").replace("  ", " ").strip()


def is_horario_atendimento() -> bool:
    now = datetime.now()
    if now.weekday() < 5:
        return 8 <= now.hour < 18
    if now.weekday() == 5:
        return 8 <= now.hour < 12
    return False


def get_msg_fora_horario() -> str:
    return random.choice(
        [
            "Oi! Recebi sua mensagem. Nosso atendimento volta no horario comercial e ja te respondo certinho.",
            "Opa, vi sua mensagem aqui. Assim que o atendimento abrir eu te retorno, combinado?",
            "Mensagem recebida. No horario comercial eu continuo com voce por aqui.",
        ]
    )


def is_numero_novo(conv: dict) -> bool:
    try:
        hist = json.loads(conv.get("historico_json", "[]"))
    except Exception:
        hist = []
    return len(hist) == 0


def is_inativo(conv: dict, dias: int = 2) -> bool:
    ultima = conv.get("ultima_msg", "")
    if not ultima:
        return False
    try:
        dt = datetime.fromisoformat(str(ultima).replace("T", " ").split(".")[0])
        return datetime.now() - dt > timedelta(days=dias)
    except Exception:
        return False


def checar_transferencia(mensagem: str) -> bool:
    msg = (mensagem or "").lower().strip()
    return any(p in msg for p in PALAVRAS_HUMANO)


def classificar_estagio(mensagem: str, historico: list | None = None) -> str:
    texto = " ".join(
        [mensagem or ""]
        + [m.get("content", "") for m in (historico or [])[-8:] if isinstance(m, dict)]
    ).lower()

    if any(p in texto for p in ["nao tenho interesse", "não tenho interesse", "nao quero", "não quero", "para de mandar"]):
        return "sem_interesse"
    if any(p in texto for p in ["tenho seguro", "ja tenho seguro", "já tenho seguro", "tenho protecao", "tenho proteção"]):
        return "ja_possui_seguro"
    if any(p in texto for p in ["valor", "quanto", "preco", "preço", "mensalidade", "custa", "cotacao", "cotação"]):
        return "pediu_valor"
    if detectar_dados_veiculo(historico or [{"content": mensagem or ""}]):
        dados = detectar_dados_veiculo((historico or []) + [{"content": mensagem or ""}])
        if dados.get("modelo") or dados.get("marca") or dados.get("ano"):
            return "informou_veiculo"
    if any(p in texto for p in ["sim", "tenho interesse", "quero", "pode", "manda", "me chama"]):
        return "interessado"
    return "lead_frio"


def _fallback_response(estagio: str, nome_cliente: str = "") -> str:
    nome = f"{nome_cliente}, " if nome_cliente else ""
    respostas = {
        "sem_interesse": f"Tranquilo, {nome}obrigado pelo retorno. Se quiser comparar valor ou cobertura depois, fico a disposicao.",
        "ja_possui_seguro": f"Perfeito, {nome}entao voce ja entende a importancia. Hoje o valor e a cobertura estao tranquilos pra voce?",
        "pediu_valor": f"Consigo ver pra voce. Me passa modelo, ano, versao e cidade do veiculo?",
        "informou_veiculo": f"Boa. Com esses dados eu ja consigo consultar pela FIPE e preparar uma condicao certinha pra voce.",
        "interessado": f"Show. Qual e o modelo, ano e versao do veiculo pra eu consultar aqui?",
        "parado": get_msg_reengajamento(nome_cliente),
        "lead_frio": f"Oi, {nome}tudo bem? Hoje voce ja usa seguro ou protecao veicular?",
    }
    return respostas.get(estagio, respostas["lead_frio"])


def extrair_contexto_cliente(historico: list, nome_whatsapp: str = "") -> str:
    contexto = []
    if nome_whatsapp:
        contexto.append(f"Nome no WhatsApp: {nome_whatsapp}")

    dados = detectar_dados_veiculo(historico)
    if dados:
        contexto.append(f"Dados detectados do veiculo: {dados}")

    texto = " ".join([m.get("content", "") for m in historico if isinstance(m, dict)]).lower()
    if any(p in texto for p in ["uber", "99", "aplicativo", "app"]):
        contexto.append("Perfil: motorista de aplicativo")
    elif any(p in texto for p in ["taxi", "táxi"]):
        contexto.append("Perfil: taxista")

    return "\n".join(contexto)


def gerar_resposta(
    mensagem: str,
    historico: list,
    api_key: str | None = None,
    prompt_extra: str = "",
    nome_cliente: str = "",
    palavras_humano: str = "",
) -> str:
    if checar_transferencia(mensagem, palavras_humano):
        return "##HUMANO##"

    if not is_horario_atendimento():
        return get_msg_fora_horario()

    estagio = classificar_estagio(mensagem, historico)
    key = api_key or GROQ_API_KEY
    if not key:
        return _fallback_response(estagio, nome_cliente)

    contexto_cliente = extrair_contexto_cliente(historico, nome_cliente)
    system = PROMPT_MESTRE + f"\n\nEstagio atual do lead: {estagio}."
    instrucoes_estagio = _instrucoes_estagio(estagio, nome_cliente, historico)
    if instrucoes_estagio:
        system += f"\n\nInstrucao comercial do estagio:\n{instrucoes_estagio}"
    if contexto_cliente:
        system += f"\n\nContexto do cliente:\n{contexto_cliente}"
    if prompt_extra:
        system += f"\n\nContexto comercial extra:\n{prompt_extra}"

    messages = [{"role": "system", "content": system}]
    messages += [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in (historico or [])[-16:]
        if isinstance(m, dict) and m.get("content")
    ]
    messages.append({"role": "user", "content": mensagem})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.78,
                "top_p": 0.92,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.2,
            },
            timeout=20,
        )
        resp.raise_for_status()
        resposta = resp.json()["choices"][0]["message"]["content"].strip()
        return _limpar_resposta(resposta) or _fallback_response(estagio, nome_cliente)
    except Exception as exc:
        print(f"Erro Groq: {exc}")
        return _fallback_response(estagio, nome_cliente)


def _limpar_resposta(resposta: str) -> str:
    resposta = resposta.replace("```", "").strip()
    linhas = [linha.strip() for linha in resposta.splitlines() if linha.strip()]
    if len(linhas) > 3:
        linhas = linhas[:3]
    texto = "\n".join(linhas).strip()
    return texto[:420]


DADOS_COTACAO_KEYS = ["marca", "modelo", "ano", "categoria"]


def detectar_dados_veiculo(historico: list) -> dict:
    texto = " ".join([m.get("content", "") for m in historico if isinstance(m, dict)]).lower()
    dados = {}

    if any(p in texto for p in ["uber", "99", "aplicativo", "app"]):
        dados["categoria"] = "uber"
    elif any(p in texto for p in ["taxi", "táxi"]):
        dados["categoria"] = "taxi"
    elif any(p in texto for p in ["moto", "motocicleta"]):
        dados["categoria"] = "moto"
    elif any(p in texto for p in ["utilitario", "utilitário", "van", "sprinter", "master"]):
        dados["categoria"] = "utilitario"
    else:
        dados["categoria"] = "passeio"

    anos = re.findall(r"\b(199[5-9]|20[0-2][0-9])\b", texto)
    if anos:
        dados["ano"] = int(anos[-1])

    marcas = {
        "chevrolet": ["gm", "chevrolet", "onix", "celta", "corsa", "spin", "tracker", "cruze", "prisma", "cobalt"],
        "volkswagen": ["vw", "volkswagen", "gol", "polo", "virtus", "t-cross", "saveiro", "voyage", "fox"],
        "fiat": ["fiat", "uno", "palio", "siena", "argo", "cronos", "mobi", "strada", "toro"],
        "ford": ["ford", "ka", "ecosport", "ranger", "fiesta", "focus"],
        "toyota": ["toyota", "corolla", "hilux", "yaris", "etios", "sw4"],
        "honda": ["honda", "civic", "hrv", "hr-v", "crv", "fit", "city"],
        "hyundai": ["hyundai", "hb20", "creta", "tucson"],
        "renault": ["renault", "kwid", "sandero", "duster", "logan", "captur"],
        "nissan": ["nissan", "kicks", "frontier", "versa", "march"],
        "jeep": ["jeep", "renegade", "compass", "commander"],
        "peugeot": ["peugeot", "208", "2008", "308"],
        "kia": ["kia", "sportage", "cerato"],
    }

    for marca, palavras in marcas.items():
        if any(p in texto for p in palavras):
            dados["marca"] = marca.capitalize()
            for palavra in palavras[1:]:
                if palavra in texto:
                    dados["modelo"] = palavra.upper() if palavra in {"hb20", "hr-v"} else palavra.capitalize()
                    break
            break

    return dados


def deve_calcular_cotacao(historico: list) -> bool:
    dados = detectar_dados_veiculo(historico)
    return ("marca" in dados or "modelo" in dados) and "ano" in dados


def gerar_cotacao_automatica(historico: list, nome_cliente: str = "") -> str | None:
    if not deve_calcular_cotacao(historico):
        return None

    dados = detectar_dados_veiculo(historico)
    marca = dados.get("marca", "")
    modelo = dados.get("modelo", marca)
    ano = dados.get("ano", 2020)
    categoria = dados.get("categoria", "passeio")

    try:
        from services.fipe_service import consultar_fipe, extrair_valor_numerico, montar_proposta_texto

        tipo_fipe = "motos" if categoria == "moto" else "carros"
        resultado = consultar_fipe(marca, modelo, ano, tipo_fipe)
        if resultado and "Valor" in resultado:
            valor = extrair_valor_numerico(resultado["Valor"])
            return montar_proposta_texto(
                nome_cliente or "voce",
                resultado.get("Marca", marca),
                resultado.get("Modelo", modelo),
                resultado.get("AnoModelo", ano),
                valor,
                categoria,
            )
    except Exception as exc:
        print(f"Erro cotacao automatica: {exc}")
    return None


def get_mensagens_aquecimento(tipo: str = "abertura") -> list:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "mensagens_aquecimento.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(tipo, data.get("abertura", []))
    except Exception:
        return []


def get_mensagem_aleatoria(tipo: str = "abertura") -> str:
    msgs = get_mensagens_aquecimento(tipo)
    return random.choice(msgs) if msgs else ""


def get_msg_abertura(nome: str = "", numero: str = "", historico: list | None = None) -> str:
    temperatura = classificar_temperatura_lead(_coletar_ultima_mensagem_usuario(historico), historico)
    if not historico:
        return (
            "Oi 😄\n"
            "Sou André Belitzck Consultor Especialista da Simples Brasil Proteção Veicular.\n\n"
            "Pra facilitar aqui rapidinho 👇\n\n"
            "1️⃣ Cotação\n"
            "2️⃣ Dúvidas\n"
            "3️⃣ Assistência 24hrs\n"
            "4️⃣ Falar comigo"
        )

    templates = _cfg_lista_por_temperatura(
        "templates_abertura",
        temperatura,
        [
            "Oi, {nome}! Tudo bem? Hoje voce ja protege seu veiculo?",
            "Ola, {nome}. Rapidinho: seu carro hoje ja tem seguro ou protecao?",
            "Fala, {nome}! Hoje voce usa seguro tradicional ou protecao veicular?",
            "Oi, {nome}. Posso te fazer uma pergunta rapida sobre seu veiculo?",
        ],
        fallback="templates_lead_frio",
    )
    ultimo = _coletar_ultimo_assistente(historico)
    chave = f"abertura:{nome}:{numero}:{datetime.now().date().isoformat()}"
    return _escolher_variante(templates, chave, ultimo).replace("{nome}", nome or "voce").strip()


def _fallback_response(estagio: str, nome_cliente: str = "", historico: list | None = None) -> str:
    nome = f"{nome_cliente}, " if nome_cliente else ""
    respostas = {
        "sem_interesse": f"Tranquilo, {nome}obrigado pelo retorno. Se quiser comparar valor ou cobertura depois, fico a disposicao.",
        "ja_possui_seguro": f"Perfeito, {nome}entao voce ja entende a importancia. Hoje o valor e a cobertura estao tranquilos pra voce?",
        "caro": get_msg_objeccao_caro(nome_cliente),
        "vou_pensar": get_msg_objeccao_vou_pensar(nome_cliente),
        "pediu_valor": f"Consigo ver pra voce. Me passa modelo, ano, versao e cidade do veiculo?",
        "informou_veiculo": f"Boa. Com esses dados eu ja consigo consultar pela FIPE e preparar uma condicao certinha pra voce.",
        "interessado": f"Show. Qual e o modelo, ano e versao do veiculo pra eu consultar aqui?",
        "parado": get_msg_reengajamento(nome_cliente),
        "lead_frio": get_msg_abertura(nome_cliente, historico=historico),
    }
    return respostas.get(estagio, respostas["lead_frio"])


def gerar_resposta(
    mensagem: str,
    historico: list,
    api_key: str | None = None,
    prompt_extra: str = "",
    nome_cliente: str = "",
    palavras_humano: str = "",
) -> str:
    if checar_transferencia(mensagem, palavras_humano):
        return "##HUMANO##"

    if not is_horario_atendimento():
        return get_msg_fora_horario()

    estagio = classificar_estagio(mensagem, historico)
    temperatura = classificar_temperatura_lead(mensagem, historico)
    key = api_key or GROQ_API_KEY
    if not key:
        return _fallback_response(estagio, nome_cliente, historico)

    contexto_cliente = extrair_contexto_cliente(historico, nome_cliente)
    system = PROMPT_MESTRE + f"\n\nEstagio atual do lead: {estagio}."
    system += f"\nTemperatura do lead: {temperatura}."
    instrucoes_estagio = _instrucoes_estagio(estagio, nome_cliente, historico)
    if instrucoes_estagio:
        system += f"\n\nInstrucao comercial do estagio:\n{instrucoes_estagio}"
    instrucoes_temperatura = _instrucoes_temperatura(temperatura)
    if instrucoes_temperatura:
        system += f"\n\nInstrucao de temperatura:\n{instrucoes_temperatura}"
    if contexto_cliente:
        system += f"\n\nContexto do cliente:\n{contexto_cliente}"
    if prompt_extra:
        system += f"\n\nContexto comercial extra:\n{prompt_extra}"

    messages = [{"role": "system", "content": system}]
    messages += [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in (historico or [])[-16:]
        if isinstance(m, dict) and m.get("content")
    ]
    messages.append({"role": "user", "content": mensagem})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.8,
                "top_p": 0.92,
                "frequency_penalty": 0.45,
                "presence_penalty": 0.2,
            },
            timeout=20,
        )
        resp.raise_for_status()
        resposta = resp.json()["choices"][0]["message"]["content"].strip()
        return _limpar_resposta(resposta) or _fallback_response(estagio, nome_cliente, historico)
    except Exception as exc:
        print(f"Erro Groq: {exc}")
        return _fallback_response(estagio, nome_cliente, historico)


# ---------------------------------------------------------------------------
# Camada humana final
# Esta eh a ultima camada carregada para garantir override real.
# ---------------------------------------------------------------------------


def _legacy_get_msg_abertura(nome: str = "", numero: str = "", historico: list | None = None) -> str:
    temperatura = classificar_temperatura_lead(_coletar_ultima_mensagem_usuario(historico), historico)
    if not historico:
        temperatura = "frio"
    templates = _cfg_lista_por_temperatura(
        "templates_abertura",
        temperatura,
        [
            "Oi, {nome}! Tudo bem? Hoje voce ja protege seu veiculo?",
            "Ola, {nome}. Rapidinho: seu carro hoje ja tem seguro ou protecao?",
            "Fala, {nome}! Hoje voce usa seguro tradicional ou protecao veicular?",
            "Oi, {nome}. Posso te fazer uma pergunta rapida sobre seu veiculo?",
        ],
        fallback="templates_lead_frio",
    )
    ctas = _cfg_lista_por_temperatura(
        "ctas",
        temperatura,
        [
            "Hoje voce ja protege seu veiculo?\n1️⃣ Sim\n2️⃣ Nao",
            "Seu carro hoje tem alguma protecao?\n1️⃣ Sim\n2️⃣ Nao",
        ],
        fallback="ctas_lead_frio",
    )
    ultimo = _coletar_ultimo_assistente(historico)
    chave = f"abertura:{nome}:{numero}:{datetime.now().date().isoformat()}"
    msg = _escolher_variante(templates, chave, ultimo).replace("{nome}", nome or "voce")
    if ctas and random.random() < 0.6 and "\n" not in msg:
        cta = _escolher_variante(ctas, chave + ":cta", ultimo)
        if cta and cta not in msg:
            msg = f"{msg}\n{cta}"
    return msg.strip()


def _legacy_get_msg_reengajamento(nome: str = "", numero: str = "", historico: list | None = None) -> str:
    temperatura = classificar_temperatura_lead(_coletar_ultima_mensagem_usuario(historico), historico)
    templates = _cfg_lista_por_temperatura(
        "reengajamento",
        temperatura,
        [
            "Oi {nome}, passando so pra ver se ainda quer que eu veja uma condicao pro seu veiculo.",
            "{nome}, tudo certo? Se ainda fizer sentido, posso montar uma simulacao sem compromisso.",
            "Oi {nome}! Quando quiser, eu ainda consigo consultar uma cotacao pro seu carro.",
            "Tudo bem por ai? Se preferir, eu sigo com uma simulacao rapida e sem compromisso.",
        ],
        fallback="reengajamento",
    )
    chave = f"reengajamento:{nome}:{numero}:{datetime.now().date().isoformat()}"
    return _escolher_variante(templates, chave).replace("{nome}", nome or "voce").strip()


def _legacy_get_msg_objeccao_caro(nome: str = "") -> str:
    templates = _cfg_lista(
        "ia",
        "objeccao_caro",
        [
            "Te entendo. Posso te mostrar uma opcao mais enxuta e comparar o custo-beneficio?",
            "Faz sentido comparar bem. Quer que eu veja uma versao mais simples?",
            "Sem problema. Posso ajustar e te mostrar algo mais leve.",
        ],
    )
    return _escolher_variante(templates, f"caro:{nome}").replace("{nome}", nome or "voce").strip()


def _legacy_get_msg_objeccao_vou_pensar(nome: str = "") -> str:
    templates = _cfg_lista(
        "ia",
        "objeccao_vou_pensar",
        [
            "Claro, decisao importante mesmo. Posso deixar um resumo curto pra voce olhar com calma?",
            "Sem pressa. Se quiser, eu separo a simulacao pra voce revisar depois.",
            "Tudo certo. Se ajudar, eu te mando uma versao bem resumida.",
        ],
    )
    return _escolher_variante(templates, f"pensar:{nome}").replace("{nome}", nome or "voce").strip()


def _legacy_get_msg_fechamento(nome: str = "") -> str:
    templates = _cfg_lista(
        "ia",
        "fechamento",
        [
            "Perfeito. Me confirma modelo, ano, versao e cidade para eu deixar tudo certo aqui.",
            "Show. Com esses dados eu ja consigo seguir com a formalizacao.",
            "Se quiser, eu ja deixo a proposta pronta pra voce.",
        ],
    )
    return _escolher_variante(templates, f"fechamento:{nome}").replace("{nome}", nome or "voce").strip()


def _legacy_classificar_estagio(mensagem: str, historico: list | None = None) -> str:
    texto = _normalizar_texto(
        " ".join([mensagem or ""] + [m.get("content", "") for m in (historico or [])[-8:] if isinstance(m, dict)])
    )

    if any(p in texto for p in ["nao tenho interesse", "nao quero", "para de mandar", "sem interesse"]):
        return "sem_interesse"
    if any(p in texto for p in ["tenho seguro", "ja tenho seguro", "tenho protecao", "ja tenho protecao"]):
        return "ja_possui_seguro"
    if any(p in texto for p in ["caro", "carissimo", "caríssimo", "muito caro", "pesado", "salgado"]):
        return "caro"
    if any(p in texto for p in ["vou pensar", "depois vejo", "mais tarde", "talvez", "depois eu olho", "vou analisar"]):
        return "vou_pensar"
    if any(p in texto for p in ["valor", "quanto", "preco", "mensalidade", "custa", "cotacao", "cota"]):
        return "pediu_valor"

    dados = detectar_dados_veiculo(historico or [{"content": mensagem or ""}])
    if dados.get("modelo") or dados.get("marca") or dados.get("ano") or dados.get("versao"):
        return "informou_veiculo"

    if any(p in texto for p in ["sim", "tenho interesse", "quero", "pode", "manda", "me chama"]):
        return "interessado"
    return "lead_frio"


def _legacy_instrucoes_estagio(estagio: str, nome_cliente: str = "", historico: list | None = None) -> str:
    mapa = {
        "lead_frio": "Abra com leveza, use no maximo 2 linhas e, se fizer sentido, finalize com resposta rapida 1 e 2.",
        "interessado": "Conduza para modelo, ano, versao e cidade. Mantenha a mensagem curta e natural.",
        "ja_possui_seguro": "Pergunte se esta satisfeito com valor e cobertura. Compare sem atacar concorrente.",
        "sem_interesse": "Respeite, agradeca e deixe a porta aberta sem insistir.",
        "caro": "Acolha a objeção, compare custo-beneficio e ofereca uma opcao mais enxuta.",
        "vou_pensar": "Respeite, nao pressione e ofereca um resumo curto para a pessoa revisar depois.",
        "pediu_valor": "Nao informe valor fechado. Peça modelo, ano, versao e cidade de forma objetiva.",
        "informou_veiculo": "Confirme os dados do veiculo e diga que vai consultar FIPE para preparar a proposta.",
        "parado": "Reengaje com leveza, sem insistencia e sem texto longo.",
    }
    return mapa.get(estagio, mapa["lead_frio"])


def _legacy_fallback_response(estagio: str, nome_cliente: str = "") -> str:
    nome = f"{nome_cliente}, " if nome_cliente else ""
    respostas = {
        "sem_interesse": f"Tranquilo, {nome}obrigado pelo retorno. Se quiser comparar valor ou cobertura depois, fico a disposicao.",
        "ja_possui_seguro": f"Perfeito, {nome}entao voce ja entende a importancia. Hoje o valor e a cobertura estao tranquilos pra voce?",
        "caro": get_msg_objeccao_caro(nome_cliente),
        "vou_pensar": get_msg_objeccao_vou_pensar(nome_cliente),
        "pediu_valor": f"Consigo ver pra voce. Me passa modelo, ano, versao e cidade do veiculo?",
        "informou_veiculo": f"Boa. Com esses dados eu ja consigo consultar pela FIPE e preparar uma condicao certinha pra voce.",
        "interessado": f"Show. Qual e o modelo, ano e versao do veiculo pra eu consultar aqui?",
        "parado": get_msg_reengajamento(nome_cliente),
        "lead_frio": get_msg_abertura(nome_cliente),
    }
    return respostas.get(estagio, respostas["lead_frio"])


def _legacy_gerar_resposta(
    mensagem: str,
    historico: list,
    api_key: str | None = None,
    prompt_extra: str = "",
    nome_cliente: str = "",
    palavras_humano: str = "",
) -> str:
    if checar_transferencia(mensagem, palavras_humano):
        return "##HUMANO##"

    if not is_horario_atendimento():
        return get_msg_fora_horario()

    estagio = classificar_estagio(mensagem, historico)
    temperatura = classificar_temperatura_lead(mensagem, historico)
    key = api_key or GROQ_API_KEY
    if not key:
        return _fallback_response(estagio, nome_cliente)

    contexto_cliente = extrair_contexto_cliente(historico, nome_cliente)
    system = PROMPT_MESTRE + f"\n\nEstagio atual do lead: {estagio}."
    system += f"\nTemperatura do lead: {temperatura}."
    instrucoes_estagio = _instrucoes_estagio(estagio, nome_cliente, historico)
    if instrucoes_estagio:
        system += f"\n\nInstrucao comercial do estagio:\n{instrucoes_estagio}"
    instrucoes_temperatura = _instrucoes_temperatura(temperatura)
    if instrucoes_temperatura:
        system += f"\n\nInstrucao de temperatura:\n{instrucoes_temperatura}"
    if contexto_cliente:
        system += f"\n\nContexto do cliente:\n{contexto_cliente}"
    if prompt_extra:
        system += f"\n\nContexto comercial extra:\n{prompt_extra}"

    messages = [{"role": "system", "content": system}]
    messages += [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in (historico or [])[-16:]
        if isinstance(m, dict) and m.get("content")
    ]
    messages.append({"role": "user", "content": mensagem})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.8,
                "top_p": 0.92,
                "frequency_penalty": 0.45,
                "presence_penalty": 0.2,
            },
            timeout=20,
        )
        resp.raise_for_status()
        resposta = resp.json()["choices"][0]["message"]["content"].strip()
        return _limpar_resposta(resposta) or _fallback_response(estagio, nome_cliente)
    except Exception as exc:
        print(f"Erro Groq: {exc}")
        return _fallback_response(estagio, nome_cliente)


# ---------------------------------------------------------------------------
# Camada humana avançada
# Sobrescreve a camada comercial antiga sem mexer no restante do sistema.
# ---------------------------------------------------------------------------


def get_msg_abertura(nome: str = "", numero: str = "", historico: list | None = None) -> str:
    temperatura = classificar_temperatura_lead(_coletar_ultima_mensagem_usuario(historico), historico)
    if not historico:
        pass

    templates = _cfg_lista_por_temperatura(
        "templates_abertura",
        temperatura,
        [
            "Oi, {nome}! Tudo bem? Hoje voce ja protege seu veiculo?",
            "Ola, {nome}. Rapidinho: seu carro hoje ja tem seguro ou protecao?",
            "Fala, {nome}! Hoje voce usa seguro tradicional ou protecao veicular?",
            "Oi, {nome}. Posso te fazer uma pergunta rapida sobre seu veiculo?",
        ],
        fallback="templates_lead_frio",
    )
    ultimo = _coletar_ultimo_assistente(historico)
    chave = f"abertura:{nome}:{numero}:{datetime.now().date().isoformat()}"
    return _escolher_variante(templates, chave, ultimo).replace("{nome}", nome or "voce").strip()


def get_msg_reengajamento(nome: str = "", numero: str = "", historico: list | None = None) -> str:
    temperatura = classificar_temperatura_lead(_coletar_ultima_mensagem_usuario(historico), historico)
    templates = _cfg_lista_por_temperatura(
        "reengajamento",
        temperatura,
        [
            "Oi {nome}, passando so pra ver se ainda quer que eu veja uma condicao pro seu veiculo.",
            "{nome}, tudo certo? Se ainda fizer sentido, posso montar uma simulacao sem compromisso.",
            "Oi {nome}! Quando quiser, eu ainda consigo consultar uma cotacao pro seu carro.",
            "Tudo bem por ai? Se preferir, eu sigo com uma simulacao rapida e sem compromisso.",
        ],
        fallback="reengajamento",
    )
    chave = f"reengajamento:{nome}:{numero}:{datetime.now().date().isoformat()}"
    return _escolher_variante(templates, chave).replace("{nome}", nome or "voce").strip()


def get_horas_reabertura(default: int = 24) -> int:
    try:
        return int(_cfg("cooldowns_horas", "reabertura", default) or default)
    except Exception:
        return default


def get_msg_reabertura(nome: str = "", numero: str = "", historico: list | None = None) -> str:
    templates = _cfg_lista(
        "ia",
        "reabertura",
        [
            "Olá, {nome}! 😊\nQue bom te ver novamente.\n\nComo posso te ajudar hoje?\n\n1️⃣ Cotação\n2️⃣ Dúvidas\n3️⃣ Falar com um consultor\n4️⃣ Assistência 24h\n\n📞 Assistência 24h:\n0800 940 2511",
            "Oi, {nome}! 😊\nBom falar com você novamente.\n\nMe diz como posso ajudar:\n\n1️⃣ Cotação\n2️⃣ Dúvidas\n3️⃣ Consultor\n4️⃣ Assistência 24h\n\n📞 0800 940 2511",
            "Olá, {nome}! 🚗\nQue bom te ver por aqui novamente.\n\nEscolha uma opção:\n\n1️⃣ Fazer cotação\n2️⃣ Tirar dúvidas\n3️⃣ Atendimento humano\n4️⃣ Assistência 24h\n\n📞 0800 940 2511",
            "Oi, {nome}! Tudo bem? 😊\nEstou à disposição novamente.\n\nComo posso ajudar hoje?\n\n1️⃣ Cotação\n2️⃣ Dúvidas\n3️⃣ Falar com consultor\n4️⃣ Assistência 24h\n\n📞 0800 940 2511",
        ],
    )
    ultimo = _coletar_ultimo_assistente(historico)
    chave = f"reabertura:{nome}:{numero}:{datetime.now().date().isoformat()}"
    return _escolher_variante(templates, chave, ultimo).replace("{nome}", nome or "voce").strip()


def mensagem_assistente_eh_reabertura(historico: list | None = None) -> bool:
    for item in reversed(historico or []):
        if not isinstance(item, dict):
            continue
        if item.get("role") != "assistant":
            continue
        texto = _normalizar_texto(item.get("content", ""))
        return (
            "0800 940 2511" in texto
            and "cotacao" in texto
            and "duvidas" in texto
            and "assistencia 24h" in texto
        )
    return False


def classificar_opcao_retorno(mensagem: str) -> str | None:
    texto = _normalizar_texto(mensagem)
    if not texto:
        return None
    if texto == "4" or texto.startswith("4 ") or "assistencia" in texto or "24h" in texto:
        return "assistencia"
    if texto == "3" or texto.startswith("3 ") or any(p in texto for p in ["consultor", "atendente", "humano", "falar comigo", "falar com consultor"]):
        return "consultor"
    if texto == "2" or texto.startswith("2 ") or "duvida" in texto:
        return "duvidas"
    if texto == "1" or texto.startswith("1 ") or any(p in texto for p in ["cotacao", "cotar", "simular", "simulacao", "fazer cotacao"]):
        return "cotacao"
    return None


def get_msg_objeccao_caro(nome: str = "") -> str:
    templates = _cfg_lista(
        "ia",
        "objeccao_caro",
        [
            "Te entendo. Posso te mostrar uma opcao mais enxuta e comparar o custo-beneficio?",
            "Faz sentido comparar bem. Quer que eu veja uma versao mais simples?",
            "Sem problema. Posso ajustar e te mostrar algo mais leve.",
        ],
    )
    return _escolher_variante(templates, f"caro:{nome}").replace("{nome}", nome or "voce").strip()


def get_msg_objeccao_vou_pensar(nome: str = "") -> str:
    templates = _cfg_lista(
        "ia",
        "objeccao_vou_pensar",
        [
            "Claro, decisao importante mesmo. Posso deixar um resumo curto pra voce olhar com calma?",
            "Sem pressa. Se quiser, eu separo a simulacao pra voce revisar depois.",
            "Tudo certo. Se ajudar, eu te mando uma versao bem resumida.",
        ],
    )
    return _escolher_variante(templates, f"pensar:{nome}").replace("{nome}", nome or "voce").strip()


def get_msg_fechamento(nome: str = "") -> str:
    templates = _cfg_lista(
        "ia",
        "fechamento",
        [
            "Perfeito. Me confirma modelo, ano, versao e cidade para eu deixar tudo certo aqui.",
            "Show. Com esses dados eu ja consigo seguir com a formalizacao.",
            "Se quiser, eu ja deixo a proposta pronta pra voce.",
        ],
    )
    return _escolher_variante(templates, f"fechamento:{nome}").replace("{nome}", nome or "voce").strip()


def classificar_estagio(mensagem: str, historico: list | None = None) -> str:
    texto = _normalizar_texto(
        " ".join([mensagem or ""] + [m.get("content", "") for m in (historico or [])[-8:] if isinstance(m, dict)])
    )

    if any(p in texto for p in ["nao tenho interesse", "nao quero", "para de mandar", "sem interesse"]):
        return "sem_interesse"
    if any(p in texto for p in ["tenho seguro", "ja tenho seguro", "tenho protecao", "ja tenho protecao"]):
        return "ja_possui_seguro"
    if any(p in texto for p in ["caro", "carissimo", "car?ssimo", "muito caro", "pesado", "salgado"]):
        return "caro"
    if any(p in texto for p in ["vou pensar", "depois vejo", "mais tarde", "talvez", "depois eu olho", "vou analisar"]):
        return "vou_pensar"
    if any(p in texto for p in ["valor", "quanto", "preco", "mensalidade", "custa", "cotacao", "cota"]):
        return "pediu_valor"

    dados = detectar_dados_veiculo(historico or [{"content": mensagem or ""}])
    if dados.get("modelo") or dados.get("marca") or dados.get("ano") or dados.get("versao"):
        return "informou_veiculo"

    if any(p in texto for p in ["sim", "tenho interesse", "quero", "pode", "manda", "me chama"]):
        return "interessado"
    return "lead_frio"


def _instrucoes_estagio(estagio: str, nome_cliente: str = "", historico: list | None = None) -> str:
    mapa = {
        "lead_frio": "Abra com leveza, use no maximo 2 linhas e, se fizer sentido, finalize com resposta rapida 1 e 2.",
        "interessado": "Conduza para modelo, ano, versao e cidade. Mantenha a mensagem curta e natural.",
        "ja_possui_seguro": "Pergunte se esta satisfeito com valor e cobertura. Compare sem atacar concorrente.",
        "sem_interesse": "Respeite, agradeca e deixe a porta aberta sem insistir.",
        "caro": "Acolha a obje\u00E7\u00E3o, compare custo-beneficio e ofereca uma opcao mais enxuta.",
        "vou_pensar": "Respeite, nao pressione e ofereca um resumo curto para a pessoa revisar depois.",
        "pediu_valor": "Nao informe valor fechado. Pe\u00E7a modelo, ano, versao e cidade de forma objetiva.",
        "informou_veiculo": "Confirme os dados do veiculo e diga que vai consultar FIPE para preparar a proposta.",
        "parado": "Reengaje com leveza, sem insistencia e sem texto longo.",
    }
    return mapa.get(estagio, mapa["lead_frio"])


def _fallback_response(estagio: str, nome_cliente: str = "", historico: list | None = None) -> str:
    nome = f"{nome_cliente}, " if nome_cliente else ""
    respostas = {
        "sem_interesse": f"Tranquilo, {nome}obrigado pelo retorno. Se quiser comparar valor ou cobertura depois, fico a disposicao.",
        "ja_possui_seguro": f"Perfeito, {nome}entao voce ja entende a importancia. Hoje o valor e a cobertura estao tranquilos pra voce?",
        "caro": get_msg_objeccao_caro(nome_cliente),
        "vou_pensar": get_msg_objeccao_vou_pensar(nome_cliente),
        "pediu_valor": f"Consigo ver pra voce. Me passa modelo, ano, versao e cidade do veiculo?",
        "informou_veiculo": f"Boa. Com esses dados eu ja consigo consultar pela FIPE e preparar uma condicao certinha pra voce.",
        "interessado": f"Show. Qual e o modelo, ano e versao do veiculo pra eu consultar aqui?",
        "parado": get_msg_reengajamento(nome_cliente),
        "lead_frio": get_msg_abertura(nome_cliente, historico=historico),
    }
    return respostas.get(estagio, respostas["lead_frio"])


def gerar_resposta(
    mensagem: str,
    historico: list,
    api_key: str | None = None,
    prompt_extra: str = "",
    nome_cliente: str = "",
    palavras_humano: str = "",
) -> str:
    if checar_transferencia(mensagem, palavras_humano):
        return "##HUMANO##"

    if not is_horario_atendimento():
        return get_msg_fora_horario()

    estagio = classificar_estagio(mensagem, historico)
    temperatura = classificar_temperatura_lead(mensagem, historico)
    key = api_key or GROQ_API_KEY
    if not key:
        return _fallback_response(estagio, nome_cliente, historico)

    contexto_cliente = extrair_contexto_cliente(historico, nome_cliente)
    system = PROMPT_MESTRE + f"\n\nEstagio atual do lead: {estagio}."
    system += f"\nTemperatura do lead: {temperatura}."
    instrucoes_estagio = _instrucoes_estagio(estagio, nome_cliente, historico)
    if instrucoes_estagio:
        system += f"\n\nInstrucao comercial do estagio:\n{instrucoes_estagio}"
    instrucoes_temperatura = _instrucoes_temperatura(temperatura)
    if instrucoes_temperatura:
        system += f"\n\nInstrucao de temperatura:\n{instrucoes_temperatura}"
    if contexto_cliente:
        system += f"\n\nContexto do cliente:\n{contexto_cliente}"
    if prompt_extra:
        system += f"\n\nContexto comercial extra:\n{prompt_extra}"

    messages = [{"role": "system", "content": system}]
    messages += [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in (historico or [])[-16:]
        if isinstance(m, dict) and m.get("content")
    ]
    messages.append({"role": "user", "content": mensagem})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.8,
                "top_p": 0.92,
                "frequency_penalty": 0.45,
                "presence_penalty": 0.2,
            },
            timeout=20,
        )
        resp.raise_for_status()
        resposta = resp.json()["choices"][0]["message"]["content"].strip()
        return _limpar_resposta(resposta) or _fallback_response(estagio, nome_cliente, historico)
    except Exception as exc:
        print(f"Erro Groq: {exc}")
        return _fallback_response(estagio, nome_cliente, historico)
# ---------------------------------------------------------------------------
# Camada comercial atualizada
# As funcoes abaixo sobrescrevem as versoes antigas acima sem quebrar a API.
# ---------------------------------------------------------------------------


def _cfg_lista(secao: str, chave: str, default: list[str]) -> list[str]:
    valor = _cfg(secao, chave, default)
    return valor if isinstance(valor, list) else default


def _coletar_ultimo_assistente(historico: list | None) -> str:
    for item in reversed(historico or []):
        if isinstance(item, dict) and item.get("role") == "assistant" and item.get("content"):
            return str(item.get("content", ""))
    return ""


def _coletar_ultima_mensagem_usuario(historico: list | None) -> str:
    for item in reversed(historico or []):
        if isinstance(item, dict) and item.get("role") == "user" and item.get("content"):
            return str(item.get("content", ""))
    return ""


def _cfg_lista_por_temperatura(base: str, temperatura: str, default: list[str], fallback: str | None = None) -> list[str]:
    config = _carregar_config_comercial().get("ia", {})
    for chave in (f"{base}_{temperatura}", fallback or base):
        valor = config.get(chave)
        if isinstance(valor, list) and valor:
            return [str(item).strip() for item in valor if str(item).strip()]
    return [str(item).strip() for item in default if str(item).strip()]


def classificar_temperatura_lead(mensagem: str, historico: list | None = None) -> str:
    texto = _normalizar_texto(
        " ".join(
            [mensagem or ""]
            + [
                m.get("content", "")
                for m in (historico or [])[-10:]
                if isinstance(m, dict) and m.get("role") == "user"
            ]
        )
    )
    if any(p in texto for p in ["nao tenho interesse", "nao quero", "sem interesse", "para de mandar"]):
        return "frio"
    if any(p in texto for p in ["quero saber", "me explica", "como funciona", "detalhe", "simular", "cotar", "preco", "valor", "mensalidade", "cobertura", "pagamento", "fechar"]):
        return "quente"
    if any(p in texto for p in ["vou pensar", "depois vejo", "talvez", "mais tarde", "resumido", "calma", "caro", "carissimo", "caríssimo"]):
        return "morno"
    if not texto:
        return "frio"
    return "morno"


def _instrucoes_temperatura(temperatura: str) -> str:
    mapa = {
        "quente": "Lead quente: seja objetivo, peça modelo, ano, versao e cidade com naturalidade. Conduza para simulacao, proposta e fechamento.",
        "morno": "Lead morno: mantenha leveza, uma pergunta por vez e enfoque em confianca e clareza antes do fechamento.",
        "frio": "Lead frio: abordagem curta, leve e sem pressao. Use CTA simples quando ajudar a resposta.",
    }
    return mapa.get(temperatura, mapa["morno"])


def _legacy3_get_msg_abertura(nome: str = "", numero: str = "", historico: list | None = None) -> str:
    templates = _cfg_lista(
        "ia",
        "templates_lead_frio",
        [
            "Oi, {nome}! Tudo bem? Hoje voce ja protege seu veiculo?",
            "Ola, {nome}. Rapidinho: seu carro hoje ja tem seguro ou protecao?",
            "Fala, {nome}! Hoje voce usa seguro tradicional ou protecao veicular?",
            "Oi, {nome}. Posso te fazer uma pergunta rapida sobre seu veiculo?",
        ],
    )
    ctas = _cfg_lista(
        "ia",
        "ctas_lead_frio",
        [
            "Hoje voce ja protege seu veiculo?\n1️⃣ Sim\n2️⃣ Nao",
            "Seu carro hoje tem alguma protecao?\n1️⃣ Sim\n2️⃣ Nao",
        ],
    )
    ultimo = _coletar_ultimo_assistente(historico)
    chave = f"abertura:{nome}:{numero}:{datetime.now().date().isoformat()}"
    msg = _escolher_variante(templates, chave, ultimo).replace("{nome}", nome or "voce")
    if ctas and random.random() < 0.6 and "\n" not in msg:
        cta = _escolher_variante(ctas, chave + ":cta", ultimo)
        if cta and cta not in msg:
            msg = f"{msg}\n{cta}"
    return msg.strip()


def _legacy2_get_msg_reengajamento(nome: str = "", numero: str = "") -> str:
    templates = _cfg_lista(
        "ia",
        "reengajamento",
        [
            "Oi {nome}, passando so pra ver se ainda quer que eu veja uma condicao pro seu veiculo.",
            "{nome}, tudo certo? Se ainda fizer sentido, posso montar uma simulacao sem compromisso.",
            "Oi {nome}! Quando quiser, eu ainda consigo consultar uma cotacao pro seu carro.",
            "Tudo bem por ai? Se preferir, eu sigo com uma simulacao rapida e sem compromisso.",
        ],
    )
    chave = f"reengajamento:{nome}:{numero}:{datetime.now().date().isoformat()}"
    return _escolher_variante(templates, chave).replace("{nome}", nome or "voce").strip()


def get_msg_fora_horario() -> str:
    mensagens = _cfg_lista(
        "ia",
        "fora_horario",
        [
            "Oi! Recebi sua mensagem. Nosso atendimento volta no horario comercial e ja te respondo certinho.",
            "Mensagem recebida. Assim que o atendimento abrir eu continuo com voce por aqui.",
            "Opa, vi sua mensagem aqui. No horario comercial eu te retorno rapidinho.",
        ],
    )
    return random.choice(mensagens).strip()


def checar_transferencia(mensagem: str, palavras_extra: str = "") -> bool:
    msg = _normalizar_texto(mensagem)
    extras = [
        p.strip()
        for p in re.split(r"[,\n;|]+", palavras_extra or "")
        if p and p.strip()
    ]
    palavras = [_normalizar_texto(p) for p in PALAVRAS_HUMANO + extras]
    return any(p and p in msg for p in palavras)


def _legacy2_classificar_estagio(mensagem: str, historico: list | None = None) -> str:
    texto = _normalizar_texto(
        " ".join([mensagem or ""] + [m.get("content", "") for m in (historico or [])[-8:] if isinstance(m, dict)])
    )

    if any(p in texto for p in ["nao tenho interesse", "nao quero", "para de mandar", "sem interesse"]):
        return "sem_interesse"
    if any(p in texto for p in ["tenho seguro", "ja tenho seguro", "tenho protecao", "ja tenho protecao"]):
        return "ja_possui_seguro"
    if any(p in texto for p in ["valor", "quanto", "preco", "mensalidade", "custa", "cotacao", "cota"]):
        return "pediu_valor"

    dados = detectar_dados_veiculo(historico or [{"content": mensagem or ""}])
    if dados.get("modelo") or dados.get("marca") or dados.get("ano") or dados.get("versao"):
        return "informou_veiculo"

    if any(p in texto for p in ["sim", "tenho interesse", "quero", "pode", "manda", "me chama"]):
        return "interessado"
    return "lead_frio"


def _legacy2_instrucoes_estagio(estagio: str, nome_cliente: str = "", historico: list | None = None) -> str:
    mapa = {
        "lead_frio": "Abra com leveza, use no maximo 2 linhas e, se fizer sentido, finalize com resposta rapida 1 e 2.",
        "interessado": "Conduza para modelo, ano, versao e cidade. Mantenha a mensagem curta e natural.",
        "ja_possui_seguro": "Pergunte se esta satisfeito com valor e cobertura. Compare sem atacar concorrente.",
        "sem_interesse": "Respeite, agradeca e deixe a porta aberta sem insistir.",
        "pediu_valor": "Nao informe valor fechado. Peça modelo, ano, versao e cidade de forma objetiva.",
        "informou_veiculo": "Confirme os dados do veiculo e diga que vai consultar FIPE para preparar a proposta.",
        "parado": "Reengaje com leveza, sem insistencia e sem texto longo.",
    }
    return mapa.get(estagio, mapa["lead_frio"])


def _legacy2_fallback_response(estagio: str, nome_cliente: str = "") -> str:
    nome = f"{nome_cliente}, " if nome_cliente else ""
    respostas = {
        "sem_interesse": f"Tranquilo, {nome}obrigado pelo retorno. Se quiser comparar valor ou cobertura depois, fico a disposicao.",
        "ja_possui_seguro": f"Perfeito, {nome}entao voce ja entende a importancia. Hoje o valor e a cobertura estao tranquilos pra voce?",
        "pediu_valor": f"Consigo ver pra voce. Me passa modelo, ano, versao e cidade do veiculo?",
        "informou_veiculo": f"Boa. Com esses dados eu ja consigo consultar pela FIPE e preparar uma condicao certinha pra voce.",
        "interessado": f"Show. Qual e o modelo, ano e versao do veiculo pra eu consultar aqui?",
        "parado": get_msg_reengajamento(nome_cliente),
        "lead_frio": get_msg_abertura(nome_cliente),
    }
    return respostas.get(estagio, respostas["lead_frio"])


def extrair_contexto_cliente(historico: list, nome_whatsapp: str = "") -> str:
    contexto = []
    if nome_whatsapp:
        contexto.append(f"Nome no WhatsApp: {nome_whatsapp}")

    dados = detectar_dados_veiculo(historico)
    if dados:
        contexto.append(f"Dados detectados do veiculo: {dados}")

    texto = _normalizar_texto(" ".join([m.get("content", "") for m in historico if isinstance(m, dict)]))
    if any(p in texto for p in ["uber", "99", "aplicativo", "app"]):
        contexto.append("Perfil: motorista de aplicativo")
    elif "taxi" in texto or "taxista" in texto:
        contexto.append("Perfil: taxista")

    return "\n".join(contexto)


def _formatar_modelo_nome(texto: str) -> str:
    partes = []
    for parte in str(texto or "").strip().split():
        if not parte:
            continue
        if len(parte) <= 3 or parte.isupper():
            partes.append(parte.upper())
        elif re.fullmatch(r"\d+[a-zA-Z0-9./-]*", parte):
            partes.append(parte)
        else:
            partes.append(parte.capitalize())
    return " ".join(partes).strip()


def detectar_dados_veiculo(historico: list) -> dict:
    texto = " ".join([m.get("content", "") for m in historico if isinstance(m, dict)])
    texto_norm = _normalizar_texto(texto)
    dados = {}

    if any(p in texto_norm for p in ["uber", "99", "aplicativo", "app"]):
        dados["categoria"] = "uber"
    elif any(p in texto_norm for p in ["taxi", "taxista"]):
        dados["categoria"] = "taxi"
    elif any(p in texto_norm for p in ["moto", "motocicleta"]):
        dados["categoria"] = "moto"
    elif any(p in texto_norm for p in ["utilitario", "van", "sprinter", "master"]):
        dados["categoria"] = "utilitario"
    else:
        dados["categoria"] = "passeio"

    anos = re.findall(r"\b(19[9][5-9]|20[0-2][0-9])\b", texto_norm)
    if anos:
        dados["ano"] = int(anos[-1])

    marcas = {
        "chevrolet": ["gm", "chevrolet", "onix", "celta", "corsa", "spin", "tracker", "cruze", "prisma", "cobalt"],
        "volkswagen": ["vw", "volkswagen", "gol", "polo", "virtus", "t-cross", "saveiro", "voyage", "fox"],
        "fiat": ["fiat", "uno", "palio", "siena", "argo", "cronos", "mobi", "strada", "toro"],
        "ford": ["ford", "ka", "ecosport", "ranger", "fiesta", "focus"],
        "toyota": ["toyota", "corolla", "hilux", "yaris", "etios", "sw4"],
        "honda": ["honda", "civic", "hrv", "hr-v", "crv", "fit", "city"],
        "hyundai": ["hyundai", "hb20", "creta", "tucson"],
        "renault": ["renault", "kwid", "sandero", "duster", "logan", "captur"],
        "nissan": ["nissan", "kicks", "frontier", "versa", "march"],
        "jeep": ["jeep", "renegade", "compass", "commander"],
        "peugeot": ["peugeot", "208", "2008", "308"],
        "kia": ["kia", "sportage", "cerato"],
    }

    stop_tokens = {
        "veiculo", "carro", "auto", "modelo", "ano", "cotacao", "cota", "valor",
        "preco", "protecao", "seguro", "para", "com", "do", "da", "de", "e", "o",
        "a", "que", "eu", "ja", "vou", "consultar", "fipe", "versao", "cidade",
        "sim", "nao", "na", "no", "pro", "pra",
    }

    for marca, palavras in marcas.items():
        for palavra in palavras:
            palavra_norm = _normalizar_texto(palavra)
            if not palavra_norm or palavra_norm not in texto_norm:
                continue

            dados["marca"] = marca.capitalize()
            if palavra != marca and palavra not in {"gm", "vw"}:
                dados["modelo"] = _formatar_modelo_nome(palavra)

            tail = texto_norm.split(palavra_norm, 1)[1].strip()
            if tail:
                tail_antes_ano = tail
                tail_depois_ano = ""
                match_ano = re.search(r"\b(19[9][5-9]|20[0-2][0-9])\b", tail)
                if match_ano:
                    tail_antes_ano = tail[:match_ano.start()].strip()
                    tail_depois_ano = tail[match_ano.end():].strip()

                tokens_base = [t for t in tail_antes_ano.split() if t not in stop_tokens]
                tokens_pos_ano = [t for t in tail_depois_ano.split() if t not in stop_tokens]
                versao_tokens_rapidos = {
                    "lt", "ltz", "ex", "exl", "xei", "lx", "s", "se", "sv", "sr", "sl",
                    "drive", "sport", "freedom", "gti", "turbo", "plus", "highline",
                    "sense", "style", "platinum", "titanium", "dynamic", "life",
                    "comfort", "advance", "black", "vision", "tech", "connect",
                    "flex", "manual", "automatico", "aut", "at", "one", "way",
                    "attractive", "adventure", "sporting", "trekking", "absolute",
                    "gl", "glx", "gls", "gls", "xr", "xrs", "xli", "xlt", "gse",
                }

                if tokens_base and "modelo" not in dados:
                    modelo_tokens = [tokens_base[0]]
                    if len(tokens_base) > 1:
                        segundo = tokens_base[1]
                        if len(tokens_base[0]) <= 2 or segundo not in versao_tokens_rapidos:
                            modelo_tokens.append(segundo)
                    dados["modelo"] = _formatar_modelo_nome(" ".join(modelo_tokens))
                    tokens_base = tokens_base[len(modelo_tokens):]

                tokens_versao = tokens_pos_ano or tokens_base
                versao_tokens = []
                for token in tokens_versao:
                    if re.fullmatch(r"(19[9][5-9]|20[0-2][0-9])", token):
                        break
                    versao_tokens.append(token)
                    if len(versao_tokens) >= 4:
                        break
                if versao_tokens:
                    dados["versao"] = _formatar_modelo_nome(" ".join(versao_tokens))
            break
        if "marca" in dados:
            break

    return dados


def deve_calcular_cotacao(historico: list) -> bool:
    dados = detectar_dados_veiculo(historico)
    return ("marca" in dados or "modelo" in dados) and "ano" in dados


def gerar_cotacao_automatica(historico: list, nome_cliente: str = "") -> str | None:
    if not deve_calcular_cotacao(historico):
        return None

    dados = detectar_dados_veiculo(historico)
    marca = dados.get("marca", "")
    modelo = dados.get("modelo", marca)
    versao = dados.get("versao", "")
    ano = dados.get("ano", 2020)
    categoria = dados.get("categoria", "passeio")

    try:
        from services.fipe_service import consultar_fipe, extrair_valor_numerico, montar_proposta_texto

        tipo_fipe = "motos" if categoria == "moto" else "carros"
        resultado = consultar_fipe(marca, modelo, ano, tipo_fipe, versao=versao)
        if resultado and "Valor" in resultado:
            valor = extrair_valor_numerico(resultado["Valor"])
            return montar_proposta_texto(
                nome_cliente or "voce",
                resultado.get("Marca", marca),
                resultado.get("Modelo", modelo),
                resultado.get("AnoModelo", ano),
                valor,
                categoria,
                versao=versao,
            )
    except Exception as exc:
        print(f"Erro cotacao automatica: {exc}")
    return None


def get_mensagens_aquecimento(tipo: str = "abertura") -> list:
    path = Path(APP_DIR) / "data" / "mensagens_aquecimento.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(tipo, data.get("abertura", []))
    except Exception:
        return []


def get_mensagem_aleatoria(tipo: str = "abertura") -> str:
    msgs = get_mensagens_aquecimento(tipo)
    return random.choice(msgs) if msgs else ""
