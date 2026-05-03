FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

# 🔥 الحل هنا
RUN dos2unix start.sh

RUN chmod +x start.sh

CMD ["./start.sh"]