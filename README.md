# Robotter Backend API

A FastAPI-based backend for the Robotter trading platform.

## Project Structure

```
robotter-backend-api/
├── src/                    # Source code
│   ├── main.py            # Application entry point
│   ├── config/            # Configuration management
│   ├── routers/           # API route handlers
│   ├── services/          # Business logic
│   ├── utils/             # Utility functions
│   ├── bots/              # Trading bot implementations
│   └── solana/            # Solana-specific functionality
├── tests/                 # Test suite
├── certs/                 # SSL certificates
├── .env.example          # Environment variable template
├── pyproject.toml        # Project & dependency configuration
├── Dockerfile            # Production container build
└── docker-compose.yml    # Container orchestration
```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [Poetry](https://python-poetry.org/) for dependency management

### Installation

1. Install Poetry:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/robotter-backend-api.git
   cd robotter-backend-api
   ```

3. Install dependencies:
   ```bash
   poetry install
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Development Workflow

1. Activate the virtual environment:
   ```bash
   poetry shell
   ```

2. Run the development server:
   ```bash
   poetry run uvicorn src.main:app --reload
   ```

3. Run tests:
   ```bash
   poetry run pytest
   ```

4. Format code:
   ```bash
   poetry run black src tests
   poetry run isort src tests
   ```

### Docker Development

Build and run the container:
```bash
docker compose up --build
```

## API Documentation

Once running, visit:
- OpenAPI documentation: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc

## Configuration

The application uses a hierarchical configuration system:

1. Environment variables (highest priority)
2. `.env` file
3. Default values in code

Key configuration options:
- `ENV`: Environment type (development/production/test)
- `DEBUG`: Enable debug mode
- `CORS_ORIGINS`: Allowed CORS origins
- See `.env.example` for all options

## Trading Strategies

Trading strategies are defined in `strategies.json`. Each strategy must include:
- `name`: Strategy identifier
- `parameters`: Configuration parameters
- `risk_level`: Risk level (1-10)
- `version`: Strategy version

Example:
```json
{
  "my_strategy": {
    "name": "my_strategy",
    "parameters": {
      "interval": "1h",
      "threshold": 0.05
    },
    "risk_level": 3,
    "version": "1.0.0"
  }
}
```

## Contributing

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure all tests pass:
   ```bash
   poetry run pytest
   ```

3. Format your code:
   ```bash
   poetry run black src tests
   poetry run isort src tests
   ```

4. Submit a pull request

## License

See [LICENSE](LICENSE) file.
