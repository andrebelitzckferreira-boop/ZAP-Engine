import csv
import os
import re
import unicodedata

VALID_STATUSES = {"pendente", "enviado", "respondeu", "erro", "ignorado"}


def _norm_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def formatar_telefone(telefone: str) -> str:
    digits = re.sub(r"\D", "", str(telefone or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("55"):
        national = digits[2:]
    else:
        national = digits

    if len(national) in (10, 11):
        return "55" + national
    return digits


def validar_telefone(telefone: str) -> bool:
    digits = formatar_telefone(telefone)
    if not digits.startswith("55"):
        return False
    national = digits[2:]
    if len(national) not in (10, 11):
        return False
    ddd = national[:2]
    number = national[2:]
    if ddd == "00" or number.startswith("0"):
        return False
    if len(set(number)) <= 2:
        return False
    return True


def normalizar_status(status: str) -> str:
    status = _norm_key(status or "pendente")
    return status if status in VALID_STATUSES else "pendente"


def _row_to_contact(row: dict) -> dict | None:
    row_norm = {_norm_key(k): (v if v is not None else "") for k, v in row.items()}
    telefone_raw = row_norm.get("telefone") or row_norm.get("celular") or row_norm.get("whatsapp") or ""
    telefone = formatar_telefone(telefone_raw)
    if not validar_telefone(telefone):
        return None

    return {
        "nome": str(row_norm.get("nome") or row_norm.get("cliente") or "").strip(),
        "telefone": telefone,
        "cidade": str(row_norm.get("cidade") or row_norm.get("municipio") or "").strip(),
        "status": normalizar_status(row_norm.get("status") or "pendente"),
        "observacoes": str(
            row_norm.get("observacoes")
            or row_norm.get("observacao")
            or row_norm.get("obs")
            or ""
        ).strip(),
    }


def importar_csv(caminho: str) -> list:
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            contatos = []
            with open(caminho, newline="", encoding=enc) as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
                except Exception:
                    dialect = csv.excel
                reader = csv.DictReader(f, dialect=dialect)
                fields = {_norm_key(x) for x in (reader.fieldnames or [])}
                if not fields.intersection({"telefone", "celular", "whatsapp"}):
                    continue
                for row in reader:
                    contato = _row_to_contact(row)
                    if contato:
                        contatos.append(contato)
            if contatos:
                return contatos
        except Exception:
            continue
    raise ValueError("Nao encontrei uma coluna de telefone valida no CSV.")


def importar_xlsx(caminho: str) -> list:
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("Instale openpyxl: pip install openpyxl") from exc

    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb.active

    header_row = None
    headers = []
    for row_idx, row in enumerate(ws.iter_rows(max_row=30, values_only=True), start=1):
        headers = [_norm_key(c) for c in row]
        if set(headers).intersection({"telefone", "celular", "whatsapp"}):
            header_row = row_idx
            break

    if header_row is None:
        wb.close()
        raise ValueError("Coluna telefone/celular/whatsapp nao encontrada na planilha.")

    contatos = []
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        values = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        contato = _row_to_contact(values)
        if contato:
            contatos.append(contato)

    wb.close()
    return contatos


def detectar_e_importar(caminho: str) -> list:
    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".csv":
        return importar_csv(caminho)
    if ext in (".xlsx", ".xlsm"):
        return importar_xlsx(caminho)
    if ext == ".xls":
        raise ValueError("Planilha .xls antiga nao e suportada. Salve como .xlsx.")
    raise ValueError(f"Formato '{ext}' nao suportado. Use .csv ou .xlsx.")
