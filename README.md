# Meetup Event Scraper

A Python-based web scraper for extracting event information from Meetup.com's event search results pages.

## Features

- Scrapes event information from Meetup.com's event search results
- Handles infinite scroll loading
- Extracts detailed event information including:
  - Event title and ID
  - Date and time (both ISO and human-readable)
  - Location
  - Group name
  - Rating
  - Attendee count
  - Event image URL
- Saves results to JSON format
- Supports both local and Docker environments

## Prerequisites

- Python 3.9 or higher
- Chrome or Brave browser
- ChromeDriver (automatically managed by webdriver-manager)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd meetup_scraper
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

The scraper is designed to work with Meetup's event search results pages. You can find these pages by:
1. Going to meetup.com
2. Clicking "Find Events"
3. Using the search bar or filters
4. Copying the URL from your browser

### Basic Usage

```bash
python meetup_scraper.py "https://www.meetup.com/find/events/?keywords=python"
```

### Command Line Options

- `url`: The Meetup events search URL to scrape (required)
- `--max-pages`, `-m`: Maximum number of scrolls to perform (default: 3)
- `--output`, `-o`: Output filename (default: events.json)

Example with options:
```bash
python meetup_scraper.py "https://www.meetup.com/find/events/?keywords=python" --max-pages 5 --output python_events.json
```

### Example URLs

Here are some example URLs you can use:
- Python events: `https://www.meetup.com/find/events/?keywords=python`
- Tech events in New York: `https://www.meetup.com/find/events/?location=us--ny--new-york&keywords=tech`
- Online events: `https://www.meetup.com/find/events/?keywords=online`

## Docker Usage

### Building the Docker Image

```bash
docker build -t meetup-scraper .
```

### Running with Docker

Basic usage:
```bash
docker run -v "$(pwd)/data:/app/data" meetup-scraper "https://www.meetup.com/find/events/?keywords=python"
```

With options:
```bash
docker run -v "$(pwd)/data:/app/data" meetup-scraper "https://www.meetup.com/find/events/?keywords=python" --max-pages 5 --output python_events.json
```

## Project Structure

```
meetup_scraper/
├── meetup_scraper.py    # Main scraper script
├── requirements.txt     # Project dependencies
├── Dockerfile          # Docker configuration
├── entrypoint.sh       # Docker entrypoint script
└── data/              # Output directory for scraped data
```

## Output Format

The scraper generates a JSON file with the following structure:

```json
[
  {
    "event_id": "307937022",
    "title": "Python x OpenAI Workshop",
    "url": "https://www.meetup.com/...",
    "date": "2025-06-14T09:30:00-05:00[America/Chicago]",
    "date_display": "Sat, Jun 14 · 9:30 AM CDT",
    "location": "Online",
    "group_name": "Tech Founders Club",
    "rating": "4.5",
    "attendees": "46 attendees",
    "image_url": "https://secure.meetupstatic.com/..."
  },
  // ... more events
]
```

## Notes

- The scraper uses infinite scroll to load more events, so the `--max-pages` parameter controls how many times it will scroll down
- Results are saved in the `data` directory
- The scraper includes random delays to be respectful to Meetup's servers
- Make sure to use the events search URL, not the group or individual event URLs

## Troubleshooting

If you encounter any issues:
1. Make sure you're using a valid Meetup events search URL
2. Check that you have the correct browser and ChromeDriver installed
3. Try increasing the `--max-pages` value if you're not getting enough results
4. Check the logs for any error messages

## License

This project is licensed under the MIT License - see the LICENSE file for details. 