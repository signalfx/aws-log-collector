#!/bin/bash

while [[ "$1" != "" ]]; do
    case $1 in
        -b | --bucket-name )    shift
                                BUCKET_NAME=$1
                                ;;
        -r | --region )         shift
                                REGION=$1
                                ;;
        -p | --profile )        shift
                                PROFILE=$1
                                ;;
        * )                     echo "Bucket name, region and profile are required."
                                exit 1
    esac
    shift
done

[[ -z "$BUCKET_NAME" ]] && { echo "Error: BUCKET_NAME not defined."; exit 1; }
[[ -z "$REGION" ]] && { echo "Error: REGION not defined."; exit 1; }
[[ -z "$PROFILE" ]] && { echo "Error: PROFILE not defined."; exit 1; }

echo "Checking if the bucket $BUCKET_NAME exists..."
BUCKET_QUERY_RESULT=`aws s3api head-bucket --profile ${PROFILE} --bucket ${BUCKET_NAME}`
if [[ $? -ne 0 ]]
then
  echo "Creating bucket $BUCKET_NAME..."

  if [[ "${REGION}" = "us-east-1" ]] #the condition is needed due to restrictions in aws s3api which handles us-east-1 a bit differently
    then
      #in us-east-1 LocationConstraint is not allowed
      aws s3api create-bucket --profile ${PROFILE} --acl private --region ${REGION} --bucket ${BUCKET_NAME}
    else
      #Outside us-east-1, using LocationConstraint is required by aws s3api
      aws s3api create-bucket --profile ${PROFILE} --acl private --region ${REGION} --create-bucket-configuration LocationConstraint=${REGION} --bucket ${BUCKET_NAME}
  fi

  if [[ $? -ne 0 ]]
    then
      echo "Error encountered when creating a S3 bucket for test deployment! Stopping the execution."
      exit 1
  fi

  echo "Attaching appropriate policy to the bucket..."
  sed "s/<your-bucket-name>/${BUCKET_NAME}/g" serverless-bucket-policy.json > serverless-bucket-policy-replaced.json
  cat serverless-bucket-policy-replaced.json
  aws s3api put-bucket-policy --profile ${PROFILE} --bucket ${BUCKET_NAME} --policy file://serverless-bucket-policy-replaced.json

  if [[ $? -ne 0 ]]
  then
    echo "Error encountered when attaching a policy to S3 bucket! Stopping the execution."
    exit 1
  fi
else
  echo "Bucket exists. Skipping."
fi

