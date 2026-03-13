# PRD: Migração do Banco de Dados Bot Omie (MySQL para PostgreSQL)

## 1. Overview
- **Problem Statement:** O projeto Bot Omie atualmente utiliza o MySQL para persistência de relatórios extraídos. No entanto, a infraestrutura central do Hub PMO foi atualizada para um novo banco de dados PostgreSQL 16 com schemas consolidados (`omie`, `psoffice`, `public`). É necessário adequar o bot a este novo padrão arquitetural para garantir a consistência e centralização dos dados da corporação, além de remover as dependências não suportadas (MySQL).
- **Objective:** Substituir o driver de banco de dados (`mysql-connector-python`) pelo `psycopg2-binary`, atualizar a conexão do banco de dados, refatorar a inferência dinâmica de criação de tabelas e modificar as lógicas de *Upsert* do MySQL (`ON DUPLICATE KEY UPDATE`) para PostgreSQL (`ON CONFLICT DO UPDATE SET`), garantindo que a extração diária não sofra interrupções.
- **Stakeholders:** Equipe de Engenharia / Desenvolvedores (Squad RPA), PMO (Consumidores dos relatórios), DBAs (Administradores do Hub PMO).

## 2. Background & Context
- O Bot Omie é responsável por extrair relatórios (Contas a Pagar, Notas Faturadas, Notas de Débito) e persisti-los via módulos dinâmicos de Upsert.
- O sistema Hub PMO mudou de 3 instâncias MySQL isoladas para 1 banco PostgreSQL contendo múltiplos *schemas*. No caso do Bot Omie, as tabelas serão migradas de `omie_db.<tabela>` para `omie.<tabela>`.
- O robô atualmente constrói as *queries* dinamicamente lendo *DataFrames* do Pandas, fazendo uso intenso na formatação local do MySQL (crases/backticks, booleanos como `TINYINT(1)`).
- A mudança requer precisão sintática rigorosa nos identificadores (`" "` ao invés de `` ` ``) devido às colunas com espaços e caracteres acentuados.

## 3. Goals & Success Metrics
| Goal | Metric | Target |
|------|--------|--------|
| **Migração Completa** | Uso exclusivo do driver PostgreSQL | 100% dos drivers MySQL removidos da base de código. |
| **Integridade de Dados** | Taxa de falha nas operações de *Upsert* | 0 erros de sintaxe (como erro em *placeholders* ou aspas) após o *deploy*. |
| **Performance do Bot** | Tempo de banco por lote processado | Velocidade igual ou superior usando `psycopg2.extras.execute_values()`. |
| **Compatibilidade** | Paridade funcional de relatórios | 3/3 relatórios do fluxo Omie persistindo com sucesso no banco homologado. |

## 4. User Stories & Requirements

### Functional Requirements
- **Como um** desenvolvedor responsável pelo RPA, **eu quero** refatorar os arquivos [app/db/db.py](cci:7://file:///c:/Users/leonardo.fiorese/Documents/bot_omie/app/db/db.py:0:0-0:0) e `app/actions/upsert_data/*.py` para usar `psycopg2-binary`, **para que** os dados se comuniquem com o novo Hub PMO.
- **Como um** consumidor (analista do PMO), **eu quero** que as extrações de amanhã ocorram da mesma forma que hoje, **para que** os painéis que leem a base Postgres reflitam a realidade financeira sem atrasos.
- **Critérios de Aceite:**
  - `requirements.txt` atualizado sem referências ao MySQL.
  - O método de conexão `get_conn()` e a auto-criação da *database* (`db.py`) devem estar adaptados ou removidos/simplificados caso a *database* já seja gerenciada pelo Terraform/DBA.
  - Queries de inserção utilizarão o sufixo schema de forma explícita (`omie.a_pagar`, etc.).
  - Uso explícito do `conn.commit()` para encerramento de transações.

### Non-Functional Requirements
- **Performance:** A ingestão em massa (`execute_values()`) não deve atrasar mais que a arquitetura atual para inserção. Lotes definidos idealmente entre 500-1000 *records*.
- **Conectividade/Segurança:** As variáveis lidas do `.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) seguem de forma limpa como parâmetros unificados no driver.
- **Manutenibilidade:** Códigos que convertem tipos dinâmicos (Pandas *dtypes*) pro SQL deverão prever mapeamento correto do Postgres (`DECIMAL/NUMERIC` ao invés de FLOAT em MySQL, entre outros).

## 5. Technical Architecture
- **Data Access Layer:** Alterada de `mysql.connector` para `psycopg2`.
- **Query Builder Changes:** 
  - Substituto de `` `Coluna Name` `` para `"Coluna Name"`.
  - Padrão do comando `ON DUPLICATE KEY` será trocado inteiramente pelo bloco `ON CONFLICT (id) DO UPDATE SET`.
  - Prefixação obrigatória de *schemas* (adicionar schema explícito nas f-strings ao rodar comandos via Python).
- **Tipagem Automática (caso persista a tabela dinâmica):** Mudança das lógicas em `.py` que antes mapeavam para `INT` no MySQL e agora devem inferir usando `BIGINT`, bem como repensar o auto-incremento de `AUTO_INCREMENT` para a cláusula `SERIAL` nativa do PG na re-criação inicial.
- **Autocommit:** Desabilitado por padrão no `psycopg2` (diferente da autocommissão do driver do MySQL em alguns cenários). Deverá exigir `self.conn.commit()`.

## 6. Implementation Phases

### Phase 1: Ajuste de Configurações e Ambiente — [Semana 1 / Dias 1-2]
- Atualizar localmente o arquivo `requirements.txt` (remover modulos do `mysql`, adicionar `psycopg2-binary>=2.9.9`).
- Adicionar ou adequar as chaves no ambiente `.env` (incluindo tratamento de `DB_PORT` com fallback para 5432).
- Adaptar o arquivo principal de banco [app/db/db.py](cci:7://file:///c:/Users/leonardo.fiorese/Documents/bot_omie/app/db/db.py:0:0-0:0) (métodos de conexão). Remover a responsabilidade do aplicativo de recriar/criar o database caso ela seja papel do admin — confirmar se basta criar o *schema* e *tabelas*.

### Phase 2: Refatoração das Camadas de Upsert — [Semana 1 / Dias 3-4]
- Alterar as *queries* estáticas/dinâmicas em `upsert_contas_a_pagar.py`, `upsert_notas_faturadas.py` e `upsert_notas_debito.py`.
- Incorporar no UPSERT a lógica de aspas duplas: `"Data de Vencimento (completa)"` ao invés de backticks.
- Refazer lógicas de `ON DUPLICATE KEY UPDATE` para o bloco PostgreSQL usando a variável temporal paralela sintética (`EXCLUDED."Nome da Coluna"`).
- Implementar `psycopg2.extras.execute_values()` em contrapartida a loop simples ou `executemany` que é lento.

### Phase 3: Validação de Tipagem em Carga e Deploy — [Semana 2 / Dia 1-2]
- Validar as rotinas que injetam valores (tratamento explícito para `NaN` do Pandas convertidos para `None/NULL`).
- Garantir que tipos decimais (`NUMERIC`) recebam *Decimals* apropriados da linguagem Python.
- Testar a gravação rodando os 3 relatórios com `auth.json` em modo Debug manual.

## 7. Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Tipagem / Erros de Syntax SQL** (Nomes de coluna complexos do PMO) | Alta | Alto | Garantir strict wrap (`""`) em todas as injeções formatadas para referenciar a coluna. Teste ponta-a-ponta rodando o parser com um log detalhado para cada query comissionada. |
| **Valores do Pandas NaN/Bool Incompatíveis** | Média | Alto | Inserir etapa `df = df.where(pd.notnull(df), None)` nativa para preencher dados ausentes antes do driver consumi-los. |
| **Sequences Dessincronizadas no Idempotency** | Baixa | Médio | Como os relatórios dependem de IDs ou re-criação lógica, atentar à estratégia de Upsert. Caso a chave primária não seja um ID numérico e sim natural, alterar a cláusula `ON CONFLICT (...)`. |

## 8. Testing Strategy
- **Teste Unitário / Validação Inicial:** Criar rodada de conexão e submissão básica sem inserir massa de dados massiva (mock). Checar apenas validade semântica da conexão (`SELECT 1`).
- **Teste de Integração (Sandbox PG):** Configurar no arquivo `.env` para subir a uma base PostgresQA / *Developer Localhost*. Disparar extração e validar comportamento dos gatilhos (`updated_at`, `created_at`).
- **Performance Testing:** Medir o delta de tempo de extração + transação no módulo.

## 9. Rollout Plan
- **Estratégia Local / Staged:**
  - Validar e "queimar" o cache do ambiente virtual.
  - Realizar pull das atualizações via repositório nos clientes (Desktop onde o `gui.py` roda).
- **Rollback:** Restauração do commit no terminal rodando os *requirements* antigos caso a tabela de PostgreSQL apresente lentidão inesperada ou queda de *connection pool*.

## 10. Open Questions & Decisions
- [ ] A lógica em `upsert_*.py` atual (descrita no CLAUDE.md) realiza `Create Table Dinâmico` caso as tabelas não existam. Para o Postgresql, nós manteremos a criação automatizada pela aplicação ou as tabelas do Hub PMO já estarão estabilizadas de forma externalizada via SQL migrations (Liquibase/Flyway)? *(Dono: Engenharia / PMO)*
- [ ] Atualmente como é definida a Primary Key em cada tabela exportada pelo Excel a ser usada no conflito em `ON CONFLICT (??) DO UPDATE` se o Excel é gerado em relatórios dinâmicos do Omie que podem não conter um "ID numérico" unívoco em todos os casos? *(Pendente de investigação na refatoração)*

## 11. Appendix
- **Guia oficial consultado:** `MIGRATION_GUIDE_PYTHON_BOTS.md`
- **Driver de Conexão Recomendado:** https://www.psycopg.org/docs/
