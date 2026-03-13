# Guia de Migração: Python Bots MySQL → PostgreSQL

Este documento contém todas as instruções necessárias para migrar bots Python que fazem upsert em MySQL para o novo banco PostgreSQL 16. Use este arquivo como contexto ao pedir ao Claude para refatorar o código.

---

## 1. Contexto da Migração

O Hub PMO migrou de **3 bancos MySQL separados** para **1 banco PostgreSQL com 3 schemas**:

| Antes (MySQL) | Depois (PostgreSQL) |
|---|---|
| `omie_db.a_pagar` | `omie.a_pagar` |
| `omie_db.nf_faturadas` | `omie.nf_faturadas` |
| `omie_db.notas_debito` | `omie.notas_debito` |
| `psoffice.projetos` | `psoffice.projetos` |
| `psoffice.atividades` | `psoffice.atividades` |
| `psoffice.<tabela>` | `psoffice.<tabela>` |
| `pmo_hub_db.users` | `public.users` (ou apenas `users`) |

---

## 2. Variáveis de Ambiente (.env)

As variáveis de ambiente são **idênticas** ao projeto Hub PMO:

```env
DB_HOST=<host_do_postgresql>
DB_PORT=<porta>
DB_NAME=pmo_hub
DB_USER=pmo_admin
DB_PASSWORD=<senha>
DB_POOL_MAX=5
DB_POOL_MIN=0
```

---

## 3. Dependência Python

### Remover
```
mysql-connector-python
pymysql
mysqlclient
```
(qualquer driver MySQL que esteja no `requirements.txt`)

### Adicionar
```
psycopg2-binary>=2.9.9
```

Ou, se preferir o wrapper mais moderno:
```
psycopg[binary]>=3.1
```

> **Recomendação:** Use `psycopg2-binary` por ser o mais estável e documentado. Os exemplos abaixo usam `psycopg2`.

---

## 4. Conexão com o Banco

### ANTES (MySQL)
```python
import mysql.connector

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASS'),
    database=os.getenv('DB_NAME')
)
cursor = conn.cursor()
```

### DEPOIS (PostgreSQL)
```python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 5432)),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cursor = conn.cursor()
```

**Mudanças importantes:**
- `database=` → `dbname=`
- `DB_PASS` → `DB_PASSWORD`
- Adicionado `port=` (PostgreSQL pode não estar na porta padrão)
- O `autocommit` é `False` por padrão no psycopg2 (precisa de `conn.commit()` explícito)

---

## 5. Sintaxe SQL: Diferenças Críticas

### 5.1 — Upsert (a mudança mais importante)

**ANTES (MySQL):**
```python
cursor.execute("""
    INSERT INTO tabela (id, col1, col2)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
        col1 = VALUES(col1),
        col2 = VALUES(col2)
""", (id_val, val1, val2))
```

**DEPOIS (PostgreSQL):**
```python
cursor.execute("""
    INSERT INTO schema.tabela (id, col1, col2)
    VALUES (%s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        col1 = EXCLUDED.col1,
        col2 = EXCLUDED.col2
""", (id_val, val1, val2))
```

**Diferenças-chave:**
| MySQL | PostgreSQL |
|---|---|
| `ON DUPLICATE KEY UPDATE` | `ON CONFLICT (coluna_pk) DO UPDATE SET` |
| `VALUES(col)` | `EXCLUDED.col` |
| Não precisa especificar a coluna de conflito | **Obrigatório** especificar `ON CONFLICT (pk_column)` |

### 5.2 — Placeholders de Parâmetros

Os placeholders `%s` do `psycopg2` são **iguais** ao `mysql-connector-python`. Não precisa mudar.

> Se o bot usava `?` (sqlite-style) ou `%(name)s` (named), o `psycopg2` suporta ambos `%s` e `%(name)s`.

### 5.3 — Quoting de Identificadores

**MySQL usa backticks:**
```sql
INSERT INTO `tabela` (`coluna com espaço`) VALUES (...)
```

