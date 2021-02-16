import re

from aws_log_collector.parsers.parser import ParsedLine
from aws_log_collector.parsers.redshift_base import RedshiftBaseParser

FIELD_NAMES = ("userid", "username", "oldusername", "action",
               "usecreatedb", "usesuper", "usecatupd",
               "valuntil", "pid", "xid", "recordtime")

# Sample user activity log line
# '2020-12-08T22:00:03Z UTC [ db=dev user=rdsdb pid=685 userid=1 xid=245578 ]' LOG: SET statement_timeout TO 120000

NEW_LOG_LINE_REGEX = re.compile(r"'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.+\[\s*db")
TIMESTAMP_START = 1
TIMESTAMP_END = 20


class RedshiftUserActivityLogParser(RedshiftBaseParser):

    def supports(self, log_file_name):
        return self._is_redshift_log(log_file_name, "useractivitylog")

    def complete_lines(self, raw_lines_generator):
        complete_line = None
        for line in raw_lines_generator:
            if NEW_LOG_LINE_REGEX.match(line):
                if complete_line is not None:
                    yield complete_line
                complete_line = line
            else:
                complete_line = complete_line + "\n" + line if complete_line is not None else line
        if complete_line is not None:
            yield complete_line

    def parse(self, metadata, line):
        hec_time = self._iso_time_to_hec_time(line[TIMESTAMP_START:TIMESTAMP_END])
        arns = [("clusterArn", metadata["clusterArn"])]
        return ParsedLine(hec_time, {}, arns, line)

    def try_parse(self, metadata, line):
        pass
