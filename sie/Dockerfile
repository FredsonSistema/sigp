FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY buscador_nfse.py /app/buscador_nfse.py

EXPOSE 5000

CMD ["python", "/app/buscador_nfse.py"]
