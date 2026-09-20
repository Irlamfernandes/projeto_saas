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

# NOSONAR
COPY . /app/ # NOSONAR

# Dá permissão de execução, cria usuário não-root e ajusta permissões em um único bloco RUN (evita camadas extras)
RUN chmod +x /app/entrypoint.sh && \
    useradd -u 1000 -m -d /home/appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]