# =============================================================================
# InfraProbe - Dev Remote State Backend
# =============================================================================
# Uncomment the block below to use S3 remote state storage.
#
# Prerequisites:
#   1. Create the S3 bucket:
#      aws s3api create-bucket \
#        --bucket infraprobe-terraform-state-dev \
#        --region eu-west-1 \
#        --create-bucket-configuration LocationConstraint=eu-west-1
#
#   2. Enable versioning:
#      aws s3api put-bucket-versioning \
#        --bucket infraprobe-terraform-state-dev \
#        --versioning-configuration Status=Enabled
#
#   3. Enable encryption:
#      aws s3api put-bucket-encryption \
#        --bucket infraprobe-terraform-state-dev \
#        --server-side-encryption-configuration \
#          '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"}}]}'
#
#   4. Create the DynamoDB table for state locking:
#      aws dynamodb create-table \
#        --table-name infraprobe-terraform-locks-dev \
#        --attribute-definitions AttributeName=LockID,AttributeType=S \
#        --key-schema AttributeName=LockID,KeyType=HASH \
#        --billing-mode PAY_PER_REQUEST \
#        --region eu-west-1
#
#   5. Block public access on the bucket:
#      aws s3api put-public-access-block \
#        --bucket infraprobe-terraform-state-dev \
#        --public-access-block-configuration \
#          BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
#
# Then uncomment the backend block and run: terraform init -migrate-state
# =============================================================================

# terraform {
#   backend "s3" {
#     bucket         = "infraprobe-terraform-state-dev"
#     key            = "dev/terraform.tfstate"
#     region         = "eu-west-1"
#     encrypt        = true
#     dynamodb_table = "infraprobe-terraform-locks-dev"
#   }
# }
