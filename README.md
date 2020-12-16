# aws-log-collector
Code and deployment scripts for AWS lambda forwarding AWS logs to o11y log ingest

## Overview
* `template.yaml` uses a Serverless "dialect" of CloudFormation. Before it can be used as a CloudFormation template, it needs to be transformed to valid CloudFormation file.
* Lambda code (or .zip) location is defined in `template.yaml` and needs to be uploaded to s3 bucket in order for CloudFormation to be able to reference it. It will happen under the hood when you run scripts below.
 
## I made changes, how do I test e2e?
1. Run
    
    `sam deploy --profile <profile-name> --region <region> --stack-name <your-test-stack> --capabilities CAPABILITY_NAMED_IAM --resolve-s3 --parameter-overrides "SplunkAPIKey=<key> SplunkLogIngestUrl=<ingest-url> SplunkMetricIngestUrl=<ingest-url> IntegrationId=<IntegrationId>"`
    
    For example:
    
    `sam deploy --profile integrations --region eu-central-1 --stack-name test-stack-dec-3 --capabilities CAPABILITY_NAMED_IAM --resolve-s3 --parameter-overrides "SplunkAPIKey=1234 SplunkLogIngestUrl=http://lab-ingest.corp.signalfuse.com:8080/v1/log SplunkMetricIngestUrl=http://lab-ingest.corp.signalfuse.com:8080/v2/datapoint IntegrationId=1234"`
2. Test
3. Delete your CF stack

## Releasing
The script will release to all regions available in the target AWS account (R&D account in case you use commands below)

1. (Optional, needed only if a new region is enabled in the account) 

    Make sure S3 buckets in all regions exist (if bucket exists, the script won't touch it).
   `./ensure_all_buckets_exist.sh --profile rnd --bucket-name-prefix o11y-public`
   
2. Transform the file, upload artifacts (code) and upload resulting `packaged.yaml`

   `./upload_packaged_to_all_buckets.sh --profile rnd --bucket-name-prefix o11y-public`
   
## Quick link to the template.

Quick link, when opened in AWS console, will present you with a form to deploy a template passed as a parameter.

The quick link format is:
`https://<region>.console.aws.amazon.com/cloudformation/home?region=<region>#/stacks/create/review?templateURL=<templateUrl>&param_IntegrationId=<integrationId>&param_SplunkAPIKey=<accessKey>&param_SplunkLogIngestUrl=<logIngestUrl>&param_SplunkMetricIngestUrl=<metricIngestUrl>`

For example, if you wish to check how the published template in eu-central-1 works, login to AWS console where you want to deploy and go to:

`https://eu-central-1.console.aws.amazon.com/cloudformation/home?region=eu-central-1#/stacks/create/review?templateURL=https://o11y-public-eu-central-1.s3.eu-central-1.amazonaws.com/aws-log-collector/packaged.yaml`

(if you don't pass parameter overrides, they will be left empty for you to fill)
