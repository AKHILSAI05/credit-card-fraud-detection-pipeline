# Run only after setting the real bucket name and confirming AWS CLI authentication.
# S3 prefixes are virtual; these empty markers make the expected project structure visible in the AWS console.

$BucketName = 'fraud-detection-<team-name>-<aws-account-id>-<region>'

$Prefixes = @(
    'landing/',
    'archive/',
    'rejects/bronze/',
    'rejects/silver/',
    'checkpoints/bronze/',
    'exports/silver/',
    'logs/'
)

foreach ($Prefix in $Prefixes) {
    aws s3api put-object --bucket $BucketName --key $Prefix
}

# Upload the Kaggle source file after download:
# aws s3 cp .\data\creditcard.csv "s3://$BucketName/landing/creditcard.csv"
