#!/bin/bash

while [[ "$1" != "" ]]; do
    case $1 in
        -b | --bucket-name-prefix )       shift
                                          BUCKET_NAME_PREFIX=$1
                                          ;;
        -p | --profile )                  shift
                                          PROFILE=$1
                                          ;;
        * )                               echo "Bucket name and profile are required."
                                          exit 1
    esac
    shift
done

[[ -z "$PROFILE" ]] && { echo "Error: PROFILE not defined."; exit 1; }
[[ -z "$BUCKET_NAME_PREFIX" ]] && { echo "Error: BUCKET_NAME_PREFIX not defined."; exit 1; }

echo "Validating template..."
sam validate --profile ${PROFILE} --template-file template_no_logs.yaml
if [[ $? -ne 0 ]]
  then
    echo "template_no_logs.yaml is not valid. Stopping the execution."
    exit 1
fi

# upload the resulting combined template to global S3
echo "Uploading packaged.yaml to bucket $BUCKET_NAME_PREFIX..."
aws s3api put-object --profile ${PROFILE} --region "us-east-1" --acl public-read --bucket ${BUCKET_NAME_PREFIX} --key aws-collector/packaged_beta.yaml --body template_no_logs.yaml

if [[ $? -ne 0 ]]
  then
    echo "Error encountered when uploading packaged_beta.yaml to a S3 bucket! Stopping the execution."
    exit 1
fi

echo "======================================================================================================"
