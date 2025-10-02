# Dockerfile
FROM python:3.11-slim

# Impostazione working directory
WORKDIR /app

# Copia file di configurazione
COPY requirements.txt ./
COPY .env ./

# Installazione dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Copia codice bot
COPY bot_forward.py ./

# Espone porta 8080 per webhook/health check
EXPOSE 8080

# Comando di avvio
CMD ["python", "bot_forward.py"]
