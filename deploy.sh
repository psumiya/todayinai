#!/usr/bin/env bash
# Upload the built page to S3 and refresh CloudFront.
# Env: S3_BUCKET (required), S3_KEY (default ainews.html), CLOUDFRONT_DISTRIBUTION_ID (optional)
set -euo pipefail
: "${S3_BUCKET:?set S3_BUCKET}"
KEY="${S3_KEY:-ainews.html}"
test -s dist/ainews.html || { echo "dist/ainews.html missing; run python -m newsletter.build" >&2; exit 1; }
aws s3 cp dist/ainews.html "s3://${S3_BUCKET}/${KEY}" \
  --content-type "text/html; charset=utf-8" \
  --cache-control "public, max-age=300"
if [[ -n "${CLOUDFRONT_DISTRIBUTION_ID:-}" ]]; then
  aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths "/${KEY}" >/dev/null
fi
echo "deployed s3://${S3_BUCKET}/${KEY}"
