"""Main CLI runner."""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

from .config_loader import load_config
from .reddit_client import RedditClient
from .collector import collect_for_icp, format_post_for_output


def setup_logging(level: str = 'INFO'):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def slugify(text: str) -> str:
    """Convert text to filename-safe slug."""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text.strip('_')


def write_json_output(
    icp_name: str,
    posts: list,
    config: any,
    query_meta: dict,
    outdir: Path
):
    """Write JSON output file."""
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    slug = slugify(icp_name)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d')
    filename = f"{slug}_{timestamp}.json"
    filepath = outdir / filename
    
    # Build output structure
    output = {
        'icp': icp_name,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'config_version': config.version,
        'config_hash': config.get_hash(),
        'query_meta': query_meta,
        'posts': [format_post_for_output(p) for p in posts]
    }
    
    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    logging.info(f"Wrote {len(posts)} posts to {filepath}")
    return filepath


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Discover high-signal Reddit threads for target ICPs'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/reddit_icp.yaml',
        help='Path to YAML config file'
    )
    parser.add_argument(
        '--icp',
        type=str,
        help='Specific ICP to process (processes all if not specified)'
    )
    parser.add_argument(
        '--outdir',
        type=str,
        default='out',
        help='Output directory for JSON files'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        help='Override top_k_per_icp from config'
    )
    parser.add_argument(
        '--since-days',
        type=int,
        help='Override days_back from config'
    )
    parser.add_argument(
        '--time-filter',
        type=str,
        choices=['hour', 'day', 'week', 'month', 'year', 'all'],
        help='Override search_time_filter from config'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', args.log_level)
    setup_logging(log_level)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Reddit ICP Discovery Scraper")
    
    # Load config
    try:
        config = load_config(args.config)
        logger.info(f"Loaded config from {args.config} (version {config.version})")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    # Apply CLI overrides
    if args.top_k:
        config.defaults['selection']['top_k_per_icp'] = args.top_k
        logger.info(f"Override: top_k_per_icp = {args.top_k}")
    
    if args.since_days:
        config.defaults['api']['days_back'] = args.since_days
        logger.info(f"Override: days_back = {args.since_days}")
    
    if args.time_filter:
        config.defaults['api']['search_time_filter'] = args.time_filter
        logger.info(f"Override: search_time_filter = {args.time_filter}")
    
    # Initialize Reddit client
    try:
        client = RedditClient()
        logger.info("Reddit client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Reddit client: {e}")
        sys.exit(1)
    
    # Get ICPs to process
    try:
        icps = config.get_icps_to_run(args.icp)
        logger.info(f"Processing {len(icps)} ICP(s)")
    except Exception as e:
        logger.error(f"Failed to get ICPs: {e}")
        sys.exit(1)
    
    # Process each ICP
    outdir = Path(args.outdir)
    results = []
    
    for icp in icps:
        icp_name = icp['name']
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing ICP: {icp_name}")
        logger.info(f"{'='*60}")
        
        try:
            # Collect posts
            posts = collect_for_icp(client, config, icp)
            
            if not posts:
                logger.warning(f"No posts found for {icp_name}")
                continue
            
            # Build query metadata
            api_config = config.get_api_config()
            query_meta = {
                'subreddits': list(icp.get('subreddit_priors', {}).keys()),
                'time_filter': api_config.get('search_time_filter', 'month'),
                'days_back': api_config.get('days_back', 90),
                'per_query_limit': api_config.get('per_query_limit', 75),
                'use_new_listing': api_config.get('use_new_listing', True),
                'buckets_executed': [b['name'] for b in icp.get('keyword_buckets', [])]
            }
            
            # Write output
            filepath = write_json_output(icp_name, posts, config, query_meta, outdir)
            results.append({
                'icp': icp_name,
                'posts_found': len(posts),
                'output_file': str(filepath)
            })
            
        except Exception as e:
            logger.error(f"Error processing {icp_name}: {e}", exc_info=True)
            continue
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    
    if results:
        for result in results:
            logger.info(f"{result['icp']}: {result['posts_found']} posts -> {result['output_file']}")
        logger.info(f"\nSuccessfully processed {len(results)} ICP(s)")
    else:
        logger.warning("No results generated")
        sys.exit(1)


if __name__ == '__main__':
    main()
