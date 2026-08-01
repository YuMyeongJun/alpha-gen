FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs

# 민감 정보(.env)는 docker-compose.yml의 env_file로 런타임에 주입
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
