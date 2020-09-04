# aws-log-collector
Code and deployment scripts for AWS lambda forwarding AWS logs to o11y log ingest

## Overview
* `template.yaml` uses a Serverless "dialect" of CloudFormation. Before it can be used as a CloudFormation template, it needs to be transformed to valid CloudFormation file.
* Lambda code (or .zip) location is defined in `template.yaml` and needs to be uploaded to s3 bucket in order for CloudFormation to be able to reference it. It will happen under the hood when you run scripts below.
 
## Releasing
0. Edit the loop in `./create_all_buckets.sh` and `./upload_packaged_to_all_buckets.sh` to loop over all regions you need them to!

1. Make sure S3 buckets in all target regions exist (if bucket exists, the script won't touch it).
   `./create_all_buckets.sh --profile <aws_profile> --bucket-name-prefix <yourbucket>`
   
2. Transform the file, upload artifacts (code) and upload resulting `packaged.yaml` to target AWS account and regions:
   `./upload_packaged_to_all_buckets.sh --profile <aws_profile> --bucket-name-prefix <yourbucket>`
    
## Quick link to the template.

The quick link format is:
`https://<region>.console.aws.amazon.com/cloudformation/home?region=<region>#/stacks/create/review?templateURL=https://<templateUrl>/packaged.yaml&param_IntegrationId=<integrationId>&param_SplunkAPIKey=<accessKey>&param_SplunkLogIngestUrl=<ingestUrl>`

