# AWS Lambda Architecture for Reddit ICP Scraper

## Architecture Overview

The application is decomposed into **3 Lambda functions** orchestrated by **Step Functions** to handle Reddit API rate limits, parallel processing, and fault tolerance.

```
EventBridge (Cron) → Step Functions State Machine
                      ├─> Lambda 1: Orchestrator (fan-out)
                      ├─> Lambda 2: ICP Scraper (parallel, per ICP)
                      └─> Lambda 3: Aggregator (fan-in)
```

## Lambda Functions

### 1. **Orchestrator Lambda** (`orchestrator_handler`)
**Purpose**: Load config from S3, fan out ICP processing tasks

**Trigger**: Step Functions
**Timeout**: 30 seconds
**Memory**: 256 MB

**Responsibilities**:
- Fetch config YAML from S3
- Retrieve Reddit credentials from Secrets Manager
- Parse ICPs and create task payloads
- Return list of ICP tasks for parallel execution

**Input**:
```json
{
  "config_bucket": "my-reddit-scraper-config",
  "config_key": "reddit_icp.yaml",
  "output_bucket": "my-reddit-scraper-results"
}
```

**Output**:
```json
{
  "tasks": [
    {
      "icp_name": "Marketing Agencies",
      "icp_config": {...},
      "defaults": {...},
      "credentials": {...},
      "output_bucket": "my-reddit-scraper-results"
    }
  ]
}
```

---

### 2. **ICP Scraper Lambda** (`scraper_handler`)
**Purpose**: Scrape Reddit for a single ICP with rate limiting

**Trigger**: Step Functions (parallel execution)
**Timeout**: 15 minutes
**Memory**: 512 MB
**Reserved Concurrency**: 2-3 (to respect Reddit API limits)

**Responsibilities**:
- Initialize Reddit client with credentials
- Build queries from keyword buckets
- Fetch posts from subreddits (with rate limiting)
- Apply filters and scoring
- Write results to S3 as JSON

**Input**: Single ICP task from Orchestrator

**Output**:
```json
{
  "icp_name": "Marketing Agencies",
  "posts_found": 15,
  "output_key": "results/marketing_agencies_20250120.json",
  "execution_time_seconds": 245
}
```

**Rate Limiting Strategy**:
- Use DynamoDB for distributed rate limiting across concurrent executions
- Track API calls per minute/hour
- Implement exponential backoff on 429 errors
- Reddit allows ~60 requests/minute per OAuth client

---

### 3. **Aggregator Lambda** (`aggregator_handler`)
**Purpose**: Collect results, send notifications

**Trigger**: Step Functions (after all scrapers complete)
**Timeout**: 1 minute
**Memory**: 256 MB

**Responsibilities**:
- Aggregate execution results
- Generate summary report
- Send SNS notification with results
- Update CloudWatch metrics

**Input**: Array of scraper outputs

**Output**:
```json
{
  "total_icps": 3,
  "successful": 3,
  "failed": 0,
  "total_posts": 45,
  "execution_summary": [...]
}
```

---

## Step Functions State Machine

```json
{
  "Comment": "Reddit ICP Scraper Workflow",
  "StartAt": "Orchestrator",
  "States": {
    "Orchestrator": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:reddit-orchestrator",
      "Next": "ParallelScrape"
    },
    "ParallelScrape": {
      "Type": "Map",
      "ItemsPath": "$.tasks",
      "MaxConcurrency": 2,
      "Iterator": {
        "StartAt": "ScrapeSingleICP",
        "States": {
          "ScrapeSingleICP": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:reddit-scraper",
            "Retry": [
              {
                "ErrorEquals": ["RateLimitError"],
                "IntervalSeconds": 60,
                "MaxAttempts": 3,
                "BackoffRate": 2.0
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "ResultPath": "$.error",
                "Next": "ScrapeFailed"
              }
            ],
            "End": true
          },
          "ScrapeFailed": {
            "Type": "Pass",
            "Result": {"status": "failed"},
            "End": true
          }
        }
      },
      "Next": "Aggregator"
    },
    "Aggregator": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:reddit-aggregator",
      "End": true
    }
  }
}
```

---

## AWS Resources

### S3 Buckets
- **Config Bucket**: `reddit-scraper-config/`
  - `reddit_icp.yaml` - Main configuration
- **Results Bucket**: `reddit-scraper-results/`
  - `results/{icp_slug}_{date}.json` - Output files
  - Lifecycle policy: Archive to Glacier after 90 days

### Secrets Manager
- **Secret Name**: `reddit-scraper/credentials`
```json
{
  "client_id": "...",
  "client_secret": "...",
  "user_agent": "reddit_icp_scraper/1.0"
}
```

