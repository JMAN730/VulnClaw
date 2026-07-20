FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates=20230311 nmap=7.93+dfsg1-1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir beautifulsoup4==4.12.3 httpx==0.27.2 lxml==5.3.0 pycryptodome==3.21.0 requests==2.32.3

RUN useradd --create-home --uid 1000 sandbox \
    && mkdir -p /workspace /vulnclaw-artifacts \
    && chown sandbox:sandbox /workspace /vulnclaw-artifacts

USER sandbox
WORKDIR /workspace
CMD ["sleep", "infinity"]
