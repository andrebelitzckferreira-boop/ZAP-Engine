#!/usr/bin/env python3
import sys, os, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, jsonify, request
from database import (
    init_db, insert_contacts_bulk, insert_contact,
    count_contacts_by_status, list_campaigns, get_campaign_stats,
    get_pending_contacts, get_antiban_settings, save_antiban_settings,
    get_today_count, get_connection
)
from services.evolution_api import (
    check_instance, send_text_message,
    fetch_conversations, fetch_messages
)
from services.disparo import executar_campanha
from utils.formatter import detectar_e_importar, formatar_telefone

app = Flask(__name__)
PANEL_HTML = open(os.path.join(os.path.dirname(__file__), "templates", "index.html"), encoding="utf-8").read()
campanha_ativa = {"rodando": False}

@app.route("/")
def index(): return PANEL_HTML

@app.route("/api/status")
def api_status():
    c = count_contacts_by_status()
    cps = list_campaigns()
    inst = check_instance()
    ab = get_antiban_settings()
    return jsonify({
        "pendentes": c.get("pendente", 0),
        "enviados": c.get("enviado", 0),
        "erros": c.get("erro", 0),
        "total_campanhas": len(cps),
        "whatsapp_conectado": inst.get("state") == "open",
        "campanha_rodando": campanha_ativa["rodando"],
        "enviados_hoje": get_today_count(),
        "limite_diario": ab.get("daily_limit", 100),
        "warmup_mode": bool(ab.get("warmup_mode", 0)),
        "warmup_day": ab.get("warmup_day", 1),
    })

@app.route("/api/contatos/importar", methods=["POST"])
def api_importar():
    if "arquivo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    arquivo = request.files["arquivo"]
    nome = arquivo.filename or ""
    if not nome.endswith((".csv", ".xlsx", ".xls")):
        return jsonify({"erro": "Use .csv ou .xlsx"}), 400
    tmp = f"/tmp/{nome}"
    arquivo.save(tmp)
    try:
        contatos = detectar_e_importar(tmp)
        inseridos, dup = insert_contacts_bulk(contatos)
        os.remove(tmp)
        return jsonify({"sucesso": True, "inseridos": inseridos, "duplicados": dup})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/contatos/manual", methods=["POST"])
def api_manual():
    d = request.json
    tel = formatar_telefone(d.get("telefone", ""))
    nome = d.get("nome", "")
    if not tel: return jsonify({"erro": "Telefone obrigatório"}), 400
    ok = insert_contact(nome, tel)
    return jsonify({"sucesso": ok, "erro": "Já cadastrado" if not ok else None})

@app.route("/api/contatos/resetar", methods=["POST"])
def api_resetar():
    conn = get_connection()
    conn.execute("UPDATE contacts SET status='pendente' WHERE status!='pendente'")
    conn.commit(); conn.close()
    return jsonify({"sucesso": True})

@app.route("/api/campanhas")
def api_campanhas():
    cps = list_campaigns()
    return jsonify([{
        "id": c["id"], "nome": c["nome"], "status": c["status"],
        "lote_tamanho": c["lote_tamanho"], "delay_msg_seg": c["delay_msg_seg"],
        "delay_lote_seg": c["delay_lote_seg"],
        "enviados": get_campaign_stats(c["id"]).get("enviado", 0),
        "erros": get_campaign_stats(c["id"]).get("erro", 0),
        "criado_em": c["criado_em"],
    } for c in cps])

@app.route("/api/disparar", methods=["POST"])
def api_disparar():
    if campanha_ativa["rodando"]:
        return jsonify({"erro": "Campanha já em andamento"}), 409
    d = request.json
    mensagens = [m.strip() for m in d.get("mensagens", []) if m.strip()]
    if not mensagens: return jsonify({"erro": "Informe pelo menos 1 mensagem"}), 400
    pendentes = get_pending_contacts()
    if not pendentes: return jsonify({"erro": "Nenhum contato pendente"}), 400

    def rodar():
        campanha_ativa["rodando"] = True
        try:
            executar_campanha(
                nome=d.get("nome", "Campanha"),
                mensagens=mensagens,
                lote_tamanho=int(d.get("lote_tamanho", 10)),
                delay_lote_seg=int(d.get("delay_lote_seg", 180)),
                delay_msg_seg=int(d.get("delay_msg_seg", 5)),
                media_url=d.get("media_url") or None,
                media_type=d.get("media_type") or None,
                daily_limit=int(d.get("daily_limit", 0)),
            )
        finally:
            campanha_ativa["rodando"] = False

    threading.Thread(target=rodar, daemon=True).start()
    return jsonify({"sucesso": True, "mensagem": f"Campanha '{d.get('nome')}' iniciada!"})

@app.route("/api/antiban", methods=["GET"])
def api_antiban_get():
    return jsonify(get_antiban_settings())

@app.route("/api/antiban", methods=["POST"])
def api_antiban_save():
    d = request.json
    save_antiban_settings(
        daily_limit=int(d.get("daily_limit", 100)),
        warmup_mode=bool(d.get("warmup_mode", False)),
        warmup_day=int(d.get("warmup_day", 1)),
    )
    return jsonify({"sucesso": True})

@app.route("/api/chat/conversas")
def api_conversas():
    try:
        convs = fetch_conversations()
        result = []
        for c in convs[:30]:
            jid = c.get("id", "")
            numero = jid.replace("@s.whatsapp.net","").replace("@g.us","")
            result.append({
                "jid": jid,
                "numero": numero,
                "nome": c.get("pushName") or c.get("name") or numero,
                "ultimo": c.get("lastMessage", {}).get("messageTimestamp", 0),
                "nao_lidas": c.get("unreadCount", 0),
            })
        return jsonify(result)
    except Exception as e:
        return jsonify([])

@app.route("/api/chat/mensagens", methods=["POST"])
def api_mensagens():
    jid = request.json.get("jid", "")
    msgs = fetch_messages(jid, limit=40)
    result = []
    for m in (msgs.get("messages", {}).get("records", []) if isinstance(msgs, dict) else msgs):
        content = (m.get("message") or {})
        texto = (content.get("conversation") or
                 content.get("extendedTextMessage", {}).get("text") or
                 "[mídia]")
        result.append({
            "de_mim": m.get("key", {}).get("fromMe", False),
            "texto": texto,
            "hora": m.get("messageTimestamp", 0),
        })
    return jsonify(result)

@app.route("/api/chat/responder", methods=["POST"])
def api_responder():
    d = request.json
    numero = d.get("numero", "")
    texto = d.get("texto", "")
    if not numero or not texto:
        return jsonify({"erro": "Número e texto obrigatórios"}), 400
    res = send_text_message(numero, texto)
    return jsonify(res)

if __name__ == "__main__":
    init_db()
    print("\n" + "="*50)
    print("  📲  PAINEL ZAP DISPARO")
    print("  Acesse: http://localhost:5000")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
