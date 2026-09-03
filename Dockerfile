# Usa a imagem oficial do Python
FROM python:3.11-slim

# Variáveis de ambiente para o Python não gerar .pyc e exibir logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema necessárias para o PostgreSQL
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Atualiza o pip e instala as dependências do projeto
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do projeto para dentro do container
COPY . /app/

# SEGURANÇA: Cria um usuário não-root (não-privilegiado) e ajusta as permissões da pasta
RUN useradd -u 1000 -m -d /home/appuser appuser && \
    chown -R appuser:appuser /app

# Alterna para o usuário não-root para executar os comandos e a aplicação
USER appuser

# Expõe a porta que o Render usa
EXPOSE 8000

# Comando para iniciar o servidor Gunicorn em produção
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]