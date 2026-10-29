#!/usr/bin/env bash
# Run the overnight renewal-book scan as a Nebius Serverless AI job (billed only while it runs).
#   NEBIUS_API_KEY=... BOOK=./my_book.csv bash deploy/nebius/job.sh
# The CSV is injected read-only into the container (Nebius limits injected files to 64 KiB, a few hundred loans);
# results are printed to the job logs as JSON and written to /tmp/out inside the container (mount a volume to keep them).
set -euo pipefail
: "${NEBIUS_API_KEY:?set NEBIUS_API_KEY (Token Factory key)}"
BOOK=${BOOK:-./book.csv}
IMAGE=${IMAGE:-ghcr.io/alenzacodes/decision-ladder:latest}

nebius ai job create \
  --name "renewal-book-$(date +%Y%m%d-%H%M)" \
  --image "$IMAGE" \
  --platform cpu-e1 \
  --preset 2vcpu-8gb \
  --inject-file "${BOOK}:/input/book.csv" \
  --env "NEBIUS_API_KEY=${NEBIUS_API_KEY}" \
  --env "DL_JOB=1" \
  --container-command python \
  --args "-m decision_ladder job renewal-book --input /input/book.csv --out /tmp/out --drafts 5"
