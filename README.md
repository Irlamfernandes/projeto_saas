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
| `SUPABASE_URL`, `SUPABASE_KEY` | para upload | Bucket `imagens` do Supabase Storage. Até 5 fotos por produto, reduzidas para 1024 px e regravadas em WebP (qualidade 70, ~25 KB cada) antes do envio (`infrastructure/utils/otimizacao_de_imagem.py`). |
| `MERCADO_PAGO_ACCESS_TOKEN` | para renovar o plano | Token da conta do Mercado Pago que recebe o Pix. `TEST-...` gera Pix de teste (não pode ser pago); `APP_USR-...` cobra de verdade. |
| `DJANGO_SECURE_SSL_REDIRECT` | não | Padrão `True` em produção; `False` só para rodar sem HTTPS. |
| `DJANGO_HSTS_SECONDS` | não | Padrão `3600`. Aumente para `31536000` depois de validar o HTTPS. |
| `WEB_CONCURRENCY` | não | Processos do Gunicorn (padrão `2` no Docker e no `render.yaml`). |

## Testes e qualidade

```bash
make test        # pytest com cobertura + jest (falha abaixo de 100%)
make lint        # ruff (Python) + ESLint (JS)
make verificar   # o mesmo que o CI confere: lint, testes, segurança, migrações e CSS
```

- A suíte usa `config/settings_test.py` (configurado no `pytest.ini`): hasher de senha rápido e
  sem redirecionamento HTTPS.
- Testes ficam em `<app>/tests/`; utilitários compartilhados em `tests/apoio.py`
  (`imagem_de_teste`, `StorageFalso`).
- Usuários criados em testes de telas da loja precisam de `deve_trocar_senha=False`
  (o padrão do model é `True`).
- A cobertura é configurada em `.coveragerc` e enviada ao SonarQube (`sonar-project.properties`).
  O objetivo é manter 100%. `make test` grava `coverage.xml` (Python) e `coverage/lcov.info` (JS);
  `SONAR_TOKEN=seu_token make sonar` roda os testes e já envia a análise, sempre com a cobertura nova.

## Visual, gráficos e relatórios

- **Tema "Petróleo"**: tokens em `tailwind.config.js` (`marca`, `destaque`, `tinta`, `fundo`, status
  `bom`/`alerta`/`critico`) e componentes em `static/css/input.css` (`.cartao`, `.btn-primario`,
  `.campo`/`.rotulo`/`.entrada`/`.ajuda`, `.pilula-*`, `.tabela`, `.kpi`...). Prefira os componentes a
  repetir utilitários. Status sempre com ícone + texto, nunca só cor.
- **Ícones**: sprite em `interfaces/templates/interfaces/_icones.html`, usado com
  `<svg class="ico"><use href="#i-nome"/></svg>`.
- **Gráficos**: a análise (em `application/relatorios/`) vira dados em `interfaces/graficos.py` e o
  template inclui `interfaces/_grafico.html` (canvas + `json_script`). Quem desenha é
  `static/js/graficos.js` com o Chart.js versionado em `static/vendor/` (sem CDN). As duas cores de
  séries (marca x destaque) foram validadas para daltonismo.
- **Relatórios**: `application/relatorios/` tem `vendas.py`, `produtos.py`, `clientes.py`,
  `indicadores.py` e `pagamentos.py`; as páginas ficam em `/relatorios/` (visão geral, vendas, produtos,
  clientes, alterações). O lucro estimado usa o preço de custo **atual** dos produtos (não há custo histórico).

## Vendas, caderneta e histórico

- **Venda com vários produtos**: o carrinho (`_carrinho.html` + `static/js/venda.js`) busca pelo nome ou
  código no navegador e envia listas paralelas `item_produto` / `item_quantidade`. Sem cliente = **balcão**,
  paga na hora; com cliente, vai para a caderneta menos o "pago agora".
- **Pagamento no ato ligado à venda** (`PagamentoCliente.venda`): se a venda muda de cliente, o pagamento vai
  junto; se vira balcão, deixa de existir. Na edição, produtos que já estavam na venda mantêm o preço da época.
- **Cancelar venda** exige a senha de quem cancela e um motivo; devolve o estoque, apaga a venda com o
  pagamento feito no ato e guarda uma cópia completa no histórico.
- **Formas de pagamento** (dinheiro, Pix, débito, crédito, outro) na venda e no pagamento da caderneta, com o
  relatório "Formas de pagamento" em Relatórios › Vendas.
- **Registro de alterações** (`RegistroDeAlteracao`, `application/auditoria/`): vendas, pagamentos, produtos e
  clientes, com antes → depois. Aparece em Relatórios › Alterações e no admin (só leitura).

## Configurações e marca da loja

- **Configurações** (engrenagem no topo do celular; último item do menu lateral): usuário e loja só para
  consulta, marca da loja, plano e "Sair" (o único lugar para sair da conta).
