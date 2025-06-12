import os
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import logging
import time
import json
import argparse
import random
from urllib.parse import urlparse, urljoin
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MeetupScraper:
    def __init__(self):
        logger.info("Initializing MeetupScraper...")
        load_dotenv()
        self.base_url = "https://www.meetup.com"
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        """Set up the Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        
        # Check if running in Docker
        if Path('/.dockerenv').exists():
            logger.info("Running in Docker environment")
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.binary_location = '/usr/bin/chromium'
        else:
            logger.info("Running in local environment")
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)

        # Add user agent
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Set up the Chrome driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set page load timeout
        self.driver.set_page_load_timeout(30)
        
        # Execute CDP commands to prevent detection
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })

    def wait_for_element(self, by: By, value: str, timeout: int = 10) -> Optional[Any]:
        """Wait for an element to be present on the page."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.warning(f"Timeout waiting for element: {value}")
            return None

    def get_next_page_url(self) -> Optional[str]:
        """Get the URL of the next page if it exists."""
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='pagination-next']")
            if "disabled" not in next_button.get_attribute("class"):
                return next_button.get_attribute("href")
        except NoSuchElementException:
            logger.info("No next page button found")
        return None

    def extract_event_info(self, event_element) -> Dict[str, Any]:
        """Extract information from an event element."""
        try:
            # Get event ID
            event_id = event_element.get_attribute('data-event-id')
            
            # Get title and URL
            title_element = event_element.find_element(By.CSS_SELECTOR, 'h3')
            title = title_element.text
            url = event_element.find_element(By.CSS_SELECTOR, 'a[href*="/events/"]').get_attribute('href')
            
            # Get date information
            time_element = event_element.find_element(By.CSS_SELECTOR, 'time')
            date = time_element.get_attribute('datetime')
            date_display = time_element.text
            
            # Get location
            try:
                location = event_element.find_element(By.CSS_SELECTOR, 'p.text-sm.text-ds-neutral500').text
            except NoSuchElementException:
                location = "Location not specified"
            
            # Get group name
            try:
                group_name = event_element.find_element(By.CSS_SELECTOR, 'p.text-sm.font-medium.text-primary').text
            except NoSuchElementException:
                group_name = "Group name not available"
            
            # Get rating
            try:
                rating_container = event_element.find_element(By.CSS_SELECTOR, 'div.flex.flex-row.text-sm.text-ds-neutral500.items-center')
                rating = rating_container.find_element(By.CSS_SELECTOR, 'span').text
            except NoSuchElementException:
                rating = "No rating"
            
            # Get attendees
            try:
                attendees_container = event_element.find_element(By.CSS_SELECTOR, 'div.mt-1.5.flex.items-center.text-xs.font-medium.text-primary')
                attendees = attendees_container.find_element(By.CSS_SELECTOR, 'span').text
            except NoSuchElementException:
                attendees = "No attendee count"
            
            # Get image URL
            try:
                image_url = event_element.find_element(By.CSS_SELECTOR, 'img').get_attribute('src')
            except NoSuchElementException:
                image_url = "No image available"
            
            return {
                'event_id': event_id,
                'title': title,
                'url': url,
                'date': date,
                'date_display': date_display,
                'location': location,
                'group_name': group_name,
                'rating': rating,
                'attendees': attendees,
                'image_url': image_url
            }
        except Exception as e:
            logger.error(f"Error extracting event info: {str(e)}")
            return None

    def scrape_events(self, url: str, max_pages: int = 3) -> List[Dict[str, Any]]:
        """Scrape events from the given URL."""
        events = []
        processed_ids = set()
        
        try:
            logger.info(f"Navigating to URL: {url}")
            self.driver.get(url)
            
            # Wait for initial page load
            time.sleep(random.uniform(2, 4))
            
            for page in range(max_pages):
                logger.info(f"Scrolling page {page + 1}/{max_pages}")
                
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))  # Wait for content to load
                
                # Find all event elements
                event_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-event-id]')
                logger.info(f"Found {len(event_elements)} event elements")
                
                # Process new events
                for event_element in event_elements:
                    event_id = event_element.get_attribute('data-event-id')
                    if event_id not in processed_ids:
                        event_info = self.extract_event_info(event_element)
                        if event_info:
                            events.append(event_info)
                            processed_ids.add(event_id)
                            logger.info(f"Added event: {event_info['title']}")
                
                logger.info(f"Total events collected so far: {len(events)}")
                
                # Check if we've reached the bottom
                if len(event_elements) == 0:
                    logger.info("No more events found, reached the bottom of the page")
                    break
                
                # Random delay between scrolls
                time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
        
        return events

    def save_events(self, events: List[Dict[str, Any]], filename: str = "events.json"):
        """Save events to a JSON file."""
        try:
            # Create data directory if it doesn't exist
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            
            # Save to file
            output_path = data_dir / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(events)} events to {output_path}")
        except Exception as e:
            logger.error(f"Error saving events: {str(e)}")

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()

def main():
    parser = argparse.ArgumentParser(description='Scrape Meetup events from a search URL')
    parser.add_argument('url', help='Meetup events search URL to scrape')
    parser.add_argument('--max-pages', '-m', type=int, default=3,
                      help='Maximum number of scrolls to perform (default: 3)')
    parser.add_argument('--output', '-o', default='events.json',
                      help='Output filename (default: events.json)')
    
    args = parser.parse_args()
    
    scraper = MeetupScraper()
    try:
        events = scraper.scrape_events(args.url, args.max_pages)
        scraper.save_events(events, args.output)
    finally:
        scraper.close()

if __name__ == "__main__":
    main() 