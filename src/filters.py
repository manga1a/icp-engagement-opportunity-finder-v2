"""Hard filters for post quality."""
import re
import logging
from typing import Dict, Any
from praw.models import Submission

logger = logging.getLogger(__name__)


def count_links(text: str) -> int:
    """Count URLs in text."""
    if not text:
        return 0
    # Simple URL pattern
    url_pattern = r'https?://[^\s]+'
    return len(re.findall(url_pattern, text))


def english_heuristic(text: str, ascii_ratio_threshold: float = 0.85) -> bool:
    """
    Simple English check based on ASCII ratio.
    
    Args:
        text: Text to check
        ascii_ratio_threshold: Minimum ratio of ASCII chars
    
    Returns:
        True if likely English
    """
    if not text:
        return False
    
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    ratio = ascii_chars / len(text) if len(text) > 0 else 0
    return ratio >= ascii_ratio_threshold


def passes_hard_filters(
    post: Submission,
    filter_config: Dict[str, Any],
    subreddit_name: str
) -> bool:
    """
    Apply hard filters to a post.
    
    Args:
        post: Reddit submission
        filter_config: Filter configuration dict
        subreddit_name: Name of subreddit (for logging)
    
    Returns:
        True if post passes all filters
    """
    # Self posts only
    if filter_config.get('self_posts_only', True) and not post.is_self:
        logger.debug(f"Filtered {post.id}: not a self post")
        return False
    
    # NSFW
    if filter_config.get('exclude_nsfw', True) and post.over_18:
        logger.debug(f"Filtered {post.id}: NSFW")
        return False
    
    # Crossposts
    if filter_config.get('exclude_crossposts', True) and hasattr(post, 'crosspost_parent'):
        logger.debug(f"Filtered {post.id}: crosspost")
        return False
    
    # Title length
    min_title_chars = filter_config.get('min_title_chars', 10)
    if len(post.title) < min_title_chars:
        logger.debug(f"Filtered {post.id}: title too short ({len(post.title)} chars)")
        return False
    
    # Selftext length
    min_selftext_chars = filter_config.get('min_selftext_chars', 120)
    selftext = post.selftext or ""
    if len(selftext) < min_selftext_chars:
        logger.debug(f"Filtered {post.id}: selftext too short ({len(selftext)} chars)")
        return False
    
    # Flair exclusions
    flair_exclude = filter_config.get('flair_exclude', [])
    if post.link_flair_text and post.link_flair_text in flair_exclude:
        logger.debug(f"Filtered {post.id}: excluded flair '{post.link_flair_text}'")
        return False
    
    # Title regex exclusions
    title_regex_exclude = filter_config.get('title_regex_exclude', '')
    if title_regex_exclude and re.search(title_regex_exclude, post.title):
        logger.debug(f"Filtered {post.id}: title matches exclusion pattern")
        return False
    
    # Link count
    max_links = filter_config.get('max_links_in_body', 2)
    link_count = count_links(selftext)
    if link_count > max_links:
        logger.debug(f"Filtered {post.id}: too many links ({link_count})")
        return False
    
    # English check
    if filter_config.get('english_only', True):
        ascii_threshold = filter_config.get('ascii_ratio_threshold', 0.85)
        combined_text = post.title + " " + selftext
        if not english_heuristic(combined_text, ascii_threshold):
            logger.debug(f"Filtered {post.id}: likely not English")
            return False
    
    return True
