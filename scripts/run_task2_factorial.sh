#!/usr/bin/env bash
# Run the Python controller in Docker, using host-identical paths for workers.
set -euo pipefail
FACTORIAL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FACTORIAL_DOCKER="$(command -v docker)"
exec docker run --rm --network none \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "${FACTORIAL_DOCKER}:/usr/local/bin/docker:ro" \
  -v "${FACTORIAL_ROOT}:${FACTORIAL_ROOT}" -w "${FACTORIAL_ROOT}" \
  -e "PYTHONPATH=${FACTORIAL_ROOT}/src:${FACTORIAL_ROOT}" \
  -e PYTHONDONTWRITEBYTECODE=1 -e OPEN_ROUTER_API_KEY -e OPENAI_API_KEY -e OPENAI_BASE_URL \
  --entrypoint python "${FACTORIAL_CONTROLLER_IMAGE:-uniagent-factorial:experiment}" \
  -c 'import sys
if len(sys.argv) > 1 and sys.argv[1] == "run":
    from scripts.task2_factorial_credentials import configure
    configure()
from scripts.task2_factorial.__main__ import main
main()' "$@"
