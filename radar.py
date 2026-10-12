"""Radar de imoveis da Caixa. Nao executa lances."""
import csv, io, json, os, re, unicodedata, urllib.request
from pathlib import Path
from urllib.parse import urlencode

ROOT=Path(__file__).parent
CONFIG=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
STATE=ROOT/"data"/"seen.json"

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD",str(s or "")) if not unicodedata.combining(c)).lower().strip()
def num(s):
    s=re.sub(r"[^0-9,.\-]","",str(s or ""))
    if "," in s: s=s.replace(".","").replace(",",".")
    try: return float(s)
    except ValueError: return 0.0
def get(row,*names):
    for k,v in row.items():
        if any(norm(n) in norm(k) for n in names): return str(v or "").strip()
    return ""
def fetch(uf):
    url=f"https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_{uf}.csv"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=40) as r: raw=r.read()
    text=raw.decode("utf-8-sig",errors="replace")
    if "cidade" not in norm(text[:3000]): text=raw.decode("latin-1",errors="replace")
    lines=text.splitlines()
    i=next((i for i,line in enumerate(lines) if "cidade" in norm(line) and "imovel" in norm(line)),None)
    if i is None: raise ValueError("Cabecalho CSV nao identificado")
    return list(csv.DictReader(io.StringIO("\n".join(lines[i:])),delimiter=";"))
def match(row,uf):
    rule=CONFIG["locations"][uf]
    city=norm(get(row,"cidade"))
    bairro=norm(get(row,"bairro"))
    if city not in [norm(c) for c in rule["cities"]]: return None
    if rule["neighborhoods"] and not any(norm(n) in bairro for n in rule["neighborhoods"]): return None
    price=num(get(row,"preco","valor de venda"))
    appraisal=num(get(row,"valor de avaliacao","avaliacao"))
    discount=100*(1-price/appraisal) if appraisal>0 else num(get(row,"desconto"))
    if not 0<price<=rule["max_price"] or discount<rule["min_discount"]: return None
    desc=get(row,"descricao","tipo")
    if rule["apartment_only"] and "apartamento" not in norm(desc): return None
    ident=get(row,"n do imovel","n° do imovel","nº do imovel","numero do imovel")
    if not ident: return None
    return {"id":uf+":"+ident,"city":get(row,"cidade"),"bairro":get(row,"bairro"),"price":price,"appraisal":appraisal,"discount":round(discount,1),"address":get(row,"endereco"),"modality":get(row,"modalidade"),"url":get(row,"link de acesso") or "https://venda-imoveis.caixa.gov.br/sistema/busca-imovel.asp"}
def send_digest(matches, changes):
    """Envia resumo diario por SMTP TLS, sem credenciais no codigo."""
    import smtplib
    from email.message import EmailMessage
    host=os.getenv("SMTP_HOST","smtp.gmail.com")
    port=int(os.getenv("SMTP_PORT","465"))
    user=os.getenv("SMTP_USER")
    password=os.getenv("SMTP_PASSWORD")
    recipient=os.getenv("ALERT_EMAIL","arthurgfrota@gmail.com")
    if not user or not password:
        print("E-mail nao configurado: defina SMTP_USER e SMTP_PASSWORD nos Secrets")
        return False
    msg=EmailMessage()
    msg["From"]=user
    msg["To"]=recipient
    msg["Subject"]=f"Radar Imobiliario | {len(changes)} novidades | {len(matches)} oportunidades"
    lines=[
        "RADAR IMOBILIARIO - RELATORIO DIARIO","",
        f"Oportunidades filtradas: {len(matches)}",
        f"Novas ou alteradas: {len(changes)}","",
        "ATENCAO: desconto calculado sobre avaliacao da Caixa, nao sobre valor de mercado.",
        "Verifique edital, matricula, ocupacao, dividas e disponibilidade antes de qualquer decisao.","",
        "NOVIDADES",""
    ]
    for item in sorted(changes,key=lambda x:-x["discount"])[:30]:
        lines.extend([
            f"{item['city']} / {item['bairro']} - R$ {item['price']:,.2f} - desconto {item['discount']}%",
            f"Avaliacao: R$ {item['appraisal']:,.2f} | {item['address']}",
            f"Modalidade: {item['modality']} | {item['url']}",""
        ])
    lines.extend(["","RESUMO DAS MELHORES OPORTUNIDADES",""])
    for item in sorted(matches,key=lambda x:-x["discount"])[:20]:
        lines.append(f"{item['city']} / {item['bairro']} | R$ {item['price']:,.2f} | {item['discount']}% | {item['url']}")
    msg.set_content("\n".join(lines))
    if port==465:
        with smtplib.SMTP_SSL(host,port,timeout=30) as smtp:
            smtp.login(user,password); smtp.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=30) as smtp:
            smtp.starttls(); smtp.login(user,password); smtp.send_message(msg)
    print("Relatorio enviado para",recipient)
    return True
def main():
    previous=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    baseline=not STATE.exists()
    updated=dict(previous); matches=[]; successful=0
    for uf in CONFIG["locations"]:
        try:
            rows=fetch(uf); successful+=1
            print(uf,"linhas:",len(rows))
            matches.extend(item for row in rows if (item:=match(row,uf)))
        except Exception as e: print("ERRO na coleta",uf,repr(e))
    if not successful: raise RuntimeError("Nenhuma fonte coletada com sucesso")
    changes=[]
    for item in matches:
        key=item["id"]; fingerprint=f"{item['price']:.2f}:{item['modality']}"
        if previous.get(key)!=fingerprint:
            changes.append(item)
    sent=send_digest(matches,changes)
    if sent:
        for item in matches:
            updated[item["id"]]=f"{item['price']:.2f}:{item['modality']}"
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"data"/"matches.json").write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Imoveis filtrados:",len(matches))
if __name__=="__main__": main()
