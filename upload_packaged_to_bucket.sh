#!/bin/bash

while [[ "$1" != "" ]]; do
    case $1 in
        -b | --bucket-name )    shift
                                BUCKET_NAME=$1
                                ;;
        -p | --profile )        shift
                                PROFILE=$1
                                ;;
        * )                     echo "Bucket name and profile are required."
                                exit 1
    esac
    shift
done

[[ -z "$BUCKET_NAME" ]] && { echo "Error: BUCKET_NAME not defined."; exit 1; }
[[ -z "$PROFILE" ]] && { echo "Error: PROFILE not defined."; exit 1; }

echo "Checking if the bucket $BUCKET_NAME exists..."
BUCKET_QUERY_RESULT=`aws s3api head-bucket --profile ${PROFILE} --bucket ${BUCKET_NAME}`
if [[ $? -eq 0 ]]
then
  echo "Bucket exists."
  echo "Validating template..."
  sam validate --profile ${PROFILE} --template-file template.yaml
  if [[ $? -ne 0 ]]
    then
      echo "Template.yaml is not valid. Stopping the execution."
      exit 1
  fi

  sam build --profile ${PROFILE} --build-dir .out
  if [[ $? -ne 0 ]]
    then
      echo "Python build failed. Stopping the execution."
      exit 1
  fi

  echo "Packaging template, uploading code to s3..."
  #sam package creates packaged.yaml and also uploads code to s3. We want the code in s3 anyway so not fighting with it.
  RAW=`sam package --profile ${PROFILE} --template-file .out/template.yaml --output-template-file packaged.yaml --s3-prefix aws-log-collector --s3-bucket ${BUCKET_NAME} --force-upload 2>&1 >/dev/null`

  if [[ $? -ne 0 ]]
    then
      echo "packaged.yaml was not prepared. Intermediary artifacts were not uploaded to the bucket. Stopping the execution."
      exit 1
  fi

  #extract the name of the uploaded file
  EXTRACTED=`echo ${RAW} | sed -En 's/(.*)Uploading to aws-log-collector\/([a-zA-Z0-9]*)(.*)/\2/p'`
  echo "File $EXTRACTED with lambda code uploaded."

  echo "Granting public access to $EXTRACTED ..."
  aws s3api put-object-acl --profile ${PROFILE} --acl public-read --bucket ${BUCKET_NAME} --key aws-log-collector/${EXTRACTED}
  if [[ $? -ne 0 ]]
    then
      echo "Could not grant public read to the uploaded artifact $EXTRACTED. Stopping the execution."
      exit 1
  fi

  echo "Uploading packaged.yaml to bucket $BUCKET_NAME..."
  aws s3api put-object --profile ${PROFILE} --acl public-read --bucket ${BUCKET_NAME} --key aws-log-collector/packaged.yaml --body packaged.yaml

  if [[ $? -ne 0 ]]
    then
      echo "Error encountered when uploading packaged.yam to a S3 bucket! Stopping the execution."
      exit 1
  fi
else
  echo "Bucket does not exist."
  exit 1
fi

