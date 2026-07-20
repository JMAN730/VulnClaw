FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nmap \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir beautifulsoup4 httpx lxml pycryptodome requests

RUN useradd --create-home --uid 1000 sandbox \
    && mkdir -p /workspace /vulnclaw-artifacts \
    && chown sandbox:sandbox /workspace /vulnclaw-artifacts

USER sandbox
WORKDIR /workspace
CMD ["sleep", "infinity"]
