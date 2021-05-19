# Copyright 2021 Splunk, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from aws_lambda_context import LambdaContext

AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "134183635603"
FORWARDER_FUNCTION_ARN_PREFIX = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:"
FORWARDER_FUNCTION_NAME = "splunk_aws_log_forwarder"
FORWARDER_FUNCTION_VERSION = "1.0.1"


def get_read_lines_mock(file_name):
    gen = get_raw_line_generator(file_name)

    def read_lines_mock(bucket, key):
        return gen

    return read_lines_mock


def get_raw_line_generator(file_name):
    lines = read_text_file(file_name)
    for line in lines:
        yield line


def read_text_file(file_name):
    with open(file_name, 'r') as file:
        return file.read().strip().split("\n")


def read_json_file(file_name):
    with open(file_name, 'r') as file:
        return json.loads(file.read())


def lambda_context():
    context = LambdaContext()
    context.function_name = FORWARDER_FUNCTION_NAME
    context.function_version = FORWARDER_FUNCTION_VERSION
    context.invoked_function_arn = FORWARDER_FUNCTION_ARN_PREFIX + FORWARDER_FUNCTION_NAME
    return context
