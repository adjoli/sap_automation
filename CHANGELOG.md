# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/),
e o versionamento segue o [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.4.0 — 2026-05-24

### Added

- `ReadMode` para controlar profundidade de extração de dados nas transações ML81N e ME23N
- Transação **ML83**: processamento de Folhas de Registro de Serviço, naming de arquivos e tratamento de erros
- Campos `item_pedido`, `local_prest_servico`, `municipio` e `UF` ao modelo FRS
- Testes unitários para ML81N, ML84, SAPConfig e Transaction (classe base)
- Fixture `FakeSAPSession` para testes sem SAP real
- Fixture HTML para relatório vazio no parser ML84
- Documentação README.md com instalação, configuração, uso e transações disponíveis
- AGENTS.md com arquitetura e convenções do projeto

### Changed

- ME23N: modelo e tela aprimorados com novos campos e validações
- ML84: tratamento de status expandido
- Refatoração do pipeline de FRS com função de mapeamento para exibição
- Correção de popup do Windows sem interação manual
- Atualização de dependências (`pyproject.toml`)
- Sessão factory aprimorada para testes ML81N

## v0.3.0 — 2026-05-14

### Added

- Transação **ME23N** (implementação básica inicial + parser HTML + tela)
- Transação **ML84** (listagem de FRS com filtros)
- Componentes reutilizáveis: `TabStrip`, `Section`, `SAPExplorer`
- `TableControl` com validadores de coluna
- `MultiSelection` (seleção múltipla sem intervalos)
- Arquivo `.env.example`

### Fixed

- Parsing de datas SAP para `datetime.date`

### Changed

- Refatoração geral de componentes e telas de automação
- Ajustes em `Config`, `Connection` e `Session`
- ML81N: tipo de retorno de `execute()` ajustado
- `TableControl`: melhorias diversas
- `Session` e mapeamento VKEY aprimorados
- Estrutura de pastas em `models/mm` reorganizada

## v0.2.0 — 2026-04-23

### Added

- Transação **ML81N** (consulta de Folha de Registro de Serviços)
- Componente `TableControl`
- `MultiSelection` (seleção múltipla básica)
- Melhorias em `Session` e mapeamento de teclas (VKEY)

### Changed

- Ajustes no nível de log no módulo `retry` e aplicação no `Session.find`

## v0.1.0 — 2026-04-17

### Added

- Conexão SAP via pywin32
- `SAPConfig` com carregamento de `.env` (dotenv)
- `Session` wrapper com suporte a `findById`
- Primeira versão da transação **ML81N**
- Estrutura base do projeto: `client/`, `transactions/`, `models/`, `core/`, `types/`
