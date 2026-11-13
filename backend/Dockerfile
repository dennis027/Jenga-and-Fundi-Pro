# syntax=docker/dockerfile:1
# Django REST API (Fundi / Jenga Pro backend)

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tesseract-ocr: required by pytesseract (M-Pesa screenshot transaction-code extraction)
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Collect static files at build time. Settings require these variables to be
# present; throwaway values are used only for this step.
RUN SECRET_KEY=build-only DB_NAME=x DB_USER=x DB_PASSWORD=x DB_HOST=x DB_PORT=5432 \
    MPESA_CONSUMER_KEY=x MPESA_CONSUMER_SECRET=x MPESA_SHORTCODE=x MPESA_PASSKEY=x MPESA_CALLBACK_URL=x \
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend EMAIL_HOST=x EMAIL_PORT=25 EMAIL_USE_TLS=False \
    EMAIL_HOST_USER=x EMAIL_HOST_PASSWORD=x DEFAULT_FROM_EMAIL=x@example.com AT_USERNAME=sandbox AT_API_KEY=x \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app \
 && mkdir -p /data/media \
 && chown -R app:app /data /app
USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
