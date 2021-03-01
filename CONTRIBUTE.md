# Testing
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

#### Known issues (prerequisites)
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

#### Running the lambda locally in Docker

```shell script
docker build -t aws-log-collector:latest . \
    --build-arg AWS_DEFAULT_REGION=*** \
    --build-arg AWS_ACCESS_KEY_ID=*** \
    --build-arg AWS_SECRET_ACCESS_KEY=***

docker run -p 9000:8080  aws-log-collector:latest --env SPLUNK_API_KEY=*** --env SPLUNK_LOG_URL=*** --env SPLUNK_METRIC_URL=***
                                                                  
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d "@tests/data/e2e/nlb_event.json"
```

# Releasing
We use CircleCi for build process.
* Every commit to each branch will trigger unit testing and publication of the zip archive in a test version (so it can be easily referenced by CF templates).
* Every commit to main branch will trigger unit testing and publication of the zip archive in a stage version.
* To release a public version, tag a chosen commit with a sem-ver git tag.

#TODO:
check if the second aws inline policy is really needed if we have s3 read only
check if the documented policy is enough
how to make repo public but not OS?
use only one url variable in lambda





