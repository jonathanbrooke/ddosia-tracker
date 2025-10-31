# DDoSia Tracker

A distributed monitoring and analytics system that tracks DDoSia attack campaigns by collecting, processing, and visualizing target data from public sources. The system provides geospatial analysis, temporal tracking, and integration with geopolitical event data.

## 🌟 Features

- **Automated Data Collection**: Continuously monitors and downloads DDoSia target lists from public sources
- **Intelligent Processing**: Deduplicates and normalizes target data with country/region mapping
- **Interactive Map**: Interactive map showing attack targets by geographic location and TLD
- **Temporal Analysis**: Track attack patterns over time with historical data
- **GDELT Integration**: Correlates attacks with geopolitical events from GDELT news database
- **Scalable Architecture**: Docker-based microservices with PostgreSQL backend

## 🏗️ Architecture

The system consists of six containerized services:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Downloader  │────▶│  Processor   │────▶│  PostgreSQL │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌────────────────────────────┼──────────────┐
                    │                            │              │
             ┌──────▼──────┐            ┌───────▼──────┐  ┌───▼────┐
             │ Map Service │            │ Map Updater  │  │ GDELT  │
             │  (Web UI)   │            │   Worker     │  │ Worker │
             └─────────────┘            └──────────────┘  └────────┘
```

### Services

1. **Downloader**: Monitors source URL for new JSON files and downloads them
2. **Processor**: Parses JSON files, deduplicates targets, and stores in PostgreSQL
3. **Map Service**: Flask web application providing REST API and interactive map
4. **Map Updater**: Maintains TLD-to-country mappings and enriches target data
5. **GDELT Worker**: Fetches geopolitical events correlated with attack dates
6. **PostgreSQL**: Central database storing targets, events, and metadata

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- 4GB+ RAM recommended
- 2GB+ disk space (includes historical data and database)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/jonathanbrooke/ddosia-tracker.git
   cd ddosia-tracker
   ```

   The repository includes 2+ years of historical DDoSia target data (2000+ JSON files from October 2023 through October 2025).

2. **Configure environment (optional)**
   ```bash
   cp .env.example .env
   # Edit .env to customize settings if needed (all services work with defaults)
   ```

3. **Build and start services**
   ```bash
   docker compose up -d
   ```

   The system will:
   - Process all historical data from `data/processed/`
   - Automatically download new DDoSia target lists as they become available
   - Start the interactive map interface

### Accessing the Application

4. **Access the applications**
   - **Map Interface**: http://localhost:8000
   - **Health Dashboard**: http://localhost:8000/health

## ⚙️ Configuration

All configuration is done through environment variables in the `.env` file. The system works out-of-the-box with default settings. See `.env.example` for all available options.

> **Note**: Since all tracked data is publicly available DDoSia attack information, there's no need to change the default database password unless you have specific security requirements for your deployment environment.

### Key Configuration Options

#### Database Settings
```bash
# Default credentials work fine for local deployments with public data
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ddosia
```

#### Downloader Settings
```bash
BASE_URL=https://www.witha.name/data/          # Source URL to monitor
DOWNLOADER_POLL_INTERVAL=300                   # Check for new files every 5 minutes
DOWNLOAD_DELAY=1.0                             # Delay between downloads (seconds)
```

#### Processor Settings
```bash
PROCESSOR_POLL_INTERVAL=10                     # Check for new files every 10 seconds
```

#### Map Service
```bash
FLASK_ENV=production                           # Flask environment
MAP_SERVICE_PORT=8000                          # External port
GUNICORN_WORKERS=2                             # Number of worker processes
```

#### GDELT Worker
```bash
GDELT_QUERY=Ukraine war                        # Search query for events
GDELT_LANGUAGES=eng                            # Filter by language (eng for English)
GDELT_MAX_EVENTS_PER_DAY=5                     # Max events to store per day
GDELT_REQUEST_DELAY=7                          # Delay between API requests (seconds)
```

## 📊 Usage

### Viewing the Map

Navigate to `http://localhost:8000` to access the interactive map interface:

- Use the date range slider to filter targets by time period
- Click on markers to see target details
- View country-level aggregations and TLD distributions

### Health Monitoring

Access `http://localhost:8000/health` to monitor:
- Database connectivity
- Recent data imports
- TLD mapping coverage
- Data quality metrics
- Service health status

### API Endpoints

The Map Service provides several REST API endpoints:

