from aws_log_collector.enrichers.base_enricher import BaseEnricher
from aws_log_collector.logger import log

LOG_GROUP_NAME_PREFIX_TO_NAMESPACE_MAPPING = {
    "/aws/lambda": "lambda",
    "/aws/rds": "rds",
    "/aws/eks": "eks",
    "api-gateway-": "api-gateway"
}


class CloudWatchLogsEnricher(BaseEnricher):

    def get_metadata(self, raw_logs, context, sfx_metrics):
        metadata = self._basic_enrichment(raw_logs, context)
        tags = self.get_tags(metadata.get("arn"), sfx_metrics)
        return self.merge(metadata, tags)

    def _basic_enrichment(self, logs, context):

        def _get_aws_namespace(log_group):
            log_group_lower = log_group.lower()
            for prefix, source in LOG_GROUP_NAME_PREFIX_TO_NAMESPACE_MAPPING.items():
                if log_group_lower.startswith(prefix):
                    return source
            return "other"

        log_group = logs['logGroup']
        aws_namespace = _get_aws_namespace(log_group)
        common_metadata = self.get_context_metadata(context)
        metadata = {'logGroup': log_group,
                    'logStream': logs['logStream'],
                    'source': aws_namespace,
                    'sourcetype': "aws:" + aws_namespace}
        namespace_metadata = self._enricher_factory(metadata['source'])(context, log_group)

        metadata.update(common_metadata)
        metadata.update(namespace_metadata)
        return metadata

    def _enricher_factory(self, source):
        def lambda_enricher(context, log_group):
            fwd_arn_parts = context.invoked_function_arn.split('function')
            arn_prefix = fwd_arn_parts[0]
            function_name = log_group.split('/')[-1].lower()
            arn = arn_prefix + "function:" + function_name
            return {'host': arn, 'arn': arn, 'functionName': function_name}

        def rds_enricher(context, log_group):
            log_group_parts = log_group.split('/')
            if len(log_group_parts) == 6:
                _, _, _, cluster_or_instance, host, name = log_group_parts
                deployment_type = "db" if cluster_or_instance == "instance" else cluster_or_instance
                region, account_id = self._parse_log_collector_function_arn(context)
                metadata = {'host': host,
                            'arn': f"arn:aws:rds:{region}:{account_id}:{deployment_type}:{host}"}
                if name == 'postgresql':
                    # only for postgresql we can detect dbType
                    metadata['dbType'] = name
                else:
                    metadata['dbLogName'] = name
                return metadata
            else:
                log.warning(f"Cannot parse rds logGroup = {log_group}")
                return default_enricher(context, log_group)

        def eks_enricher(context, log_group):
            log_group_parts = log_group.split("/")
            if len(log_group_parts) == 5:
                region, account_id = self._parse_log_collector_function_arn(context)
                _, _, _, eks_cluster_name, _ = log_group_parts
                arn = f"arn:aws:eks:{region}:{account_id}:cluster/{eks_cluster_name}"
                return {'host': eks_cluster_name, 'arn': arn, 'eksClusterName': eks_cluster_name}
            else:
                log.warning(f"Cannot parse eks logGroup = {log_group}")
                return default_enricher(context, log_group)

        def api_gateway_enricher(context, log_group):
            log_group_parts = log_group.split("/")
            if len(log_group_parts) == 2:
                prefix, stage = log_group_parts
                api_gateway_id = prefix.split("_")[-1]
                region, _ = self._parse_log_collector_function_arn(context)
                arn = f"arn:aws:apigateway:{region}::/restapis/{api_gateway_id}/stages/{stage}"
                return {'arn': arn, 'host': arn, 'apiGatewayStage': stage, 'apiGatewayId': api_gateway_id}
            else:
                log.warning(f"Cannot parse apigateway logGroup = {log_group}")
                return default_enricher(context, log_group)

        def default_enricher(_, log_group):
            return {'host': log_group}

        enrichers = {
            'lambda': lambda_enricher,
            'rds': rds_enricher,
            'eks': eks_enricher,
            'api-gateway': api_gateway_enricher
        }
        return enrichers.get(source, default_enricher)
