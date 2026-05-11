#!/usr/bin/env python3
# =============================================================
# main.py — Menu interativo do sistema de disparo
# =============================================================
import sys
import os

# Garante que os imports internos funcionem ao rodar main.py diretamente
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, insert_contacts_bulk, count_contacts_by_status, list_campaigns, get_campaign_stats
from services import check_instance, executar_campanha
from utils import importar_csv, importar_xlsx, detectar_e_importar, log


# ── Helpers de UI ────────────────────────────────────────────

def cabecalho():
    print("\n" + "="*55)
    print("  📲  SISTEMA DE DISPARO WHATSAPP — Evolution API")
    print("="*55)


def linha():
    print("-"*55)


def input_int(prompt: str, minimo: int = 1) -> int:
    while True:
        try:
            valor = int(input(prompt))
            if valor < minimo:
                print(f"  ⚠️  Digite um valor maior que {minimo - 1}.")
            else:
                return valor
        except ValueError:
            print("  ⚠️  Digite apenas números inteiros.")


# ── Menus ────────────────────────────────────────────────────

def menu_importar():
    print("\n📥  IMPORTAR CONTATOS")
    linha()
    print("  Opções:")
    print("  [1] Importar de arquivo CSV  (.csv)")
    print("  [2] Importar de planilha Excel (.xlsx)")
    print("  [3] Adicionar número manualmente")
    print("  [0] Voltar")
    opcao = input("\n  Escolha: ").strip()

    if opcao in ("1", "2"):
        tipo = "CSV" if opcao == "1" else "Excel (.xlsx)"
        caminho = input(f"  Caminho do arquivo {tipo}: ").strip().strip('"')
        try:
            contatos = detectar_e_importar(caminho)
            inseridos, duplicados = insert_contacts_bulk(contatos)
            print(f"\n  ✅ {inseridos} contatos importados | ⚠️  {duplicados} duplicados ignorados")
        except Exception as e:
            print(f"\n  ❌ Erro ao importar: {e}")

    elif opcao == "3":
        telefone = input("  Telefone (ex: 11999999999): ").strip()
        nome = input("  Nome (opcional): ").strip()
        from database import insert_contact
        from utils import formatar_telefone
        ok = insert_contact(nome, formatar_telefone(telefone))
        if ok:
            print("  ✅ Contato adicionado!")
        else:
            print("  ⚠️  Telefone já cadastrado.")


def menu_disparar():
    print("\n🚀  NOVO DISPARO EM MASSA")
    linha()

    # Verifica status da instância
    print("  Verificando conexão com WhatsApp...")
    status = check_instance()
    if "error" in status:
        print(f"  ❌ Erro ao conectar na Evolution API: {status['error']}")
        print("  Verifique as configurações em config/settings.py")
        return

    estado = status.get("instance", {}).get("state", "unknown")
    if estado != "open":
        print(f"  ❌ WhatsApp não conectado (estado: {estado}). Escaneie o QR Code na Evolution API.")
        return
    print(f"  ✅ WhatsApp conectado!\n")

    # Mostra resumo de contatos
    contagem = count_contacts_by_status()
    pendentes = contagem.get("pendente", 0)
    print(f"  📋 Contatos pendentes: {pendentes}")
    if pendentes == 0:
        print("  ⚠️  Nenhum contato pendente. Importe contatos primeiro.")
        return

    linha()
    print("  Configure sua campanha:\n")

    nome = input("  Nome da campanha: ").strip() or "Campanha sem nome"

    print("\n  Mensagem (use {nome} para personalizar com o nome do contato):")
    print("  ──────────────────────────────────────────")
    mensagem = input("  > ").strip()
    if not mensagem:
        print("  ❌ Mensagem não pode ser vazia.")
        return

    linha()
    print("\n  ⚙️  Configurações de delay:\n")

    lote_tamanho = input_int(
        f"  Quantas mensagens por lote? (ex: 10): "
    )
    delay_msg_seg = input_int(
        f"  Delay entre mensagens em segundos? (ex: 5): ", minimo=1
    )
    delay_lote_seg = input_int(
        f"  Delay entre lotes em segundos? (ex: 180 para 3 min): ", minimo=1
    )

    linha()
    print(f"\n  Resumo da campanha:")
    print(f"    📛 Nome        : {nome}")
    print(f"    👥 Contatos    : {pendentes}")
    print(f"    📦 Lote        : {lote_tamanho} msgs")
    print(f"    ⏱️  Entre msgs  : {delay_msg_seg}s")
    print(f"    ⏸️  Entre lotes : {delay_lote_seg}s ({delay_lote_seg//60}min {delay_lote_seg%60}s)")
    print(f"    💬 Mensagem    : {mensagem[:60]}{'...' if len(mensagem)>60 else ''}")

    confirma = input("\n  Confirmar disparo? (s/n): ").strip().lower()
    if confirma != "s":
        print("  ❌ Disparo cancelado.")
        return

    executar_campanha(
        nome=nome,
        mensagem=mensagem,
        lote_tamanho=lote_tamanho,
        delay_lote_seg=delay_lote_seg,
        delay_msg_seg=delay_msg_seg,
    )


def menu_relatorio():
    print("\n📊  RELATÓRIOS")
    linha()

    # Contatos
    contagem = count_contacts_by_status()
    print("  Status dos contatos:")
    for status, total in contagem.items():
        icone = {"pendente": "🕐", "enviado": "✅", "erro": "❌"}.get(status, "•")
        print(f"    {icone} {status.capitalize()}: {total}")

    # Campanhas
    campanhas = list_campaigns()
    if campanhas:
        print(f"\n  Campanhas ({len(campanhas)} total):")
        linha()
        for c in campanhas[:10]:   # Mostra as últimas 10
            stats = get_campaign_stats(c["id"])
            env = stats.get("enviado", 0)
            err = stats.get("erro", 0)
            print(f"  [{c['id']}] {c['nome']} — {c['status']}")
            print(f"       ✅ {env} enviados | ❌ {err} erros | 📅 {c['criado_em'][:16]}")
    else:
        print("\n  Nenhuma campanha criada ainda.")


# ── Menu principal ───────────────────────────────────────────

def main():
    init_db()   # Garante que o banco existe

    while True:
        cabecalho()
        contagem = count_contacts_by_status()
        pendentes = contagem.get("pendente", 0)
        print(f"  📋 Contatos pendentes: {pendentes}")
        linha()
        print("  [1] Importar contatos (CSV ou manual)")
        print("  [2] Iniciar disparo em massa")
        print("  [3] Ver relatórios")
        print("  [0] Sair")
        linha()

        opcao = input("  Escolha uma opção: ").strip()

        if opcao == "1":
            menu_importar()
        elif opcao == "2":
            menu_disparar()
        elif opcao == "3":
            menu_relatorio()
        elif opcao == "0":
            print("\n  👋 Até logo!\n")
            sys.exit(0)
        else:
            print("  ⚠️  Opção inválida.")

        input("\n  [Enter para continuar...]")


if __name__ == "__main__":
    main()
