import copy
import os
from urllib.parse import unquote_plus

from enrichers.base_enricher import BaseEnricher


class S3LogsEnricher(BaseEnricher):

    def get_metadata(self, namespace, parsed_line, common_metadata, sfx_metrics):
        result = copy.deepcopy(common_metadata)

        if namespace == "s3" and parsed_line.get("bucket", "-") != "-":
            bucket_arn = "arn:aws:s3:::" + parsed_line["bucket"]
            bucket_tags = self.get_tags(bucket_arn, sfx_metrics)
            result = self.merge(result, {"bucketArn": bucket_arn}, bucket_tags)

            if parsed_line.get("key", "-") != "-":
                object_arn = "arn:aws:s3:::" + os.path.join(parsed_line["bucket"], self._decode_key(parsed_line["key"]))
                object_tags = self.get_tags(object_arn, sfx_metrics)
                result = self.merge(result, {"objectArn": object_arn}, object_tags)

        return result

    @staticmethod
    def _decode_key(url_encoded_s3_request_key):
        """
        Decodes S3 object key as stored in the S3 access log
        """
        s3_request_key = unquote_plus(url_encoded_s3_request_key)  # name%2Bwith%2Bspaces%252Band%2B%252B%2Bpluses.jpeg
        raw_key_name = unquote_plus(s3_request_key)  # name+with+spaces%2Band+%2B+pluses.jpeg
        return raw_key_name  # name with spaces+and + pluses.jpeg
