FROM python:3.11-slim
WORKDIR /app

# Copia solo code e requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot_forward.py ./

EXPOSE 8080
CMD ["python", "bot_forward.py"]
