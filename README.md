# Radar Imobiliario

Monitor de anuncios publicos de imoveis da Caixa para Fortaleza, Eusebio e bairros selecionados de Sao Paulo. Projeto experimental; **nao realiza lances** e **nao substitui diligencia juridica**.

## Como funciona
- Busca diariamente CSVs publicos de SP e CE da Caixa.
- Filtra por cidade, bairro, preco e desconto sobre **avaliacao** (nao valor de mercado).
- Mantem historico em `data/seen.json` e lista filtrada em `data/matches.json`.
- Envia alertas pelo Telegram para novos anuncios e mudancas de preco apos o primeiro baseline.

## Telegram
Crie um bot com @BotFather, abra uma conversa com o bot e obtenha o chat ID. No GitHub, em Settings > Secrets and variables > Actions, crie dois **repository secrets**:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

**Nunca publique tokens em arquivos, issues ou mensagens.**

## Execucao
Acesse Actions > Radar Imobiliario > Run workflow. A rotina tambem e agendada para 11:15 UTC (08:15 em Fortaleza/Sao Paulo, horario padrao atual). O agendamento do GitHub pode atrasar.

O primeiro processamento cria um baseline sem enviar alertas antigos. Para receber alertas de todos os resultados na primeira execucao, altere `alert_on_first_run` em `config.json` para `true` antes de executar.

## Limitacoes
Somente a fonte Caixa esta implementada. Zuk, Superbid e leiloeiros locais exigem integracoes adicionais e respeito as condicoes de acesso. Anuncios podem estar desatualizados; valores de avaliacao podem nao refletir o mercado. O historico persistido no repositorio publico tambem e publico. **Nao adicione informacoes privadas ao repositorio.**
