# =============================================================
# services/fipe_service.py — Consulta à tabela FIPE
# API pública: parallelum.com.br/fipe/api/v1
# =============================================================
import requests
import json
import unicodedata
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from config.settings import (
    APP_DIR,
    FIPE_API_URL,
    PLACA_FIPE_API_KEY,
    PLACA_FIPE_API_URL,
    PLACA_FIPE_PROVIDER,
)

FIPE_BASE = FIPE_API_URL.rstrip("/") or "https://parallelum.com.br/fipe/api/v1"

# Cache simples em memória para evitar chamadas repetidas
_cache = {}

def _normalizar(texto: str) -> str:
    """Remove acentos e deixa minúsculo para comparação."""
    nfkd = unicodedata.normalize('NFKD', texto.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

def _get(url: str) -> list | dict | None:
    if url in _cache:
        return _cache[url]
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        _cache[url] = data
        return data
    except Exception as e:
        print(f"FIPE API erro: {e}")
        return None


def _request_json(method: str, url: str, *, params: dict | None = None, data: dict | None = None, json_body: dict | None = None, headers: dict | None = None, timeout: int = 12) -> dict | list | None:
    try:
        resp = requests.request(method.upper(), url, params=params, data=data, json=json_body, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Placa/FIPE API erro: {e}")
        return None


def _normalizar_placa(placa: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (placa or "").upper().strip())


def validar_placa(placa: str) -> bool:
    placa_n = _normalizar_placa(placa)
    if not placa_n:
        return False
    return bool(
        re.fullmatch(r"[A-Z]{3}[0-9]{4}", placa_n)
        or re.fullmatch(r"[A-Z]{3}[0-9][A-Z][0-9]{2}", placa_n)
    )


def _extrair_valor_numero_any(valor) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    if not valor:
        return 0.0
    texto = str(valor)
    numero = re.sub(r"[^0-9,.-]", "", texto)
    if "," in numero and "." in numero:
        numero = numero.replace(".", "").replace(",", ".")
    else:
        numero = numero.replace(".", "").replace(",", ".")
    try:
        return float(numero)
    except Exception:
        return 0.0


def _placa_data_matches(placa_req: str, data: dict) -> bool:
    placa_req_n = _normalizar_placa(placa_req)
    if not placa_req_n:
        return False
    candidatos = [
        data.get("placa"),
        data.get("placa_original"),
        data.get("placa_original_formatada"),
        data.get("placaMercosul"),
        data.get("placa_mercosul"),
    ]
    for cand in candidatos:
        if cand and _normalizar_placa(str(cand)) == placa_req_n:
            return True
    return False


def _primeiro_dict_com_chave(obj, chave: str):
    if isinstance(obj, dict):
        if chave in obj:
            return obj
        for v in obj.values():
            achado = _primeiro_dict_com_chave(v, chave)
            if achado is not None:
                return achado
    elif isinstance(obj, list):
        for item in obj:
            achado = _primeiro_dict_com_chave(item, chave)
            if achado is not None:
                return achado
    return None


def _lista_fipe_da_resposta(data) -> list[dict]:
    if not isinstance(data, dict):
        return []
    candidatos = []
    if isinstance(data.get("fipe"), dict) and isinstance(data["fipe"].get("dados"), list):
        candidatos = data["fipe"]["dados"]
    elif isinstance(data.get("dados"), list):
        candidatos = data["dados"]
    else:
        bloco = _primeiro_dict_com_chave(data, "dados")
        if isinstance(bloco, dict) and isinstance(bloco.get("dados"), list):
            candidatos = bloco["dados"]
    return [c for c in candidatos if isinstance(c, dict)]


def _selecionar_melhor_fipe(dados: list[dict]) -> dict | None:
    if not dados:
        return None

    def score(item: dict) -> tuple[float, float, float]:
        peso = _extrair_valor_numero_any(item.get("score") or item.get("Score"))
        valor = _extrair_valor_numero_any(item.get("texto_valor") or item.get("valor") or item.get("Valor"))
        codigo = 1.0 if (item.get("codigo_fipe") or item.get("codigoFipe") or item.get("CodigoFipe")) else 0.0
        return (peso, codigo, valor)

    return max(dados, key=score)


def _normalizar_resultado_placa(placa: str, data: dict, categoria: str = "passeio") -> dict | None:
    if not isinstance(data, dict):
        return None

    if not _placa_data_matches(placa, data):
        placa_api = data.get("placa") or data.get("placa_original") or data.get("placaMercosul") or ""
        if placa_api and _normalizar_placa(placa_api) != _normalizar_placa(placa):
            return None

    fipe_lista = _lista_fipe_da_resposta(data)
    fipe_sel = _selecionar_melhor_fipe(fipe_lista) if fipe_lista else None
    fonte = fipe_sel or data

    marca = fonte.get("texto_marca") or fonte.get("marca") or data.get("marca") or data.get("marca_nome") or ""
    modelo = fonte.get("texto_modelo") or fonte.get("modelo") or data.get("modelo") or data.get("modelo_nome") or ""
    versao = fonte.get("texto_versao") or fonte.get("versao") or data.get("versao") or data.get("versao_nome") or ""
    ano_modelo = fonte.get("ano_modelo") or fonte.get("anoModelo") or data.get("ano_modelo") or data.get("anoModelo") or data.get("ano") or 0
    codigo_fipe = fonte.get("codigo_fipe") or fonte.get("codigoFipe") or fonte.get("CodigoFipe") or data.get("codigo_fipe") or ""
    valor_fmt = fonte.get("texto_valor") or fonte.get("valor") or fonte.get("Valor") or data.get("valor") or data.get("valor_fipe") or ""
    valor_num = _extrair_valor_numero_any(valor_fmt)

    if not codigo_fipe or valor_num <= 0:
        return None

    try:
        ano_modelo = int(str(ano_modelo)[:4])
    except Exception:
        ano_modelo = 0

    resultado = {
        "Placa": _normalizar_placa(placa),
        "Marca": str(marca).strip(),
        "Modelo": str(modelo).strip(),
        "Versao": str(versao).strip(),
        "AnoModelo": ano_modelo,
        "CodigoFipe": str(codigo_fipe).strip(),
        "Valor": valor_fmt if isinstance(valor_fmt, str) else f"R$ {valor_num:,.2f}",
        "ValorNumerico": valor_num,
        "Categoria": str(data.get("categoria") or data.get("especie") or categoria or "").strip(),
        "Provider": PLACA_FIPE_PROVIDER,
        "raw": data,
    }
    return resultado

def buscar_marcas(tipo: str = "carros") -> list:
    """tipo: carros | motos | caminhoes"""
    return _get(f"{FIPE_BASE}/{tipo}/marcas") or []

def buscar_modelos(tipo: str, marca_id: str) -> list:
    data = _get(f"{FIPE_BASE}/{tipo}/marcas/{marca_id}/modelos")
    if data and isinstance(data, dict):
        return data.get("modelos", [])
    return []

def buscar_anos(tipo: str, marca_id: str, modelo_id: str) -> list:
    return _get(f"{FIPE_BASE}/{tipo}/marcas/{marca_id}/modelos/{modelo_id}/anos") or []

def buscar_valor(tipo: str, marca_id: str, modelo_id: str, ano_combustivel: str) -> dict | None:
    return _get(f"{FIPE_BASE}/{tipo}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_combustivel}")


def consultar_fipe_por_ids(marca_id: str, modelo_id: str, ano_codigo: str, tipo: str = "carros") -> dict | None:
    if not (marca_id and modelo_id and ano_codigo):
        return None
    resultado = buscar_valor(tipo, str(marca_id), str(modelo_id), str(ano_codigo))
    if not resultado:
        return None
    valor = extrair_valor_numerico(resultado.get("Valor", "0"))
    if valor <= 0 or not resultado.get("CodigoFipe"):
        return None
    return {
        "Marca": resultado.get("Marca", ""),
        "Modelo": resultado.get("Modelo", ""),
        "Versao": resultado.get("Modelo", ""),
        "AnoModelo": resultado.get("AnoModelo") or resultado.get("anoModelo") or 0,
        "CodigoFipe": resultado.get("CodigoFipe", ""),
        "Valor": resultado.get("Valor", ""),
        "ValorNumerico": valor,
        "raw": resultado,
    }


def consultar_fipe_exata(marca_nome: str, modelo_nome: str, ano: int, tipo: str = "carros") -> dict | None:
    """Busca FIPE usando correspondência estrita, sem fuzzy, para dados vindos da placa."""
    marcas = buscar_marcas(tipo)
    if not marcas:
        return None

    marca_norm = _normalizar(marca_nome)
    marca_sel = None
    for m in marcas:
        nome = _normalizar(m.get("nome", ""))
        if nome == marca_norm or marca_norm == nome:
            marca_sel = m
            break
    if not marca_sel:
        return None

    marca_id = marca_sel["codigo"]
    modelos = buscar_modelos(tipo, marca_id)
    if not modelos:
        return None

    modelo_norm = _normalizar(modelo_nome)
    modelo_sel = None
    for m in modelos:
        nome = _normalizar(m.get("nome", ""))
        if nome == modelo_norm or modelo_norm in nome or nome in modelo_norm:
            modelo_sel = m
            break
    if not modelo_sel:
        return None

    modelo_id = modelo_sel["codigo"]
    anos = buscar_anos(tipo, marca_id, str(modelo_id))
    if not anos:
        return None

    ano_sel = None
    for a in anos:
        nome = _normalizar(a.get("nome", ""))
        if str(ano) in nome:
            ano_sel = a
            break
    if not ano_sel:
        return None

    resultado = buscar_valor(tipo, marca_id, str(modelo_id), ano_sel["codigo"])
    if not resultado:
        return None
    valor = extrair_valor_numerico(resultado.get("Valor", "0"))
    if valor <= 0 or not resultado.get("CodigoFipe"):
        return None
    resultado["ValorNumerico"] = valor
    return resultado


def consultar_veiculo_por_placa(placa: str, categoria: str = "passeio") -> dict | None:
    placa_n = _normalizar_placa(placa)
    if not validar_placa(placa_n):
        return None

    provider = (PLACA_FIPE_PROVIDER or "buscafipe").strip().lower()
    data = None

    if provider == "apiplacas":
        token = PLACA_FIPE_API_KEY.strip()
        if not token:
            return None
        base = PLACA_FIPE_API_URL.rstrip("/")
        url = f"{base}/{placa_n}/{token}"
        data = _request_json("GET", url)

    elif provider == "custom":
        base = PLACA_FIPE_API_URL.rstrip("/")
        if not base:
            return None
        url = base.format(placa=placa_n, key=PLACA_FIPE_API_KEY.strip())
        method = "POST" if "{" not in PLACA_FIPE_API_URL else "GET"
        if method == "POST":
            data = _request_json("POST", url, data={"placa": placa_n, "key": PLACA_FIPE_API_KEY.strip()})
        else:
            data = _request_json("GET", url)

    else:
        base = (PLACA_FIPE_API_URL or "https://buscafipe.com/api").rstrip("/")
        url = f"{base}/placa.php"
        payload = {"placa": placa_n}
        headers = {}
        if PLACA_FIPE_API_KEY.strip():
            headers["Authorization"] = f"Bearer {PLACA_FIPE_API_KEY.strip()}"
        data = _request_json("POST", url, data=payload, headers=headers or None)
        if not data:
            data = _request_json("GET", url, params=payload, headers=headers or None)

    resultado = _normalizar_resultado_placa(placa_n, data or {}, categoria=categoria)
    if resultado:
        return resultado

    # fallback: se a resposta traz marca/modelo/ano confiáveis, tenta FIPE exata sem fuzzy
    if isinstance(data, dict):
        marca = data.get("marca") or data.get("marca_nome") or ""
        modelo = data.get("modelo") or data.get("modelo_nome") or ""
        ano = data.get("ano_modelo") or data.get("anoModelo") or data.get("ano") or 0
        if marca and modelo and ano:
            exata = consultar_fipe_exata(marca, modelo, int(str(ano)[:4]), "carros")
            if exata:
                valor = extrair_valor_numerico(exata.get("Valor", "0"))
                if valor > 0 and exata.get("CodigoFipe"):
                    exata["Placa"] = placa_n
                    exata["ValorNumerico"] = valor
                    exata["Versao"] = exata.get("Modelo", "")
                    exata["Categoria"] = categoria
                    exata["Provider"] = provider
                    return exata
    return None

def _match_score(query: str, item_nome: str) -> int:
    """Retorna score de similaridade entre query e nome do item."""
    q = _normalizar(query)
    n = _normalizar(item_nome)
    if not q or not n:
        return 0.0

    if q == n:
        return 1000.0

    partes = [p for p in re.split(r"[^a-z0-9]+", q) if p]
    partes_item = [p for p in re.split(r"[^a-z0-9]+", n) if p]
    if not partes or not partes_item:
        return 0.0

    score = 0.0
    for parte in partes:
        melhor_parte = 0.0
        for parte_item in partes_item:
            if parte == parte_item:
                candidato = 45.0 + (len(parte) * 2.0)
            else:
                ratio = SequenceMatcher(None, parte, parte_item).ratio()
                if parte in parte_item or parte_item in parte:
                    ratio = max(ratio, 0.85)
                candidato = (ratio * 40.0) + min(len(parte), len(parte_item))
            if candidato > melhor_parte:
                melhor_parte = candidato
        score += melhor_parte

    if q in n:
        score += 12.0
    if n in q:
        score += 8.0

    return score if score >= 20.0 else 0.0


def _score_modelo(modelo_nome: str, item_nome: str, versao: str = "") -> tuple[float, float]:
    base = _match_score(modelo_nome, item_nome)
    bonus_versao = 0.0
    if versao:
        bonus_versao = _match_score(versao, item_nome)
        versao_norm = _normalizar(versao)
        item_norm = _normalizar(item_nome)
        if versao_norm and versao_norm in item_norm:
            bonus_versao += 15.0
    return (base, bonus_versao)

def consultar_fipe(marca_nome: str, modelo_nome: str, ano: int, tipo: str = "carros") -> dict | None:
    """
    Consulta o valor FIPE de um veículo pelo nome da marca, modelo e ano.
    Retorna dict com Valor, Marca, Modelo, AnoModelo, CodigoFipe ou None.
    """
    # 1. Busca marcas e encontra a mais próxima
    marcas = buscar_marcas(tipo)
    if not marcas:
        return None

    melhor_marca = max(marcas, key=lambda m: _match_score(marca_nome, m.get("nome", "")))
    if _match_score(marca_nome, melhor_marca.get("nome", "")) == 0:
        return None

    marca_id = melhor_marca["codigo"]

    # 2. Busca modelos e encontra o mais próximo
    modelos = buscar_modelos(tipo, marca_id)
    if not modelos:
        return None

    melhor_modelo = max(modelos, key=lambda m: _match_score(modelo_nome, m.get("nome", "")))
    if _match_score(modelo_nome, melhor_modelo.get("nome", "")) == 0:
        return None

    modelo_id = melhor_modelo["codigo"]

    # 3. Busca anos disponíveis e encontra o mais próximo
    anos = buscar_anos(tipo, marca_id, str(modelo_id))
    if not anos:
        return None

    ano_encontrado = None
    for a in anos:
        nome_ano = a.get("nome", "")
        if str(ano) in nome_ano:
            ano_encontrado = a
            break

    if not ano_encontrado:
        # Pega o ano mais próximo
        def dist_ano(a):
            match = re.search(r'\d{4}', a.get("nome", ""))
            return abs(int(match.group()) - ano) if match else 9999
        ano_encontrado = min(anos, key=dist_ano)

    # 4. Consulta o valor
    resultado = buscar_valor(tipo, marca_id, str(modelo_id), ano_encontrado["codigo"])
    return resultado


def extrair_valor_numerico(valor_fipe_str: str) -> float:
    """Converte 'R$ 60.705,00' para 60705.0"""
    try:
        limpo = re.sub(r'[R$\s]', '', valor_fipe_str)
        limpo = limpo.replace('.', '').replace(',', '.')
        return float(limpo)
    except Exception:
        return 0.0


# ── Tabela de preços completa ────────────────────────────────
TABELA_PRECOS = {
    "passeio": [
        (0, 30000, 130), (30001, 35000, 140), (35001, 40000, 150),
        (40001, 45000, 165), (45001, 50000, 180), (50001, 55000, 195),
        (55001, 60000, 210), (60001, 65000, 230), (65001, 70000, 250),
        (70001, 75000, 260), (75001, 80000, 270), (80001, 85000, 280),
        (85001, 90000, 290), (90001, 95000, 300), (95001, 100000, 310),
        (100001, 105000, 330), (105001, 110000, 350), (110001, 115000, 370),
        (115001, 120000, 390), (120001, 125000, 410), (125001, 130000, 430),
        (130001, 135000, 450), (135001, 140000, 470), (140001, 145000, 490),
        (145001, 150000, 510), (150001, 155000, 520), (155001, 160000, 530),
        (160001, 165000, 540), (165001, 170000, 550), (170001, 175000, 560),
        (175001, 180000, 570), (180001, 185000, 580), (185001, 190000, 590),
        (190001, 195000, 600), (195001, 200000, 610), (200001, 205000, 620),
        (205001, 210000, 630), (210001, 215000, 640), (215001, 220000, 650),
        (220001, 225000, 660), (225001, 230000, 670), (230001, 235000, 680),
        (235001, 240000, 690), (240001, 245000, 700), (245001, 999999, 710),
    ],
    "taxi": [
        (0, 30000, 140), (30001, 35000, 150), (35001, 40000, 160),
        (40001, 45000, 175), (45001, 50000, 190), (50001, 55000, 205),
        (55001, 60000, 220), (60001, 65000, 240), (65001, 70000, 260),
        (70001, 75000, 270), (75001, 80000, 280), (80001, 85000, 290),
        (85001, 90000, 300), (90001, 95000, 310), (95001, 100000, 320),
        (100001, 105000, 340), (105001, 110000, 360), (110001, 115000, 380),
        (115001, 120000, 400), (120001, 125000, 420), (125001, 130000, 440),
        (130001, 135000, 460), (135001, 140000, 480), (140001, 145000, 500),
        (145001, 150000, 520), (150001, 155000, 530), (155001, 160000, 540),
        (160001, 165000, 550), (165001, 170000, 560), (170001, 175000, 570),
        (175001, 180000, 580), (180001, 185000, 590), (185001, 190000, 600),
        (190001, 195000, 610), (195001, 200000, 620), (200001, 205000, 630),
        (205001, 210000, 640), (210001, 215000, 650), (215001, 220000, 660),
        (220001, 225000, 670), (225001, 230000, 680), (230001, 235000, 690),
        (235001, 240000, 700), (240001, 245000, 710), (245001, 999999, 720),
    ],
    "uber": [
        (0, 30000, 160), (30001, 35000, 170), (35001, 40000, 180),
        (40001, 45000, 195), (45001, 50000, 210), (50001, 55000, 225),
        (55001, 60000, 240), (60001, 65000, 260), (65001, 70000, 280),
        (70001, 75000, 290), (75001, 80000, 300), (80001, 85000, 310),
        (85001, 90000, 320), (90001, 95000, 330), (95001, 100000, 340),
        (100001, 105000, 360), (105001, 110000, 380), (110001, 115000, 400),
        (115001, 120000, 420), (120001, 125000, 440), (125001, 130000, 460),
        (130001, 135000, 480), (135001, 140000, 500), (140001, 145000, 520),
        (145001, 150000, 540), (150001, 999999, 550),
    ],
    "utilitario": [
        (0, 30000, 160), (30001, 35000, 170), (35001, 40000, 180),
        (40001, 45000, 195), (45001, 50000, 210), (50001, 55000, 225),
        (55001, 60000, 240), (60001, 65000, 260), (65001, 70000, 280),
        (70001, 75000, 290), (75001, 80000, 300), (80001, 85000, 310),
        (85001, 90000, 320), (90001, 95000, 330), (95001, 100000, 340),
        (100001, 105000, 360), (105001, 110000, 380), (110001, 115000, 400),
        (115001, 120000, 420), (120001, 125000, 440), (125001, 130000, 460),
        (130001, 135000, 480), (135001, 140000, 500), (140001, 145000, 520),
        (145001, 150000, 540), (150001, 999999, 550),
    ],
    "moto": [
        (0, 10000, 105), (10001, 15000, 125), (15001, 20000, 145),
        (20001, 25000, 165), (25001, 30000, 185), (30001, 35000, 205),
        (35001, 40000, 225), (40001, 45000, 265), (45001, 50000, 305),
        (50001, 55000, 345), (55001, 60000, 385), (60001, 65000, 425),
        (65001, 999999, 465),
    ],
}

COTA_PARTICIPACAO = {
    "passeio": 5, "taxi": 5, "uber": 5,
    "utilitario": 5, "moto": 10, "diferenciado": 10,
}

ADESAO = {
    "passeio": "Sem mínimo", "taxi": "Sem mínimo", "uber": "Sem mínimo",
    "utilitario": "Sem mínimo", "moto": "Sem mínimo",
    "vans": "R$ 500,00+",
}

def calcular_mensalidade(valor_fipe: float, categoria: str) -> float:
    """Retorna a mensalidade baseada no valor FIPE e categoria."""
    tabela = TABELA_PRECOS.get(categoria.lower(), TABELA_PRECOS["passeio"])
    for faixa_min, faixa_max, mensalidade in tabela:
        if faixa_min <= valor_fipe <= faixa_max:
            return float(mensalidade)
    # Se acima da última faixa, usa a última
    return float(tabela[-1][2])


def calcular_cota(valor_fipe: float, categoria: str) -> float:
    """Retorna o valor da cota de participação."""
    pct = COTA_PARTICIPACAO.get(categoria.lower(), 5)
    cota = valor_fipe * (pct / 100)
    return max(cota, 2000.0)  # Mínimo R$2.000


def montar_proposta_texto(
    nome_cliente: str,
    marca: str,
    modelo: str,
    ano: int,
    valor_fipe: float,
    categoria: str,
) -> str:
    """Monta a proposta formatada para envio no WhatsApp."""
    mensalidade = calcular_mensalidade(valor_fipe, categoria)
    cota = calcular_cota(valor_fipe, categoria)
    cota_pct = COTA_PARTICIPACAO.get(categoria.lower(), 5)

    cat_map = {
        "passeio": "PASSEIO",
        "taxi": "TÁXI",
        "uber": "APP/UBER",
        "utilitario": "UTILITÁRIO",
        "moto": "MOTO",
    }
    plano = cat_map.get(categoria.lower(), categoria.upper())

    coberturas = "✔ Roubo e Furto\n✔ Colisão\n✔ Perda Total\n✔ Incêndio\n✔ Fenômenos da Natureza\n✔ Assistência 24h nacional\n✔ Clube de Benefícios"
    if categoria.lower() == "taxi":
        coberturas += "\n✔ Dias parados (táxi)"
    if categoria.lower() == "moto":
        coberturas = "✔ Roubo e Furto\n✔ Perda Total\n✔ Incêndio\n✔ Assistência 24h"

    proposta = f"""*{nome_cliente}*, segue sua cotação! 😊

🚗 *{marca} {modelo} {ano}*
📋 FIPE: *R$ {valor_fipe:,.2f}*

━━━━━━━━━━━━━━━━━━━
*PLANO {plano}*

{coberturas}

💰 *Mensalidade: R$ {mensalidade:,.2f}*
🤝 Cota de participação: {cota_pct}% FIPE
━━━━━━━━━━━━━━━━━━━

Gostou dessa condição? 😊"""

    return proposta


# ---------------------------------------------------------------------------
# Camada atualizada
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _carregar_config_comercial() -> dict:
    path = Path(APP_DIR) / "data" / "ia_comercial_config.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _cfg_fipe(chave: str, default=None):
    valor = _carregar_config_comercial().get("fipe", {}).get(chave, default)
    return default if valor in ("", None) else valor


def obter_produtos_inclusos(categoria: str = "passeio") -> list[str]:
    produtos = _cfg_fipe("produtos_inclusos", {})
    if not isinstance(produtos, dict):
        produtos = {}
    lista = produtos.get((categoria or "passeio").lower(), produtos.get("passeio", []))
    return lista if isinstance(lista, list) else []


def obter_nome_plano(categoria: str = "passeio") -> str:
    planos = _cfg_fipe("planos", {})
    if not isinstance(planos, dict):
        planos = {}
    return str(planos.get((categoria or "passeio").lower(), (categoria or "passeio").upper()))


def consultar_fipe(marca_nome: str, modelo_nome: str, ano: int, tipo: str = "carros", versao: str = "") -> dict | None:
    """
    Consulta o valor FIPE de um veiculo pelo nome da marca, modelo, ano e opcionalmente versao.
    Retorna dict com Valor, Marca, Modelo, AnoModelo, CodigoFipe ou None.
    """
    modelo_busca = modelo_nome or ""
    marcas = buscar_marcas(tipo)
    if not marcas:
        return None

    melhor_marca = max(marcas, key=lambda m: _match_score(marca_nome, m.get("nome", "")))
    if _match_score(marca_nome, melhor_marca.get("nome", "")) == 0:
        return None

    marca_id = melhor_marca["codigo"]
    modelos = buscar_modelos(tipo, marca_id)
    if not modelos:
        return None

    melhor_modelo = max(modelos, key=lambda m: _score_modelo(modelo_busca, m.get("nome", ""), versao))
    if _match_score(modelo_busca, melhor_modelo.get("nome", "")) == 0:
        return None

    modelo_id = melhor_modelo["codigo"]
    anos = buscar_anos(tipo, marca_id, str(modelo_id))
    if not anos:
        return None

    ano_encontrado = None
    for a in anos:
        nome_ano = a.get("nome", "")
        if str(ano) in nome_ano:
            ano_encontrado = a
            break

    if not ano_encontrado:
        def dist_ano(a):
            match = re.search(r"\d{4}", a.get("nome", ""))
            return abs(int(match.group()) - ano) if match else 9999

        ano_encontrado = min(anos, key=dist_ano)

    return buscar_valor(tipo, marca_id, str(modelo_id), ano_encontrado["codigo"])


def montar_proposta_texto(
    nome_cliente: str,
    marca: str,
    modelo: str,
    ano: int,
    valor_fipe: float,
    categoria: str,
    versao: str = "",
    produtos_inclusos: list[str] | None = None,
) -> str:
    """Monta a proposta formatada para envio no WhatsApp."""
    mensalidade = calcular_mensalidade(valor_fipe, categoria)
    cota = calcular_cota(valor_fipe, categoria)
    cota_pct = COTA_PARTICIPACAO.get(categoria.lower(), 5)
    plano = obter_nome_plano(categoria)
    produtos = produtos_inclusos if produtos_inclusos is not None else obter_produtos_inclusos(categoria)
    produtos = [p for p in produtos if str(p).strip()]

    veiculo = f"{marca} {modelo}".strip()
    if ano:
        veiculo = f"{veiculo} {ano}".strip()
    if versao:
        veiculo = f"{veiculo} {versao}".strip()

    produtos_txt = "\n".join(f"• {item}" for item in produtos) if produtos else "• Roubo e Furto\n• Colisao\n• Assistencia 24h"

    proposta = (
        f"*PROPOSTA COMERCIAL*\n\n"
        f"*Associado:* {nome_cliente}\n"
        f"*Veiculo:* {veiculo}\n"
        f"*FIPE:* *R$ {valor_fipe:,.2f}*\n"
        f"*Plano:* {plano}\n\n"
        f"*Produtos inclusos:*\n{produtos_txt}\n\n"
        f"*Mensalidade:* *R$ {mensalidade:,.2f}*\n"
        f"*Cota de participacao:* {cota_pct}% FIPE\n"
        f"*Cota estimada:* R$ {cota:,.2f}\n\n"
        f"Se quiser, eu ja sigo com a formalizacao."
    )
    return proposta
