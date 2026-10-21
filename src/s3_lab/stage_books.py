#!/usr/bin/env python3
"""Create a public S3 bucket and upload the books plus an index page to it.
"""

import json
import logging
import os
import sys
import time

import boto3
import requests
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read the command line arguments
    """
    if len(sys.argv) < 4:
        log.error(f"Usage: {sys.argv[0]} <book_list_file> <index_html_path> <bucket_name>")
        sys.exit(1)

    list_file = sys.argv[1]
    index_path = sys.argv[2]
    bucket = sys.argv[3]

    return list_file, index_path, bucket


def download_books(list_file, dest_dir):
    """Download every book listed in list_file into dest_dir
    """
    os.makedirs(dest_dir, exist_ok=True)

    paths = []
    try:
        with open(list_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        log.error(f"Book list not found: {list_file}")
        return paths

    for url in urls:
        filename = url.split("/")[-1]
        path = os.path.join(dest_dir, filename)

        if os.path.exists(path):
            log.info(f"Already downloaded, skipping: {path}")
            paths.append(path)
            continue

        try:
            log.info(f"Downloading {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as out:
                out.write(response.content)
            paths.append(path)
            log.info(f"Saved {path}")
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")
        except OSError as e:
            log.error(f"Error saving {path}: {e}")

        time.sleep(1)

    return paths


def create_bucket(bucket):
    """Create the bucket if it does not already exist
    """
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket {bucket} already exists")
        return True
    except ClientError:
        log.info(f"Bucket {bucket} not found, creating it")

    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket {bucket}: {e}")
        return False


def make_public(bucket):
    """Allow anyone to read the objects.
    """
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        log.info(f"Block Public Access turned off for {bucket}")

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Public read policy attached to {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error making bucket {bucket} public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload the book files to the top level of the bucket
    """
    count = 0
    for path in file_paths:
        key = os.path.basename(path)
        try:
            s3.upload_file(
                path,
                bucket,
                key,
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
            )
            log.info(f"Uploaded {path} as {key}")
            count += 1
        except FileNotFoundError:
            log.error(f"File not found: {path}")
        except (ClientError, S3UploadFailedError) as e:
            log.error(f"Error uploading {path}: {e}")
    return count


def upload_index(bucket, index_path):
    """Upload the index page as index.html
    """
    try:
        s3.upload_file(
            index_path,
            bucket,
            "index.html",
            ExtraArgs={"ContentType": "text/html"},
        )
        log.info(f"Uploaded {index_path} as index.html")
        return True
    except FileNotFoundError:
        log.error(f"File not found: {index_path}")
        return False
    except (ClientError, S3UploadFailedError) as e:
        log.error(f"Error uploading {index_path}: {e}")
        return False


def main():
    """Run all the steps"""
    list_file, index_path, bucket = parse_args()

    paths = download_books(list_file, "books")
    if not paths:
        log.error("No books were downloaded")
        sys.exit(1)

    if not create_bucket(bucket):
        log.error("Could not create the bucket")
        sys.exit(1)

    if not make_public(bucket):
        log.error("Could not make the bucket public")
        sys.exit(1)

    uploaded = upload_files(bucket, paths)
    index_ok = upload_index(bucket, index_path)

    if uploaded == len(paths) and index_ok:
        log.info(f"Success: uploaded {uploaded} books and the index page")
    else:
        log.error(f"Finished with problems: {uploaded}/{len(paths)} books uploaded, "
                  f"index uploaded: {index_ok}")
    log.info(f"Index page: https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()
