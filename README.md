# sap-automation

Biblioteca Python para automação de tarefas no SAP GUI, usando o SAP GUI Scripting API (pywin32).

Elimina a operação manual repetitiva no SAP — consulte pedidos de compra, folhas de registro de serviço (FRS) e muito mais diretamente do seu código Python.

## Pré-requisitos

- Windows (único SO com suporte ao SAP GUI)
- SAP GUI instalado com **Scripting** habilitado
- Python >= 3.13.3
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes)

## Instalação

```bash
uv pip install -e .
```

Isso instala o pacote em modo edição, refletindo automaticamente qualquer alteração no código fonte.

Se preferir não instalar como pacote, configure a variável `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "$env:PYTHONPATH;C:\caminho\para\src"
```

## Configuração

Copie o arquivo de exemplo e preencha as credenciais:

```bash
cp .env.example .env
```

### `.env.example`

```
# Configurações de ambiente para a automação SAP
SAP_USER=
SAP_PASSWD_PRD=
SAP_PASSWD_QAS=

# Ambiente de execução: PRD ou QAS
SAP_ENV=PRD

# Configurações de conexão para os ambientes PRD e QAS
SAP_CONN_NAME_PRD="F04 - SAP Scripting Transpetro PRD"
SAP_CONN_NAME_QAS="TEQ - SAP ECC Transpetro QAS"

# Configurações adicionais
SAP_CLIENT=400
SAP_LANG=PT
```

A senha carregada depende do ambiente definido em `SAP_ENV` — se `PRD`, usa `SAP_PASSWD_PRD`; se `QAS`, usa `SAP_PASSWD_QAS`.

## Uso

O ponto de entrada é a classe `SAP`, que gerencia a conexão e expõe as transações organizadas por módulo funcional:

```python
from sap_automation import SAPConfig
from sap_automation.sap import SAP

# Conecta ao SAP (lê credenciais do .env)
sap = SAP(SAPConfig.from_env()).connect()

# Consulta um pedido de compras (ME23N)
pedido = sap.mm.me23n("4500012345")
print(pedido.fornecedor_nome)

# Consulta uma Folha de Registro de Serviços (ML81N)
frs = sap.mm.ml81n("1001904414")
print(frs.status_liberacao)

# Lista FRS com filtros (ML84)
lista = sap.mm.ml84(
    pedidos=["4500012345"],
    status="nao_aceito",
)
for item in lista:
    print(item.numero_frs, item.aceito)
```

## Transações disponíveis

| Transação | Módulo | Descrição                      |
|-----------|--------|--------------------------------|
| `ME23N`   | MM     | Consulta de pedido de compras  |
| `ML81N`   | MM     | Consulta de FRS (Folha de Registro de Serviços) |
| `ML84`    | MM     | Listagem de FRS com filtros    |

Novas transações são adicionadas como métodos no respectivo módulo (`sap.mm`, `sap.fi`, `sap.pm`, etc.), bastando implementar a classe `Transaction` correspondente.

## Desenvolvimento

### Setup

```bash
uv sync
```

### Testes

```bash
pytest
```

## Licença

MIT — veja o arquivo [LICENSE](LICENSE) para detalhes.
