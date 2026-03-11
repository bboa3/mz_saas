# MozEconomia SaaS — Funcionalidades (`mz_saas`)

Aplicação Frappe separada que gere contratos SaaS de clientes da MozEconomia Cloud.
Depende de `erpnext` e `erpnext_mz`.

---

## Índice

1. [Instalação](#instalação)
2. [DocTypes](#doctypes)
3. [Campos Personalizados no Contrato](#campos-personalizados-no-contrato)
4. [Campos Personalizados na Fatura de Venda](#campos-personalizados-na-fatura-de-venda)
5. [Ciclo de Vida do Contrato](#ciclo-de-vida-do-contrato)
6. [Notificações por Email](#notificações-por-email)
7. [Monitor de Atrasos](#monitor-de-atrasos)
8. [Tarefas Agendadas](#tarefas-agendadas)
9. [Estrutura de Ficheiros](#estrutura-de-ficheiros)
10. [Verificação e Testes](#verificação-e-testes)

---

## Instalação

```bash
# 1. Garantir que o pacote Python está instalado no virtualenv do bench
./env/bin/pip install -e apps/mz_saas

# 2. Adicionar à lista de apps do bench
echo "mz_saas" >> sites/apps.txt

# 3. Instalar na site
sudo -u erp-user bench --site erp.local install-app mz_saas

# 4. Migrar (cria tabelas e sincroniza custom fields)
sudo -u erp-user bench --site erp.local migrate

# 5. Limpar cache
sudo -u erp-user bench --site erp.local clear-cache
```

**Apps requeridas (devem estar instaladas antes):** `erpnext`, `erpnext_mz`

---

## DocTypes

### `MZ SaaS Plan`

Catálogo de serviços facturáveis. Cada registo representa um serviço SaaS disponível para venda.

| Campo | Tipo | Descrição |
|---|---|---|
| `plan_name` | Data | Nome do plano (também serve de chave primária) |
| `description` | Small Text | Descrição do serviço |
| `billing_cycle` | Select | `Monthly` / `Quarterly` / `Annual` |
| `price` | Currency | Preço base |
| `currency` | Link: Currency | Moeda (padrão: MZN) |
| `status` | Select | `Active` / `Inactive` |
| `linked_subscription_plan` | Link: Subscription Plan | Criado automaticamente ao gravar |

**Comportamento automático no `validate()`:**
- Se `linked_subscription_plan` estiver vazio, cria automaticamente um `Subscription Plan` ERPNext com o mesmo nome, preço e ciclo de facturação.
- Se já existir, sincroniza o preço e ciclo no `Subscription Plan` ligado.
- Cria também um `Item` de serviço (`SVC-<NOME_SCRUBBED>`) se ainda não existir, necessário para a facturação ERPNext.

---

### `MZ Contract Service Line` *(child table)*

Tabela de linhas de serviço associada ao Contrato via campo `mz_service_lines`.

| Campo | Tipo | Descrição |
|---|---|---|
| `service_plan` | Link: MZ SaaS Plan | Plano selecionado |
| `service_description` | Data | Preenchido automaticamente do plano |
| `billing_cycle` | Select | Preenchido automaticamente do plano |
| `unit_price` | Currency | Preenchido automaticamente, editável |
| `quantity` | Int | Quantidade (padrão: 1) |
| `total` | Currency | Calculado: `unit_price × quantity` |

---

### `MZ Overdue Review`

Registo de clientes sinalizados para possível suspensão por faturas em atraso.
Criado automaticamente pelo agendador diário; gerido manualmente pela equipa comercial.

| Campo | Tipo | Descrição |
|---|---|---|
| `customer` | Link: Customer | Cliente em atraso |
| `contract` | Link: Contract | Contrato associado |
| `outstanding_amount` | Currency | Valor total em dívida |
| `overdue_since` | Date | Data de vencimento da fatura |
| `review_status` | Select | `Pending Review` / `Suspend` / `Reactivate` / `Deactivate` |
| `assigned_to` | Link: User | Responsável comercial do contrato |
| `notes` | Text | Notas internas |

**Deduplicação:** o agendador só cria um novo registo se não existir já um com `review_status = "Pending Review"` para o mesmo contrato.

---

## Campos Personalizados no Contrato

Adicionados automaticamente via `install.py` (`after_install` / `after_migrate`).
Visíveis no separador **"MozEconomia Cloud"** do formulário de Contrato.

| Fieldname | Tipo | Descrição |
|---|---|---|
| `mz_saas_tab` | Tab Break | Separador "MozEconomia Cloud" |
| `mz_service_lines` | Table: MZ Contract Service Line | Linhas de serviço e facturação |
| `mz_service_status` | Select | `Draft` / `Active` / `Suspended` / `Deactivated` |
| `mz_customer_email` | Data (Email) | Email do cliente para notificações |
| `mz_sales_responsible` | Link: User | Responsável comercial interno |
| `mz_technical_responsible` | Link: User | Responsável técnico interno |
| `mz_linked_subscription` | Link: Subscription | Subscrição ERPNext (só leitura, preenchido automaticamente) |
| `mz_internal_notes` | Text | Notas internas |

> `mz_customer_email` deve ser preenchido manualmente (ou via client script) com o email de contacto do cliente — é o destinatário do email de boas-vindas.

---

## Campos Personalizados na Fatura de Venda

Definidos em `install.py`. Preenchidos automaticamente no `on_submit` da fatura quando gerada por uma subscrição MZ SaaS.

| Fieldname | Tipo | Descrição |
|---|---|---|
| `mz_saas_managed` | Check | `1` se a fatura foi gerada por um Contrato MZ SaaS |
| `mz_contract` | Link: Contract | Contrato de origem |
| `mz_sales_responsible_email` | Data (Email) | Email do responsável comercial (para filtragem nas Notificações) |

Estes campos permitem que as Notificações nativas do Frappe filtrem e enderecem os emails correctamente sem joins entre DocTypes.

---

## Ciclo de Vida do Contrato

### Submissão (`on_submit`)

`mz_saas.saas.contract_lifecycle.on_contract_submit`

Condições para activação:
- `party_type == "Customer"`
- `mz_service_lines` não vazia
- Cada linha deve ter um `MZ SaaS Plan` com `linked_subscription_plan` preenchido

Acções:
1. Cria uma `Subscription` ERPNext com os planos das linhas de serviço.
2. A `Subscription` fica automaticamente `Active` (gerido pelo controller ERPNext).
3. Grava `mz_linked_subscription` e `mz_service_status = "Active"` no Contrato.
4. O Frappe dispara a Notificação **"MZ SaaS - Boas-Vindas"** para `mz_customer_email`.

### Alteração de Estado (`on_update_after_submit`)

`mz_saas.saas.contract_lifecycle.on_contract_status_change`

| `mz_service_status` | Acção |
|---|---|
| `Suspended` | Cancela a `Subscription` via `cancel_subscription()` |
| `Deactivated` | Cancela a `Subscription` (mesmo comportamento que Suspended) |
| `Active` | Se a `Subscription` existe e está `Cancelled`, chama `restart_subscription()`; caso contrário cria uma nova |

### Tagging de Faturas (`on_submit` Sales Invoice)

`mz_saas.saas.contract_lifecycle.on_invoice_submit`

Quando uma `Sales Invoice` é submetida e tem `subscription` preenchido:
1. Verifica se existe um Contrato com `mz_linked_subscription` igual à subscrição da fatura.
2. Se sim, preenche `mz_saas_managed = 1`, `mz_contract`, e `mz_sales_responsible_email`.

### Fluxo completo

```
Contrato (Draft)
  → [Submeter] → on_contract_submit()
       └── _setup_subscription()  → cria Subscription (SUB-YYYY-xxxx), status=Active
                                       └── ERPNext gera Sales Invoices automaticamente

  → [Evento Submit dispara Notificação Frappe]
       └── "MZ SaaS - Boas-Vindas" → email para mz_customer_email

[Agendador ERPNext — diário]
  └── gera Sales Invoice → on_invoice_submit() marca mz_saas_managed=1

[Agendador trigger_daily_alerts — 08:00, definido em erpnext_mz]
  ├── "MZ SaaS - Lembrete de Fatura"          → email 7 dias antes do vencimento
  ├── "MZ SaaS - Fatura em Atraso (Cliente)"  → email 1 dia após vencimento
  └── "MZ SaaS - Alerta Interno Atraso"       → email ao responsável comercial

[Agendador diário — mz_saas]
  └── flag_overdue_customers() → cria MZ Overdue Review para revisão manual

[Acção manual no Contrato]
  mz_service_status = "Suspended"    → cancela Subscription
  mz_service_status = "Deactivated"  → cancela Subscription
  mz_service_status = "Active"       → reactiva ou recria Subscription
```

---

## Notificações por Email

Definidas como fixtures em `fixtures/notification.json`. Importadas automaticamente durante `install-app` e `migrate`.

Todas usam `channel = "Email"` e `message_type = "HTML"`.

| Nome | DocType | Evento | Condição | Destinatário |
|---|---|---|---|---|
| MZ SaaS - Boas-Vindas | Contract | Submit | `doc.party_type == 'Customer' and doc.mz_customer_email` | `mz_customer_email` |
| MZ SaaS - Lembrete de Fatura | Sales Invoice | 7 dias antes de `due_date` | `doc.mz_saas_managed` | `contact_email` |
| MZ SaaS - Fatura em Atraso (Cliente) | Sales Invoice | 1 dia após `due_date` | `doc.mz_saas_managed and doc.outstanding_amount > 0` | `contact_email` |
| MZ SaaS - Alerta Interno Atraso | Sales Invoice | 1 dia após `due_date` | `doc.mz_saas_managed and doc.outstanding_amount > 0` | `mz_sales_responsible_email` |

> O agendador `trigger_daily_alerts` (diário às 08:00) já está registado em `erpnext_mz/hooks.py` — não é necessário nenhum scheduler adicional para as notificações de dias antes/depois.

Para testar o envio manualmente:
```bash
bench --site erp.local execute frappe.email.doctype.notification.notification.trigger_daily_alerts
```

---

## Monitor de Atrasos

`mz_saas.saas.billing_monitor.flag_overdue_customers`

Executado diariamente. Pesquisa faturas MZ SaaS submetidas com `outstanding_amount > 0` e `due_date < hoje`, e cria um registo `MZ Overdue Review` para cada contrato em atraso (se ainda não existir um com `review_status = "Pending Review"`).

Para executar manualmente:
```bash
bench --site erp.local execute mz_saas.saas.billing_monitor.flag_overdue_customers
```

---

## Tarefas Agendadas

| Tipo | Função | Propósito |
|---|---|---|
| `daily` | `mz_saas.saas.billing_monitor.flag_overdue_customers` | Cria registos MZ Overdue Review |
| `cron 0 8 * * *` *(erpnext_mz)* | `frappe.email.doctype.notification.notification.trigger_daily_alerts` | Dispara notificações "Days Before/After" |

---

## Estrutura de Ficheiros

```
apps/mz_saas/
├── mz_saas/
│   ├── __init__.py                          # __version__ = "1.0.0"
│   ├── hooks.py                             # Metadados, doc_events, scheduler, fixtures
│   ├── install.py                           # after_install / after_migrate
│   ├── modules.txt                          # "MZ SaaS"
│   ├── config/
│   │   └── __init__.py
│   ├── fixtures/
│   │   ├── custom_field.json                # Exportado após migrate (inicialmente vazio)
│   │   └── notification.json                # 4 Notificações Frappe
│   ├── mz_saas/                             # Módulo Frappe (scrubbed: "MZ SaaS")
│   │   ├── __init__.py
│   │   └── doctype/
│   │       ├── mz_saas_plan/
│   │       │   ├── mz_saas_plan.json
│   │       │   └── mz_saas_plan.py          # Auto-cria Subscription Plan + Item
│   │       ├── mz_contract_service_line/
│   │       │   ├── mz_contract_service_line.json
│   │       │   └── mz_contract_service_line.py
│   │       └── mz_overdue_review/
│   │           ├── mz_overdue_review.json
│   │           └── mz_overdue_review.py
│   └── saas/
│       ├── contract_lifecycle.py            # on_submit, on_update_after_submit, on_invoice_submit
│       └── billing_monitor.py               # flag_overdue_customers
└── pyproject.toml
```

---

## Verificação e Testes

### Após instalação

```bash
# 1. Verificar custom fields no Contrato e Sales Invoice
bench --site erp.local execute frappe.db.get_all \
  --kwargs "{'doctype': 'Custom Field', 'filters': {'dt': 'Contract', 'module': 'MZ SaaS'}, 'fields': ['fieldname']}"

# 2. Verificar Notificações importadas
bench --site erp.local execute frappe.db.get_all \
  --kwargs "{'doctype': 'Notification', 'filters': [['name', 'like', 'MZ SaaS%']], 'fields': ['name', 'enabled']}"
```

### Fluxo de teste manual

```
1. Criar MZ SaaS Plan (ex: "Plano Básico", Monthly, 5000 MZN)
   → Verificar que Subscription Plan ERPNext foi criado automaticamente

2. Criar Customer + Contrato (party_type=Customer)
   → Preencher mz_service_lines com o plano criado
   → Preencher mz_customer_email
   → Submeter o Contrato
   → Verificar: mz_linked_subscription preenchido, mz_service_status = Active
   → Verificar: Subscription existe em ERPNext Accounts
   → Verificar: "MZ SaaS - Boas-Vindas" na Fila de Email (frappe → Email Queue)

3. Alterar mz_service_status para "Suspended"
   → Verificar: Subscription.status = Cancelled

4. Alterar mz_service_status para "Active"
   → Verificar: Subscription reactiva (status = Active)

5. Testar monitor de atrasos:
   bench --site erp.local execute mz_saas.saas.billing_monitor.flag_overdue_customers
   → Verificar: MZ Overdue Review criado para faturas vencidas
```

### Exportar fixtures após customização

Após criar/alterar Notificações ou Custom Fields via UI:
```bash
sudo -u erp-user bench --site erp.local export-fixtures --app mz_saas
```
