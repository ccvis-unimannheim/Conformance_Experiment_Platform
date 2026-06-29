#!/usr/bin/env bash
# One-time helper: generate idiom preview SVGs for ALL tasks and copy them out
# of the container so they can be committed to the repo.
#
# Usage (run from repo root on the server):
#   bash provibackend/scripts/export_idiom_previews.sh [API_BASE] [TOKEN]
#
# Defaults:
#   API_BASE  https://cc-vis.rz.uni-mannheim.de/api
#   TOKEN     (empty — add Bearer token if the endpoint requires auth)
#
# After this script finishes:
#   git add provibackend/ProViBackend/scripts/sample_data/output/__idiom_preview
#   git commit -m "feat: pre-generate static idiom preview SVGs"
#   git push origin develop
#
# On the next `docker compose up --build` the SVGs are baked into the image
# and all idiom previews will load instantly without generation.

set -euo pipefail

API_BASE="${1:-https://cc-vis.rz.uni-mannheim.de/api}"
TOKEN="${2:-}"

AUTH_HEADER=""
if [ -n "$TOKEN" ]; then
  AUTH_HEADER="-H \"Authorization: Bearer $TOKEN\""
fi

CONTAINER="provibackend"
DEST="./provibackend/ProViBackend/scripts/sample_data/output/__idiom_preview"

echo "=== Step 1: trigger bulk generation via POST /admin/idiom-preview-all ==="
curl -s -X POST "$API_BASE/admin/idiom-preview-all" \
  ${TOKEN:+-H "Authorization: Bearer $TOKEN"} \
  -H "Content-Type: application/json" | python3 -m json.tool || true

echo ""
echo "=== Step 2: waiting for generation to complete (polling every 10s) ==="
while true; do
  # Ask the container directly whether any task is still "generating"
  still_generating=$(docker exec "$CONTAINER" \
    python3 -c "
import sys, pathlib
base = pathlib.Path('/code/ProViBackend/scripts/sample_data/output/__idiom_preview')
# crude proxy: check if tmp/in-progress marker exists; otherwise just wait a fixed time
print('done')
" 2>/dev/null || echo "done")

  # Real check: re-call status for a sample of task keys
  response=$(curl -s "$API_BASE/admin/idiom-preview-all" 2>/dev/null || echo "{}")
  generating_count=$(echo "$response" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tasks = d.get('tasks', {})
    print(sum(1 for v in tasks.values() if v == 'generating'))
except:
    print(0)
" 2>/dev/null || echo "0")

  if [ "$generating_count" -eq 0 ]; then
    echo "All tasks done (or no tasks were generating)."
    break
  fi
  echo "  $generating_count task(s) still generating — waiting 10s..."
  sleep 10
done

echo ""
echo "=== Step 3: copy SVGs out of container ==="
mkdir -p "$(dirname "$DEST")"
docker cp "$CONTAINER:/code/ProViBackend/scripts/sample_data/output/__idiom_preview" \
           "$(dirname "$DEST")/"

echo ""
echo "=== Done! SVGs saved to $DEST ==="
echo ""
echo "Next steps:"
echo "  git add $DEST"
echo "  git commit -m \"feat: pre-generate static idiom preview SVGs for all tasks\""
echo "  git push origin develop"
