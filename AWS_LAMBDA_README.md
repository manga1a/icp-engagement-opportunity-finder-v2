# AWS Lambda Implementation - Quick Start

This directory contains the AWS Lambda implementation of the Reddit ICP Scraper.

## 📁 Structure

```
├── lambda/
│   ├── orchestrator/       # Fan-out: Load config, create tasks
│   ├── scraper/           # Core: Scrape Reddit per ICP
│   ├── aggregator/        # Fan-in: Collect results, notify
│   └── requirements.txt   # Python dependencies
├── statemachine/
│   └── scraper.asl.json   # Step Functions workflow
├── docs/
│   ├── AWS_LAMBDA_ARCHITECTURE.md    # Detailed architecture
│   ├── DEPLOYMENT_GUIDE.md           # Step-by-step deployment
│   └── ARCHITECTURE_DIAGRAMS.md      # Visual diagrams
└── template.yaml          # AWS SAM template

```

## 🚀 Quick Deploy

```bash
# 1. Install dependencies
pip install aws-sam-cli

# 2. Store Reddit credentials
aws secretsmanager create-secret \
  --name reddit-scraper/credentials \
  --secret-string '{"client_id":"...","client_secret":"...","user_agent":"..."}'

# 3. Build and deploy
sam build
sam deploy --guided

# 4. Upload config
aws s3 cp config/reddit_icp.yaml s3://YOUR-CONFIG-BUCKET/

# 5. Test
aws stepfunctions start-execution \
  --state-machine-arn YOUR-STATE-MACHINE-ARN \
  --input '{"config_bucket":"...","config_key":"reddit_icp.yaml","output_bucket":"..."}'
```

## 🏗️ Architecture

**3 Lambda Functions + Step Functions:**

1. **Orchestrator** (30s, 256MB): Load config from S3, fan out ICP tasks
2. **Scraper** (15min, 512MB): Scrape Reddit per ICP with rate limiting
3. **Aggregator** (60s, 256MB): Collect results, send SNS notification

**Key Features:**
- ✅ Parallel processing (2-3 ICPs concurrently)
- ✅ DynamoDB-based distributed rate limiting
- ✅ Fault tolerance with Step Functions retry logic
- ✅ Config-driven from S3
- ✅ Secrets in AWS Secrets Manager
- ✅ ~$0.90/month cost

## 📊 Rate Limiting

Reddit API allows ~60 requests/minute. Implementation:

- DynamoDB tracks requests per minute bucket
- Atomic increment with conditional check
- Automatic backoff when limit reached
- Reserved concurrency (2-3) prevents overload

## 📈 Monitoring

- **CloudWatch Logs**: All Lambda execution logs
- **CloudWatch Metrics**: Custom metrics (PostsScraped, ICPProcessingTime)
- **CloudWatch Alarms**: Error alerts, execution failures
- **SNS Notifications**: Daily summary emails

## 📖 Documentation

- [**AWS_LAMBDA_ARCHITECTURE.md**](docs/AWS_LAMBDA_ARCHITECTURE.md) - Complete architecture details
- [**DEPLOYMENT_GUIDE.md**](docs/DEPLOYMENT_GUIDE.md) - Step-by-step deployment
- [**ARCHITECTURE_DIAGRAMS.md**](docs/ARCHITECTURE_DIAGRAMS.md) - Visual diagrams

## 💰 Cost Estimate

Monthly cost for daily execution (3 ICPs):

| Service | Cost |
|---------|------|
| Lambda (Orchestrator) | $0.00 |
| Lambda (Scraper) | $0.45 |
| Lambda (Aggregator) | $0.00 |
| Step Functions | $0.03 |
| S3 | $0.01 |
| DynamoDB | $0.01 |
| Secrets Manager | $0.40 |
| **Total** | **~$0.90** |

## 🔧 Configuration

All configuration remains in `config/reddit_icp.yaml` - just upload to S3:

```yaml
icps:
  - name: "Marketing Agencies"
    subreddit_priors:
      r/marketingagency: 1.0
    keyword_buckets:
      - name: "client_reporting"
        include_phrases: ["client report", "dashboard"]
```

## 🛠️ Troubleshooting

**Lambda timeout?**
- Reduce `per_query_limit` in config
- Increase timeout in template.yaml

**Rate limit errors?**
- Check DynamoDB table
- Reduce `MaxConcurrency` in Step Functions

**No posts found?**
- Check CloudWatch logs
- Verify Reddit credentials
- Adjust `min_final_score` threshold

## 🔐 Security

- ✅ Credentials in Secrets Manager (never in code)
- ✅ Least-privilege IAM roles
- ✅ S3 bucket encryption
- ✅ VPC support (optional)
- ✅ CloudTrail audit logging

## 📝 Next Steps

1. Review [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)
2. Customize `template.yaml` for your needs
3. Deploy with `sam deploy --guided`
4. Monitor in CloudWatch console
5. Subscribe to SNS topic for notifications

## 🤝 Migration from Local

The Lambda implementation maintains the same:
- Configuration format (YAML)
- Filtering logic
- Scoring algorithm
- Output format (JSON)

Only differences:
- Config from S3 (not local file)
- Secrets from Secrets Manager (not .env)
- Distributed rate limiting (DynamoDB)
- Parallel execution (Step Functions)
