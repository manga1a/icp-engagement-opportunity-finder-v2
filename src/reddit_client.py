"""Reddit API client wrapper."""
import os
import time
import logging
from typing import List, Iterator, Optional
import praw
from praw.models import Submission, Subreddit

logger = logging.getLogger(__name__)


class RedditClient:
    """Read-only Reddit API client."""
    
    def __init__(self):
        """Initialize PRAW client with credentials from environment."""
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        user_agent = os.getenv('REDDIT_USER_AGENT', 'reddit_icp_scraper/1.0')
        
        if not client_id or not client_secret:
            raise ValueError(
                "Missing Reddit credentials. Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET environment variables."
            )
        
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.reddit.read_only = True
        self.rate_limit_qps = int(os.getenv('RATE_LIMIT_QPS', '10'))
        self.min_delay = 1.0 / self.rate_limit_qps if self.rate_limit_qps > 0 else 0.5
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Simple rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()
    
    def search_subreddit(
        self,
        subreddit_name: str,
        query: str,
        limit: int = 100,
        sort: str = 'new',
        time_filter: str = 'month'
    ) -> List[Submission]:
        """
        Search a subreddit with a query.
        
        Args:
            subreddit_name: Name of subreddit (with or without r/)
            query: Lucene search query
            limit: Max results to fetch
            sort: Sort order (relevance, hot, top, new, comments)
            time_filter: Time filter (hour, day, week, month, year, all)
        
        Returns:
            List of submissions
        """
        self._rate_limit()
        
        # Clean subreddit name
        sr_name = subreddit_name.replace('r/', '')
        
        try:
            subreddit = self.reddit.subreddit(sr_name)
            results = list(subreddit.search(
                query,
                sort=sort,
                time_filter=time_filter,
                limit=limit
            ))
            logger.info(f"Search r/{sr_name}: '{query[:50]}...' -> {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"Search failed for r/{sr_name}: {e}")
            return []
    
    def fetch_new(
        self,
        subreddit_name: str,
        limit: int = 200
    ) -> List[Submission]:
        """
        Fetch newest posts from a subreddit.
        
        Args:
            subreddit_name: Name of subreddit (with or without r/)
            limit: Max results to fetch
        
        Returns:
            List of submissions
        """
        self._rate_limit()
        
        sr_name = subreddit_name.replace('r/', '')
        
        try:
            subreddit = self.reddit.subreddit(sr_name)
            results = list(subreddit.new(limit=limit))
            logger.info(f"Fetch new from r/{sr_name}: {len(results)} posts")
            return results
        except Exception as e:
            logger.warning(f"Fetch new failed for r/{sr_name}: {e}")
            return []
    
    def get_subreddit(self, subreddit_name: str) -> Optional[Subreddit]:
        """Get subreddit object."""
        sr_name = subreddit_name.replace('r/', '')
        try:
            return self.reddit.subreddit(sr_name)
        except Exception as e:
            logger.warning(f"Could not access r/{sr_name}: {e}")
            return None
