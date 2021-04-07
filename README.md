# aws-log-collector
This project contains an AWS Lambda function. Aws-log-collector needs to be deployed by users of Splunk Observability Suite in each region where they want to collect AWS logs.
Splunk provides [a variety of CloudFormation templates](https://github.com/signalfx/aws-cloudformation-templates) which deploy and configure this function. We strongly recommend using these templates if possible in your environment.

Deployment of this function alone is not enough to send AWS logs to Splunk Observability Suite. You need to configure a matching integration in Observability Backend. 
Please start the process from your Splunk Observability account if you haven't done so. 

Continue to read, if you started the setup of AWS Integration in Splunk Observability but can't or don't want to use the default deployment process to which you were directed.

# Production deployment

## Deployment using AWS CloudFormation (recommended)
If you are looking to deploy aws-log-collector with AWS CloudFormation, but not in the recommended setup, please examine the alternatives in [this doc](https://github.com/signalfx/aws-cloudformation-templates/blob/main/README.md).

## Deployment using AWS Console & other tools
### Overview
You should follow this section if you are looking to deploy aws-log-collector using AWS Console or to automate the deployment with a tool other than CloudFormation

You need to complete following steps:
##### 1) Get the .zip archive containing lambda code
###### AWS Standard regions

In AWS Standard regions, Splunk hosts the latest version of zip archive. You can directly reference the archive in S3 in your region, or [download it](https://o11y-public-us-east-1.s3.amazonaws.com/aws-log-collector/aws-log-collector.release.zip) and use a local copy.

For S3 links, in us-east-1, use the following url: https://o11y-public-us-east-1.s3.amazonaws.com/aws-log-collector/aws-log-collector.release.zip

In other standard regions, use an url in the format of `https://o11y-public-REPLACEWITHREGION.s3.REPLACEWITHREGION.amazonaws.com/aws-log-collector/aws-log-collector.release.zip`
, for example:
https://o11y-public-af-south-1.s3.af-south-1.amazonaws.com/aws-log-collector/aws-log-collector.release.zip

All regions host the same version of the archive.

###### AWS China and Gov
Splunk doesn't host the archive in China or Gov. Please [download the archive](https://o11y-public-us-east-1.s3.amazonaws.com/aws-log-collector/aws-log-collector.release.zip) and host a copy yourself.
You can use the provided CloudFormation template with the downloaded archive. 
    
##### 2) Create IAM role

You need an IAM role with following Policies:
* AWS managed policy `AmazonS3ReadOnlyAccess`
* AWS managed policy `AWSLambdaBasicExecutionRole`
* Inline policy which makes it possible for the lambda to read logs from S3 buckets.
```
{
    "Statement": [
        {
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "*",
            "Effect": "Allow",
            "Sid": "GetS3LogObjects"
        }
    ]
}
```
* Inline policy which makes it possible for the lambda to enrich log entries with resource tags
```
{
    "Statement": [
        {
            "Action": [
                "tag:GetResources"
            ],
            "Resource": "*",
            "Effect": "Allow",
            "Sid": "AWSGetTagsOfResources"
        }
    ]
}
```


##### 3) Create AWS Lambda function using the archive and the role

##### 4) Grant AWS services permissions to invoke your lambda function 
CloudWatch logs and S3 file creation events must have permissions to trigger aws-log-collector. 
You can add resource based permissions to the lambda you have just created with `aws cli`. Please replace names and numbers in the examples to match your environment.
You can limit these permissions only to resource groups and buckets from which you want to forward logs.

If in doubt, see [Granting function access to AWS services](https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html).

```
aws lambda add-permission \
     --function-name aws-log-collector \
     --action "lambda:InvokeFunction"
     --statement-id s3-account \
     --principal s3.amazonaws.com --source-arn arn:aws:s3:::* \
     --source-account 123456789012
```

```
aws lambda add-permission \
    --function-name aws-log-collector \
    --action "lambda:InvokeFunction" \
    --statement-id log-groups \
    --principal logs.region.amazonaws.com \
    --source-arn arn:aws:logs:region:123456789123:log-group:*:* \
    --source-account 123456789012
```

##### 5) Set environment variables
These 3 variables are required:
* `SPLUNK_API_KEY` set to the Access Token from your Splunk Observability organization
* `SPLUNK_LOG_URL` set to your Splunk Observability ingest url with an additional suffix `/v1/log`. You can find ingest url in `Profile --> Account Settings --> Endpoints --> Real-time Data Ingest`.
 For example, if your ingest url is `https://ingest.us0.signalfx.com` then the variable should be set to `https://ingest.us0.signalfx.com/v1/log`	.
* `SPLUNK_METRIC_URL` set to Real-time Data Ingest url from your account. That is the same endpoint as above, but without the suffix. In our example, the value would be `https://ingest.us0.signalfx.com`. Splunk uses this to monitor the usage and adoption of aws-collector-lambda.

##### 6) Tag the lambda function
Tag the lambda function you've created with a tag consisting of a key `splunk-log-collector-id` and value containing region code, for example `splunk-log-collector-id`: `af-south-1`.

##### 7) Wait (up to ~15 minutes)
The tag which you have just added is used by Splunk Observability backend to discover your lambda function. Once it is discovered, the backend will start managing lambda triggers.

