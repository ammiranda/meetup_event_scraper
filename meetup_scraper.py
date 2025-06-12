import os
from datetime import datetime
from typing import List, Dict, Optional
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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
        """Initialize the Selenium WebDriver with appropriate options."""
        logger.info("Setting up WebDriver...")
        chrome_options = Options()
        
        # Use headless mode with additional options
        chrome_options.add_argument("--headless=new")  # Use new headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")  # Set a realistic window size
        
        # Add additional options to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Set a realistic user agent
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Check if running in Docker
        if os.path.exists("/.dockerenv"):
            logger.info("Running in Docker environment")
            # In Docker, use the system Chrome and ChromeDriver
            chrome_options.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium")
            service = Service("/usr/bin/chromedriver")
        else:
            logger.info("Running in local environment")
            # Local development - try Brave first, then fallback to Chrome
            brave_path = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
            if os.path.exists(brave_path):
                logger.info("Using Brave browser")
                chrome_options.binary_location = brave_path
            
            # Try to use a local chromedriver if specified
            chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
            if chromedriver_path and os.path.exists(chromedriver_path):
                logger.info(f"Using local ChromeDriver at {chromedriver_path}")
                service = Service(chromedriver_path)
            else:
                try:
                    logger.info("Attempting to use ChromeDriverManager")
                    service = Service(ChromeDriverManager().install())
                except Exception as e:
                    logger.error("Failed to setup ChromeDriver", exc_info=True)
                    raise Exception(
                        "Could not auto-detect Chrome version. Please download the correct chromedriver for your browser version, "
                        "place it somewhere on your system, and set the CHROMEDRIVER_PATH environment variable to its path.\n"
                        f"Original error: {e}"
                    )
        
        logger.info("Creating Chrome WebDriver instance...")
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute CDP commands to prevent detection
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        # Set window size
        self.driver.set_window_size(1920, 1080)
        
        logger.info("WebDriver setup complete")

    def wait_for_element(self, by: By, value: str, timeout: int = 20) -> Optional[webdriver.remote.webelement.WebElement]:
        """Wait for an element to be present and return it."""
        try:
            # First wait for the page to be fully loaded
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            # Then wait for the specific element
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

    def extract_event_info(self, element) -> Optional[Dict]:
        """Extract information from an event element."""
        try:
            # Get the event ID
            event_id = element.get_attribute('data-event-id')
            
            # Find the main link element that contains all event information
            link = element.find_element(By.CSS_SELECTOR, "a[data-event-label='Revamped Event Card']")
            
            # Extract title from h3
            title = link.find_element(By.CSS_SELECTOR, "h3").text
            
            # Extract URL
            url = link.get_attribute('href')
            
            # Extract date/time
            date_element = link.find_element(By.CSS_SELECTOR, "time")
            date = date_element.get_attribute('datetime')  # Get the ISO datetime
            date_display = date_element.text  # Get the human-readable date
            
            # Extract location
            location = None
            try:
                location_div = link.find_element(By.CSS_SELECTOR, "div.flex.items-center.gap-1.rounded.bg-\\[\\#f5f5f5\\]")
                location = location_div.text
            except NoSuchElementException:
                pass
            
            # Extract group name
            group_name = None
            try:
                group_div = link.find_element(By.CSS_SELECTOR, "div.flex-shrink.min-w-0.truncate")
                group_name = group_div.text.replace('by ', '')
            except NoSuchElementException:
                pass
            
            # Extract rating
            rating = None
            try:
                # Look for the rating in the flex row with star icon
                rating_container = link.find_element(By.CSS_SELECTOR, "div.flex.flex-row.text-sm.text-ds-neutral500.items-center")
                rating_span = rating_container.find_element(By.CSS_SELECTOR, "span.mt-0\\.5.font-medium.leading-none.text-ds-neutral500.mb-0.text-xs")
                rating = rating_span.text
            except NoSuchElementException:
                pass
            
            # Extract attendees count
            attendees = None
            try:
                # Look for attendees in the mt-1.5 flex items-center container
                attendees_container = link.find_element(By.CSS_SELECTOR, "div.mt-1\\.5.flex.items-center.text-xs.font-medium.text-primary")
                attendees_span = attendees_container.find_element(By.CSS_SELECTOR, "span.font-medium")
                attendees = attendees_span.text
            except NoSuchElementException:
                pass
            
            # Extract image URL
            image_url = None
            try:
                img = link.find_element(By.CSS_SELECTOR, "img[alt*='Workshop']")
                image_url = img.get_attribute('src')
            except NoSuchElementException:
                pass
            
            if title and url:  # Only return if we have at least title and URL
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
            logger.warning(f"Could not extract all information for an event: {str(e)}")
            return None

    def scrape_events(self, url: str, max_pages: int = 3) -> List[Dict]:
        """
        Scrape events from a Meetup URL.
        
        Args:
            url (str): The Meetup URL to scrape events from
            max_pages (int): Maximum number of scrolls to perform (default: 3)
            
        Returns:
            List[Dict]: List of event information
        """
        logger.info(f"Scraping events from URL: {url}")
        all_events = []
        current_scroll = 0
        last_height = 0
        
        try:
            # Load the initial page
            self.driver.get(url)
            time.sleep(2 + random.random() * 3)  # Initial wait for page load
            
            while current_scroll < max_pages:
                logger.info(f"Scrolling page {current_scroll + 1}")
                
                # Wait for event elements to load using data-event-id attribute
                if not self.wait_for_element(By.CSS_SELECTOR, "[data-event-id]"):
                    logger.warning("No events found with data-event-id")
                    break
                
                # Find all event elements
                event_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-event-id]")
                logger.info(f"Found {len(event_elements)} events on current view")
                
                # Process each event
                for element in event_elements:
                    try:
                        event_id = element.get_attribute('data-event-id')
                        # Skip if we've already processed this event
                        if any(e['event_id'] == event_id for e in all_events):
                            continue
                            
                        event_info = self.extract_event_info(element)
                        if event_info:
                            all_events.append(event_info)
                            logger.info(f"Found event: {event_info['title']} (ID: {event_id})")
                    except Exception as e:
                        logger.warning(f"Error extracting event info: {str(e)}")
                        continue
                
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2 + random.random() * 2)  # Wait for new content to load
                
                # Check if we've reached the bottom
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logger.info("Reached the bottom of the page")
                    break
                    
                last_height = new_height
                current_scroll += 1
                
        except Exception as e:
            logger.error(f"Error during scrolling: {str(e)}", exc_info=True)
        
        logger.info(f"Finished scrolling. Found {len(all_events)} total events")
        return all_events

    def save_results(self, data: List[Dict], filename: str):
        """Save results to a JSON file."""
        output_path = os.path.join('data', filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved results to {output_path}")

    def close(self):
        """Clean up resources."""
        if self.driver:
            logger.info("Closing WebDriver...")
            self.driver.quit()
            logger.info("WebDriver closed")

def main():
    parser = argparse.ArgumentParser(description='Scrape Meetup events from a URL')
    parser.add_argument('url', help='The Meetup URL to scrape events from')
    parser.add_argument('--max-pages', '-m', type=int, default=3, help='Maximum number of scrolls to perform (default: 3)')
    parser.add_argument('--output', '-o', help='Output filename (optional)')
    args = parser.parse_args()

    logger.info("Starting Meetup scraper...")
    scraper = MeetupScraper()
    try:
        # Scrape events from the provided URL
        events = scraper.scrape_events(args.url, args.max_pages)
        
        # Generate output filename
        output_filename = args.output if args.output else "events.json"
        
        # Save results
        scraper.save_results(events, output_filename)
        logger.info("Scraping complete!")
        
    except Exception as e:
        logger.error("An error occurred during scraping", exc_info=True)
        raise
    finally:
        scraper.close()
        logger.info("Scraper finished")

if __name__ == "__main__":
    main() 