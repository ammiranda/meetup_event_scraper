import time
import logging
from typing import Optional
from datetime import datetime
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def safe_request(func):
    """Decorator to handle request retries and errors."""
    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff
    return wrapper

def save_to_csv(data: list, filename: str, output_dir: str = "data") -> None:
    """
    Save data to a CSV file.
    
    Args:
        data (list): List of dictionaries to save
        filename (str): Name of the output file
        output_dir (str): Directory to save the file in
    """
    try:
        df = pd.DataFrame(data)
        df.to_csv(f"{output_dir}/{filename}", index=False)
        logger.info(f"Successfully saved data to {filename}")
    except Exception as e:
        logger.error(f"Error saving data to {filename}: {str(e)}")
        raise

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse date string from Meetup format to datetime object.
    
    Args:
        date_str (str): Date string in Meetup format
        
    Returns:
        Optional[datetime]: Parsed datetime object or None if parsing fails
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        logger.warning(f"Failed to parse date: {date_str}")
        return None 