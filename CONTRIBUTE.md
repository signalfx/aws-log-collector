# Prerequisites

If you want to work with the `aws-log-collector` lambda locally (e.g. run unit tests, extend the code, etc.) run the following command first to install all required dependencies:

```
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Alternatively you may run `make init` if you use the make tool.

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
* Setup environment variables. See required variables [here](./README.md#4-set-environment-variables).
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
    --build-arg AWS_DEFAULT_REGION=${REPLACE_WITH_REGION} \
    --build-arg AWS_ACCESS_KEY_ID=${REPLACE_WITH_KEY_ID} \
    --build-arg AWS_SECRET_ACCESS_KEY=${REPLACE_WITH_KEY}

docker run -p 9000:8080  aws-log-collector:latest --env SPLUNK_API_KEY=${REPLACE_WITH_API_KEY} --env SPLUNK_LOG_URL=${REPLACE_WITH_LOG_INGEST_URL} --env SPLUNK_METRIC_URL=${REPLACE_WITH_INGEST_URL}
                                                                  
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d "@tests/data/e2e/nlb_event.json"
```

# Releasing 

### CircleCI
We use CircleCi for build process.
* Every commit to each branch will trigger unit testing. If you want your commits to automatically publish test version to rnd account in AWS, use a branch name starting with "pipeline". If you push a commit to a branch prefixed with "pipeline", the test artifact will be uploaded to AWS.

* Every commit to the main branch will trigger unit testing and publication of the zip archive in a stage version.

* To release a public version, tag a chosen commit with a sem-ver git tag, for example `1.0.0`.

Adding tag `1.0.0` to commit `9fceb02`:
```
git tag -a 1.0.0 9fceb02
git push origin main --tags
```

Deleting tag `1.0.0` if you made a mistake:
 
```
# delete local tag '1.0.0'
git tag -d 1.0.0
# delete remote tag '1.0.0'
git push origin :refs/tags/1.0.0

# alternative approach
git push --delete origin 1.0.0
git tag -d 1.0.0
```

### Manual Process

After you have successfully tested your changes and CircleCI published new version to the R&D account you just need to make a GitHub release manually.

Go to the https://github.com/signalfx/aws-log-collector/releases and make a new release based on the commit you have just tested.
