# GDELT Query Service

A standalone Flask service that provides an interactive web interface for querying the GDELT (Global Database of Events, Language, and Tone) Project API.

## Features

- 🔍 **Keyword Search**: Search for news articles by custom keywords
- 📅 **Date Range Filtering**: Select specific time periods for your search
- 🌐 **Language Prioritization**: Automatically prioritizes English-language articles
- 🎨 **Modern UI**: Clean, responsive interface matching the DDoSia Tracker theme
- ⚡ **Real-time Results**: Live search with progress indicators
- 🔗 **Direct Links**: Quick access to original article sources
- 🚦 **Rate Limiting**: Respects GDELT API limits with built-in delays

## Architecture

The service is a lightweight Flask application that:
1. Provides a web interface for GDELT queries
2. Acts as a proxy to the GDELT API
3. Filters and formats results for optimal presentation
4. Runs independently from the main DDoSia tracking system

## API Endpoint

### POST /api/query

Query GDELT for news articles matching specified criteria.

**Request Body:**
```json
{
  "keywords": "cyber attack",
  "start_date": "2025-10-01",
  "end_date": "2025-10-31",
  "max_results": 10
}
```

**Response:**
```json
{
  "success": true,
  "count": 5,
  "total_found": 47,
  "articles": [
    {
      "title": "Article title here",
      "url": "https://example.com/article",
      "domain": "example.com",
      "language": "English",
      "date": "2025-10-15",
      "seendate": "20251015120000"
    }
  ]
}
```

**Parameters:**
- `keywords` (required): Search terms for GDELT query
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format
- `max_results` (optional): Maximum number of results to return (1-10, default: 10)

**Error Response:**
```json
{
  "success": false,
  "error": "Error message here"
}
```

## Configuration

Environment variables:
- `GDELT_TIMEOUT`: API request timeout in seconds (default: 30)
- `GDELT_REQUEST_DELAY`: Delay between requests in seconds (default: 7)

## Usage

### Via Docker Compose

The service is automatically started with the main application:

```bash
docker compose up gdelt_query
```

Access at: http://localhost:8001

### Standalone

```bash
cd gdelt-query-service
pip install -r requirements.txt
python app.py
```

## User Interface

The web interface includes:

1. **Search Panel**
   - Keyword input field
   - Start/end date pickers (defaults to last 7 days)
   - Maximum results selector (1-10)
   - Search button with loading state

2. **Progress Indicator**
   - Animated spinner
   - Result count display
   - Status messages

3. **Results Display**
   - Article cards with:
     - Title
     - Publication date
     - Source domain
     - Language
     - Link to original article
   - Staggered fade-in animations
   - Hover effects

4. **Error Handling**
   - Clear error messages
   - User-friendly validation
   - Network error handling

## Rate Limiting & API Respect

The service implements several measures to respect GDELT API limits:

- Configurable request delays (default: 7 seconds)
- Timeout controls to prevent hanging requests
- Limited max results per query (10 articles)
- User education through UI messaging

## Integration

The service integrates with the DDoSia Tracker ecosystem:

- Shares the same visual theme and design language
- Navigation links to/from other services
- Can be deployed alongside other services via docker-compose
- Independent operation - no database dependency

## Development

The service is built with:
- **Flask**: Web framework
- **Flask-CORS**: Cross-origin resource sharing
- **Requests**: HTTP library for GDELT API calls
- **Gunicorn**: Production WSGI server

File structure:
```
gdelt-query-service/
├── app.py                  # Flask application
├── requirements.txt        # Python dependencies
└── static/
    └── gdelt-query.html   # Frontend UI
```

## Troubleshooting

**No results found:**
- Try broader keywords
- Expand date range
- Check GDELT service status

**Timeout errors:**
- Increase `GDELT_TIMEOUT` environment variable
- Check network connectivity
- Verify GDELT API is accessible

**Service won't start:**
- Check port 8001 is available
- Verify requirements are installed
- Check Docker logs: `docker compose logs gdelt_query`
