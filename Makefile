.PHONY: help install setup run clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make setup      - Setup environment (copy .env.example)"
	@echo "  make run        - Run scraper for all ICPs"
	@echo "  make run-agency - Run scraper for Marketing Agencies only"
	@echo "  make clean      - Clean output and cache files"

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

clean:
	rm -rf out/*.json
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
