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

REGIONS=$(aws ec2 --profile "${PROFILE}" describe-regions | jq -r '.Regions | map(.RegionName) | join(" ")')
for region in $REGIONS
do
  BUCKET_NAME=${BUCKET_NAME_PREFIX}-$region
  echo "=========== Uploading to S3 bucket ${BUCKET_NAME} in region $region ============="
  ./upload_packaged_to_bucket.sh --bucket-name ${BUCKET_NAME} --profile ${PROFILE} --region $region
  if [[ $? -ne 0 ]]
  then
    echo "Error uploading S3 bucket! Stopping the execution."
    exit 1
  fi

  echo "======================================================================================================"
done