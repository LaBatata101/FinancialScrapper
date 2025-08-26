# Financial AUM Scraping System

A comprehensive web scraping system designed to automatically discover, extract, and normalize Assets Under Management (AUM) data from financial companies' public sources.

## Overview

This system takes a list of financial companies and autonomously:

1. **Discovers** relevant web resources (corporate sites, social media, reports, news)
2. **Scrapes** content from discovered URLs using headless browsers
3. **Extracts** AUM values using AI-powered analysis
4. **Normalizes** financial data into standardized formats
5. **Tracks** token usage and provides reporting capabilities

## Architecture

### Core Components

- **FastAPI Web Server** (`app/main.py`) - RESTful API for system interaction
- **Celery Workers** (`app/workers/`) - Asynchronous task processing
- **Database Layer** (`app/db/`) - PostgreSQL with SQLAlchemy ORM
- **Discovery Service** (`app/services/discovery.py`) - Web search and URL categorization
- **Scraping Service** (`app/services/scraping.py`) - Content extraction using Playwright
- **AI Agent** (`app/workers/agent.py`) - OpenAI GPT-4 powered AUM extraction
- **Budget Manager** (`app/services/budget_manager.py`) - Token usage tracking

### Data Flow

```
CSV Upload → Company Creation → Celery Task → Discovery → Scraping → AI Extraction → Database Storage
```

## Features

- 🔍 **Intelligent Discovery**: Multi-platform search (DuckDuckGo) with categorized results
- 🤖 **AI-Powered Extraction**: GPT-4 analysis for AUM value identification
- 📊 **Data Normalization**: Converts various formats (R$ 2,3 bi → 2,300,000,000)
- 📈 **Usage Tracking**: Complete token consumption monitoring
- 📋 **CSV Export**: Generate reports of extracted AUM data
- 🔄 **Re-processing**: Manually trigger company re-analysis
- 🧪 **Comprehensive Testing**: Unit and integration tests with 90%+ coverage

## Installation

### Prerequisites

- Python 3.13+
- PostgreSQL database
- RabbitMQ message broker
- OpenAI API key
- Playwright browsers

### Setup

1. **Clone the repository**

```bash
git clone <repository-url>
cd financial-aum-scraper
```

2. **Install dependencies**

```bash
pip install -e .
```

3. **Install Playwright browsers**

```bash
playwright install chromium
```

4. **Environment configuration**
   Create a `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/aum_scraper
RABBITMQ_URL=amqp://guest:guest@localhost:5672//
OPENAI_API_KEY=your_openai_api_key_here
```

5. **Database setup**

```bash
# Run migrations
alembic upgrade head
```

6. **Start services**

Terminal 1 - Start the API server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 - Start Celery worker:

```bash
celery -A app.workers.tasks worker --loglevel=info
```

## Usage

### API Endpoints

#### 1. Upload Companies for Processing

```bash
POST /api/v1/scraping/start
```

Upload a CSV file with company names in an "Empresa" column.

**Example:**

```bash
curl -X POST "http://localhost:8000/api/v1/scraping/start" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@companies.csv"
```

**CSV Format:**

```csv
Empresa
XP Investimentos
BTG Pactual
Itaú Asset Management
```

#### 2. Re-process a Company

```bash
POST /api/v1/scraping/re-scrape?company_id=1
# or
POST /api/v1/scraping/re-scrape?company_name="Company Name"
```

#### 3. Export Results to CSV

```bash
GET /api/v1/results/export-csv
```

Downloads a CSV file with all extracted AUM data.

#### 4. Get Daily Token Usage

```bash
GET /api/v1/usage/today
```

Returns detailed breakdown of token consumption for the current day.

### CSV Upload Example

Create a `companies.csv` file:

```csv
Empresa
XP Investimentos
BTG Pactual
Itaú Asset Management
Bradesco Asset Management
Santander Asset Management
```

Then upload:

```bash
curl -X POST "http://localhost:8000/api/v1/scraping/start" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@companies.csv"
```

## How It Works

### 1. Discovery Phase

- Executes targeted searches on DuckDuckGo for each company
- Categorizes discovered URLs into: corporate, social media, reports, news
- Stores search results and company links in database

