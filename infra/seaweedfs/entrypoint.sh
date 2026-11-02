#!/bin/sh
# Render S3 credentials from env into SeaweedFS identity config, then start
# master + volume + filer + S3 gateway in one process (fine for a single node).
set -eu

cat > /tmp/s3.json <<EOF
{"identities": [{
  "name": "admin",
  "credentials": [{"accessKey": "${S3_ACCESS_KEY}", "secretKey": "${S3_SECRET_KEY}"}],
  "actions": ["Admin", "Read", "Write", "List", "Tagging"]
}]}
EOF

exec weed server \
  -dir=/data \
  -ip.bind=0.0.0.0 \
  -master.volumeSizeLimitMB=1024 \
  -volume.max=0 \
  -s3 -s3.port=8333 -s3.config=/tmp/s3.json
