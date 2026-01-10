# Reddit ICP Discovery Scraper

A Python tool to discover high-signal Reddit threads where your target ICPs (Ideal Customer Profiles) discuss their pain points.

## Features

- **Config-driven**: Define ICPs, subreddits, keywords, and scoring weights in YAML
- **Quality over quantity**: Multi-stage filtering and scoring to surface the most relevant posts
- **Recency-focused**: Prioritizes latest posts with exponential decay
- **JSON output**: Structured data ready for analysis

## Deployment Options

**Local Execution** (this guide): Full-featured implementation with advanced filtering, scoring, and profiling. Best for development and detailed analysis.

**AWS Lambda** ([docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)): Serverless deployment with parallel processing, distributed rate limiting, and AI-powered summarization via Bedrock. Optimized for cost (~$1.05/month).

## Setup

1. **Install dependencies**:
   ```bash
   make install
   ```

2. **Get Reddit API credentials**:
   - Go to https://www.reddit.com/prefs/apps
   - Click "create another app..."
   - Choose "script" type
   - Copy your client ID and secret

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the scraper**:
   ```bash
   # Scrape all ICPs
   make run

   # Scrape specific ICP
   make run-agency|run-ecommerce|run-courses
   
   # Clean output
   make clean

   # Override settings
   python -m src.run --config config/reddit_icp.yaml --top-k 30 --since-days 30
   ```

## Output

Results are saved to `out/{icp_slug}_{YYYYMMDD}.json` with:
- Post metadata (title, author, subreddit, timestamps)
- Engagement metrics (score, comments, upvote ratio)
- Matched keywords and phrases
- Scoring components breakdown
- Final relevance score

## Configuration

Edit `config/reddit_icp.yaml` to:
- Add/modify ICPs and their target subreddits
- Define keyword buckets for each ICP
- Adjust scoring weights and filters
- Set quality thresholds

See the config file for detailed inline documentation.

## Performance Profiling

The scraper includes built-in profiling support to identify performance bottlenecks and optimize execution time.

### Quick Start

```bash
# Run with profiling enabled
make profile

# Profile a specific ICP
make profile-agency

# View the most recent profile results
make profile-view

# List all available profile files
make profile-list
```

### Manual Profiling

```bash
# Profile all ICPs
python -m src.run --config config/reddit_icp.yaml --profile

# Profile specific ICP with custom output directory
python -m src.run --icp "Marketing Agencies" --profile --profile-output my_profiles

# Combine with other options
python -m src.run --profile --top-k 50 --since-days 7
```

### Analyzing Profile Results

Profile results are saved to `profile_stats/` directory with two files:
- `reddit_scraper_YYYYMMDD_HHMMSS.prof` - Binary stats (for detailed analysis)
- `reddit_scraper_YYYYMMDD_HHMMSS.txt` - Human-readable report

**Analyze a specific profile:**
```bash
python scripts/analyze_profile.py analyze profile_stats/reddit_scraper_20251220_143022.prof
```

**Compare two profiles** (e.g., before/after optimization):
```bash
python scripts/analyze_profile.py compare \
  profile_stats/reddit_scraper_20251220_143022.prof \
  profile_stats/reddit_scraper_20251220_150000.prof
```

**List all available profiles:**
```bash
python scripts/analyze_profile.py list
```

### Understanding Profile Output

The profiler shows:
- **Total time**: Overall execution time
- **Function calls**: Number of times each function was called
- **Cumulative time**: Time spent in function + all subfunctions
- **Internal time**: Time spent only in the function itself

**Key areas to examine:**
1. **API calls** (`reddit_client.py`) - Network I/O bottlenecks
2. **Collection** (`collector.py`) - Main processing loop
3. **Filtering** (`filters.py`) - Filter performance
4. **Scoring** (`scorer.py`) - Scoring algorithm efficiency

### Tips for Optimization

- Look for functions with high cumulative time but low call counts (expensive operations)
- Identify functions called many times with moderate per-call time (optimization candidates)
- Check for unexpected function calls or redundant operations
- Compare profiles before/after changes to measure improvement