**PostgreSQL usa aspas duplas:**
```sql
INSERT INTO "tabela" ("coluna com espaço") VALUES (...)
```

> **Regra prática:** Se o nome da coluna contém espaços, acentos, parênteses, barra `/`, ou começa com maiúscula — **deve** ser envolvido em aspas duplas `"..."`.

### 5.4 — Booleanos

**MySQL:** `TINYINT(1)` com valores `0` e `1`
**PostgreSQL:** `BOOLEAN` nativo com `TRUE`/`FALSE`

```python
# Python bool funciona direto com psycopg2
cursor.execute("INSERT INTO tabela (ativo) VALUES (%s)", (True,))
cursor.execute("INSERT INTO tabela (ativo) VALUES (%s)", (False,))

# Se o dado vem como 0/1 do relatório, converta:
valor_bool = bool(int(valor_original))
```

### 5.5 — REPLACE INTO (não existe no PostgreSQL)

Se o bot usa `REPLACE INTO`:
```python
# ANTES (MySQL):
cursor.execute("REPLACE INTO tabela (id, col1) VALUES (%s, %s)", (1, 'val'))

# DEPOIS (PostgreSQL) - use ON CONFLICT com todos os campos:
cursor.execute("""
    INSERT INTO schema.tabela (id, col1)
    VALUES (%s, %s)
    ON CONFLICT (id) DO UPDATE SET
        col1 = EXCLUDED.col1
""", (1, 'val'))
```

### 5.6 — TRUNCATE

```python
# MySQL:
cursor.execute("TRUNCATE TABLE tabela")

# PostgreSQL (idêntico, mas pode precisar de CASCADE):
cursor.execute("TRUNCATE TABLE schema.tabela CASCADE")
# Ou reiniciar sequences:
cursor.execute("TRUNCATE TABLE schema.tabela RESTART IDENTITY CASCADE")
```

### 5.7 — Commit e Autocommit

```python
# psycopg2 NÃO faz autocommit por padrão
conn = psycopg2.connect(...)

# Opção 1: Commit explícito (recomendado para bots com upsert em lote)
cursor.execute("INSERT INTO ...")
cursor.execute("INSERT INTO ...")
conn.commit()  # OBRIGATÓRIO

# Opção 2: Autocommit
conn.autocommit = True  # Cada statement é commitado automaticamente
```

---

## 6. Bulk Upsert Eficiente

Para bots que inserem muitos registros de uma vez, use `execute_values` do psycopg2:

```python
from psycopg2.extras import execute_values

data = [
    (id1, val1a, val1b),
    (id2, val2a, val2b),
    (id3, val3a, val3b),
]

execute_values(
    cursor,
    """
    INSERT INTO omie.a_pagar (id, "Tipo", "Valor da Conta")
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
        "Tipo" = EXCLUDED."Tipo",
        "Valor da Conta" = EXCLUDED."Valor da Conta"
    """,
    data,
    page_size=1000  # Envia em lotes de 1000
)
conn.commit()
```

> `execute_values` é **10-100x mais rápido** que `executemany` para grandes volumes.

---

## 7. Schemas e Prefixos de Tabela

Toda query deve usar o prefixo do schema:

```python
# Tabelas Omie:
cursor.execute('SELECT * FROM omie.a_pagar WHERE ...')
cursor.execute('INSERT INTO omie.nf_faturadas (...) VALUES ...')
cursor.execute('INSERT INTO omie.notas_debito (...) VALUES ...')

# Tabelas PSOffice:
cursor.execute('SELECT * FROM psoffice.projetos WHERE ...')
cursor.execute('INSERT INTO psoffice.atividades (...) VALUES ...')

# Tabelas públicas (schema public):
cursor.execute('SELECT * FROM users WHERE ...')  # public é default, não precisa prefixo
```

**Alternativa:** Definir o search_path na conexão:
```python
# Se o bot só mexe em um schema (ex: só omie):
cursor.execute("SET search_path TO omie")
# Agora pode usar sem prefixo:
cursor.execute("SELECT * FROM a_pagar WHERE ...")
```

---

## 8. Referência Completa das Tabelas

