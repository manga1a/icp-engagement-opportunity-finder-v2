import json
import os
import boto3

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')
sns = boto3.client('sns')

def summarize_post(title: str, body: str) -> str:
    prompt = f"""Summarize this Reddit post in 2-3 sentences focusing on the pain point or need expressed:

Title: {title}
Body: {body[:1000]}

Summary:"""
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 150,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-haiku-20240307-v1:0',
        body=json.dumps(request_body)
    )
    
    result = json.loads(response['body'].read())
    return result['content'][0]['text'].strip()

def lambda_handler(event, context):
    results = event
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    results_bucket = os.environ['RESULTS_BUCKET']
    
    for result in results:
        if 'posts_found' not in result or result['posts_found'] == 0:
            continue
        
        response = s3.get_object(Bucket=results_bucket, Key=result['output_key'])
        data = json.loads(response['Body'].read())
        
        email_lines = [
            f"Reddit ICP Discovery: {result['icp_name']}",
            "=" * 60,
            f"Found {result['posts_found']} high-signal posts\n"
        ]
        
        for i, post in enumerate(data['posts'], 1):
            body = post.get('selftext', '')
            summary = summarize_post(post['title'], body)
            
            email_lines.extend([
                f"\n{i}. {post['title']}",
                f"   Score: {post['final_score']} | {post['subreddit']} | {post['num_comments']} comments",
                f"   Summary: {summary}",
                f"   URL: {post['permalink']}"
            ])
        
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=f"Reddit ICP Discovery: {result['icp_name']}",
            Message="\n".join(email_lines)
        )
    
    return {'status': 'emails_sent', 'icp_count': len(results)}
