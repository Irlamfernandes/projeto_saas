FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . /app/

# Dá permissão de execução para o script de entrada
RUN chmod +x /app/entrypoint.sh

# Cria o usuário não-root e ajusta permissões
RUN useradd -u 1000 -m -d /home/appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Executa o script usando a sintaxe Exec (Formato de Vetor)
ENTRYPOINT ["/app/entrypoint.sh"]