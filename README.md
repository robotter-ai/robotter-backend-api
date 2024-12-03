# Robotter Backend API

Backend API for [Robotter](https://www.robotter.ai), a platform for automated trading on Solana. Built on top of [hummingbot/backend-api](https://github.com/hummingbot/backend-api).

## Prerequisites

- Docker and Docker Compose
- Solana RPC endpoint
- Birdeye API key

## Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in:
```bash
# Required external services
SOLANA_RPC_URL=your_rpc_endpoint
BIRDEYE_API_KEY=your_api_key

# Optional for development
ENABLE_DEBUGGER=true
```

3. Start the services:
```bash
# Production
docker compose up --build

# Development (with hot reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

The API will be available at:
- http://localhost:8000
- http://localhost:8000/docs (Swagger UI)

## Development

### Hot Reload
Changes to your code will automatically reload the server. To rebuild just the backend API:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build backend-api
```

### Debugging
1. Set `ENABLE_DEBUGGER=true` in `.env`
2. Start services in development mode
3. Use VS Code's "FastAPI: Remote Debug" configuration

### Testing
Tests run in a Docker container to ensure consistency with the production environment.

```bash
# Run all tests
docker compose -f docker-compose.test.yml up --build

# Run specific test file
docker compose -f docker-compose.test.yml run --rm test pytest tests/integration/test_backtest_workflow.py -v

# Run tests with specific marker
docker compose -f docker-compose.test.yml run --rm test pytest -m "integration" -v

# Run tests and leave container running for debugging
docker compose -f docker-compose.test.yml run --rm test bash
root@container:/backend-api# pytest tests/ -v
```

### Logs
```bash
# All services
docker compose logs -f

# Just backend API
docker compose logs -f backend-api
```

## API Endpoints

### Bot Management
- `POST /api/v1/bots` - Create bot
- `GET /api/v1/bots/{bot_id}/wallet` - Get wallet info
- `POST /api/v1/bots/{bot_id}/start` - Start bot
- `POST /api/v1/bots/{bot_id}/stop` - Stop bot

### Performance Tracking
- `GET /api/v1/bots/{bot_id}/trades` - Trade history
- `GET /api/v1/bots/{bot_id}/performance` - Performance stats

### Strategy Management
- `GET /api/v1/strategies` - List available strategies
- `POST /api/v1/backtest` - Run strategy backtest

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License
[Add license information]