### 2. Scraping Phase

- Uses Playwright with Chrome in headless mode
- Scrapes content from discovered URLs in priority order:
    1. Reports (highest priority)
    2. Corporate sites
    3. News articles
    4. Social media (LinkedIn, Facebook, Instagram, Twitter)
- Handles dynamic content loading and scrolling
- Logs all scraping attempts with success/failure status

### 3. AI Extraction Phase

- Extracts relevant text chunks containing AUM keywords
- Sends context to OpenAI GPT-4 with specialized prompt
- Parses AI response for AUM values and source URLs
- Normalizes extracted values to standardized numeric format

### 4. Data Storage

- Stores raw AUM values (e.g., "R$ 2,3 bi")
- Converts to standardized numeric values (e.g., 2,300,000,000)
- Tracks extraction source URLs and timestamps
- Logs all token usage for cost monitoring

## Database Schema

### Key Tables

- **companies**: Company information and metadata
- **company_links**: Discovered URLs categorized by platform
- **search_results**: Search query results and titles
- **scrape_logs**: Scraping attempt logs with status
- **aum_snapshots**: Extracted AUM data with normalization
- **usage**: Token consumption tracking

## Configuration

### Environment Variables

| Variable         | Description                  | Example                                       |
| ---------------- | ---------------------------- | --------------------------------------------- |
| `DATABASE_URL`   | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost/db` |
| `RABBITMQ_URL`   | RabbitMQ broker URL          | `amqp://guest:guest@localhost:5672//`         |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4     | `sk-...`                                      |

### Browser Options

The system is configured to use Chromium with specific options for headless scraping:

- User agent rotation
- No sandbox mode for containers
- Optimized memory usage
- Full HD viewport (1920x1080)

## Testing

Run the complete test suite:

```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Docker Deployment

### Quick Start with Docker Compose (Recommended)

The easiest way to run the entire system is using Docker Compose, which sets up all required services automatically.

#### Prerequisites

- Docker and Docker Compose installed
- OpenAI API key

#### Setup Steps

1. **Clone and navigate to project**

```bash
git clone <repository-url>
cd financial-aum-scraper
```

2. **Create environment file**

```bash
# Create .env file with your OpenAI API key
echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
```

3. **Start all services**

```bash
docker-compose up -d
```

This will start:

- **PostgreSQL Database** (port 5432)
- **RabbitMQ Message Broker** (ports 5672, 15672 for management UI)
- **FastAPI Backend** (port 8000)
- **Celery Worker** (background processing)

4. **Initialize database**

```bash
# Run database migrations
docker-compose exec backend alembic upgrade head
```

5. **Verify services**

- API: http://localhost:8000/docs (FastAPI Swagger UI)
- RabbitMQ Management: http://localhost:15672 (guest/guest)
- Database: localhost:5432 (scraper/scraperpw/scraperdb)

#### Docker Compose Services

```yaml
services:
    db: # PostgreSQL database
        image: postgres:15
        ports: ["5432:5432"]

    rabbitmq: # Message broker + management UI
        image: rabbitmq:3-management
        ports: ["5672:5672", "15672:15672"]

    backend: # FastAPI web server
        build: .
        ports: ["8000:8000"]

    celery: # Background worker
        build: .
        command: celery -A app.workers.tasks.celery worker --loglevel=info
```

#### Usage with Docker

Once all services are running, you can use the API exactly as described in the Usage section:

```bash
# Upload companies for processing
curl -X POST "http://localhost:8000/api/v1/scraping/start" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@companies.csv"

# Check daily usage
curl http://localhost:8000/api/v1/usage/today

# Export results
curl -O -J http://localhost:8000/api/v1/results/export-csv
```

#### Docker Management Commands

```bash
# View logs
docker-compose logs backend    # API server logs
docker-compose logs celery     # Worker logs
docker-compose logs -f         # Follow all logs

# Scale workers (for high load)
docker-compose up -d --scale celery=3

# Stop all services
docker-compose down

# Stop and remove volumes (full reset)
docker-compose down -v
```
