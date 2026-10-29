# Decision Ladder Mortgage OS.
# Runs as a Nebius Serverless AI endpoint (or job), on a Nebius AI Cloud VM, or any container host.
# Inference is NVIDIA Nemotron on Nebius Token Factory (NEBIUS_API_KEY); nothing runs on a GPU here.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
# Node.js runs the JavaScript apps' own calculator code (Cash to Close, Mortgage Suite, Renewal Check, ...)
RUN apt-get update && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/* && node --version
# Renewal Radar (a Python module of the OS) has its own dependencies
COPY modules/renewal-radar/requirements.txt /tmp/rr-requirements.txt
RUN pip install --no-cache-dir -r /tmp/rr-requirements.txt
COPY decision_ladder ./decision_ladder
COPY modules ./modules
COPY evals ./evals
RUN useradd -r -u 10001 app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health',timeout=4)"
CMD ["sh", "-c", "python -m decision_ladder serve ${PORT}"]
