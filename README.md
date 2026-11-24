# PFI v0.1.0
Aplicação local de gestão patrimonial. Python 3.10+; Windows: extraia o ZIP e execute iniciar.bat. Abra http://127.0.0.1:8000. Linux/macOS: python3 -m venv .venv; source .venv/bin/activate; pip install -r requirements.txt; python -m uvicorn main:app --host 127.0.0.1 --port 8000. API documentada em /docs.

A aplicação começa sem ativos ou movimentações pessoais, com preferências genéricas que podem ser alteradas na interface. A carteira-alvo é apenas planejamento. Movimentações não alteram saldos automaticamente: atualize os saldos manualmente. Não há integração bancária, cotações ao vivo, IA, execução de ordens ou cálculo tributário nesta versão.

O banco data/pfi.db é criado na primeira execução. Faça backup pela interface. Para restaurar, encerre o servidor, preserve uma cópia do banco atual e substitua data/pfi.db pelo backup. Não exponha a porta à internet. Não há autenticação nem criptografia; use apenas em computador pessoal confiável. Dependências exigem internet na instalação; uso normal offline. Não publique dados pessoais em GitHub.

Testes: python -m unittest discover -s tests. Valores monetários armazenados em centavos inteiros. Projeções são hipotéticas, nominais e usam taxa anual efetiva convertida para mensal.
