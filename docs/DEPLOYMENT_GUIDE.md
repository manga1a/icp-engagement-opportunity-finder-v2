# AWS Lambda Deployment Guide

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed (`pip install aws-sam-cli`)
- Reddit API credentials (client_id, client_secret)
- Python 3.11

## Step-by-Step Deployment

### 1. Install Dependencies for Lambda Layers

```bash
# Create layer directory
mkdir -p lambda/layers/python

# Install dependencies
pip install -r lambda/requirements.txt -t lambda/layers/python/

# Copy to each Lambda function
cp -r lambda/layers/python lambda/orchestrator/
cp -r lambda/layers/python lambda/scraper/
cp -r lambda/layers/python lambda/aggregator/
```

### 2. Store Reddit Credentials in Secrets Manager

```bash
aws secretsmanager create-secret \
  --name reddit-scraper/credentials \
  --description "Reddit API credentials for ICP scraper" \
  --secret-string '{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "user_agent": "reddit_icp_scraper/1.0"
  }'
```

### 3. Build SAM Application

```bash
sam build
```

### 4. Deploy to AWS

```bash
# First deployment (guided)
sam deploy --guided

# Follow prompts:
# - Stack Name: reddit-scraper
# - AWS Region: us-east-1 (or your preferred region)
# - Parameter ConfigBucketName: reddit-scraper-config-YOURNAME
# - Parameter ResultsBucketName: reddit-scraper-results-YOURNAME
# - Confirm changes before deploy: Y
# - Allow SAM CLI IAM role creation: Y
# - Save arguments to configuration file: Y

# Subsequent deployments
sam deploy
```

### 5. Upload Configuration to S3

```bash
# Get bucket name from stack outputs
CONFIG_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name reddit-scraper \
  --query 'Stacks[0].Outputs[?OutputKey==`ConfigBucket`].OutputValue' \
  --output text)

# Upload config
aws s3 cp config/reddit_icp.yaml s3://${CONFIG_BUCKET}/reddit_icp.yaml
```

### 6. Subscribe to SNS Notifications

```bash
# Get SNS topic ARN
SNS_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name reddit-scraper \
  --query 'Stacks[0].Outputs[?OutputKey==`NotificationTopicArn`].OutputValue' \
  --output text)

# Subscribe your email
aws sns subscribe \
  --topic-arn ${SNS_TOPIC} \
  --protocol email \
  --notification-endpoint your-email@example.com

# Confirm subscription via email
```

### 7. Test the Workflow

```bash
# Get state machine ARN
STATE_MACHINE=$(aws cloudformation describe-stacks \
  --stack-name reddit-scraper \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# Start execution manually
aws stepfunctions start-execution \
  --state-machine-arn ${STATE_MACHINE} \
  --input '{
    "config_bucket": "reddit-scraper-config-YOURNAME",
    "config_key": "reddit_icp.yaml",
    "output_bucket": "reddit-scraper-results-YOURNAME"
  }'
```

### 8. Monitor Execution

```bash
# View CloudWatch logs
sam logs -n reddit-scraper --stack-name reddit-scraper --tail

# Check Step Functions console
# https://console.aws.amazon.com/states/home

# View results in S3
aws s3 ls s3://${RESULTS_BUCKET}/results/
```

## Updating the Application

### Update Configuration

```bash
# Edit config locally
vim config/reddit_icp.yaml

# Upload to S3
aws s3 cp config/reddit_icp.yaml s3://${CONFIG_BUCKET}/reddit_icp.yaml
```

### Update Lambda Code

```bash
# Make code changes
vim lambda/scraper/handler.py

# Rebuild and deploy
sam build
sam deploy
```

### Update Secrets

```bash
aws secretsmanager update-secret \
  --secret-id reddit-scraper/credentials \
  --secret-string '{
    "client_id": "NEW_CLIENT_ID",
    "client_secret": "NEW_CLIENT_SECRET",
    "user_agent": "reddit_icp_scraper/1.0"
  }'
```

## Troubleshooting

### Lambda Timeout Issues

If scraper Lambda times out:
1. Reduce `per_query_limit` in config
2. Reduce number of keyword buckets
3. Increase Lambda timeout in template.yaml

### Rate Limit Errors

If hitting Reddit rate limits:
1. Check DynamoDB table for request counts
2. Reduce `MaxConcurrency` in Step Functions (template.yaml)
3. Increase delays in scraper code

### No Posts Found

1. Check CloudWatch logs for filter/scoring issues
2. Verify subreddit names in config
3. Adjust `min_final_score` threshold
4. Check Reddit API credentials

### View Logs

```bash
# Orchestrator logs
aws logs tail /aws/lambda/reddit-orchestrator --follow

# Scraper logs
aws logs tail /aws/lambda/reddit-scraper --follow

# Aggregator logs
aws logs tail /aws/lambda/reddit-aggregator --follow
```

## Cleanup

To remove all resources:

```bash
# Delete stack
sam delete --stack-name reddit-scraper

# Delete S3 buckets (must be empty)
aws s3 rm s3://${CONFIG_BUCKET} --recursive
aws s3 rb s3://${CONFIG_BUCKET}
aws s3 rm s3://${RESULTS_BUCKET} --recursive
aws s3 rb s3://${RESULTS_BUCKET}

# Delete secret
aws secretsmanager delete-secret \
  --secret-id reddit-scraper/credentials \
  --force-delete-without-recovery
```

## Cost Optimization

- Use EventBridge schedule to run only when needed
- Set appropriate Lambda memory sizes (current: 256-512 MB)
- Use S3 lifecycle policies to archive old results
- Monitor CloudWatch metrics to optimize execution time
- Consider using Lambda reserved concurrency to control costs

## Security Best Practices

- Never commit credentials to git
- Use least-privilege IAM policies
- Enable S3 bucket encryption
- Enable CloudTrail for audit logging
- Rotate Reddit API credentials periodically
- Use VPC endpoints if running in VPC
