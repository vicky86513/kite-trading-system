.PHONY: help build up down logs ps restart clean test

help:
	@echo "Trading System Docker Commands"
	@echo "=============================="
	@echo "make build          - Build Docker image"
	@echo "make up              - Start containers"
	@echo "make down            - Stop containers"
	@echo "make logs            - Show container logs"
	@echo "make ps              - Show running containers"
	@echo "make restart         - Restart containers"
	@echo "make clean           - Clean up images & volumes"
	@echo "make shell           - Open shell in container"
	@echo "make test            - Run tests"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f trading-system

logs-web:
	docker-compose logs -f web-server

ps:
	docker-compose ps

restart:
	docker-compose restart trading-system

clean:
	docker-compose down -v
	docker system prune -f

shell:
	docker-compose exec trading-system /bin/bash

test:
	docker-compose run --rm trading-system python -m pytest tests/

build-prod:
	docker build -t trading-system:latest --target production .

run-prod:
	docker run -d \
		--name trading-system \
		--env-file .env \
		-v trading_data:/app/data \
		-v trading_cache:/app/data/cache \
		-p 80:8000 \
		trading-system:latest

stop-prod:
	docker stop trading-system
	docker rm trading-system