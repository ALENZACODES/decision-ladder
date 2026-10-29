# Decision Ladder: runs on a Nebius AI Cloud VM (or any container host) and calls
# NVIDIA Nemotron through Nebius Token Factory. Standard library only: no pip install needed.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
COPY decision_ladder ./decision_ladder
COPY evals ./evals
RUN useradd -r -u 10001 app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health',timeout=4)"
CMD ["sh", "-c", "python -m decision_ladder serve ${PORT}"]
