"""Scoring and ranking logic for posts."""
import re
import math
import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Tuple
from praw.models import Submission

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    if not text:
        return ""
    # Lowercase and collapse whitespace
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def match_keywords(
    post_text: str,
    phrases: List[str],
    terms: List[str]
) -> Dict[str, List[str]]:
    """
    Match keywords and phrases in text.
    
    Args:
        post_text: Normalized post text (title + selftext)
        phrases: List of exact phrases to match
        terms: List of individual terms to match
    
    Returns:
        Dict with 'phrases' and 'terms' lists of matches
    """
    matched_phrases = []
    matched_terms = []
    
    # Exact phrase matching
    for phrase in phrases:
        if phrase.lower() in post_text:
            matched_phrases.append(phrase)
    
    # Term matching
    for term in terms:
        # Word boundary matching for better precision
        pattern = r'\b' + re.escape(term.lower()) + r'\b'
        if re.search(pattern, post_text):
            matched_terms.append(term)
    
    return {
        'phrases': matched_phrases,
        'terms': matched_terms
    }


def compute_keyword_score(
    matches: Dict[str, List[str]],
    caps: Dict[str, float]
) -> float:
    """
    Compute keyword relevance score.
    
    Args:
        matches: Dict with matched phrases and terms
        caps: Dict with exact_phrase_cap and normalize_divisor
    
    Returns:
        Score in [0, 1]
    """
    score = 0.0
    
    # Exact phrase matches: +1.0 each, capped
    phrase_score = min(len(matches['phrases']) * 1.0, caps.get('exact_phrase_cap', 2.0))
    score += phrase_score
    
    # Term matches: +0.3 each
    term_score = len(matches['terms']) * 0.3
    score += term_score
    
    # Normalize
    divisor = caps.get('normalize_divisor', 3.0)
    normalized = min(1.0, score / divisor)
    
    return normalized


def compute_recency_score(created_utc: float, half_life_days: float) -> float:
    """
    Compute recency score with exponential decay.
    
    Args:
        created_utc: Post creation timestamp (UTC)
        half_life_days: Half-life for exponential decay
    
    Returns:
        Score in [0, 1]
    """
    now = datetime.now(UTC).timestamp()
    age_days = (now - created_utc) / 86400.0  # seconds to days
    
    if age_days < 0:
        age_days = 0
    
    # Exponential decay: exp(-age / half_life)
    score = math.exp(-age_days / half_life_days)
    return score


def sigmoid(x: float) -> float:
    """Sigmoid function."""
    return 1.0 / (1.0 + math.exp(-x))


def compute_engagement_score(
    score: int,
    num_comments: int,
    upvote_ratio: float,
    created_utc: float,
    params: Dict[str, Any]
) -> float:
    """
    Compute engagement score.
    
    Args:
        score: Reddit score (upvotes - downvotes)
        num_comments: Number of comments
        upvote_ratio: Upvote ratio (0-1)
        created_utc: Post creation timestamp
        params: Engagement parameters (a_score, b_comments, c_upvote_ratio, grace_hours)
    
    Returns:
        Score in [0, 1]
    """
    a = params.get('a_score', 0.6)
    b = params.get('b_comments', 0.8)
    c = params.get('c_upvote_ratio', 0.8)
    grace_hours = params.get('new_post_comment_grace_hours', 24)
    
    # Grace period for very new posts
    now = datetime.now(UTC).timestamp()
    age_hours = (now - created_utc) / 3600.0
    
    # Reduce comment weight for very new posts
    b_adjusted = b
    if age_hours < grace_hours and num_comments < 3:
        b_adjusted = b * 0.5
    
    # Compute weighted sum
    x = (
        a * math.log1p(max(0, score)) +
        b_adjusted * math.log1p(num_comments) +
        c * (upvote_ratio - 0.5)
    )
    
    return sigmoid(x)


def compute_penalties(
    post: Submission,
    filter_config: Dict[str, Any],
    penalty_config: Dict[str, float]
) -> Dict[str, float]:
    """
    Compute penalties for low-quality signals.
    
    Returns:
        Dict with penalty names and values
    """
    penalties = {
        'promo_in_title': 0.0,
        'low_effort_body': 0.0,
        'excessive_links': 0.0
    }
    
    # Promo in title
    title_regex_exclude = filter_config.get('title_regex_exclude', '')
    if title_regex_exclude and re.search(title_regex_exclude, post.title):
        penalties['promo_in_title'] = penalty_config.get('promo_in_title', 0.3)
    
    # Low effort body
    min_selftext = filter_config.get('min_selftext_chars', 120)
    selftext_len = len(post.selftext or "")
    if selftext_len < min_selftext:
        penalties['low_effort_body'] = penalty_config.get('low_effort_body', 0.2)
    
    # Excessive links
    max_links = filter_config.get('max_links_in_body', 2)
    from .filters import count_links
    link_count = count_links(post.selftext or "")
    if link_count > max_links:
        penalties['excessive_links'] = penalty_config.get('excessive_links', 0.2)
    
    return penalties


def score_post(
    post: Submission,
    icp: Dict[str, Any],
    scoring_config: Dict[str, Any],
    filter_config: Dict[str, Any]
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute final score for a post.
    
    Args:
        post: Reddit submission
        icp: ICP configuration
        scoring_config: Scoring configuration
        filter_config: Filter configuration
    
    Returns:
        Tuple of (final_score, components_dict)
    """
    # Normalize post text
    post_text = normalize_text(post.title + " " + (post.selftext or ""))
    
    # Collect all keywords from buckets
    all_phrases = []
    all_terms = []
    for bucket in icp.get('keyword_buckets', []):
        all_phrases.extend(bucket.get('include_phrases', []))
        all_terms.extend(bucket.get('include_terms', []))
    
    # Match keywords
    matches = match_keywords(post_text, all_phrases, all_terms)
    
    # Keyword score
    keyword_caps = scoring_config.get('keyword_caps', {})
    keyword_score = compute_keyword_score(matches, keyword_caps)
    
    # Recency score
    half_life = scoring_config.get('recency_half_life_days', 7)
    recency_score = compute_recency_score(post.created_utc, half_life)
    
    # Engagement score
    engagement_params = scoring_config.get('engagement', {})
    engagement_score = compute_engagement_score(
        post.score,
        post.num_comments,
        post.upvote_ratio,
        post.created_utc,
        engagement_params
    )
    
    # Subreddit prior
    subreddit_priors = icp.get('subreddit_priors', {})
    subreddit_key = f"r/{post.subreddit.display_name}"
    subreddit_prior = subreddit_priors.get(subreddit_key, 0.5)
    
    # Penalties
    penalty_config = scoring_config.get('penalties', {})
    penalties = compute_penalties(post, filter_config, penalty_config)
    total_penalty = sum(penalties.values())
    
    # Weighted final score
    weights = scoring_config.get('weights', {})
    final_score = (
        weights.get('keyword', 0.45) * keyword_score +
        weights.get('recency', 0.30) * recency_score +
        weights.get('engagement', 0.20) * engagement_score +
        weights.get('subreddit_prior', 0.05) * subreddit_prior -
        total_penalty
    )
    
    # Clamp to [0, 1]
    final_score = max(0.0, min(1.0, final_score))
    
    components = {
        'keyword': round(keyword_score, 3),
        'recency': round(recency_score, 3),
        'engagement': round(engagement_score, 3),
        'subreddit_prior': round(subreddit_prior, 3),
        'penalties': {k: round(v, 3) for k, v in penalties.items()},
        'matched': matches,
        'final_score': round(final_score, 3)
    }
    
    return final_score, components