### DynamoDB Table (Rate Limiting)
- **Table Name**: `reddit-scraper-rate-limits`
- **Partition Key**: `client_id` (String)
- **Sort Key**: `minute_bucket` (String, format: `YYYY-MM-DD-HH-MM`)
- **Attributes**:
  - `request_count` (Number)
  - `ttl` (Number, auto-expire after 1 hour)

### EventBridge Rule
- **Schedule**: `cron(0 9 * * ? *)` - Daily at 9 AM UTC
- **Target**: Step Functions State Machine

### IAM Roles

**Lambda Execution Role** needs:
- `s3:GetObject` on config bucket
- `s3:PutObject` on results bucket
- `secretsmanager:GetSecretValue` for credentials
- `dynamodb:PutItem`, `dynamodb:GetItem`, `dynamodb:UpdateItem` for rate limiting
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- `sns:Publish` for notifications (Aggregator only)

---

## Rate Limiting Implementation

### DynamoDB-based Distributed Rate Limiter

```python
import time
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('reddit-scraper-rate-limits')

def check_rate_limit(client_id: str, max_per_minute: int = 50) -> bool:
    """Check if we can make a request without exceeding rate limit."""
    minute_bucket = datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
    
    try:
        response = table.update_item(
            Key={'client_id': client_id, 'minute_bucket': minute_bucket},
            UpdateExpression='ADD request_count :inc SET ttl = :ttl',
            ExpressionAttributeValues={
                ':inc': 1,
                ':ttl': int(time.time()) + 3600,
                ':max': max_per_minute
            },
            ConditionExpression='attribute_not_exists(request_count) OR request_count < :max',
            ReturnValues='ALL_NEW'
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return False

def wait_for_rate_limit(client_id: str, max_per_minute: int = 50):
    """Block until rate limit allows request."""
    while not check_rate_limit(client_id, max_per_minute):
        time.sleep(1)
```

---

## Deployment

### Using AWS SAM

**template.yaml** (see separate file)

**Deploy commands**:
```bash
# Build
sam build

# Deploy
sam deploy --guided

# Upload config
aws s3 cp config/reddit_icp.yaml s3://reddit-scraper-config/

# Store secrets
aws secretsmanager create-secret \
  --name reddit-scraper/credentials \
  --secret-string '{"client_id":"...","client_secret":"...","user_agent":"..."}'
```

---

## Cost Estimation (Monthly)

**Assumptions**: Daily execution, 3 ICPs, ~5 min per ICP

- **Lambda**: 
  - Orchestrator: 30 invocations × 0.5s × 256MB ≈ $0.00
  - Scraper: 90 invocations × 300s × 512MB ≈ $0.45
  - Aggregator: 30 invocations × 5s × 256MB ≈ $0.00
- **Step Functions**: 30 executions × 4 state transitions ≈ $0.03
- **S3**: ~10 MB/day × 30 days ≈ $0.01
- **DynamoDB**: On-demand, ~5000 writes/month ≈ $0.01
- **Secrets Manager**: 1 secret ≈ $0.40

**Total**: ~$0.90/month

---

## Monitoring & Alerts

### CloudWatch Metrics
- Custom metrics: `PostsScraped`, `ICPProcessingTime`, `RateLimitHits`
- Lambda metrics: Duration, Errors, Throttles

### CloudWatch Alarms
- Scraper Lambda errors > 1 in 5 minutes
- Step Function execution failures
- DynamoDB throttling

### SNS Notifications
- Daily summary email with results
- Error alerts for failed executions

---

## Advantages of This Architecture

1. **Parallel Processing**: Multiple ICPs processed simultaneously (respecting rate limits)
2. **Fault Tolerance**: Step Functions retry logic, isolated failures per ICP
3. **Cost Efficient**: Pay only for execution time, ~$1/month
4. **Scalable**: Add more ICPs without code changes
5. **Maintainable**: Config-driven, easy to update via S3
6. **Observable**: CloudWatch logs/metrics, SNS notifications
7. **Rate Limit Safe**: DynamoDB-based distributed rate limiting

---

## Migration Checklist

- [ ] Create S3 buckets (config, results)
- [ ] Create DynamoDB table for rate limiting
- [ ] Store Reddit credentials in Secrets Manager
- [ ] Deploy Lambda functions via SAM
- [ ] Create Step Functions state machine
- [ ] Set up EventBridge schedule
- [ ] Configure SNS topic for notifications
- [ ] Upload config YAML to S3
- [ ] Test with single ICP
- [ ] Enable CloudWatch alarms
- [ ] Document runbook for operations team
