#!/usr/bin/env bash
# STORY-222: Generate TypeScript types from backend OpenAPI schema.
#
# Usage:
#   ./scripts/generate-api-types.sh              # Fetch from running backend
#   ./scripts/generate-api-types.sh --check      # Check if generated types are up-to-date
#   OPENAPI_URL=http://... ./scripts/generate-api-types.sh  # Custom URL
#
# Prerequisites:
#   - Backend running at $OPENAPI_URL (default: http://localhost:8000)
#   - npx available (openapi-typescript installed as devDep in frontend/)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
OUTPUT_FILE="$FRONTEND_DIR/app/api-types.generated.ts"
OPENAPI_URL="${OPENAPI_URL:-http://localhost:8000/openapi.json}"

echo "=== STORY-222: OpenAPI → TypeScript Codegen ==="
echo "Source:  $OPENAPI_URL"
echo "Output:  $OUTPUT_FILE"

# Fetch OpenAPI schema to verify backend is reachable
echo ""
echo "Fetching OpenAPI schema..."
if ! curl -sf "$OPENAPI_URL" > /dev/null 2>&1; then
  echo "ERROR: Cannot reach backend at $OPENAPI_URL"
  echo "Make sure the backend is running: cd backend && uvicorn main:app --port 8000"
  exit 1
fi
echo "Backend is reachable."

# Generate types
echo "Generating TypeScript types..."
cd "$FRONTEND_DIR"

# Generate directly (matches CI: openapi-typescript raw output)
npx openapi-typescript "$OPENAPI_URL" --output "$OUTPUT_FILE" 2>&1

echo "Generated: $OUTPUT_FILE"

# --check mode: verify generated types match existing file
if [[ "${1:-}" == "--check" ]]; then
  echo ""
  echo "Checking if generated types are up-to-date..."

  # Generate to a comparison file
  COMPARE_FILE=$(mktemp)
  npx openapi-typescript "$OPENAPI_URL" --output "$COMPARE_FILE" 2>&1

  if diff -q "$OUTPUT_FILE" "$COMPARE_FILE" > /dev/null 2>&1; then
    echo "Types are up-to-date."
    rm -f "$COMPARE_FILE"
  else
    echo "ERROR: Generated types are out of date!"
    echo "Run: npm run generate:api-types"
    rm -f "$COMPARE_FILE"
    exit 1
  fi
fi

# Type-check the generated file
echo ""
echo "Running TypeScript check..."
npx tsc --noEmit --pretty 2>&1 || {
  echo ""
  echo "WARNING: TypeScript errors detected. Review generated types."
  exit 1
}

echo ""
echo "Done. Types generated and validated successfully."
