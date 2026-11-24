# PFI 1.0 — primeira versão consolidada
Aplicação local para gestão financeira pessoal, sem IA, sem chaves bancárias, sem ordens de negociação. Python 3.10+, FastAPI, SQLite, HTML/CSS/JS. Esta entrega consolida as etapas 0.3–1.0; é uma base para testes do usuário, não uma certificação de produção.

## Atualização Windows
1. Encerre o servidor anterior. Copie a pasta PFI inteira, inclusive `data/pfi.db`, para local privado.
2. Extraia o ZIP e copie o conteúdo da pasta PFI sobre a anterior, substituindo somente código. Não exclua `data/` nem `.venv` se estiverem funcionais. Não há banco no pacote.
3. Execute `iniciar.bat` e abra http://127.0.0.1:8000. A instalação requer internet; o uso local funciona offline, exceto atualização de mercado. API: http://127.0.0.1:8000/docs.
4. Confira saldos, metas e histórico após a migração. Um backup SQLite `pfi-pre-v1-*.db` é criado em `data/` antes da migração. Se necessário, pare o servidor, preserve o banco atual e restaure a cópia anterior.
Linux/macOS: `python3 -m venv .venv`; `source .venv/bin/activate`; `pip install -r requirements.txt`; `python -m uvicorn main:app --host 127.0.0.1 --port 8000`.

## Operação diária
- Patrimônio: saldo de cada ativo ou dívida, manual, sem sincronização com banco. Dados iniciais informados, não verificados: Caixa R$50.000; computador R$5.211 nominais restantes; despesa mensal R$1.000; meta R$100.000. São exemplos pessoais, não saldos consultados.
- Movimentações, parcelas e diário de investimentos: registros independentes; atualize o saldo manualmente uma única vez. Não conte a transferência entre contas como renda. Pagamento registrado reduz dívida nominal, não saldo bancário. Não calcula desconto de quitação.
- Investimentos: classifique o ativo previamente cadastrado, indique instituição, custo remanescente, liquidez, vencimento, taxa e data do saldo. Variação sobre custo não é retorno total, líquido ou anualizado. Não atualiza cotações de ações automaticamente.
- Histórico: salve a posição do dia; nenhum histórico é reconstruído artificialmente.
- Mercado: botão de atualização consulta API pública do Banco Central, séries SGS 432, 12, 433 e 1; datas e unidades são exibidas. Falhas preservam último cache. A consulta externa real ainda deve ser validada na sua rede. Nenhum dado pessoal é enviado ao BCB.
- Comparador: taxas de duas ofertas em % do CDI, CDI anual hipotético, dias úteis explícitos, imposto configurável. Não contempla IOF (mínimo 30 dias), taxas, inadimplência, regras tributárias individuais ou liquidez. Verifique tributos vigentes antes de investir. Não é um precificador de Tesouro IPCA+ ou títulos prefixados.
- Análises e alertas: metas por classe somando 100%, reserva por meses de despesas, concentração por instituição, vencimentos, saldos antigos. A liquidez é declarada pelo usuário; não equivale a proteção pelo FGC. Alertas apenas ao abrir a aba, sem serviço em segundo plano.
- Independência: três hipóteses de retorno nominal, ajustadas pela inflação, aportes em poder de compra constante; taxa de retirada escolhida pelo usuário. Não modela volatilidade, sequência de retornos ou garantia de renda futura.
- Relatórios: fechamento mensal e CSV. Backup em Configurações.

## Segurança
Somente rede local loopback. Banco sem criptografia e sem autenticação. Não exponha à internet, não sincronize em repositório público. Os backups contêm dados pessoais. Guarde-os em local privado. O arquivo de configuração não guarda senhas bancárias.

## Testes
Instale `pip install -r requirements-dev.txt`, execute `python testar.py`. O executor usa banco temporário isolado. Foram aprovados 18 testes Python e a verificação de sintaxe dos três arquivos JS. A navegação automatizada em Chromium foi bloqueada pelo ambiente; validação visual no Windows/Firefox ainda necessária. API de mercado testada com respostas simuladas e falha de rede, não consulta real.

## Versões
`versoes/` contém os ZIPs históricos originais 0.1 e 0.2 e as notas separadas de cada etapa 0.3–1.0. Somente o código da raiz corresponde à versão consolidada atual; não instale os arquivos históricos por cima da versão nova.
