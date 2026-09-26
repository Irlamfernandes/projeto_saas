# Projeto SaaS — Gestão de Lojas

Sistema multi-loja para pequenos comércios: cadastro de produtos (com fotos), clientes com
caderneta de fiado, vendas com baixa de estoque, extrato do cliente em PDF, relatórios com
exportação em PDF/Excel e dashboard. Funciona como PWA no celular.

Cada usuário pertence a uma loja e só enxerga os dados dela; superusuários enxergam todas.

**Stack:** Django 5.2 · PostgreSQL (Supabase) ou SQLite local · Supabase Storage · Tailwind CSS 3 ·
ReportLab/openpyxl · Gunicorn + WhiteNoise · deploy no Render.

## Arquitetura

```
application/      Regras de negócio, sem HTTP
  tenancy.py        filtro e controle de acesso por loja
  <domínio>/        vendas, produtos, clientes, relatorios, contas
    selectors.py      consultas (leitura)
    services.py       operações transacionais (escrita)
    exceptions.py     erros de negócio (mensagem exibível ao usuário)
infrastructure/   Models, admin, migrations e integrações (Supabase Storage, geração de PDF/Excel)
interfaces/       Camada web: views, forms, templates, decorators
config/           settings, urls, wsgi
```

Convenções:

- **Views são finas**: validam um Django Form, chamam um service e respondem. O fluxo padrão é
  `executar_formulario()` em `interfaces/views/comum.py`.
- **Toda view de loja usa `@loja_required`** (`interfaces/decorators.py`): exige login, loja
  ativa e que a senha temporária já tenha sido trocada.
- **Erros de negócio** herdam de `RegraDeNegocioError` e viram mensagem para o usuário;
  qualquer outra exceção é bug e vai para o log (nunca exibir `str(e)` na tela).
- Consultas por loja passam por `filtrar_por_loja(queryset, user)`.
- Saldo de clientes em lote: `Cliente.objects.com_saldo()` (evita N+1).
- Listas longas são paginadas com `paginar()` + `{% include 'interfaces/_paginacao.html' %}`
  (50 por página; `?pagina=` preserva os filtros).
- Valores em reais nos templates: `{% load formatacao %}` e `{{ valor|moeda }}` (mesma saída do
  `floatformat:2` em pt-BR, bem mais rápido em listas).

## Rodando localmente

Pré-requisitos: Python 3.12 e Node.js (para os testes JS e o Tailwind).

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
npm install

cp .env.example .env          # ajuste as variáveis (veja abaixo)
set -a; source .env; set +a   # o Django lê as variáveis do ambiente

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Com Docker: `make build` (sobe em `http://localhost:8000` usando o `.env`). Veja os demais
atalhos no `Makefile` (`make migrate`, `make superuser`, `make logs`...).

**Primeiro acesso:** entre em `/admin/` com o superusuário, crie uma **Loja** e depois os
**Usuários** dela. O admin mostra uma senha temporária; no primeiro login o usuário é obrigado
a trocá-la.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DJANGO_DEBUG` | não | `True` em desenvolvimento. Desligado (padrão) ativa HTTPS, cookies seguros e HSTS. |
| `DJANGO_SECRET_KEY` | **sim, em produção** | Sem ela e com `DEBUG` desligado, a aplicação não sobe. |
| `DJANGO_ALLOWED_HOSTS` | não | Hosts separados por vírgula (padrão: `localhost,127.0.0.1`). |
| `DATABASE_URL` | não | Postgres. Vazio usa SQLite (`db.sqlite3`). |
| `DATABASE_SSL_REQUIRE` | não | Padrão `True` quando há `DATABASE_URL`. |
| `SUPABASE_URL`, `SUPABASE_KEY` | para upload | Bucket `imagens` do Supabase Storage. |
| `DJANGO_SECURE_SSL_REDIRECT` | não | Padrão `True` em produção; `False` só para rodar sem HTTPS. |
| `DJANGO_HSTS_SECONDS` | não | Padrão `3600`. Aumente para `31536000` depois de validar o HTTPS. |
| `WEB_CONCURRENCY` | não | Processos do Gunicorn (padrão `2` no Docker e no `render.yaml`). |

## Testes e qualidade

```bash
make test        # pytest com cobertura + jest
```

- A suíte usa `config/settings_test.py` (configurado no `pytest.ini`): hasher de senha rápido e
  sem redirecionamento HTTPS.
- Testes ficam em `<app>/tests/`; utilitários compartilhados em `tests/apoio.py`
  (`imagem_de_teste`, `StorageFalso`).
- Usuários criados em testes de telas da loja precisam de `deve_trocar_senha=False`
  (o padrão do model é `True`).
- A cobertura é configurada em `.coveragerc` e enviada ao SonarQube (`sonar-project.properties`).
  O objetivo é manter 100%.

## CSS (Tailwind)

`static/css/output.css` é **versionado** e servido direto em produção. Sempre que adicionar ou
trocar classes nos templates ou em `static/js`, recompile:

```bash
make css         # ou: npm run watch:css durante o desenvolvimento
```

## Deploy (Render)

`render.yaml` define o serviço: `build.sh` instala dependências, roda `collectstatic` e
`migrate`; a aplicação sobe com Gunicorn. Configure no painel do Render ao menos
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `SUPABASE_URL` e `SUPABASE_KEY`
(elas precisam existir também durante o build).