### 8.1 — Schema `omie`

#### `omie.a_pagar`
- **PK:** `id` (SERIAL — auto-incremento)
- **Colunas (TODAS precisam de aspas duplas por ter espaços/acentos):**

| Coluna | Tipo PostgreSQL |
|---|---|
| `id` | SERIAL (auto) |
| `"Data de Vencimento (completa)"` | TIMESTAMP |
| `"Data de Emissão (completa)"` | TIMESTAMP |
| `"Última Data de Pagto ou Recbto (completa)"` | TIMESTAMP |
| `"Tipo"` | VARCHAR(50) |
| `"Origem"` | VARCHAR(54) |
| `"NF/CF"` | VARCHAR(50) |
| `"Cliente ou Fornecedor (Nome Fantasia)"` | VARCHAR(144) |
| `"Categoria"` | VARCHAR(88) |
| `"Departamento"` | VARCHAR(73) |
| `"Projeto"` | VARCHAR(90) |
| `"Valor da Conta"` | NUMERIC(15,2) |
| `"Impostos Retidos"` | NUMERIC(15,2) |
| `"Pago ou Recebido"` | NUMERIC(15,2) |
| `"A Pagar ou Receber"` | NUMERIC(15,2) |
| `"Valor Líquido"` | NUMERIC(15,2) |
| `"Grupo"` | VARCHAR(55) |
| `"Situação"` | VARCHAR(50) |
| `"CNPJ/CPF"` | VARCHAR(50) |
| `created_at` | TIMESTAMPTZ (auto) |
| `updated_at` | TIMESTAMPTZ (auto via trigger) |

**Exemplo de upsert:**
```python
cursor.execute("""
    INSERT INTO omie.a_pagar (
        "Data de Vencimento (completa)",
        "Data de Emissão (completa)",
        "Tipo",
        "NF/CF",
        "Cliente ou Fornecedor (Nome Fantasia)",
        "Valor da Conta",
        "Situação"
    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        "Data de Vencimento (completa)" = EXCLUDED."Data de Vencimento (completa)",
        "Tipo" = EXCLUDED."Tipo",
        "NF/CF" = EXCLUDED."NF/CF",
        "Cliente ou Fornecedor (Nome Fantasia)" = EXCLUDED."Cliente ou Fornecedor (Nome Fantasia)",
        "Valor da Conta" = EXCLUDED."Valor da Conta",
        "Situação" = EXCLUDED."Situação"
""", (dt_venc, dt_emissao, tipo, nf_cf, cliente, valor, situacao))
```

#### `omie.nf_faturadas`
- **PK:** `id` (SERIAL)
- **Colunas:**

| Coluna | Tipo |
|---|---|
| `id` | SERIAL (auto) |
| `"Data de Emissão (completa)"` | TIMESTAMP |
| `"Data de Vencimento (completa)"` | TIMESTAMP |
| `"Situação"` | VARCHAR(50) |
| `"NF/CF"` | VARCHAR(50) |
| `"Cliente ou Fornecedor (Razão Social)"` | VARCHAR(90) |
| `"Cliente ou Fornecedor (Nome Fantasia)"` | VARCHAR(82) |
| `"Projeto"` | VARCHAR(88) |
| `"Departamento"` | VARCHAR(55) |
| `"Parcela"` | VARCHAR(50) |
| `"Valor da Conta"` | NUMERIC(15,2) |
| `"Impostos Retidos"` | NUMERIC(15,2) |
| `"Valor Líquido"` | NUMERIC(15,2) |
| `"Pago ou Recebido"` | NUMERIC(15,2) |
| `"A Pagar ou Receber"` | NUMERIC(15,2) |
| `"Tipo"` | VARCHAR(50) |
| `"ISS Retido"` | NUMERIC(15,2) |
| `"COFINS Retido"` | NUMERIC(15,2) |
| `"PIS Retido"` | NUMERIC(15,2) |
| `"Multa"` | NUMERIC(15,2) |
| `"Desconto"` | NUMERIC(15,2) |
| `created_at` | TIMESTAMPTZ (auto) |
| `updated_at` | TIMESTAMPTZ (auto via trigger) |

