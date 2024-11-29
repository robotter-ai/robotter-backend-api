# Robotter Backend API

## Overview
This is the backend API for [Robotter](https://www.robotter.ai), a platform for automated trading on Solana. The API is built on top of [hummingbot/backend-api](https://github.com/hummingbot/backend-api), extending it with specialized features for Solana DeFi trading, performance analytics, and multi-bot management.

Visit [robotter.ai](https://www.robotter.ai) to learn more about the project.

## Features
- **Bot Management**: Create, start, stop, and monitor trading bots
- **Performance Analytics**: Track bot performance, trade history, and statistics
- **Wallet Integration**: Secure Solana wallet management for trading operations
- **Strategy Management**: Configure and deploy trading strategies
- **Market Data**: Access real-time and historical market data via Birdeye
- **Backtesting**: Test strategies against historical data

## System Architecture
The system consists of several interconnected services:
- **Backend API** (this repository): Main API service for bot management
- **EMQX Broker**: Message broker for bot communication
- **Gateway**: Handles blockchain interactions
- **Transaction Service**: Manages Solana transactions

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Solana RPC endpoint
- Birdeye API key

### Required Environment Variables
Create a `.env` file with:
```bash
# Required
SOLANA_RPC_URL=your_rpc_endpoint
BIRDEYE_API_KEY=your_api_key
GATEWAY_CERT_PASSPHRASE=your_passphrase
CONFIG_PASSWORD=your_password
TRANSACTION_SERVICE_RPC_KEY=your_key
TRANSACTION_SERVICE_WEBHOOK_ID=your_id
TRANSACTION_SERVICE_RPC_LANDER=your_lander

# Development
ENABLE_DEBUGGER=true
```

### Development Setup

The backend API runs in Docker with hot reload capabilities for development. The setup uses a development-specific Dockerfile and compose configuration.

#### 1. Development Files

`Dockerfile.dev`:
```dockerfile
FROM continuumio/miniconda3:latest

RUN apt-get update && \
    apt-get install -y sudo libusb-1.0 python3-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /backend-api

# Copy and create conda environment
COPY environment.yml .
RUN conda env create -f environment.yml

# Install development dependencies
COPY requirements-dev.txt .
RUN conda run -n backend-api pip install -r requirements-dev.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p /backend-api/bots/credentials

# Make sure we use the conda environment
SHELL ["conda", "run", "-n", "backend-api", "/bin/bash", "-c"]

# Set environment path
ENV PATH /opt/conda/envs/backend-api/bin:$PATH

# Activate conda environment and run uvicorn with hot reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/backend-api"]
```

`docker-compose.dev.yml`:
```yaml
services:
  backend-api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - .:/backend-api  # Mount the entire project directory
    environment:
      - ENABLE_DEBUGGER=true
      - PYTHONPATH=/backend-api
    ports:
      - "8000:8000"
      - "5678:5678"  # Debug port
```

#### 2. Start Development Environment
```bash
# Start all services with development configuration
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Or to rebuild and restart just the backend API:
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build backend-api
```

This will:
- Start all required services (EMQX, Gateway, Transaction Service)
- Run the backend API with hot reload enabled
- Mount your local code into the container
- Enable debugging capabilities

#### 3. Development Features
- **Hot Reload**: Changes to your code will automatically reload the server
- **Live Logs**: View logs in real-time
- **Debugging**: Full debugging support through VS Code
- **Local Development**: Edit code locally, changes reflect immediately

#### 4. Accessing the API
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Debugging

#### VS Code Debugging
1. Ensure `ENABLE_DEBUGGER=true` in your `.env`
2. Start the services as described above
3. In VS Code:
   - Open "Run and Debug" (Ctrl+Shift+D)
   - Select "FastAPI: Remote Debug"
   - Set breakpoints in your code
   - Start debugging

#### Viewing Logs
```bash
# View backend API logs
docker compose logs -f backend-api

# View all services logs
docker compose logs -f

# View specific services
docker compose logs -f backend-api gateway
```

#### Troubleshooting

1. If changes aren't reloading:
```bash
# Check if the directory is properly mounted
docker compose exec backend-api ls -la /backend-api

# Restart the backend API service
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart backend-api
```

2. If you need to rebuild:
```bash
# Rebuild specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml build backend-api

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build backend-api
```

## API Documentation

### Key Endpoints

#### Bot Management
- `POST /api/v1/bots` - Create a new bot
- `GET /api/v1/bots/{bot_id}/wallet` - Get bot's wallet info
- `POST /api/v1/bots/{bot_id}/start` - Start a bot
- `POST /api/v1/bots/{bot_id}/stop` - Stop a bot

#### Performance Tracking
- `GET /api/v1/bots/{bot_id}/trades` - Get bot's trade history
- `GET /api/v1/bots/{bot_id}/performance` - Get bot's performance stats

Full API documentation is available in the Swagger UI at http://localhost:8000/docs

## Development Guidelines

### Code Structure
```
robotter-backend-api/
├── routers/          # API endpoints
├── services/         # Business logic
├── utils/           # Helper functions
└── tests/           # Test cases
```

### Best Practices
- Write type hints for all functions
- Document complex logic
- Add tests for new features
- Use the debugger for development
- Follow PEP 8 style guidelines

## Contributing
We welcome contributions from the community! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to your branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

For major changes, please open an issue first to discuss what you would like to change.

## License
[Add appropriate license information]

## Acknowledgments
This project builds upon [hummingbot/backend-api](https://github.com/hummingbot/backend-api), extending it with Solana-specific features and performance analytics. We're grateful to the Hummingbot team for their excellent foundation.
