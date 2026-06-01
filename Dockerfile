# GridWatch AU web dashboard — deploy-ready image.
# Build:  docker build -t gridwatch-au .
# Run:    docker run -p 8000:8000 -v "$PWD/data:/data" gridwatch-au
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . gunicorn

# The web app loads its append-only ledger from here; mount a volume to persist it.
ENV GRIDWATCH_LEDGER=/data/ledger.jsonl PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} 'gridwatch.web:create_app()'"]
