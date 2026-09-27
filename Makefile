.PHONY: build up down restart logs shell migrate makemigrations superuser collectstatic test sonar css traducoes

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
