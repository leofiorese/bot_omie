# Guia de Teste - Bot Omie

Este documento descreve como testar o Bot Omie após a implementação dos seletores reais.

---

## Pré-requisitos

1. ✅ Arquivo `.env` configurado com credenciais do banco
2. ✅ Playwright instalado: `playwright install firefox`
3. ✅ Dependências instaladas: `pip install -r requirements.txt`
4. ✅ Autenticação concluída (arquivo `auth.json` existe)

---

## Seletores Implementados

### Navegação Inicial
| Ação | Seletor Playwright |
|------|-------------------|
| Botão "Acessar" | `getByRole('button', { name: 'Acessar' })` |
| Link "Finanças" | `getByRole('link', { name: 'Finanças' })` |
| Revelar menu de relatórios | Hover em `getByRole('link', { name: 'paid' })` |

### Dentro de cada Relatório
| Ação | Seletor Playwright | Observação |
|------|-------------------|------------|
| Botão Executar | `getByRole('button', { name: ' Executar' })` | Tem espaço antes! |
| Aguardar execução | `wait_for_selector('table')` | Timeout: 5 minutos |
| Menu Exportar (hover) | `getByRole('menuitem', { name: 'Exportar' })` | - |
| Formato Excel | `getByRole('menuitem', { name: 'Excel' }).locator('span').first()` | - |

### Relatórios Mapeados
- **Contas a Pagar - PMO** → `A PAGAR.xlsx` → `OMIE_CONTAS_A_PAGAR`
- **Notas Faturadas - PMO** → `NF_FATURADAS.xlsx` → `OMIE_NOTAS_FATURADAS`
- **Notas Debito - PMO** → `NOTAS_DEBITO.xlsx` → `OMIE_NOTAS_DEBITO`

---

## Testes

### Teste 1: Autenticação (Primeira Vez)
```bash
python app/gui.py
```
1. Clicar em "Primeira Configuração"
2. Fazer login no browser que abrir (incluindo 2FA)
3. Pressionar ENTER no terminal
4. Verificar que `auth.json` foi criado

### Teste 2: Extração Manual (Com Browser Visível)
```bash
# Editar main.py linha 263: headless=False
python app/main.py
```
**Resultado esperado:**
- Browser abre visível
- Navega automaticamente
- Para cada relatório:
  - Clica no nome
  - Clica "Executar"  
  - Aguarda até 5 minutos
  - Exporta para Excel
  - Salva em `app/downloads/`

### Teste 3: Verificar Banco de Dados
```sql
USE omie_db;
SHOW TABLES;
-- Deve listar: OMIE_CONTAS_A_PAGAR, OMIE_NOTAS_FATURADAS, OMIE_NOTAS_DEBITO

SELECT COUNT(*) FROM OMIE_CONTAS_A_PAGAR;
```

### Teste 4: Verificar Arquivamento
Verificar se os arquivos foram movidos para:
```
Z:\3-Corporativo\PMO\0-Gerência do PMO\6-Controles\8-Estruturação PMO\4 - Implementação\2 - Custos\Database
```

Arquivos esperados:
- `OMIE_CONTAS_A_PAGAR.xlsx`
- `OMIE_NOTAS_FATURADAS.xlsx`
- `OMIE_NOTAS_DEBITO.xlsx`

### Teste 5: Extração via GUI
```bash
python app/gui.py
```
1. Selecionar relatórios desejados
2. Clicar "Iniciar Extração"
3. Acompanhar pelo log viewer

---

## Troubleshooting

### Erro: "Element not found"
**Causa:** Seletor mudou ou página não carregou.  
**Solução:** Rodar `python app/tools/get_selectors.py` e confirmar seletores.

### Erro: "Timeout waiting for selector"
**Causa:** Relatório demorou mais de 5 minutos.  
**Solução:** Aumentar `REPORT_EXECUTION_TIMEOUT` em `main.py`.

### Erro: "auth.json not found"
**Causa:** Primeira configuração não foi feita.  
**Solução:** Rodar GUI e clicar "Primeira Configuração".

### Download não inicia
**Causa:** Botão de exportar mudou.  
**Solução:** Verificar sequência hover → Exportar → Excel → span.first.

---

## Próximos Passos

- [ ] Testar com todos os 3 relatórios
- [ ] Verificar performance (tempo total de execução)
- [ ] Configurar agendamento (Windows Task Scheduler)
- [ ] Monitorar logs (`omie_bot.log`)
