FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot_forward.py ./

# Espone la porta usata da Render (default 10000)
EXPOSE 8080

CMD ["python", "bot_forward.py"]
