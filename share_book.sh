#!/bin/bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <book_url> <bucket> <expiration_seconds>" >&2
    echo "Example: $0 https://www.gutenberg.org/cache/epub/11/pg11.txt secret-mst3k 3600" >&2
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"

# Keep the file name from the URL
FILENAME="$(basename "$URL")"

# Download the book into the books
mkdir -p books
echo "Downloading $URL"
curl -fsSL "$URL" -o "books/$FILENAME"

# Create the bucket
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket $BUCKET already exists"
else
    echo "Creating bucket $BUCKET"
    aws s3 mb "s3://$BUCKET"
fi

# Upload the book with a content type
echo "Uploading books/$FILENAME"
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# Create and print a URL
echo "Presigned URL (valid for $EXPIRES seconds):"
aws s3 presign "s3://$BUCKET/$FILENAME" --expires-in "$EXPIRES"
