import json

from aws_lambda_context import LambdaContext

AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "134183635603"
FORWARDER_FUNCTION_ARN_PREFIX = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:"
FORWARDER_FUNCTION_NAME = "splunk_aws_log_forwarder"
FORWARDER_FUNCTION_VERSION = "1.0.1"


def read_json_file(file_name):
    with open(file_name, 'r') as file:
        return json.loads(file.read())


def read_text_file(file_name):
    with open(file_name, 'r') as file:
        return file.read().strip().split("\n")


def lambda_context():
    context = LambdaContext()
    context.function_name = FORWARDER_FUNCTION_NAME
    context.function_version = FORWARDER_FUNCTION_VERSION
    context.invoked_function_arn = FORWARDER_FUNCTION_ARN_PREFIX + FORWARDER_FUNCTION_NAME
    return context
