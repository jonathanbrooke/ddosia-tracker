"""
GDELT Query Service - Flask API for querying GDELT events
Provides a user-friendly interface for searching GDELT news articles
with date range and keyword filtering
"""
import os
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("gdelt-query-service")

app = Flask(__name__, static_folder="static")
CORS(app)

# Configuration
GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_TIMEOUT = int(os.getenv("GDELT_TIMEOUT", "30"))
GDELT_REQUEST_DELAY = int(os.getenv("GDELT_REQUEST_DELAY", "7"))


@app.route("/")
def index():
    """Serve the GDELT query interface"""
    return send_from_directory(app.static_folder, "gdelt-query.html")


@app.route("/api/query", methods=["POST"])
def query_gdelt():
    """
    Query GDELT API with user-provided parameters
    
    Request body:
    {
        "keywords": "search terms",
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "max_results": 10
    }
    
    Returns:
    {
        "success": true,
        "count": 5,
        "articles": [...]
    }
    """
    try:
        data = request.get_json()
        
        # Validate input
        keywords = data.get("keywords", "").strip()
        start_date = data.get("start_date", "").strip()
        end_date = data.get("end_date", "").strip()
        max_results = int(data.get("max_results", 10))
        
        if not keywords:
            return jsonify({
                "success": False,
                "error": "Keywords are required"
            }), 400
        
        if not start_date or not end_date:
            return jsonify({
                "success": False,
                "error": "Both start and end dates are required"
            }), 400
        
        # Validate and parse dates
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Invalid date format. Use YYYY-MM-DD"
            }), 400
        
        if start_dt > end_dt:
            return jsonify({
                "success": False,
                "error": "Start date must be before end date"
            }), 400
        
        # Limit max results
        max_results = min(max_results, 10)
        
        logger.info(
            f"Querying GDELT: '{keywords}' from {start_date} to {end_date}, "
            f"max {max_results} results"
        )
        
        # Build GDELT API request
        params = {
            "query": keywords,
            "mode": "artlist",
            "maxrecords": "100",  # Fetch more to filter for English
            "format": "json",
            "startdatetime": start_dt.strftime("%Y%m%d") + "000000",
            "enddatetime": end_dt.strftime("%Y%m%d") + "235959"
        }
        
        # Make request to GDELT API
        response = requests.get(
            GDELT_API_URL,
            params=params,
            timeout=GDELT_TIMEOUT
        )
        
        if response.status_code != 200:
            logger.error(f"GDELT API error: {response.status_code}")
            return jsonify({
                "success": False,
                "error": f"GDELT API returned status {response.status_code}"
            }), 502
        
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            return jsonify({
                "success": True,
                "count": 0,
                "articles": [],
                "message": "No articles found for this query"
            })
        
        # Process and filter articles
        processed_articles = []
        for article in articles:
            if len(processed_articles) >= max_results:
                break
            
            try:
                # Extract article data
                title = article.get("title", "No Title")
                url = article.get("url", "")
                domain = article.get("domain", "")
                language = article.get("language", "").lower()
                seendate = article.get("seendate", "")
                
                # Parse date
                article_date = ""
                if len(seendate) >= 8:
                    try:
                        article_date = f"{seendate[0:4]}-{seendate[4:6]}-{seendate[6:8]}"
                    except:
                        article_date = "Unknown"
                
                # Filter for English articles (prioritize English)
                if language != "english":
                    continue
                
                processed_articles.append({
                    "title": title[:200],  # Truncate long titles
                    "url": url,
                    "domain": domain,
                    "language": language.capitalize(),
                    "date": article_date,
                    "seendate": seendate
                })
                
            except Exception as e:
                logger.warning(f"Error processing article: {e}")
                continue
        
        # If we didn't get enough English articles, add non-English ones
        if len(processed_articles) < max_results:
            for article in articles:
                if len(processed_articles) >= max_results:
                    break
                
                try:
                    title = article.get("title", "No Title")
                    url = article.get("url", "")
                    language = article.get("language", "").lower()
                    
                    # Skip if already added
                    if any(a["title"] == title for a in processed_articles):
                        continue
                    
                    domain = article.get("domain", "")
                    seendate = article.get("seendate", "")
                    
                    article_date = ""
                    if len(seendate) >= 8:
                        try:
                            article_date = f"{seendate[0:4]}-{seendate[4:6]}-{seendate[6:8]}"
                        except:
                            article_date = "Unknown"
                    
                    processed_articles.append({
                        "title": title[:200],
                        "url": url,
                        "domain": domain,
                        "language": language.capitalize() if language else "Unknown",
                        "date": article_date,
                        "seendate": seendate
                    })
                    
                except Exception as e:
                    logger.warning(f"Error processing article: {e}")
                    continue
        
        logger.info(
            f"Returned {len(processed_articles)} articles "
            f"(from {len(articles)} total)"
        )
        
        return jsonify({
            "success": True,
            "count": len(processed_articles),
            "total_found": len(articles),
            "articles": processed_articles
        })
        
    except requests.exceptions.Timeout:
        logger.error("GDELT API timeout")
        return jsonify({
            "success": False,
            "error": "Request to GDELT API timed out"
        }), 504
        
    except requests.exceptions.RequestException as e:
        logger.error(f"GDELT API request failed: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to connect to GDELT API"
        }), 502
        
    except Exception as e:
        logger.exception("Unexpected error in query_gdelt")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "gdelt-query"
    })


if __name__ == "__main__":
    # Run with gunicorn in production, but allow direct run for dev
    app.run(host="0.0.0.0", port=8001, debug=False)
