import csv
from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from datetime import timezone
from typing import Dict, List, Optional

import dateutil

from aws_log_collector.logger import log


@dataclass
class ParsedLine:
    """
    Represents parsed log line with optional metadata.

    hec_time    log event time (seconds.ms), e.g. 1607371315.177
    fields      log forwarder and log event metadata: e.g. AWS region,
                AWS account Id, resource names, etc.
    arns        list of tuples (name, arn), e.g. [("clusterArn", "arn:aws:redshift...)]
    log_line    complete log line as read from the log file
    """
    hec_time: float = None
    fields: Dict = field(default_factory=dict)  #
    arns: List[tuple] = field(default_factory=list)
    log_line: str = None


class Parser(ABC):
    """
    Base class for various access logs parsers.
    """

    def __init__(self, delimiter=" "):
        self._delimiter = delimiter

    @abstractmethod
    def get_namespace(self) -> str:
        """
        Returns AWS namespace related to this parser.
        """
        pass

    @abstractmethod
    def supports(self, log_file_name) -> bool:
        """
        Indicates if this parser supports given log file
        """
        pass

    def get_file_metadata(self, context_metadata, log_file_name) -> Dict:
        """
        Returns log file related metadata based on the context metadata and
        log file name itself.
        """
        return {}

    def complete_lines(self, raw_lines_generator):
        """
        Returns generator that yields complete log lines. Some log files split
        single logical log line into multiple lines. In such a case this method
        provides a convenient hook to transform split lines into complete lines.

        The default implementation assumes each log line is complete.
        """
        return raw_lines_generator

    def parse(self, metadata, line) -> ParsedLine:
        """
        Converts complete log line into ParsedLine. Note all ParsedLine fields
        except the log_line may or may not be present in the returned ParsedLine.
        """
        reader = csv.reader([line], delimiter=self._delimiter)
        record = next(reader, None)

        result = self.try_parse(metadata, record) if record is not None else None
        if result is None:
            result = ParsedLine()

        result.log_line = line
        return result

    @abstractmethod
    def try_parse(self, metadata, record) -> Optional[ParsedLine]:
        pass

    def validate_line(self, line) -> bool:
        return True

    def _iso_time_to_hec_time(self, timestamp):
        try:
            dt = dateutil.parser.isoparse(timestamp)
            return self._naive_time_to_zone_aware_time(dt).timestamp()
        except ValueError as ex:
            log.warning(f"Failed to parse {self.get_namespace()} timestamp {timestamp}: {ex}")
            return None

    @staticmethod
    def _naive_time_to_zone_aware_time(dt):
        # https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
