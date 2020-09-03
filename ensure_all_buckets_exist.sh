#!/bin/bash

usage()
{
    echo "usage: ./ensure_all_buckets_exist.sh. Make sure AWS_SECRET_ACCESS_KEY and AWS_ACCESS_KEY_ID variables are set and point to the right account.
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
  echo "Making sure S3 bucket with artifacts exists..."
  ./ensure_bucket_exists.sh --bucket-name ${BUCKET_NAME} --region ${region} --profile ${PROFILE}
  if [[ $? -ne 0 ]]
  then
    echo "Problem preparing S3 bucket! Stopping the execution."
    exit 1
  fi
done