import os

from smart_open import open


class S3Service:

    @staticmethod
    def read_lines(bucket, key):
        path = os.path.join(bucket, key)
        with open(f"s3://{path}", "r") as s3file:
            for line in s3file:
                yield line

    @staticmethod
    def get_aws_namespace(key):
        """
        Extracts AWS namespce from S3 object key that stores access logs.
        Key format is "logs/<integration-id>/<namespace>/<timestamp>-<random-id>"
        """
        path = os.path.normpath(key)
        parts = path.split(os.sep, 3)
        return parts[2] if len(parts) >= 2 else None