- `GET /api/tld?from=YYYY-MM-DD&to=YYYY-MM-DD` - TLD aggregated data
- `GET /api/country?from=YYYY-MM-DD&to=YYYY-MM-DD` - Country aggregated data
- `GET /api/domains?from=YYYY-MM-DD&to=YYYY-MM-DD&limit=100` - Top domains
- `GET /api/tld/available-range` - Available date range
- `GET /api/last-update` - Most recent data timestamp
- `GET /api/health/*` - Various health check endpoints

### Database Access

The system uses PostgreSQL with the following main tables:

- **files**: Metadata about downloaded JSON files
- **targets**: DDoSia attack targets with normalized hostnames
- **randoms**: Random data generation parameters from target lists
- **tld_geo**: Top-level domain to country/coordinates mapping
- **events**: Geopolitical events from GDELT and curated sources
- **gdelt_processed_dates**: Tracking table for GDELT backfill

## 🔧 Maintenance

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f downloader
docker compose logs -f processor
docker compose logs -f map
```

### Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove data volumes (WARNING: deletes all data)
docker compose down -v
```

### Database Access

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres -d ddosia

# Backup database
docker compose exec postgres pg_dump -U postgres ddosia > backup.sql

# Restore database
cat backup.sql | docker compose exec -T postgres psql -U postgres ddosia
```

### Updating TLD Mappings

To update country mappings for TLDs, edit:
```
map-worker/mappings/tld_to_country.json
```

The Map Updater service will automatically apply changes every 5 minutes.

## 🛡️ Security Considerations

### Before Deploying to Production

> **Note on Database Security**: Since all tracked data is publicly available DDoSia attack information, the default PostgreSQL password is acceptable for most deployments. The database doesn't contain any sensitive or private data.

1. **Network security**
   - Use a reverse proxy (nginx, Caddy) with HTTPS for public deployments
   - Restrict database access to internal network only
   - Consider adding API authentication for public-facing instances

2. **Rate limiting**
   - Configure rate limits for public endpoints
   - Monitor for abuse

3. **Optional: Custom database credentials**
   - If you have specific organizational security policies, you can change `POSTGRES_PASSWORD` in `.env`
   - Update the password in `DATABASE_URL` to match

## 🔍 Troubleshooting

### Services won't start

```bash
# Check service status
docker compose ps

# Check logs for errors
docker compose logs

# Restart services
docker compose restart
```

### Database connection errors

- Verify `DATABASE_URL` matches `POSTGRES_PASSWORD`
- Ensure PostgreSQL is healthy: `docker compose ps postgres`
- Check PostgreSQL logs: `docker compose logs postgres`

### No data appearing

- Check downloader is running: `docker compose logs downloader`
- Verify source URL is accessible: check `BASE_URL` in `.env`
- Check processor logs: `docker compose logs processor`
- Ensure `data/downloads/` directory has write permissions

### Map shows no locations

- Check Map Updater service: `docker compose logs map_updater`
- Verify TLD mapping file exists: `map-worker/mappings/tld_to_country.json`
- Check TLD coverage at `/health` endpoint

## 📁 Project Structure

```
.
├── docker-compose.yml          # Service orchestration
├── .env.example                # Configuration template
├── .gitignore                  # Git ignore rules
├── migrations/                 # Database schema migrations
│   ├── 001_init.sql
│   ├── 002_tld_geo.sql
│   └── ...
├── src/                        # Downloader and Processor
│   ├── main.py                # Downloader entry point
│   ├── downloader.py          # Download logic
│   └── processor.py           # Processing logic
├── map-service/               # Web UI and API
│   ├── app.py                 # Flask application
│   └── static/                # HTML, CSS, JS
├── map-worker/                # TLD mapping updater
│   ├── worker.py
│   └── mappings/              # Country mappings
├── gdelt-worker/              # GDELT event fetcher
│   ├── worker.py
│   └── run_loop.sh
├── data/                      # Runtime data
│   ├── downloads/            # Downloaded JSON files
│   ├── pending/              # Files awaiting processing
│   └── processed/            # Processed files
└── tests/                    # Unit tests
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is provided as-is for research and educational purposes.

## 🙏 Acknowledgments

- Data source: [witha.name/data](https://www.witha.name/data/)
- GDELT Project for geopolitical event data
- Open-source community for the various tools and libraries used

## 📧 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**⚠️ Disclaimer**: This tool is intended for research and defensive security purposes only. The data tracked represents public information about ongoing cyber attacks. Use responsibly and in accordance with applicable laws.
