from datetime import datetime
from typing import List, Dict, Optional, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import os
import sys
import logging
import time
import json
import argparse
import random
from urllib.parse import urlparse
from pathlib import Path
from urllib.robotparser import RobotFileParser

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
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
        self.user_agent = 'MeetupScraper/0.0.1 (https://github.com/yourusername/meetup_scraper; your@email.com)'
        self.setup_driver()

    def check_robots_txt(self, url: str) -> bool:
        """Check if we're allowed to scrape the given URL according to robots.txt."""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            # Create a robot parser
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            # Check if we're allowed to fetch the URL
            can_fetch = rp.can_fetch(self.user_agent, url)
            
            if not can_fetch:
                logger.warning(f"Scraping not allowed for {url} according to robots.txt")
            else:
                # Get crawl delay if specified
                crawl_delay = rp.crawl_delay(self.user_agent)
                if crawl_delay:
                    logger.info(f"Respecting crawl delay of {crawl_delay} seconds")
                    time.sleep(crawl_delay)
            
            return can_fetch
        except Exception as e:
            logger.error(f"Error checking robots.txt: {str(e)}")
            return False

    def setup_driver(self):
        """Set up the Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        
        # Check if running in Docker
        if os.path.exists('/usr/bin/chromedriver'):
            logger.info("Running in Docker environment")
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.binary_location = '/usr/bin/chromium-browser'
            # Use system ChromeDriver in Docker
            service = Service('/usr/bin/chromedriver')
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
            # Use ChromeDriverManager only in local environment
            service = Service(ChromeDriverManager().install())

        # Add user agent
        chrome_options.add_argument(f'--user-agent={self.user_agent}')
        
        # Add options for better Docker termination
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-features=TranslateUI')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        
        # Set up the Chrome driver
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set page load timeout
        self.driver.set_page_load_timeout(30)
        self.driver.implicitly_wait(10)
        self.driver.set_script_timeout(30)
        
        # Execute CDP commands to prevent detection
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": self.user_agent
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
            # Convert to ISO format if not already
            try:
                # Remove timezone info in square brackets and convert Z to +00:00
                date = date.split('[')[0].replace('Z', '+00:00')
                date_obj = datetime.fromisoformat(date)
                date = date_obj.isoformat()
            except ValueError:
                logger.warning(f"Could not parse date: {date}")
            date_display = time_element.text
            
            # Get group name
            try:
                group_element = event_element.find_element(By.CSS_SELECTOR, 'div.flex-shrink.min-w-0.truncate')
                group_text = group_element.text
                # Remove the "by " prefix and any leading/trailing whitespace
                group_name = group_text.replace('by ', '', 1).strip()
            except NoSuchElementException:
                group_name = "Group name not available"
            
            # Get rating
            try:
                rating_container = event_element.find_element(By.CSS_SELECTOR, '[class*="text-ds-neutral500"]')
                rating = rating_container.find_element(By.CSS_SELECTOR, 'span').text
            except NoSuchElementException:
                rating = "No rating"
            
            # Get attendees
            try:
                attendees_container = event_element.find_element(By.CSS_SELECTOR, '[class*="text-primary"][class*="text-xs"]')
                attendees_text = attendees_container.find_element(By.CSS_SELECTOR, 'span').text
                # Extract number from text like "46 attendees"
                attendees = int(''.join(filter(str.isdigit, attendees_text)))
            except (NoSuchElementException, ValueError):
                attendees = 0
            
            # Get image URL
            try:
                # Get the first image element with a meetupstatic.com URL
                img_element = event_element.find_element(By.CSS_SELECTOR, 'img[src*="meetupstatic.com"]')
                image_url = img_element.get_attribute('src')
                if not image_url or not image_url.startswith('http'):
                    image_url = "No image available"
            except NoSuchElementException:
                image_url = "No image available"
            except Exception as e:
                logger.warning(f"Error extracting image URL: {str(e)}")
                image_url = "No image available"
            
            return {
                'event_id': event_id,
                'title': title,
                'url': url,
                'date': date,
                'date_display': date_display,
                'group_name': group_name,
                'rating': rating,
                'attendees': attendees,
                'image_url': image_url
            }
        except Exception as e:
            logger.error(f"Error extracting event info: {str(e)}")
            return None

    def scrape_events(self, url: str, max_pages: int = 3, exhaustive: bool = False) -> List[Dict[str, Any]]:
        """Scrape events from the given URL."""
        events = []
        processed_ids = set()
        
        # Check robots.txt first
        if not self.check_robots_txt(url):
            logger.error("Scraping not allowed by robots.txt")
            return events
        
        try:
            logger.info(f"Navigating to URL: {url}")
            self.driver.get(url)
            
            # Wait for initial page load with timeout
            time.sleep(random.uniform(2, 4))

            page = 0

            while True:
                if not exhaustive and page >= max_pages:
                    break
                
                if exhaustive:
                    logger.info(f"Scrolling page {page + 1}")
                else:
                    logger.info(f"Scrolling page {page + 1}/{max_pages}")
                
                try:
                    # Scroll down with timeout
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(2, 4))  # Wait for content to load
                    
                    # Find all event elements with timeout
                    event_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-event-id]')
                    logger.info(f"Found {len(event_elements)} event elements")
                    
                    # Track if we found any new events in this scroll
                    found_new_events = False
                    
                    # Process new events
                    for event_element in event_elements:
                        try:
                            event_id = event_element.get_attribute('data-event-id')
                            if event_id not in processed_ids:
                                event_info = self.extract_event_info(event_element)
                                if event_info:
                                    events.append(event_info)
                                    processed_ids.add(event_id)
                                    found_new_events = True
                                    logger.info(f"Added event: {event_info['title']}")
                        except Exception as e:
                            logger.warning(f"Error processing event element: {str(e)}")
                            continue
                    
                    logger.info(f"Total events collected so far: {len(events)}")
                    
                    # If no new events were found in this scroll, we've reached the end
                    if not found_new_events:
                        logger.info("No new events found in this scroll, reached the end of available events")
                        break
                    
                    # Random delay between scrolls
                    time.sleep(random.uniform(1, 3))
                    page += 1
                    
                except Exception as e:
                    logger.error(f"Error during page {page + 1}: {str(e)}")
                    break
            
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
        finally:
            logger.info(f"Scraping completed. Total events collected: {len(events)}")
        
        return events

    def save_events(self, events: List[Dict[str, Any]], filename: str = "events.json"):
        """Save events to a JSON file."""
        try:
            # Create data directory if it doesn't exist
            data_dir = Path("/data")
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
            try:
                logger.info("Closing WebDriver...")
                self.driver.quit()
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {str(e)}")
            finally:
                self.driver = None

def main():
    parser = argparse.ArgumentParser(description='Scrape Meetup events from a search URL')
    parser.add_argument('url', help='Meetup events search URL to scrape')
    parser.add_argument('--max-pages', '-m', type=int, default=3,
                      help='Maximum number of scrolls to perform (default: 3)')
    parser.add_argument('--output', '-o', default='events.json',
                      help='Output filename (default: events.json)')
    parser.add_argument('--exhaustive', '-e', action='store_true',
                        help='Scrape all events on the page')
    
    args = parser.parse_args()
    
    scraper = MeetupScraper()
    try:
        events = scraper.scrape_events(args.url, args.max_pages, args.exhaustive)
        scraper.save_events(events, args.output)
        logger.info("Script completed successfully")
    except Exception as e:
        logger.error(f"Script failed with error: {str(e)}")
        raise
    finally:
        scraper.close()

if __name__ == "__main__":
    main() 