"""Post collection and deduplication logic."""
import logging
from datetime import datetime, timezone, timedelta, UTC
from typing import Dict, Any, List, Set
from praw.models import Submission

from .reddit_client import RedditClient
from .query_builder import build_all_queries_for_icp
from .filters import passes_hard_filters
from .scorer import score_post

logger = logging.getLogger(__name__)


def collect_for_icp(
    client: RedditClient,
    config: Any,
    icp: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Collect and score posts for a single ICP.
    
    Args:
        client: Reddit API client
        config: Configuration object
        icp: ICP configuration dict
    
    Returns:
        List of scored post dicts, sorted by score descending
    """
    api_config = config.get_api_config()
    filter_config = config.get_filter_config()
    scoring_config = config.get_scoring_config()
    selection_config = config.get_selection_config()
    
    icp_name = icp['name']
    logger.info(f"Starting collection for ICP: {icp_name}")
    
    # Track seen post IDs to deduplicate
    seen_ids: Set[str] = set()
    all_posts: List[Submission] = []
    
    # Get subreddits
    subreddits = list(icp.get('subreddit_priors', {}).keys())
    logger.info(f"Target subreddits: {', '.join(subreddits)}")
    
    # Build queries
    query_buckets = build_all_queries_for_icp(icp)
    logger.info(f"Built {len(query_buckets)} query buckets")
    
    # Recency cutoff
    days_back = api_config.get('days_back', 90)
    cutoff_time = datetime.now(UTC) - timedelta(days=days_back)
    cutoff_timestamp = cutoff_time.timestamp()
    
    # Collect from search queries
    for subreddit in subreddits:
        for bucket_info in query_buckets:
            bucket_name = bucket_info['bucket_name']
            queries = bucket_info['queries']
            
            for query in queries:
                results = client.search_subreddit(
                    subreddit,
                    query,
                    limit=api_config.get('per_query_limit', 75),
                    sort=api_config.get('sort', 'new'),
                    time_filter=api_config.get('search_time_filter', 'month')
                )
                
                for post in results:
                    if post.id not in seen_ids and post.created_utc >= cutoff_timestamp:
                        seen_ids.add(post.id)
                        all_posts.append(post)
    
    logger.info(f"Collected {len(all_posts)} posts from search queries")
    
    # Optionally collect from new listings
    # if api_config.get('use_new_listing', True):
    #     new_listing_fetch = api_config.get('new_listing_fetch', 200)
        
    #     for subreddit in subreddits:
    #         results = client.fetch_new(subreddit, limit=new_listing_fetch)
            
    #         for post in results:
    #             # Stop if too old
    #             if post.created_utc < cutoff_timestamp:
    #                 break
                
    #             if post.id not in seen_ids:
    #                 seen_ids.add(post.id)
    #                 all_posts.append(post)
        
    #     logger.info(f"Total posts after new listing: {len(all_posts)}")
    
    # Apply hard filters
    filtered_posts = []
    for post in all_posts:
        if passes_hard_filters(post, filter_config, post.subreddit.display_name):
            filtered_posts.append(post)
    
    logger.info(f"Posts after hard filters: {len(filtered_posts)}")
    
    # Score and rank
    scored_posts = []
    for post in filtered_posts:
        final_score, components = score_post(post, icp, scoring_config, filter_config)
        
        # Apply minimum score threshold
        min_score = selection_config.get('min_final_score', 0.45)
        if final_score >= min_score:
            scored_posts.append({
                'post': post,
                'score': final_score,
                'components': components
            })
    
    logger.info(f"Posts above min score threshold: {len(scored_posts)}")
    
    # Sort by score descending
    scored_posts.sort(key=lambda x: x['score'], reverse=True)
    
    # Take top K
    top_k = selection_config.get('top_k_per_icp', 20)
    top_posts = scored_posts[:top_k]
    
    logger.info(f"Returning top {len(top_posts)} posts for {icp_name}")
    
    return top_posts


def format_post_for_output(scored_post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a scored post for JSON output.
    
    Args:
        scored_post: Dict with 'post', 'score', 'components'
    
    Returns:
        Dict ready for JSON serialization
    """
    post = scored_post['post']
    components = scored_post['components']
    
    # Truncate selftext for excerpt
    selftext = post.selftext or ""
    excerpt_length = 150
    selftext_excerpt = selftext[:excerpt_length]
    if len(selftext) > excerpt_length:
        selftext_excerpt += "..."
    
    return {
        'id': post.id,
        'permalink': post.permalink,
        'url': f"https://www.reddit.com{post.permalink}",
        'title': post.title,
        'author': f"u/{post.author.name}" if post.author else "[deleted]",
        'subreddit': f"r/{post.subreddit.display_name}",
        'created_utc': datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
        'is_self': post.is_self,
        'nsfw': post.over_18,
        'score': post.score,
        'upvote_ratio': post.upvote_ratio,
        'num_comments': post.num_comments,
        'selftext_excerpt': selftext_excerpt,
        'matched': components['matched'],
        'components': {
            'keyword': components['keyword'],
            'recency': components['recency'],
            'engagement': components['engagement'],
            'subreddit_prior': components['subreddit_prior']
        },
        'penalties': components['penalties'],
        'final_score': components['final_score']
    }
