
# Pneutrack — Flask + SQLite + SQLAlchemy

App demo com papéis **Gestor** e **Borracheiro**, persistência em **SQLite** e modelos:
`User, Veiculo, Eixo, Pneu, PosicaoPneu, Historico, ServicoAutorizado`.

## Rodando
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
flask --app app.py init-db   # popula dados demo
python app.py
```
Acesse http://localhost:5000

**Login demo**
- Gestor: `gestor@empresa.com` / `123456`
- Borracheiro: `tecnico@empresa.com` / `123456`

## Notas
- Em **/gestor**, autorize serviços por veículo (criando registros em `ServicoAutorizado`).
- Em **/borracheiro → Fila**, abra um veículo e atualize **pressão, sulco e movimentação** por posição.
  - Movimentações como `estoque`, `vendido`, `sucateado`, `recapagem`, `conserto` **desinstalam** o pneu da posição (fica sem pneu). É criado um registro em `Historico`.
- **Estoque** lista todos os pneus e seus status.

## Próximos passos
- CRUD completo (criar/editar pneus, veículos, eixos) na UI.
- Regras de permissão detalhadas e auditoria.
- Alertas/Notificações em tempo real (Flask-SocketIO) e push.
- Relatórios de custo por km e comparativos por marca/modelo.
- Integração com leitura de **RFID/código de barras**.
- Upload de anexos em Ordens de Serviço.


## Funcionalidades novas
- CRUD de Pneus e Veículos (com adição/remoção de Eixos)
- Ordens de Serviço com itens e custos (totalização, status)


## Extras adicionados
- RFID/Código de barras: busca e vínculo ao pneu
- Checklists de inspeção por veículo (workflow de aprovação Gestor)
- Upload de anexos (OS e Veículo)
- Notificações simples por função (Gestor/Borracheiro)
