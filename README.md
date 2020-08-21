# cloudwatch-log-collector
Code and deployment scripts for AWS lambda forwarding CloudWatch logs to o11y log ingest

# CloudFormation template preparation
1. `template.yaml` uses a Serverless "dialect" of CloudFormation.
 Before it can be used as a CloudFormation template, it needs to be transformed to valid CloudFormation file.
 
2. In order to transform the file:
    1. Make sure you have access to the S3 bucket with appropriate serverless policy. If bucket does not exist, you can create it
    with `ensure_bucket_exists.sh --bucket-name-prefix <yourbucket>`. Make sure to set AWS credentials as environment variables.
    2. Run validation:
    `sam validate --profile <aws_profile> --template-file template.yaml`
    3. Run packaging:
    `sam package --profile <aws_profile> --template-file template.yaml --output-template-file packaged.yaml --s3-bucket <bucket>`.
    This will upload the code of the function to the bucket and create a packaged.yaml file locally.
    
# Creating a quick link to the template.

3. In order to create a quick link to the template, one needs to upload it to s3 bucket and make it publicly accessible. 
The template needs to be uploaded to each region in which we want quick links to work. Make sure to upload `packaged.yaml` file, and not the source `template.yaml`.

4. The quick link format:
`https://<region>.console.aws.amazon.com/cloudformation/home?region=<region>#/stacks/create/review?templateURL=https://<templateUrl>/packaged.yaml&param_IntegrationId=<integrationId>&param_SignalFxAPIKey=<accessKey>&param_SignalFxLogIngestUrl=<ingestUrl>`