- **Marca da loja** (`LojaModel.logo_url`, `application/lojas/`): qualquer usuário da loja envia; é reduzida para
  512px em WebP e aparece no topo do sistema e no cabeçalho dos PDFs (extrato e relatórios, `pdf_marca.py`).
  O PDF baixa a marca só do bucket do Supabase; se não conseguir, sai sem ela.

## Plano e vencimento

- `LojaModel.vencimento`: loja nova ganha 30 dias grátis. Só muda com pagamento confirmado (ou pelo
  superusuário no admin). O vencimento vale até o fim do dia.
- Avisos no Início a partir de 7 dias antes (`application/assinatura/situacao.py`); vencido, uma faixa
  aparece em todas as telas.
- **Modo só consulta:** com o plano vencido, `@loja_required` recusa qualquer envio de formulário (POST) e
  volta para a tela anterior com aviso. Consultar e exportar continuam. Telas que precisam funcionar mesmo
  assim usam `@loja_required(trava_plano_vencido=False)` (Configurações e a renovação).
- **Renovação por Pix** (Configurações › Ver planos e renovar): planos 30 dias, 90 dias, 6 meses e 12 meses
  (preços editáveis no admin; começam em R$ 0,01 para teste). O Pix (QR code e copia e cola) é gerado pelo
  Mercado Pago (`infrastructure/pagamentos/mercado_pago.py`) e a tela consulta sozinha a cada 5 s.
- **Só confirma com certeza** (`application/assinatura/services.py`): o vencimento só avança depois de o
  próprio Mercado Pago responder aprovado, com o valor da cobrança, em reais e com a referência dela. A soma
  parte do maior entre hoje e o vencimento atual (planos em meses somam meses de calendário) e nunca é feita
  duas vezes para a mesma cobrança. O e-mail do comprovante é guardado exatamente como foi digitado.
- **Pagou e fechou a tela?** Ao abrir o Início ou Configurações, os Pix ainda abertos da loja são conferidos
  (`conferir_pendentes`); Configurações lista os que seguem aguardando pagamento.

## Marca da CorsariosCode

Quem desenvolveu o sistema aparece sem atrapalhar a loja. Os contatos ficam só em `interfaces/desenvolvedor.py`
(campo vazio esconde o botão; o Instagram entra quando a conta existir).

- **Login e troca de senha:** faixa compacta com o emblema "CC", o nome e o WhatsApp.
- **Login › "Quero cadastrar minha loja":** WhatsApp com o pedido de acesso já escrito (contas novas são
  criadas pelo administrador).
- **Fim das páginas:** "Sistema feito por CorsariosCode", discreto e não fixo (não tira espaço do trabalho).
- **Configurações › Suporte:** WhatsApp com a mensagem já escrita com o nome da loja.
- **Relatórios em PDF:** rodapé com data, página e "Sistema CorsariosCode". O extrato do cliente **não** leva
  a marca: é um documento da loja para o cliente dela.

## Admin