#### `omie.notas_debito`
- **PK:** `id` (SERIAL)
- **Colunas:**

| Coluna | Tipo |
|---|---|
| `id` | SERIAL (auto) |
| `"Situação"` | VARCHAR(50) |
| `"Data de Emissão (completa)"` | TIMESTAMP |
| `"Data de Vencimento (completa)"` | TIMESTAMP |
| `"NF/CF"` | VARCHAR(50) |
| `"Cliente ou Fornecedor (Nome Fantasia)"` | VARCHAR(84) |
| `"Projeto"` | VARCHAR(85) |
| `"Departamento"` | VARCHAR(50) |
| `"Valor da Conta"` | NUMERIC(15,2) |
| `"Pago ou Recebido"` | NUMERIC(15,2) |
| `"A Pagar ou Receber"` | NUMERIC(15,2) |
| `"Grupo"` | VARCHAR(55) |
| `"Desconto"` | NUMERIC(15,2) |
| `created_at` | TIMESTAMPTZ (auto) |
| `updated_at` | TIMESTAMPTZ (auto via trigger) |

---

### 8.2 — Schema `psoffice`

> **Importante:** As tabelas do psoffice usam PKs **não auto-incrementais** (exceto `relatorio_pso_insights_llm`). Os IDs são fornecidos pelo sistema PSOffice e devem ser passados pelo bot.

#### Tabelas com PK simples (INTEGER)

| Tabela | PK | Colunas BOOLEAN |
|---|---|---|
| `psoffice.projetos` | `"PROJ_ID"` | `"IND_IMPOSTOS_NA_TAXA_FAT"`, `"IND_HR_FAT_ATIV_OS"`, `"IND_HORAS_FATURAVEIS"`, `"IND_APO_BLOQ"`, `"IND_FAT_BLOQ"`, `"IND_PLAN_BLOQ"`, `"IND_OS_HABILITADO"`, `"IND_CALCULO_MANUAL"`, `"IND_DT_PREV_ATUALIZADA"`, `"IND_BILLIMATIC_PREV"`, `"IND_BILLIMATIC_FAT_AUTOMATICO"`, `"AGILE_IND_APONTAMENTO"`, `"AGILE_IND_PROJETO"` |
| `psoffice.atividades` | `"ATIV_ID"` | `"IND_ENCERRADA"`, `"IND_ETAPA"`, `"IND_APROVADA"`, `"IND_APO_BLOQUEADO"`, `"IND_OS"`, `"IND_OS_INICIAL"`, `"IND_OS_FINAL"`, `"IND_HORAS_FATURAVEIS"` |
| `psoffice.apontamentos` | `"APON_ID"` | nenhuma |
| `psoffice.atribuicoes` | `"ATRIB_ID"` | nenhuma |
| `psoffice.info_colabs` | `"USU_ID"` | `"ATIVO"`, `"IND_BANCO_HORAS"`, `"IND_APONTAMENTO_HORAS"` |
| `psoffice.empresas` | `"PJ_ID"` | nenhuma (usa VARCHAR(1) 'S'/'N') |
| `psoffice.faturamento` | `"MF_ID"` | nenhuma |
| `psoffice.despesas` | `"DESP_ID"` | nenhuma (usa VARCHAR(1)) |
| `psoffice.despesa_tipo` | `"DESPT_ID"` | `"IND_ATIVO"` |
| `psoffice.despesa_orcada` | `"DESPT_ID"` | `"REEMBOLSAVEL"`, `"COBRAVEL"`, `"APON_BLOQUEADO"` |
| `psoffice.centros_de_resultado` | `"CR_ID"` | `"IND_ATIVO"`, `"IND_ADIANTAMENTOS"` |
| `psoffice.agrupamento` | `"FUNC_ID"` | nenhuma |
| `psoffice.calendarios` | `"CAL_ID"` | nenhuma |
| `psoffice.d_calend_proj` | `"PROJ_ID"` | nenhuma |
| `psoffice.grref` | `"PROJ_ID"` | nenhuma |
| `psoffice.pso_taxa` | `"TAXA_ID"` | nenhuma |
| `psoffice.pso_usu_funcoes` | `"USU_ID"` | nenhuma |
| `psoffice.recursos` | `"PROJREC_ID"` | nenhuma |
| `psoffice.resumo_de_horas` | `"RESHR_ID"` | nenhuma |
| `psoffice.resumo_de_horas_ativ` | `"RESHRATI_ID"` | nenhuma |
| `psoffice.taxa_historico` | `"TAXAH_ID"` | nenhuma |
| `psoffice.relatorio_de_colaboradores` | `"Login"` (VARCHAR) | nenhuma |
| `psoffice.relatorio_pso_realizado` | `"APON_ID"` | `"ATIVO"` |
| `psoffice.relatorio_pso_insights_llm` | `id_insight` (SERIAL) | nenhuma |

