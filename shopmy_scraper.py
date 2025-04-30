from playwright.sync_api import sync_playwright
import pandas as pd
import time
import re
from urllib.parse import unquote, urlparse, parse_qs
import requests
import csv
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import logging
from typing import List, Dict, Optional, Any
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_url(url):
    """Clean affiliate URLs and return the direct product URL."""
    try:
        # Handle different affiliate URL patterns
        if "api.shopmy.us/api/redirect_click" in url:
            # Extract the actual URL from the 'url' parameter
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'url' in params:
                url = unquote(params['url'][0])
        elif "anrdoezrs.net/click" in url:
            # Extract URL after the 'url=' parameter
            url = url.split('url=')[-1]
            url = unquote(url)
        elif "click.linksynergy.com/deeplink" in url:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'murl' in params:
                url = unquote(params['murl'][0])
        
        # Clean up any remaining URL encoding
        url = unquote(url)
        
        # Remove tracking parameters
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Keep only essential query parameters (like product variants)
        params = parse_qs(parsed.query)
        essential_params = {k: v[0] for k, v in params.items() 
                          if k.lower() in ['variant', 'color', 'size']}
        
        if essential_params:
            param_str = '&'.join(f"{k}={v}" for k, v in essential_params.items())
            return f"{base_url}?{param_str}"
        
        return base_url
    except:
        return url

def extract_brand_from_url_and_title(url, title):
    """Extract brand name from URL and title."""
    known_brands = {
        'stella-mccartney': 'Stella McCartney',
        'lcuppini': 'L.Cuppini',
        'nanushka': 'Nanushka',
        'havaianas': 'Havaianas',
        'gap': 'Gap',
        'jennikayne': 'Jenni Kayne',
        'aritzia': 'Aritzia',
        'jimmy-choo': 'Jimmy Choo',
        'hunting-season': 'Hunting Season',
        'cesta': 'Cesta Collective',
        'eliou': 'Éliou',
        'reformation': 'Reformation',
        'nour-hammour': 'Nour Hammour',
        'khaite': 'Khaite',
        'staud': 'Staud',
        'sezane': 'Sezane',
        'veronica-beard': 'Veronica Beard',
        'tory-burch': 'Tory Burch',
        'shonajoy': 'Shona Joy',
        'anine-bing': 'Anine Bing',
        'saint-laurent': 'Saint Laurent',
        'loro-piana': 'Loro Piana',
        'ralph-lauren': 'Ralph Lauren',
        'leset': 'Le Set',
        'co-collections': 'CO'
    }
    
    # Try to extract brand from URL
    parsed_url = urlparse(url).netloc.lower()
    for brand_key, brand_name in known_brands.items():
        if brand_key in parsed_url:
            return brand_name
    
    # Try to extract from path
    path = urlparse(url).path.lower()
    for brand_key, brand_name in known_brands.items():
        if brand_key in path:
            return brand_name
    
    # Try to extract from title
    if title and title != "N/A":
        # Look for brand name before the | symbol
        if "|" in title:
            potential_brand = title.split("|")[0].strip()
            return potential_brand
        
        # Look for known brands in title
        for brand_name in known_brands.values():
            if brand_name.lower() in title.lower():
                return brand_name
    
    return "N/A"

def verify_url(url):
    """Verify if a URL is accessible."""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def retry_with_backoff(func, max_retries=3, initial_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            delay = initial_delay * (2 ** attempt)
            logger.info(f"Attempt {attempt + 1} failed, retrying in {delay} seconds...")
            time.sleep(delay)

def scrape_shopmy_collection(url: str) -> List[Dict[str, str]]:
    products_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            logger.info("Starting the scraper...")
            logger.info(f"Navigating to {url}")
            
            def load_page():
                page.goto(url, timeout=90000, wait_until='networkidle')
            
            retry_with_backoff(load_page)
            logger.info("Page loaded, waiting for content...")
            
            # Try different selectors for product elements
            selectors = ['[class*="product"]', '.product-card', '.product-item']
            product_selector = None
            
            for selector in selectors:
                try:
                    logger.info(f"Trying selector: {selector}")
                    page.wait_for_selector(selector, timeout=30000)
                    product_selector = selector
                    logger.info(f"Found working selector: {selector}")
                    break
                except PlaywrightTimeout:
                    continue
            
            if not product_selector:
                raise Exception("Could not find any product elements on the page")
            
            logger.info("Waiting for React to fully render...")
            page.wait_for_timeout(2000)
            
            logger.info("Scrolling to load all content...")
            last_height = page.evaluate('document.body.scrollHeight')
            while True:
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                page.wait_for_timeout(2000)
                new_height = page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    break
                last_height = new_height
            
            logger.info("Extracting product information...")
            products = page.query_selector_all(product_selector)
            
            for idx, product in enumerate(products, 1):
                logger.info(f"Processing product {idx}")
                
                # Initialize product data
                product_data = {
                    'title': 'N/A',
                    'brand': 'N/A',
                    'image_url': 'N/A',
                    'product_url': 'N/A'
                }
                
                try:
                    # Try to get title
                    title_element = product.query_selector('[class*="title"]') or product.query_selector('h3') or product.query_selector('h2')
                    if title_element:
                        product_data['title'] = title_element.inner_text().strip()
                    
                    # Try to get brand
                    brand_element = product.query_selector('[class*="brand"]') or product.query_selector('[class*="vendor"]')
                    if brand_element:
                        product_data['brand'] = brand_element.inner_text().strip()
                    
                    # Try to get image URL
                    img_element = product.query_selector('img')
                    if img_element:
                        product_data['image_url'] = img_element.get_attribute('src') or img_element.get_attribute('data-src') or 'N/A'
                        if product_data['image_url'].startswith('//'):
                            product_data['image_url'] = 'https:' + product_data['image_url']
                    
                    # Try to get product URL
                    link_element = product.query_selector('a')
                    if link_element:
                        product_url = link_element.get_attribute('href')
                        if product_url:
                            if product_url.startswith('//'):
                                product_url = 'https:' + product_url
                            elif product_url.startswith('/'):
                                product_url = 'https://shopmy.us' + product_url
                            product_data['product_url'] = product_url
                    
                    # Only add product if we have at least some information
                    if any(value != 'N/A' for value in product_data.values()):
                        products_data.append(product_data)
                        logger.info(f"Added product: {product_data['title']}")
                    
                except Exception as e:
                    logger.error(f"Error processing product {idx}: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to complete scraping: {str(e)}")
            page.screenshot(path='error_screenshot.png')
            raise
        
        finally:
            browser.close()
    
    return products_data

def save_to_csv(products_data: List[Dict[str, str]], filename: str = 'shopmy_products.csv'):
    if not products_data:
        logger.warning("No products to save")
        return
    
    # Remove duplicates based on title and product_url
    seen = set()
    unique_products = []
    for product in products_data:
        # Create a tuple of values we want to check for uniqueness
        key = (product['title'], product['product_url'])
        if key not in seen:
            seen.add(key)
            unique_products.append(product)
    
    logger.info(f"Removed {len(products_data) - len(unique_products)} duplicate products")
    
    fieldnames = ['title', 'brand', 'image_url', 'product_url']
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique_products)
    
    logger.info(f"Saved {len(unique_products)} unique products to {filename}")
    logger.info("First few rows of data:")
    for product in unique_products[:5]:
        logger.info(product)

def main():
    url = "https://shopmy.us/collections/727615"
    try:
        products = scrape_shopmy_collection(url)
        save_to_csv(products)
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
