FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    dos2unix \
    libxcb-shm0 \
    libxcb1 \
    libx11-6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN dos2unix start.sh

RUN chmod +x start.sh
RUN chmod +x ./tiny/ffmpeg

CMD ["./start.sh"]
