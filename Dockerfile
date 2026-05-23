FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs

# config.py는 런타임에 마운트 (민감 정보)
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
