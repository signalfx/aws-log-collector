# aws-log-collector
This project contains AWS Lambda function. Aws-log-collector needs to be deployed by users who wish to send AWS logs to Splunk Observability Suite in each region they wish to monitor.
Splunk provides a variety of CloudFormation templates which deploy and configure this function. We strongly recommend using these templates if possible in your environment.

Deployment of this function alone is not enough to send AWS logs to Splunk Observability Suite. You need to configure a matching integration in Observability Backend. 
Please start the process from your Splunk Observability account if you haven't done so. 

Continue to read, if you started the setup of AWS Integration in Splunk Observability but can't or don't want to use the default deployment process to which you were directed.

# Production deployment

## Deployment using AWS CloudFormation (recommended)
If you are looking to deploy aws-log-collector with AWS CloudFormation, but not in the recommended setup, please examine alternatives in [this doc](https://github.com/signalfx/aws-cloudformation-templates/blob/main/README.md).

## Deployment using AWS Console & other tools
### Overview
You should follow this section if you are looking to deploy aws-log-collector using AWS Console or to automate the deployment with a tool other than CloudFormation

You need to complete following steps:
##### 1) Get the .zip archive containing lambda code
###### AWS Standard regions

In AWS Standard regions, Splunk hosts the latest version of zip archive. You can directly reference the archive in S3 in your region, or [download it](https://o11y-public-us-east-1.s3.amazonaws.com/aws-log-collector/aws-log-collector.release.zip) and use a local copy.

For S3, in us-east-1, use the following url: https://o11y-public-us-east-1.s3.amazonaws.com/aws-log-collector/aws-log-collector.release.zip

In other standard regions, use an url in the format of `https://o11y-public-REPLACEWITHREGION.s3.REPLACEWITHREGION.amazonaws.com/aws-log-collector/aws-log-collector.release.zip`
, for example:
https://o11y-public-af-south-1.s3.af-south-1.amazonaws.com/aws-log-collector/aws-log-collector.release.zip

All regions host the same version of the archive.

###### AWS China and Gov
Splunk doesn't host the archive in China or Gov. Please [download the archive](https://o11y-public-us-east-1.s3.amazonaws.com/aws-log-collector/aws-log-collector.release.zip) and host a copy yourself.
    
##### 2) Create IAM role

You need an IAM role with following Policies:
* AWS managed policy `AmazonS3ReadOnlyAccess`
* AWS managed policy `AWSLambdaBasicExecutionRole`
* Inline policy which makes it possible for the lambda to be triggered by creation of  S3 objects (log entries)
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
CloudWatch logs and S3 must be able to trigger aws-log-collector. You can add resource based permissions to the lambda you have just created with `aws cli`

```
aws lambda add-permission --function-name my-function --action lambda:InvokeFunction --statement-id s3 \
--principal s3.amazonaws.com --output text
```

```
aws lambda add-permission --function-name my-function --action lambda:InvokeFunction --statement-id sns \
--principal sns.amazonaws.com --output text
```

##### 4) Set environment variables
These 3 variables are required:
* `SPLUNK_API_KEY` set to the Access Token from your Splunk Observability organization
* `SPLUNK_LOG_URL` set to your Splunk Observability ingest url with an additional suffix `/v1/log`. You can find ingest url in `Profile --> Account Settings --> Endpoints --> Real-time Data Ingest`.
 For example, if your ingest url is `https://ingest.us0.signalfx.com` then the variable should be set to `https://ingest.us0.signalfx.com/v1/log`	.
* `SPLUNK_METRIC_URL` set to Real-time Data Ingest url from your account. That is the same endpoint as above, but without the suffix. In our example, the value would be `https://ingest.us0.signalfx.com`. Splunk uses this to monitor the usage and adoption of aws-collector-lambda.

##### 5) Tag the lambda
Tag the lambda function you've created with a tag consisting of a key `splunk-log-collector-id` and value containing region code, for example `splunk-log-collector-id:af-south-1`.

##### 6) Wait (up to ~15 minutes)
The tag which you have just added is used by Splunk Observability backend to discover your lambda function. Once it is discovered, the backend will start managing lambda triggers.

