FROM node:22.23.3-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS renderer
WORKDIR /opt/trust-receipt-renderer
COPY src/trust_receipt/reporting/assets/renderer/package*.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

FROM python:3.12-slim-bookworm@sha256:0f5b26b9518d002b6173fd61daad821fa340635ebfec5bba471013f9ca114579

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    REPORT_RENDERER_NODE=/opt/trust-receipt-renderer/renderer-node \
    REPORT_RENDERER_MODULES=/opt/trust-receipt-renderer/node_modules

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home /app app
RUN apt-get update && apt-get install -y --no-install-recommends fontconfig \
    && rm -rf /var/lib/apt/lists/*
COPY --from=renderer /usr/local/bin/node /usr/local/bin/node
COPY --from=renderer /usr/local/LICENSE /usr/local/share/doc/node/LICENSE
COPY --from=renderer /opt/trust-receipt-renderer /opt/trust-receipt-renderer
COPY src/trust_receipt/reporting/assets/ReportSans-Regular.ttf /usr/local/share/fonts/report/
COPY src/trust_receipt/reporting/assets/OFL.txt /usr/local/share/fonts/report/OFL.txt
RUN fc-cache -f && fc-match -f '%{family}' 'TreasuryTally Report Sans' | grep -F 'TreasuryTally Report Sans'

COPY pyproject.toml ./
COPY requirements.lock.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import subprocess,sys,tomllib; deps=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; subprocess.run([sys.executable,'-m','pip','install','-c','requirements.lock.txt',*deps],check=True)"
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-deps . && python -m pip check
COPY scripts/deploy/renderer_node.py /opt/trust-receipt-renderer/renderer-node
RUN chmod 0555 /opt/trust-receipt-renderer/renderer-node

COPY app ./app
COPY .streamlit ./.streamlit
COPY fixtures ./fixtures
COPY scripts/deploy/check_image.py /opt/trust-receipt-smoke/check_image.py
COPY scripts/deploy/check_report_runtime.py /opt/trust-receipt-smoke/check_report_runtime.py
COPY scripts/deploy/check_report_downloads.py /opt/trust-receipt-smoke/check_report_downloads.py
COPY scripts/deploy/check_report_memory.py /opt/trust-receipt-smoke/check_report_memory.py
RUN mkdir -p /app/data /app/receipts/private && chown -R app:app /app

USER app
RUN python -c "import runpy; runpy.run_path('/opt/trust-receipt-smoke/check_image.py', run_name='__main__')"
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/trust-receipt/_stcore/health', timeout=3)"

CMD ["python", "-m", "streamlit", "run", "app/streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.baseUrlPath=trust-receipt", "--server.headless=true", \
     "--browser.gatherUsageStats=false"]

