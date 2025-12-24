import json
import os
import time
import boto3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Set
import praw
from praw.models import Submission

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
rate_limit_table = dynamodb.Table(os.environ['RATE_LIMIT_TABLE'])

class RateLimitError(Exception):
    pass

def check_rate_limit(client_id: str, max_per_minute: int = 50) -> bool:
    minute_bucket = datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
    try:
        rate_limit_table.update_item(
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

def wait_for_rate_limit(client_id: str):
    while not check_rate_limit(client_id):
        time.sleep(2)

def search_subreddit(reddit, subreddit_name: str, query: str, limit: int, sort: str, time_filter: str, client_id: str):
    wait_for_rate_limit(client_id)
    sr_name = subreddit_name.replace('r/', '')
    try:
        subreddit = reddit.subreddit(sr_name)
        return list(subreddit.search(query, sort=sort, time_filter=time_filter, limit=limit))
    except Exception as e:
        print(f"Search failed for r/{sr_name}: {e}")
        return []

def passes_filters(post: Submission, filter_config: Dict) -> bool:
    if filter_config.get('self_posts_only', True) and not post.is_self:
        return False
    if filter_config.get('exclude_nsfw', True) and post.over_18:
        return False
    if len(post.title) < filter_config.get('min_title_chars', 10):
        return False
    selftext = post.selftext or ""
    if len(selftext) < filter_config.get('min_selftext_chars', 120):
        return False
    return True

def score_post(post: Submission, icp: Dict, scoring_config: Dict) -> float:
    # Simplified scoring - keyword match + recency
    import math
    post_text = (post.title + " " + (post.selftext or "")).lower()
    
    # Keyword score
    keyword_score = 0.0
    for bucket in icp.get('keyword_buckets', []):
        for phrase in bucket.get('include_phrases', []):
            if phrase.lower() in post_text:
                keyword_score += 1.0
        for term in bucket.get('include_terms', []):
            if term.lower() in post_text:
                keyword_score += 0.3
    keyword_score = min(1.0, keyword_score / 3.0)
    
    # Recency score
    now = datetime.now(timezone.utc).timestamp()
    age_days = (now - post.created_utc) / 86400.0
    recency_score = math.exp(-age_days / 7.0)
    
    # Weighted final
    weights = scoring_config.get('weights', {})
    return (
        weights.get('keyword', 0.45) * keyword_score +
        weights.get('recency', 0.30) * recency_score +
        0.25  # baseline
    )

def lambda_handler(event, context):
    start_time = time.time()
    
    icp_name = event['icp_name']
    icp_config = event['icp_config']
    defaults = event['defaults']
    credentials = event['credentials']
    output_bucket = event['output_bucket']
    
    # Initialize Reddit client
    reddit = praw.Reddit(
        client_id=credentials['client_id'],
        client_secret=credentials['client_secret'],
        user_agent=credentials['user_agent']
    )
    reddit.read_only = True
    
    api_config = defaults.get('api', {})
    filter_config = defaults.get('filters', {})
    scoring_config = defaults.get('scoring', {})
    selection_config = defaults.get('selection', {})
    
    # Collect posts
    seen_ids: Set[str] = set()
    all_posts: List[Submission] = []
    
    subreddits = list(icp_config.get('subreddit_priors', {}).keys())
    days_back = api_config.get('days_back', 90)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
    cutoff_timestamp = cutoff_time.timestamp()
    
    # Build simple queries
    for subreddit in subreddits:
        for bucket in icp_config.get('keyword_buckets', []):
            phrases = bucket.get('include_phrases', [])[:3]  # Limit to avoid long queries
            if not phrases:
                continue
            
            query = f"self:yes AND ({' OR '.join([f'\"{p}\"' for p in phrases])})"
            
            results = search_subreddit(
                reddit, subreddit, query,
                limit=api_config.get('per_query_limit', 75),
                sort=api_config.get('sort', 'new'),
                time_filter=api_config.get('search_time_filter', 'week'),
                client_id=credentials['client_id']
            )
            
            for post in results:
                if post.id not in seen_ids and post.created_utc >= cutoff_timestamp:
                    seen_ids.add(post.id)
                    all_posts.append(post)
    
    # Filter and score
    scored_posts = []
    for post in all_posts:
        if passes_filters(post, filter_config):
            score = score_post(post, icp_config, scoring_config)
            if score >= selection_config.get('min_final_score', 0.45):
                scored_posts.append({
                    'id': post.id,
                    'permalink': f"https://www.reddit.com{post.permalink}",
                    'title': post.title,
                    'author': f"u/{post.author.name}" if post.author else "[deleted]",
                    'subreddit': f"r/{post.subreddit.display_name}",
                    'created_utc': datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
                    'score': post.score,
                    'num_comments': post.num_comments,
                    'final_score': round(score, 3)
                })
    
    # Sort and take top K
    scored_posts.sort(key=lambda x: x['final_score'], reverse=True)
    top_posts = scored_posts[:selection_config.get('top_k_per_icp', 20)]
    
    # Write to S3
    slug = icp_name.lower().replace(' ', '_')
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d')
    output_key = f"results/{slug}_{timestamp}.json"
    
    output_data = {
        'icp': icp_name,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'posts': top_posts
    }
    
    s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=json.dumps(output_data, indent=2),
        ContentType='application/json'
    )
    
    execution_time = time.time() - start_time
    
    return {
        'icp_name': icp_name,
        'posts_found': len(top_posts),
        'output_key': output_key,
        'execution_time_seconds': round(execution_time, 2)
    }
