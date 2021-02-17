# aws-log-collector
This project contains AWS Lambda function. Aws-log-collector needs to be deployed by users who wish to send AWS logs to Splunk Observability Suite.
Splunk provides a variety of CloudFormation templates which deploy and configure this function. We strongly recommend using these templates if possible in your environment.

Deployment of this function alone is not enough to send AWS logs to Splunk Observability Suite. You need to configure a matching integration in Observability Backend. 
Please start the process from your Splunk Observability account if you haven't done so. 

Continue to read, if you started the setup of AWS Integration in Splunk Observability and wish to deploy log collector using AWS Console, or a tool other than CloudFormation.

#Production deployment

## AWS GOV and AWS China deployment using CloudFormation

## AWS deployment using CloudFormation without StackSets

## Manual deployment
### Overview
Whatever the tool of choice, you need to complete following steps to deploy and configure this lambda function in a way which guarantees successful submission of logs to Splunk Observability.

You need to complete following steps:
1) Get the .zip archive containing lambda code
2) Create IAM role
3) Create AWS Lambda function using the archive and the role
3) Set environment variables
4) Tag the lambda
5) Wait (up to ~15 minutes)

### Getting the .zip archive
Option 1) Download zip archive from TODO_LINK_HERE
Option 2) Build lambda from source

### Creating IAM role
Required policy:
```shell script

```

### Creating AWS Lambda

### Setting environment variables

### Tag the lambda

#Maintainers info

### Unit Testing
`make tests`

### E2E Testing: deploy using AWS SAM
* Build `.zip` archive containing your changes with `make local-zip`
* Run 
```
TEST_STACK_NAME=$(whoami)-$(ts -n)-test-stack    
sam deploy --profile integrations --region eu-central-1 --stack-name $TEST_STACK_NAME --capabilities CAPABILITY_NAMED_IAM --resolve-s3 --template-file template_build.yaml
```
* Setup environment variables
* Cleanup 
```
aws cloudformation --profile integrations --region eu-central-1 delete-stack --stack-name $TEST_STACK_NAME
```

### E2E Testing: running locally using Docker
Lambdas can now be run as Docker containers.

### Known issues
The context event passed from lambda runtime emulator to lambda handler does not contain a valid function arn. Aws-log-collector lambda fails, because it is unable to extract a valid account id from it.
The known workaround for purpose of local testing is to modify `base_enricher.py` file:
* add an import:
```python
from tests.utils import lambda_context
```
* replace `get_context_metadata(self, context)` implementation with the following:
```
    def get_context_metadata(self, __):
        context = lambda_context()
        region, aws_account_id = self._parse_log_collector_function_arn(context)
        return {
            "logForwarder": self._get_log_forwarder(context),
            "region": region,
            "awsAccountId": aws_account_id
        }
```
The limitation is also the only reason why Dockerfile contains the `tests` module which would be otherwise not needed.

### Running the lambda locally in Docker

```shell script
docker build -t aws-log-collector:latest . \
    --build-arg AWS_DEFAULT_REGION=*** \
    --build-arg AWS_ACCESS_KEY_ID=*** \
    --build-arg AWS_SECRET_ACCESS_KEY=***

docker run -p 9000:8080  aws-log-collector:latest --env SPLUNK_API_KEY=*** --env SPLUNK_LOG_URL=*** --env SPLUNK_METRIC_URL=***
                                                                  
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d "@tests/data/e2e/nlb_event.json"
```