O admin usa o tema [django-unfold](https://unfoldadmin.com/) com as cores Petróleo (`UNFOLD` em `config/settings.py`).
As regras e permissões são as mesmas de antes; mudou o visual.

- **Painel** (`infrastructure/admin/painel.py`, só para o superusuário): lojas ativas e em teste, vencendo em
  7 dias, vencidas, recebido no mês; gráficos de recebido e de lojas novas por mês e da situação dos planos;
  listas de lojas que vencem logo e das últimas cobranças.
- **Menu lateral** em grupos (Lojas, Assinaturas, Auditoria, Sistema), em `infrastructure/admin/tema.py`.
- **Erros do sistema** (Sistema): toda página que quebra em produção (erro 500) e todo `logger.error`/
  `logger.exception` do código vira um registro com tipo, mensagem, ponto do código, tela, loja, usuário e o
  traceback — o mesmo erro soma em "ocorrências". Corrigiu? Marque como resolvido; se voltar, reabre como novo.
  O painel avisa no topo quando há erro em aberto. Os erros também saem no console (log do Render).
  Configuração em `LOGGING` (`config/settings.py`) e `infrastructure/registro_de_erros.py`. Não guarda o que foi
  digitado nem os parâmetros do endereço. Nos testes o registro no banco fica desligado (`config/settings_test.py`).
- **Backups** (Sistema, só o superusuário): *Configurar* liga/desliga o automático, define de quanto em quanto
  tempo (horas, dias ou meses) e quantas cópias guardar; *Fazer backup agora* faz na hora; cada cópia tem *Baixar*.
  - O arquivo é o `dumpdata` do Django compactado e criptografado (AES-256-GCM, senha `BACKUP_CHAVE`): não depende
    do `pg_dump` e restaura em qualquer banco. Fica no bucket **privado** `backups` do Supabase (criado sozinho na
    primeira vez; se alguém deixá-lo público, o backup recusa). As fotos não entram: já ficam no Storage.
  - Quem dispara é o `.github/workflows/backup.yml`, de hora em hora, chamando `POST /interno/backup/` com o
    `BACKUP_TOKEN`; o sistema só faz se estiver ligado e na hora (com 30 min de folga para o atraso do agendador).
    Num servidor próprio, o mesmo pelo cron: `python manage.py fazer_backup --agendado`.
  - **Restaurar** (num banco novo): `python manage.py migrate` e depois
    `python manage.py restaurar_backup backup-AAAAMMDD-HHMMSS.json.gz.enc` (senha: `BACKUP_CHAVE` ou `--chave`).
  - Para ligar: no Render, `BACKUP_CHAVE` e `BACKUP_TOKEN` (valores longos e aleatórios; guarde a chave também fora
    do Render — sem ela nenhum backup abre); no GitHub, os segredos `SITE_URL` e `BACKUP_TOKEN` (o mesmo do Render).
- **Listas** com pílulas coloridas (situação do plano, tipo de acesso, senha a trocar, status da cobrança).
- **Resetar senha** do usuário fica num formulário próprio abaixo da edição (`admin/usuario_resetar_senha.html`).
- **Tradução:** o Unfold não vem em português; as frases dele estão em `locale/pt_BR/LC_MESSAGES/django.po`.
  Depois de editar, rode `make traducoes` (usa o Babel do `requirements-dev.txt`) e versione o `.mo`.

## CSS (Tailwind)

`static/css/output.css` é **versionado** e servido direto em produção. Sempre que adicionar ou
trocar classes nos templates ou em `static/js`, recompile:

```bash
make css         # ou: npm run watch:css durante o desenvolvimento
```

**Unidades** (para funcionar bem em qualquer tela e com a letra grande do celular/navegador):

- `rem` para textos, espaços e tamanhos (é o que as classes do Tailwind já geram);
- `em` nos pontos de quebra (`screens` em `tailwind.config.js`): com letra grande, o layout vira o de celular antes;
- `dvh` para altura de tela cheia (`min-h-dvh`), que desconta a barra de endereço do celular;
- `px` só em bordas, anéis de foco e sombras. `width`/`height` de `<img>` são números sem unidade (só a proporção).
- Nos gráficos (canvas só aceita px), o texto é convertido de `rem` na hora (`remEmPx` em `graficos.js`).

## Homologação e produção

```
homologacao ──PR──▶ main ──▶ Render (produção)
```

- **`homologacao`**: onde o trabalho acontece. Commit e push direto, à vontade; a cada push o CI roda e mostra
  ✓ ou ✗ no GitHub, sem travar nada.
- **`main`**: só a produção. Recebe um PR vindo da `homologacao`, aceito apenas com o CI verde. Cada merge
  vira deploy no Render (e o Render guarda os anteriores: *Rollback* volta um deploy com um clique).
- **Testar antes de liberar**: `make homologar` sobe o sistema na sua máquina **em modo produção**
  (DEBUG desligado, gunicorn, estáticos comprimidos, Postgres em container). Abre em `http://localhost:8000`
  e no celular pela mesma rede Wi-Fi. Primeira vez: `make homologar-admin` cria seu usuário;
  `make homologar-parar` desliga o banco (os dados continuam lá para a próxima vez).
  Fotos e Pix só funcionam se `SUPABASE_*` e `MERCADO_PAGO_ACCESS_TOKEN` estiverem no ambiente — use
  credenciais de teste, nunca as de produção.

**CI** (`.github/workflows/ci.yml`), em todo push e PR da `homologacao` e da `main`:

| Parte | O que confere |
|---|---|
| Python | ruff; testes no Postgres 17 com 100% de cobertura; `check --deploy` com DEBUG desligado; migrações em dia e indo e voltando; `collectstatic` |
| JavaScript | ESLint; testes com 100% de cobertura; `output.css` em dia com os templates |
| Segurança | Bandit, Semgrep (OWASP, Django, Python, JS, segredos), pip-audit, npm audit, gitleaks no histórico |

**Atualizações** (`.github/workflows/atualizacoes.yml`): toda segunda, lista as bibliotecas com versão nova,
roda os testes com elas (todas juntas e, se quebrar, uma por uma) e publica na issue *Atualizações das
bibliotecas*: o que é "só atualizar", o que "precisa mexer no código" e o link do que mudou. Não abre PR.
Localmente: `make atualizacoes` (a lista) e `make atualizar PACOTES="nome outro"` (aplica no requirements).
O Dependabot fica pausado; se religado, abre os PRs na `homologacao` e espera 7 dias de cada versão.

**Proteção da `main`** (uma vez, no GitHub: *Settings → Branches → Add branch ruleset*): alvo `main`;
marque *Require a pull request before merging* e *Require status checks to pass* com os três checks do CI
(`Python · testes no Postgres, lint e Django`, `JavaScript · testes, lint e CSS`,
`Segurança · código, bibliotecas e segredos`); e *Block force pushes*.

## Deploy (Render)

`render.yaml` define o serviço: `build.sh` instala dependências, roda `collectstatic` e
`migrate`; a aplicação sobe com Gunicorn. Configure no painel do Render ao menos
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `SUPABASE_URL` e `SUPABASE_KEY`
(elas precisam existir também durante o build).
