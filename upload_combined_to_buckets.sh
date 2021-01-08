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

echo "Validating templates..."
sam validate --profile ${PROFILE} --template-file template_build.yaml
if [[ $? -ne 0 ]]
  then
    echo "template_build.yaml is not valid. Stopping the execution."
    exit 1
fi

sam validate --profile ${PROFILE} --template-file template_combined.yaml
if [[ $? -ne 0 ]]
  then
    echo "template_combined.yaml is not valid. Stopping the execution."
    exit 1
fi

echo "Building Lambda code..."
sam build --profile ${PROFILE} --template-file template_build.yaml --build-dir .out
if [[ $? -ne 0 ]]
  then
    echo "Python build failed. Stopping the execution."
    exit 1
fi

REGIONS=$(aws ec2 --profile "${PROFILE}" describe-regions | jq -r '.Regions | map(.RegionName) | join(" ")')
for REGION in $REGIONS
do
  BUCKET_NAME=${BUCKET_NAME_PREFIX}-$REGION
  echo "Checking if the bucket $BUCKET_NAME exists..."
  BUCKET_QUERY_RESULT=`aws s3api head-bucket --profile ${PROFILE} --bucket ${BUCKET_NAME}`
  if [[ $? -ne 0 ]]
  then
    echo "Bucket does not exist."
    exit 1
  fi

  echo "Packaging template, uploading code to s3..."
  #sam package creates packaged.yaml and also uploads code to s3. We want the code in s3 anyway so not fighting with it.
  #turns out region parameter is needed when using opt-in regions, due to a bug in s3api (not documented)
  RAW=`sam package --profile ${PROFILE} --region ${REGION} --template-file .out/template.yaml --output-template-file packaged.yaml --s3-prefix aws-log-collector --s3-bucket ${BUCKET_NAME} --force-upload 2>&1 >/dev/null`

  if [[ $? -ne 0 ]]
    then
      echo "packaged.yaml was not prepared. Intermediary artifacts were not uploaded to the bucket. Stopping the execution."
      exit 1
  fi

  #extract the name of the uploaded file
  EXTRACTED=`echo ${RAW} | sed -En 's/(.*)Uploading to aws-log-collector\/([a-zA-Z0-9]*)(.*)/\2/p'`
  echo "File $EXTRACTED with lambda code uploaded."

  echo "Granting public access to $EXTRACTED ..."
  aws s3api put-object-acl --profile ${PROFILE} --region ${REGION} --acl public-read --bucket ${BUCKET_NAME} --key aws-log-collector/${EXTRACTED}
  if [[ $? -ne 0 ]]
    then
      echo "Could not grant public read to the uploaded artifact $EXTRACTED. Stopping the execution."
      exit 1
  fi

  # replace lambda code path with the value extracted when uploading the archives to S3
  sed "s/lambda_archive_name/${EXTRACTED}/g" template_combined.yaml > packaged_combined.yaml

  # upload the resulting combined template to S3
  echo "Uploading packaged_combined.yaml to bucket $BUCKET_NAME..."
  aws s3api put-object --profile ${PROFILE} --region ${REGION} --acl public-read --bucket ${BUCKET_NAME} --key aws-log-collector/packaged_combined.yaml --body packaged_combined.yaml

  if [[ $? -ne 0 ]]
    then
      echo "Error encountered when uploading packaged_combined.yam to a S3 bucket! Stopping the execution."
      exit 1
  fi

done

echo "======================================================================================================"
