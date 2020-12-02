# aws-log-collector
Code and deployment scripts for AWS lambda forwarding AWS logs to o11y log ingest

## Overview
* `template.yaml` uses a Serverless "dialect" of CloudFormation. Before it can be used as a CloudFormation template, it needs to be transformed to valid CloudFormation file.
* Lambda code (or .zip) location is defined in `template.yaml` and needs to be uploaded to s3 bucket in order for CloudFormation to be able to reference it. It will happen under the hood when you run scripts below.
 
## Releasing
The script will release to all regions available in the target AWS account (R&D account in case you use commands below)

1. (Optional, needed only if a new region is enabled in the account) 

    Make sure S3 buckets in all regions exist (if bucket exists, the script won't touch it).
   `./ensure_all_buckets_exist.sh --profile rnd --bucket-name-prefix o11y-public`
   
2. Transform the file, upload artifacts (code) and upload resulting `packaged.yaml`

   `./upload_packaged_to_all_buckets.sh --profile rnd --bucket-name-prefix o11y-public`
    
## Quick link to the template.

The quick link format is:
`https://<region>.console.aws.amazon.com/cloudformation/home?region=<region>#/stacks/create/review?templateURL=https://<templateUrl>/packaged.yaml&param_IntegrationId=<integrationId>&param_SplunkAPIKey=<accessKey>&param_SplunkLogIngestUrl=<logIngestUrl>&param_SplunkMetricIngestUrl=<metricIngestUrl>`
