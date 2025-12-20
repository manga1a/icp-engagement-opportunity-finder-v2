.PHONY: help install setup run clean profile profile-agency profile-list profile-view

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make setup         - Setup environment (copy .env.example)"
	@echo "  make run           - Run scraper for all ICPs"
	@echo "  make run-agency    - Run scraper for Marketing Agencies only"
	@echo "  make profile       - Run scraper with profiling enabled"
	@echo "  make profile-agency - Profile Marketing Agencies ICP only"
	@echo "  make profile-list  - List all available profile results"
	@echo "  make profile-view  - Analyze the most recent profile"
	@echo "  make clean         - Clean output and cache files"

install:
	pip install -r requirements.txt

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file. Please edit it with your Reddit API credentials."; \
	else \
		echo ".env file already exists."; \
	fi

run:
	python -m src.run --config config/reddit_icp.yaml

run-agency:
	python -m src.run --config config/reddit_icp.yaml --icp "Marketing Agencies"

run-ecommerce:
	python -m src.run --config config/reddit_icp.yaml --icp "E-commerce SMBs"

run-courses:
	python -m src.run --config config/reddit_icp.yaml --icp "Course Creators / Educators"

profile:
	python -m src.run --config config/reddit_icp.yaml --profile

profile-agency:
	python -m src.run --config config/reddit_icp.yaml --icp "Marketing Agencies" --profile

profile-list:
	@python scripts/analyze_profile.py list

profile-view:
	@latest=$$(ls -t profile_stats/*.prof 2>/dev/null | head -n1); \
	if [ -z "$$latest" ]; then \
		echo "No profile files found. Run 'make profile' first."; \
	else \
		python scripts/analyze_profile.py analyze "$$latest"; \
	fi

clean:
	rm -rf out/*.json
	rm -rf profile_stats/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
