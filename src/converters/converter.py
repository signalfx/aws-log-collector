from abc import abstractmethod

from logger import log


class Converter:

    @abstractmethod
    def supports(self, log_event):
        pass

    def convert_to_hec(self, log_event, context, sfx_metrics):
        try:
            return list(self._convert_to_hec(log_event, context, sfx_metrics))
        except Exception as ex:
            log.error(f"Exception occurred: {ex}")
            sfx_metrics.inc_counter("sf.org.awsLogCollector.num.errors")

    @abstractmethod
    def _convert_to_hec(self, log_event, context, sfx_metrics):
        pass
