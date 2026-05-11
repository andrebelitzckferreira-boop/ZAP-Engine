# =============================================================
# utils/formatter.py — Formatação de telefone, CSV e XLSX
# =============================================================
import re
import csv
import os


def formatar_telefone(telefone: str) -> str:
    """
    Remove tudo que não for dígito e garante código do país.
    Entrada:  '(11) 99999-9999'  ou  '11999999999'  ou  '5511999999999'
    Saída:    '5511999999999'
    """
    apenas_digitos = re.sub(r"\D", "", str(telefone))
    if not apenas_digitos.startswith("55"):
        apenas_digitos = "55" + apenas_digitos
    return apenas_digitos


def importar_csv(caminho: str) -> list[dict]:
    """
    Importa contatos de um arquivo CSV.
    Colunas esperadas: 'telefone' (obrigatório), 'nome' (opcional).

    Exemplo:
        nome,telefone
        João Silva,11999999999
    """
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    contatos = []
    with open(caminho, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "telefone" not in (reader.fieldnames or []):
            raise ValueError("O CSV precisa ter uma coluna chamada 'telefone'.")
        for row in reader:
            telefone = formatar_telefone(row.get("telefone", ""))
            if len(telefone) >= 12:
                contatos.append({
                    "nome": row.get("nome", "").strip(),
                    "telefone": telefone,
                })
    return contatos


def importar_xlsx(caminho: str) -> list[dict]:
    """
    Importa contatos de um arquivo Excel (.xlsx).
    Colunas esperadas: 'telefone' (obrigatório), 'nome' (opcional).
    Aceita qualquer posição de coluna — busca pelo nome do cabeçalho.

    Exemplo de planilha:
        | nome         | telefone    |
        | João Silva   | 11999999999 |
        | Maria        | 11988888888 |
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError(
            "Biblioteca 'openpyxl' não instalada.\n"
            "Rode: pip install openpyxl"
        )

    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb.active

    # Lê o cabeçalho (primeira linha)
    headers = [str(cell.value).strip().lower() if cell.value else "" for cell in ws[1]]

    if "telefone" not in headers:
        raise ValueError(
            "A planilha precisa ter uma coluna chamada 'telefone'.\n"
            f"Colunas encontradas: {[h for h in headers if h]}"
        )

    col_telefone = headers.index("telefone")
    col_nome = headers.index("nome") if "nome" in headers else None

    contatos = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        valor_tel = row[col_telefone]
        if not valor_tel:
            continue
        telefone = formatar_telefone(str(valor_tel))
        if len(telefone) >= 12:
            nome = str(row[col_nome]).strip() if col_nome is not None and row[col_nome] else ""
            contatos.append({"nome": nome, "telefone": telefone})

    wb.close()
    return contatos


def detectar_e_importar(caminho: str) -> list[dict]:
    """
    Detecta automaticamente o tipo de arquivo (.csv ou .xlsx)
    e chama o importador correto.
    """
    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".csv":
        return importar_csv(caminho)
    elif ext in (".xlsx", ".xls", ".xlsm"):
        return importar_xlsx(caminho)
    else:
        raise ValueError(f"Formato não suportado: '{ext}'. Use .csv ou .xlsx")
