FROM python:3.11-slim

# تثبيت FFmpeg و Git
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# إنشاء مجلد العمل
WORKDIR /app

# نسخ الملفات
COPY . .

# إعطاء صلاحيات التنفيذ
RUN chmod +x start.sh run.py

# أمر التشغيل
CMD ["./start.sh"]