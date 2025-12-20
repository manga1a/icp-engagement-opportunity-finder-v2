"""Build Reddit search queries from keyword buckets."""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def build_queries(
    keyword_bucket: Dict[str, Any],
    max_terms_per_query: int = 8
) -> List[str]:
    """
    Build Lucene search queries from a keyword bucket.
    
    Args:
        keyword_bucket: Dict with include_phrases, include_terms, exclude_terms
        max_terms_per_query: Max include items per query to avoid length limits
    
    Returns:
        List of query strings
    """
    include_phrases = keyword_bucket.get('include_phrases', [])
    include_terms = keyword_bucket.get('include_terms', [])
    exclude_terms = keyword_bucket.get('exclude_terms', [])
    
    # Combine phrases and terms
    all_includes = []
    
    # Wrap phrases in quotes
    for phrase in include_phrases:
        all_includes.append(f'"{phrase}"')
    
    # Add individual terms
    all_includes.extend(include_terms)
    
    if not all_includes:
        logger.warning(f"Keyword bucket '{keyword_bucket.get('name', 'unnamed')}' has no include terms")
        return []
    
    # Build exclusion part
    exclusion_part = ""
    if exclude_terms:
        exclusion_part = " NOT (" + " OR ".join(exclude_terms) + ")"
    
    # Chunk includes into multiple queries if needed
    queries = []
    for i in range(0, len(all_includes), max_terms_per_query):
        chunk = all_includes[i:i + max_terms_per_query]
        include_part = " OR ".join(chunk)
        
        # Build full query: self:yes AND (includes) NOT (excludes)
        query = f"self:yes AND ({include_part}){exclusion_part}"
        queries.append(query)
    
    logger.debug(f"Built {len(queries)} queries from bucket '{keyword_bucket.get('name', 'unnamed')}'")
    return queries


def build_all_queries_for_icp(icp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build all queries for an ICP.
    
    Returns:
        List of dicts with 'bucket_name' and 'queries'
    """
    all_queries = []
    
    for bucket in icp.get('keyword_buckets', []):
        queries = build_queries(bucket)
        if queries:
            all_queries.append({
                'bucket_name': bucket.get('name', 'unnamed'),
                'queries': queries
            })
    
    return all_queries
