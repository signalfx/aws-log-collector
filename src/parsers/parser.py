import csv
from abc import abstractmethod

from dataclasses import dataclass, field

from typing import Dict, List, Optional

import dateutil
from datetime import timezone

from logger import log


@dataclass
class ParsedLine:
    hec_time: float = None
    fields: Dict = field(default_factory=dict)
    arns: List[tuple] = field(default_factory=list)
    raw_log_line: str = None


class Parser:

    def __init__(self, delimiter=" "):
        self._delimiter = delimiter

    @abstractmethod
    def get_namespace(self) -> str:
        pass

    @abstractmethod
    def supports(self, log_file_name) -> bool:
        pass

    def get_file_metadata(self, context_metadata, log_file_name) -> Dict:
        return {}

    def parse(self, metadata, line) -> ParsedLine:
        reader = csv.reader([line], delimiter=self._delimiter)
        record = next(reader, None)

        result = self.try_parse(metadata, record) if record is not None else None
        if result is None:
            result = ParsedLine()

        result.raw_log_line = line
        return result

    @abstractmethod
    def try_parse(self, metadata, line) -> Optional[ParsedLine]:
        pass

    def iso_time_to_hec_time(self, timestamp):
        try:
            dt = dateutil.parser.isoparse(timestamp)
            # https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError as ex:
            log.warning(f"Failed to parse {self.get_namespace()} timestamp {timestamp}: {ex}")
            return None
