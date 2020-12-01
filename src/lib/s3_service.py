import os

from smart_open import open


class S3Service:

    @staticmethod
    def read_lines(bucket, key):
        path = os.path.join(bucket, key)
        with open(f"s3://{path}", "r") as s3file:
            for line in s3file:
                yield line
