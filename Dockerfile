# LeoBot — Dockerfile جایگزین برای Railway (در کنار Nixpacks)
# اگر بیلدر Railway را روی "Dockerfile" تنظیم کنید، از همین فایل استفاده می‌شود.

FROM python:3.11-slim

# جلوگیری از بافر شدن stdout/stderr تا لاگ‌ها بلافاصله در Railway دیده شوند
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# پوشه‌های داده/لاگ از قبل ساخته شوند (در صورت نبود Volume، همچنان کار می‌کند)
RUN mkdir -p /app/data /app/logs

CMD ["python", "main.py"]
