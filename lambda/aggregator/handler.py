import json
import os
import boto3
from datetime import datetime

sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    results = event  # Array of scraper outputs
    
    total_icps = len(results)
    successful = sum(1 for r in results if 'posts_found' in r)
    failed = total_icps - successful
    total_posts = sum(r.get('posts_found', 0) for r in results)
    
    # Publish CloudWatch metrics
    cloudwatch.put_metric_data(
        Namespace='RedditScraper',
        MetricData=[
            {
                'MetricName': 'PostsScraped',
                'Value': total_posts,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'ICPsProcessed',
                'Value': successful,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            }
        ]
    )
    
    # Build summary message
    summary_lines = [
        "Reddit ICP Scraper - Daily Summary",
        "=" * 50,
        f"Total ICPs: {total_icps}",
        f"Successful: {successful}",
        f"Failed: {failed}",
        f"Total Posts Found: {total_posts}",
        "",
        "Details:"
    ]
    
    for result in results:
        if 'posts_found' in result:
            summary_lines.append(
                f"  - {result['icp_name']}: {result['posts_found']} posts "
                f"({result['execution_time_seconds']}s)"
            )
        else:
            summary_lines.append(f"  - {result.get('icp_name', 'Unknown')}: FAILED")
    
    message = "\n".join(summary_lines)
    
    # Send SNS notification
    sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if sns_topic_arn:
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject='Reddit Scraper Daily Summary',
            Message=message
        )
    
    return {
        'total_icps': total_icps,
        'successful': successful,
        'failed': failed,
        'total_posts': total_posts,
        'execution_summary': results
    }
