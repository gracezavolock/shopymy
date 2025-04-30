# shopymy

This script scrapes product information from ShopMy collections and saves it to a CSV file.

## Files
- `shopmy_scraper.py` - The main Python script
- `requirements.txt` - List of required Python packages
- `shopmy_products.csv` - The output file containing scraped product data

## Setup

1. Make sure you have Python 3.7+ installed

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

## Usage

1. Run the script:
```bash
python3 shopmy_scraper.py
```

The script will:
- Scrape product information from the ShopMy collection
- Remove any duplicate products
- Save unique products to `shopmy_products.csv`

## Output

The script creates a CSV file (`shopmy_products.csv`) with the following columns:
- title: Product title
- brand: Brand name (when available)
- image_url: URL of the product image
- product_url: URL to purchase the product

## Troubleshooting

If you encounter any issues:
1. Make sure all required packages are installed
2. Check that Playwright browsers are installed
3. Verify your internet connection
4. Try running the script again 
