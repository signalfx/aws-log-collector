from parsers.parser import ParsedLine
from parsers.redshift_base import RedshiftBaseParser

FIELD_NAMES = ("userid", "username", "oldusername", "action",
               "usecreatedb", "usesuper", "usecatupd",
               "valuntil", "pid", "xid", "recordtime")


class RedshiftUserLogParser(RedshiftBaseParser):

    def supports(self, log_file_name):
        return self._is_redshift_log(log_file_name, "userlog")

    def try_parse(self, metadata, record):
        fields = dict(zip(FIELD_NAMES, record))

        hec_time = self._redshift_time_to_hec_time(fields["recordtime"]) if "recordtime" in fields else None
        arns = [("clusterArn", metadata["clusterArn"])]
        return ParsedLine(hec_time, fields, arns)