#### Tabelas com PK composta

| Tabela | PK Composta | Colunas BOOLEAN |
|---|---|---|
| `psoffice.relatorio_pso_orcado` | `("PROJ_ID", "TX_ID_RECURSO")` | `"ATIVO"` |
| `psoffice.relatorio_pso_planejado` | `("PROJ_ID", "ATIV_ID", "ATRIB_ID")` | `"ATIVO"` |

**Exemplo upsert PK composta:**
```python
cursor.execute("""
    INSERT INTO psoffice.relatorio_pso_orcado (
        "PROJ_ID", "TX_ID_RECURSO", "CODIGO_PROJETO", "NOME_PROJETO",
        "VALOR_PROJETO", "ATIVO", "NOME_RECURSO", "TX_RECURSO"
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT ("PROJ_ID", "TX_ID_RECURSO") DO UPDATE SET
        "CODIGO_PROJETO" = EXCLUDED."CODIGO_PROJETO",
        "NOME_PROJETO" = EXCLUDED."NOME_PROJETO",
        "VALOR_PROJETO" = EXCLUDED."VALOR_PROJETO",
        "ATIVO" = EXCLUDED."ATIVO",
        "NOME_RECURSO" = EXCLUDED."NOME_RECURSO",
        "TX_RECURSO" = EXCLUDED."TX_RECURSO"
""", (proj_id, tx_id, codigo, nome, valor, True, nome_rec, taxa))
```

---

## 9. Padrão de Migração Genérico (Checklist)

Use este checklist ao refatorar qualquer bot Python:

### 9.1 — requirements.txt
- [ ] Remover `mysql-connector-python` / `pymysql` / `mysqlclient`
- [ ] Adicionar `psycopg2-binary>=2.9.9`

### 9.2 — .env
- [ ] Renomear `DB_PASS` → `DB_PASSWORD` (se aplicável)
- [ ] Adicionar `DB_PORT` (se não existia)
- [ ] Mudar `DB_NAME` de `omie_db` ou `psoffice` → `pmo_hub`
- [ ] Valores: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_POOL_MAX=5`, `DB_POOL_MIN=0`

### 9.3 — Conexão
- [ ] `import mysql.connector` → `import psycopg2`
- [ ] `mysql.connector.connect(...)` → `psycopg2.connect(...)`
- [ ] `database=` → `dbname=`
- [ ] Adicionar `conn.commit()` após operações de escrita (se não existia)

### 9.4 — SQL Queries
- [ ] `ON DUPLICATE KEY UPDATE col = VALUES(col)` → `ON CONFLICT (pk) DO UPDATE SET col = EXCLUDED.col`
- [ ] `REPLACE INTO` → `INSERT ... ON CONFLICT ... DO UPDATE SET`
- [ ] Backticks `` ` `` → aspas duplas `"`
- [ ] Prefixar tabelas com schema: `omie.a_pagar`, `psoffice.projetos`
- [ ] Referências a `omie_db.` → `omie.`
- [ ] Referências a `psoffice.` → `psoffice.` (sem mudança)
- [ ] `NOW()` funciona igual no PostgreSQL

