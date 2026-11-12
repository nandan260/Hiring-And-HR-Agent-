FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 hireflow && \
    useradd --uid 10001 --gid hireflow --create-home --shell /usr/sbin/nologin hireflow

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

COPY . /app
RUN mkdir -p /app/storage/uploads /app/storage/sandboxes /app/storage/browsers && \
    chown -R hireflow:hireflow /app

USER hireflow

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
