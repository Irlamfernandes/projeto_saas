.PHONY: build up down restart logs shell migrate makemigrations superuser collectstatic test sonar seguranca css traducoes \
	lint verificar homologar homologacao-banco homologar-admin homologar-parar atualizacoes atualizar

# Sobe os containers em background fazendo build
up:
	docker compose up -d

# Faz o build do zero e sobe os containers
build:
	docker compose up --build -d

# Derruba os containers
down:
	docker compose down

# Reinicia os containers
restart:
	docker compose restart

# Exibe os logs em tempo real
logs:
	docker compose logs -f

# Acessa o terminal bash do container web
shell:
	docker compose exec web python manage.py shell

# Roda as migrações do banco de dados
migrate:
	docker compose exec web python manage.py migrate

# Cria as migrações para o app infrastructure (ou geral)
makemigrations:
	docker compose exec web python manage.py makemigrations

# Cria um superusuário
superuser:
	docker compose exec web python manage.py createsuperuser

# Coleta arquivos estáticos (útil para produção)
collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

# Roda as suítes Python (com cobertura) e JS localmente; requer requirements-dev.txt e npm install
# Testes com cobertura; também gera coverage.xml e coverage/lcov.info, lidos pelo SonarQube
test:
	python -m pytest --cov --cov-report=term-missing --cov-report=xml
	npm test -- --coverage

# O que o SonarQube não vê: falhas conhecidas nas bibliotecas e senhas/chaves no histórico do git.
# Gitleaks: https://github.com/gitleaks/gitleaks (binário único; valores sempre ocultos no relatório)
seguranca:
	pip-audit -r requirements.txt -r requirements-dev.txt
	npm audit
	@command -v gitleaks >/dev/null || (echo "Instale o gitleaks: https://github.com/gitleaks/gitleaks/releases"; exit 1)
	gitleaks git . --redact --no-banner

# Roda os testes (gerando a cobertura) e envia a análise ao SonarQube local.
# O token não fica em arquivo: SONAR_TOKEN=seu_token make sonar
sonar: test
	@test -n "$$SONAR_TOKEN" || (echo "Defina SONAR_TOKEN: SONAR_TOKEN=seu_token make sonar"; exit 1)
	sonar-scanner

# Recompila o Tailwind (static/css/output.css é versionado: rode após mudar classes nos templates)
css:
	npm run build:css

# Compila as traduções (locale/pt_BR/.../django.po -> .mo, versionado). Requer requirements-dev.
traducoes:
	pybabel compile -D django -d locale

# Linters: ruff (Python) e ESLint (JS). Os dois também rodam no CI.
lint:
	ruff check .
	npm run -s lint

# O mesmo que o CI confere, na sua máquina (menos o Postgres: aqui os testes usam SQLite).
verificar: lint test seguranca
	DJANGO_DEBUG=True python manage.py makemigrations --check --dry-run
	npm run -s build:css && git diff --exit-code static/css/output.css

# ---------- Homologação local ----------
# Sobe o sistema em MODO PRODUÇÃO na sua máquina: Postgres em container (os dados ficam entre uma vez e outra),
# gunicorn, DEBUG desligado e estáticos comprimidos. Abre no PC e no celular (mesma rede Wi-Fi).
# Primeira vez: `make homologar-admin` para criar seu usuário. Para parar o banco: `make homologar-parar`.
IP_LOCAL = $(shell hostname -I 2>/dev/null | awk '{print $$1}')
HOMOLOGACAO = DJANGO_SETTINGS_MODULE=config.settings_homologacao \
	DATABASE_URL=postgresql://postgres:homologacao@localhost:55432/postgres DATABASE_SSL_REQUIRE=False \
	DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,$(IP_LOCAL)" \
	DJANGO_SECRET_KEY=homologacao-local-$(shell cat /etc/machine-id 2>/dev/null || hostname)

homologacao-banco:
	@docker start homologacao-db >/dev/null 2>&1 || \
		docker run -d --name homologacao-db -e POSTGRES_PASSWORD=homologacao -p 55432:5432 postgres:17-alpine >/dev/null
	@until docker exec homologacao-db pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done

homologar: homologacao-banco
	$(HOMOLOGACAO) python manage.py migrate --no-input
	$(HOMOLOGACAO) python manage.py collectstatic --no-input --ignore tests -v0
	@echo "Abra http://localhost:8000 ou, no celular, http://$(IP_LOCAL):8000  (Ctrl+C para parar)"
	$(HOMOLOGACAO) gunicorn config.wsgi:application --bind 0.0.0.0:8000 --threads 4

homologar-admin: homologacao-banco
	$(HOMOLOGACAO) python manage.py migrate --no-input
	$(HOMOLOGACAO) python manage.py createsuperuser

homologar-parar:
	docker stop homologacao-db

# ---------- Atualizações ----------
# O que tem versão nova (a verificação semanal no GitHub também roda os testes com elas: `relatorio --testar`).
atualizacoes:
	python scripts/atualizacoes.py relatorio

# Troca a versão fixada nos requirements pela mais nova: make atualizar PACOTES="django coverage"
atualizar:
	@test -n "$(PACOTES)" || (echo 'Informe os pacotes: make atualizar PACOTES="nome outro"'; exit 1)
	python scripts/atualizacoes.py aplicar $(PACOTES)
	pip install -r requirements-dev.txt
