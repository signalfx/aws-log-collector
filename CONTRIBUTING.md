# Contributing Guidelines

Thank you for your interest in contributing to our project! Whether it's a bug
report, new feature, question, or additional documentation, we greatly value
feedback and contributions from our community. Read through this document
before submitting any issues or pull requests to ensure we have all the
necessary information to effectively respond to your bug report or
contribution.

In addition to this document, please review our [Code of
Conduct](CODE_OF_CONDUCT.md). For any code of conduct questions or comments
please email oss@splunk.com.

## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest
features. When filing an issue, please check existing open, or recently closed,
issues to make sure somebody else hasn't already reported the issue. Please try
to include as much information as you can. Details like these are incredibly
useful:

- A reproducible test case or series of steps
- The version of our code being used
- Any modifications you've made relevant to the bug
- Anything unusual about your environment or deployment
- Any known workarounds

When filing an issue, please do *NOT* include:

- Internal identifiers such as JIRA tickets
- Any sensitive information related to your environment, users, etc.

## Contributing via Pull Requests

Contributions via Pull Requests (PRs) are much appreciated. Before sending us a
pull request, please ensure that:

1. You are working against the latest source on the `main` branch.
2. You check existing open, and recently merged, pull requests to make sure
   someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your
   time to be wasted.
4. You submit PRs that are easy to review and ideally less 500 lines of code.
   Multiple PRs can be submitted for larger contributions.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please ensure a single change per PR. If you also
   reformat all the code, it will be hard for us to focus on your change.
3. Ensure local tests pass and add new tests related to the contribution.
4. Commit to your fork using clear commit messages.
5. Send us a pull request, answering any default questions in the pull request
   interface.
6. Pay attention to any automated CI failures reported in the pull request, and
   stay involved in the conversation.

GitHub provides additional documentation on [forking a
repository](https://help.github.com/articles/fork-a-repo/) and [creating a pull
request](https://help.github.com/articles/creating-a-pull-request/).

## Finding contributions to work on

Looking at the existing issues is a great way to find something to contribute
on. As our projects, by default, use the default GitHub issue labels
(enhancement/bug/duplicate/help wanted/invalid/question/wontfix), looking at
any 'help wanted' issues is a great place to start.

## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to
confirm the licensing of your contribution.

We may ask you to sign a [Contributor License Agreement
(CLA)](http://en.wikipedia.org/wiki/Contributor_License_Agreement) for larger
changes.

# Local development/testing guidelines

## Prerequisites

If you want to work with the `aws-log-collector` lambda locally (e.g. run unit tests, extend the code, etc.) run the following command first to install all required dependencies:

```
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Alternatively you may run `make init` if you use the make tool.

## Testing
### How to run unit tests
`make tests`

### E2E Testing: deploy using AWS SAM
* Build `.zip` archive containing your changes with `make local-zip`
* Run 
```
TEST_STACK_NAME=$(whoami)-$(ts -n)-test-stack    
sam deploy --profile <your-aws-profile> --region <your-aws-region> --stack-name $TEST_STACK_NAME --capabilities CAPABILITY_NAMED_IAM --resolve-s3 --template-file template_build.yaml
```
* Setup environment variables. See required variables [here](./README.md#4-set-environment-variables).
* Cleanup 
```
aws cloudformation --profile <your-aws-profile> --region <your-aws-region> delete-stack --stack-name $TEST_STACK_NAME
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
