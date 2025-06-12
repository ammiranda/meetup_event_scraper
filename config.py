from typing import Dict, Any

# Scraping settings
SCRAPING_SETTINGS: Dict[str, Any] = {
    "request_delay": 2,  # Delay between requests in seconds
    "max_retries": 3,    # Maximum number of retries for failed requests
    "timeout": 30,       # Request timeout in seconds
}

# Output settings
OUTPUT_SETTINGS: Dict[str, Any] = {
    "output_dir": "data",
    "group_file": "groups.csv",
    "events_file": "events.csv",
}

# Search settings
SEARCH_SETTINGS: Dict[str, Any] = {
    "default_location": "San Francisco",
    "max_results": 100,
    "radius": 25,  # Search radius in miles
} 