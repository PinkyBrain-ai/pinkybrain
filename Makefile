# PinkyBrain Makefile
# Quick reference: make help

.PHONY: install uninstall serve test docker-build docker-run \
        docker-stop docker-logs status clean help

# ─── Configuration ───────────────────────────────────────────
PYTHON      ?= python3
PIP         ?= pip3
DOCKER      ?= docker
COMPOSE     ?= docker compose
PROJECT_DIR ?= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
VERSION     ?= $(shell cat $(PROJECT_DIR)/VERSION 2>/dev/null || echo "0.0.0")
IMAGE_NAME  ?= pinkybrain/server
IMAGE_TAG   ?= $(VERSION)

# ─── Install / Uninstall ────────────────────────────────────
install: ## Install PinkyBrain as a system service (requires sudo)
	@sudo bash $(PROJECT_DIR)/deploy/install.sh

uninstall: ## Uninstall PinkyBrain service (use --purge to remove all data)
	@sudo bash $(PROJECT_DIR)/deploy/uninstall.sh

# ─── Run ─────────────────────────────────────────────────────
serve: ## Run PinkyBrain server in foreground (for development)
	@$(PYTHON) -m src.pinkybrain_cli serve --config config/default.json

serve-dev: ## Run with auto-reload (development)
	@$(PYTHON) -m src.pinkybrain_cli serve --config config/default.json --debug

# ─── Test ────────────────────────────────────────────────────
test: ## Run all tests
	@$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing

test-quick: ## Run tests without coverage (faster)
	@$(PYTHON) -m pytest tests/ -v -x

test-integration: ## Run integration tests only
	@$(PYTHON) -m pytest tests/integration/ -v

lint: ## Run linters (black, flake8, mypy)
	@$(PYTHON) -m black --check src/ tests/
	@$(PYTHON) -m flake8 src/ tests/
	@$(PYTHON) -m mypy src/

format: ## Auto-format code with black
	@$(PYTHON) -m black src/ tests/

# ─── Docker ──────────────────────────────────────────────────
docker-build: ## Build Docker image
	@$(DOCKER) build -t $(IMAGE_NAME):$(IMAGE_TAG) \
		-t $(IMAGE_NAME):latest \
		-f $(PROJECT_DIR)/deploy/Dockerfile \
		$(PROJECT_DIR)

docker-run: ## Run with docker compose (production)
	@cd $(PROJECT_DIR)/deploy && $(COMPOSE) up -d

docker-stop: ## Stop docker compose services
	@cd $(PROJECT_DIR)/deploy && $(COMPOSE) down

docker-logs: ## Follow docker compose logs
	@cd $(PROJECT_DIR)/deploy && $(COMPOSE) logs -f

docker-restart: ## Restart docker compose services
	@cd $(PROJECT_DIR)/deploy && $(COMPOSE) restart

docker-status: ## Show docker compose status
	@cd $(PROJECT_DIR)/deploy && $(COMPOSE) ps

# ─── Status ──────────────────────────────────────────────────
status: ## Show PinkyBrain service status
	@systemctl status pinkybrain --no-pager 2>/dev/null || \
		echo "Service not installed. Run: make install"

# ─── Clean ───────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	@rm -rf build/ dist/ *.egg-info .eggs/
	@rm -rf .pytest_cache .mypy_cache .coverage htmlcov/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean."

# ─── Help ────────────────────────────────────────────────────
help: ## Show this help
	@echo "PinkyBrain Makefile — v$(VERSION)"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Environment variables:"
	@echo "  PYTHON      Python binary (default: python3)"
	@echo "  PIP         Pip binary (default: pip3)"
	@echo "  DOCKER      Docker binary (default: docker)"
	@echo "  COMPOSE     Docker compose command (default: docker compose)"
	@echo "  IMAGE_NAME  Docker image name (default: pinkybrain/server)"