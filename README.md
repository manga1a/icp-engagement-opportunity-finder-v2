# Reddit ICP Discovery Scraper

A Python tool to discover high-signal Reddit threads where your target ICPs (Ideal Customer Profiles) discuss their pain points.

## Features

- **Config-driven**: Define ICPs, subreddits, keywords, and scoring weights in YAML
- **Quality over quantity**: Multi-stage filtering and scoring to surface the most relevant posts
- **Recency-focused**: Prioritizes latest posts with exponential decay
- **JSON output**: Structured data ready for analysis

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
