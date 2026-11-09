FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

# requirements.txt incluye «-e .»: copiar los metadatos y el paquete src/ ANTES de pip.
COPY pyproject.toml README.md requirements.txt ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir uvicorn==0.35.0 \
    && python -c "from backend.gateway.api import create_app; assert callable(create_app)"

RUN groupadd --gid 10001 privateway \
    && useradd --uid 10001 --gid privateway --no-create-home --shell /usr/sbin/nologin privateway \
    && mkdir -p /var/lib/privateway/audit \
    && chown -R privateway:privateway /var/lib/privateway/audit /app

USER privateway
EXPOSE 8000
# La instancia ASGI se obtiene mediante la factoría create_app del gateway experimental.
CMD ["uvicorn", "backend.gateway.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
