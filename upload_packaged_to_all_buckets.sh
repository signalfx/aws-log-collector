#!/bin/bash

usage()
{
    echo "usage: ./upload_packaged_to_all_buckets.sh.
    --bucket-name-prefix            (required), will be concatenated with region to create a bucket name
    --profile                       (required), will be used to issue aws commands
    "
}


while [ "$1" != "" ]; do
    case $1 in
        -b | --bucket-name-prefix )       shift
                                          BUCKET_NAME_PREFIX=$1
                                          ;;
        -p | --profile )                  shift
                                          PROFILE=$1
                                          ;;
        * )                               usage
                                          exit 1
    esac
    shift
done

[[ -z "$PROFILE" ]] && { echo "Error: PROFILE not defined."; exit 1; }
[[ -z "$BUCKET_NAME_PREFIX" ]] && { echo "Error: BUCKET_NAME_PREFIX not defined."; exit 1; }

for region in us-east-2 us-east-1 #eu-central-1 us-west-1 us-west-2 ap-south-1 ap-northeast-1 ap-northeast-2 ap-southeast-1 ap-southeast-2 ca-central-1 eu-west-1 eu-west-2 eu-west-3 eu-north-1 sa-east-1
do
  BUCKET_NAME=${BUCKET_NAME_PREFIX}-$region
  echo "=========== Uploading to S3 bucket ${BUCKET_NAME} in region $region ============="
  ./upload_packaged_to_bucket.sh --bucket-name ${BUCKET_NAME} --region ${region} --profile ${PROFILE}
  echo "=========================================================================================================================="
  if [[ $? -ne 0 ]]
  then
    echo "Error uploading S3 bucket! Stopping the execution."
    exit 1
  fi
done