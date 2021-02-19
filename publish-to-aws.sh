#!/bin/bash
if [[ -z "$CI" ]]; then # to protect from running the process from localhost by accident
    echo "This script is intended to be run from CI only!" # CI variable is exposed by CircleCI by default.
    echo "If you insist, modify the script and proceed with care." 1>&2
    exit 1
fi

REGIONS="${REGIONS:-$(aws ec2 describe-regions | jq -r '.Regions | map(.RegionName) | join(" ")')}"
for region in $REGIONS
do
  BUCKET_NAME=o11y-public-$region
  aws s3 --region "${region}" cp "${ZIP}" s3://"${BUCKET_NAME}"/aws-log-collector/"${ZIP}"; FILES_COPIED=$?

  if [ "$FILES_COPIED" -eq 0 ]
  then
    echo "$ZIP copied to $BUCKET_NAME."
  else
    echo "Could not upload $ZIP to $BUCKET_NAME" >&2
    exit 1
  fi

  if [[ -v $PUBLIC ]]
  then
    aws s3api put-object-acl --bucket "$BUCKET_NAME" --key aws-log-collector/"${ZIP}" --acl public-read; PUBLIC_ACCESS=$?
    if [ "$PUBLIC_ACCESS" -eq 0 ]
    then
      echo "Public read access granted to $ZIP in $region."
    else
      echo "Could not grant public access to $ZIP in $region" >&2
      exit 1
    fi
  fi
done