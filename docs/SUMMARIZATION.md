# Summarization Feature Deployment

## Overview

The workflow now includes AI-powered summarization using Amazon Bedrock (Claude Haiku) that sends individual emails per ICP via SNS.

## Workflow Steps

1. **Orchestrator**: Load config, fan out ICP tasks
2. **Scraper** (parallel): Scrape Reddit posts per ICP
3. **Summarizer**: Summarize posts with Bedrock, send emails
4. **Aggregator**: Send final summary notification

## Email Format

Each ICP gets a dedicated email with:
- Post title
- AI-generated summary (2-3 sentences focusing on pain points)
- Engagement metrics (score, comments)
- Original Reddit URL

## Prerequisites

### Enable Bedrock Model Access

```bash
# Request access to Claude 3 Haiku in your AWS region
# Go to: AWS Console > Bedrock > Model access
# Enable: anthropic.claude-3-haiku-20240307-v1:0
```

### Subscribe to SNS Topic

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

## Deployment

```bash
# Build and deploy
sam build
sam deploy

# Test execution
aws stepfunctions start-execution \
  --state-machine-arn YOUR-STATE-MACHINE-ARN \
  --input '{"config_bucket":"...","config_key":"reddit_icp.yaml","output_bucket":"..."}'
```

## Cost Estimate

- **Bedrock Claude Haiku**: ~$0.25 per 1M input tokens, ~$1.25 per 1M output tokens
- **Typical usage**: 20 posts × 3 ICPs × 200 tokens = ~12K tokens/day
- **Monthly cost**: ~$0.15 for Bedrock + existing Lambda costs

## IAM Permissions

The Summarizer Lambda requires:
- `s3:GetObject` on results bucket
- `bedrock:InvokeModel` for Claude Haiku
- `sns:Publish` to notification topic
