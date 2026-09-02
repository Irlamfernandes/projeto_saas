.PHONY: build up down restart logs shell migrate superuser test

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