### 9.5 — Tipos de Dados
- [ ] Booleanos: `0`/`1` → `True`/`False` (Python bool)
- [ ] Decimais: usar `Decimal` do Python para colunas NUMERIC
- [ ] Datas: `datetime` do Python funciona direto com psycopg2
- [ ] NULL: `None` do Python funciona direto

### 9.6 — Error Handling
```python
import psycopg2

try:
    cursor.execute(...)
    conn.commit()
except psycopg2.IntegrityError as e:
    conn.rollback()
    print(f"Erro de integridade: {e}")
except psycopg2.OperationalError as e:
    conn.rollback()
    print(f"Erro operacional: {e}")
except psycopg2.Error as e:
    conn.rollback()
    print(f"Erro de banco: {e}")
```

---

## 10. Exemplo Completo: Bot Omie (Antes/Depois)

### ANTES (MySQL)
```python
import mysql.connector
import os
import pandas as pd

class OmieBot:
    def __init__(self):
        self.conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            database='omie_db'
        )

    def upsert_contas_a_pagar(self, df: pd.DataFrame):
        cursor = self.conn.cursor()
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO a_pagar (
                    `Data de Vencimento (completa)`,
                    `Tipo`,
                    `Cliente ou Fornecedor (Nome Fantasia)`,
                    `Valor da Conta`,
                    `Situação`
                ) VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `Tipo` = VALUES(`Tipo`),
                    `Cliente ou Fornecedor (Nome Fantasia)` = VALUES(`Cliente ou Fornecedor (Nome Fantasia)`),
                    `Valor da Conta` = VALUES(`Valor da Conta`),
                    `Situação` = VALUES(`Situação`)
            """, (
                row['Data de Vencimento (completa)'],
                row['Tipo'],
                row['Cliente ou Fornecedor (Nome Fantasia)'],
                row['Valor da Conta'],
                row['Situação']
            ))
        self.conn.commit()
        cursor.close()
```

### DEPOIS (PostgreSQL)
```python
import psycopg2
from psycopg2.extras import execute_values
import os
import pandas as pd
from decimal import Decimal

class OmieBot:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 5432)),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )

    def upsert_contas_a_pagar(self, df: pd.DataFrame):
        cursor = self.conn.cursor()

        data = []
        for _, row in df.iterrows():
            data.append((
                row['Data de Vencimento (completa)'],
                row['Tipo'],
                row['Cliente ou Fornecedor (Nome Fantasia)'],
                Decimal(str(row['Valor da Conta'])) if pd.notna(row['Valor da Conta']) else None,
                row['Situação']
            ))

        execute_values(
            cursor,
            """
            INSERT INTO omie.a_pagar (
                "Data de Vencimento (completa)",
                "Tipo",
                "Cliente ou Fornecedor (Nome Fantasia)",
                "Valor da Conta",
                "Situação"
            ) VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                "Tipo" = EXCLUDED."Tipo",
                "Cliente ou Fornecedor (Nome Fantasia)" = EXCLUDED."Cliente ou Fornecedor (Nome Fantasia)",
                "Valor da Conta" = EXCLUDED."Valor da Conta",
                "Situação" = EXCLUDED."Situação"
            """,
            data,
            page_size=1000
        )

        self.conn.commit()
        cursor.close()
```

---

## 11. Exemplo Completo: Bot PSOffice (Antes/Depois)

### ANTES (MySQL)
```python
import mysql.connector

def upsert_projetos(self, projetos_list):
    cursor = self.conn.cursor()
    for p in projetos_list:
        cursor.execute("""
            INSERT INTO projetos (PROJ_ID, NOME, DT_INICIO, DT_FIM, ATIVO, VALOR)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                NOME = VALUES(NOME),
                DT_INICIO = VALUES(DT_INICIO),
                DT_FIM = VALUES(DT_FIM),
                ATIVO = VALUES(ATIVO),
                VALOR = VALUES(VALOR)
        """, (p['PROJ_ID'], p['NOME'], p['DT_INICIO'], p['DT_FIM'], p['ATIVO'], p['VALOR']))
    self.conn.commit()
```

