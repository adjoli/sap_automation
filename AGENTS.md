# sap-automation — AGENTS.md

## Setup
- Python 3.13.3, uv package manager
- `uv pip install -e .` para instalar o pacote (alternativa: `PYTHONPATH=src\`)
- `uv sync` para instalar dependências (incluindo dev)
- Windows-only: depende de `pywin32` + SAP GUI instalado com Scripting habilitado
- Arquivo `.env` obrigatório (ver `.env.example`) com `SAP_USER`, `SAP_PASSWD_PRD`/`SAP_PASSWD_QAS`, `SAP_ENV`

## Comandos
- Rodar todos os testes: `pytest`
- Rodar um arquivo: `pytest tests/unit/test_config.py -v`
- Rodar um teste específico: `pytest tests/unit/test_config.py::TestCarregamento::test_carrega_usuario -v`

## Arquitetura
- Ponto de entrada para o usuário: `SAP(SAPConfig.from_env()).connect()` → expõe `sap.mm.*`
- `main.py` é script de desenvolvimento local — não faz parte da API pública
- Toda transação estende `Transaction` (ABC) com ciclo: `run()` → `go_home() → start() → execute() → finally cleanup()`
- Telas complexas (ME23N) usam `Screen` + `SAPExplorer`; transações simples (ML81N, ML84) acessam `session` direto
- Parsers são funções puras (testáveis sem SAP)

## Estrutura de Diretórios
- `client/` — Config, Connection (COM), Session (wrapper findById)
- `transactions/` — Lógica de negócio por transação SAP (ME23N, ML81N, ML84)
- `components/` — Abstrações reutilizáveis: Explorer, TableControl, TabStrip, Section, MultiSelection
- `models/` — Pydantic: Pedido, FRS, ML84Item, Fiscal
- `parsers/` — Parse de HTML exportado (BeautifulSoup)
- `services/` — SAPExporter (exporta lista para HTML)
- `core/` — converters, logging, retry, timeout, sap_errors
- `types/` — VKEY (mapeamento de teclas)
- `screens/` — Navegação de tela específica (ME23N)

## Convenções
- Ciclo: `go_home() → start() → execute()` com `cleanup()` em `finally`
- `cleanup()` engole exceções — nunca mascara erro de `execute()`
- `SAPConfig.from_env()` lê de variáveis de ambiente (dotenv)
- Modelos Pydantic em `models/mm/`

## Testes
- pytest + pytest-mock
- Test doubles em `tests/fixtures/sap_fake.py`: `FakeSAPSession`, `FakeElement`, `FakeTabStrip`, `FakeTable`
- Fakes são restritivos (lançam exceção para caminho não registrado)

## Gotchas
- `test_connection.py` está comentado — não executa
- `tests/integration/` vazio
- `grid.py` vazio, `variant.py` não validado, `experimental/` vazio
- Sem lint/typecheck configurado
- SAP roda apenas em Windows com SAP GUI + Scripting ativo
