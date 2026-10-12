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
def notify(item):
    token=os.getenv("TELEGRAM_BOT_TOKEN"); chat=os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Telegram nao configurado:",item["id"]); return False
    msg=(f"RADAR IMOBILIARIO | {item['city']} - {item['bairro']}\n"
         f"Preco: R$ {item['price']:,.0f}\nAvaliacao: R$ {item['appraisal']:,.0f}\n"
         f"Desconto sobre avaliacao: {item['discount']}%\n{item['address']}\n"
         f"{item['modality']}\n{item['url']}\n"
         "Conferir disponibilidade, edital, matricula, ocupacao e dividas.")
    req=urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",data=urlencode({"chat_id":chat,"text":msg}).encode())
    with urllib.request.urlopen(req,timeout=20) as r:
        if not json.load(r).get("ok"): raise RuntimeError("Telegram recusou mensagem")
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
    for item in matches:
        key=item["id"]; fingerprint=f"{item['price']:.2f}:{item['modality']}"
        if previous.get(key)==fingerprint: continue
        if baseline and not CONFIG.get("alert_on_first_run",False):
            print("BASELINE",key); updated[key]=fingerprint
        elif notify(item): updated[key]=fingerprint
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"data"/"matches.json").write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Imoveis filtrados:",len(matches))
if __name__=="__main__": main()