### DEPOIS (PostgreSQL)
```python
import psycopg2

def upsert_projetos(self, projetos_list):
    cursor = self.conn.cursor()
    for p in projetos_list:
        cursor.execute("""
            INSERT INTO psoffice.projetos ("PROJ_ID", "NOME", "DT_INICIO", "DT_FIM", "ATIVO", "VALOR")
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT ("PROJ_ID") DO UPDATE SET
                "NOME" = EXCLUDED."NOME",
                "DT_INICIO" = EXCLUDED."DT_INICIO",
                "DT_FIM" = EXCLUDED."DT_FIM",
                "ATIVO" = EXCLUDED."ATIVO",
                "VALOR" = EXCLUDED."VALOR"
        """, (p['PROJ_ID'], p['NOME'], p['DT_INICIO'], p['DT_FIM'], p['ATIVO'], p['VALOR']))
    self.conn.commit()
```

---

## 12. Tabela de Conversão Rápida

| Conceito | MySQL | PostgreSQL |
|---|---|---|
| Driver Python | `mysql-connector-python` | `psycopg2-binary` |
| Import | `import mysql.connector` | `import psycopg2` |
| Conectar | `mysql.connector.connect(database=...)` | `psycopg2.connect(dbname=...)` |
| Upsert | `ON DUPLICATE KEY UPDATE col = VALUES(col)` | `ON CONFLICT (pk) DO UPDATE SET col = EXCLUDED.col` |
| Replace | `REPLACE INTO` | `INSERT ... ON CONFLICT ... DO UPDATE SET` |
| Quoting | `` `coluna` `` | `"coluna"` |
| Boolean | `TINYINT(1)`: `0`/`1` | `BOOLEAN`: `True`/`False` |
| Auto-increment | `AUTO_INCREMENT` | `SERIAL` |
| Last Insert ID | `cursor.lastrowid` | `RETURNING id` na query |
| Commit | Autocommit por padrão | `conn.commit()` obrigatório |
| Bulk insert | `executemany()` | `psycopg2.extras.execute_values()` |
| JSON | `JSON` | `JSONB` |
| Decimal | `DECIMAL(M,N)` | `NUMERIC(M,N)` |
| Truncate + reset | `TRUNCATE TABLE t` | `TRUNCATE TABLE schema.t RESTART IDENTITY CASCADE` |

---

## 13. Notas Finais

1. **Triggers `updated_at`:** Todas as tabelas possuem um trigger que atualiza `updated_at` automaticamente em qualquer UPDATE. Não inclua `updated_at` no `SET` do upsert — o trigger cuida disso.

2. **`created_at`:** Tem default `NOW()`. Se o bot não enviar, será preenchido automaticamente no INSERT. No UPDATE (via ON CONFLICT), não sobrescreva o `created_at`.

3. **Sequences (auto-increment):** Após upserts com IDs explícitos em tabelas SERIAL (omie), pode ser necessário resetar a sequence:
   ```sql
   SELECT setval(pg_get_serial_sequence('omie.a_pagar', 'id'), COALESCE(MAX(id), 1)) FROM omie.a_pagar;
   ```

4. **Encoding:** PostgreSQL usa UTF-8 nativo. Caracteres acentuados (é, ã, ç) funcionam sem configuração extra.

5. **Connection pooling:** Para bots de longa duração, considere usar connection pool:
   ```python
   from psycopg2.pool import SimpleConnectionPool
   pool = SimpleConnectionPool(
       minconn=int(os.getenv('DB_POOL_MIN', 0)),
       maxconn=int(os.getenv('DB_POOL_MAX', 5)),
       host=os.getenv('DB_HOST'),
       port=int(os.getenv('DB_PORT', 5432)),
       dbname=os.getenv('DB_NAME'),
       user=os.getenv('DB_USER'),
       password=os.getenv('DB_PASSWORD')
   )
   conn = pool.getconn()
   # ... usar conn ...
   pool.putconn(conn)
   ```
