# QA only. Never used by the application or deployed to production.
ARG QA_BASE=node:22-bookworm-slim
FROM ${QA_BASE}
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer poppler-utils python3 python3-pil python3-pip \
    python3-fonttools fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --break-system-packages pdf2image==1.17.0
RUN mkdir -p /qa/input /qa/output /qa/tools /usr/local/share/fonts/report
WORKDIR /qa
