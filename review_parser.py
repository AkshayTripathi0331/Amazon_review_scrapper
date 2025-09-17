
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests, time, os

ZIP_CODE = "10001"

def init_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def set_zip_code_via_ajax(session, zip_code):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'x-requested-with': 'XMLHttpRequest'
    }
    try:
        response = session.post(
            'https://www.amazon.com/gp/delivery/ajax/address-change.html',
            data={
                'locationType': 'LOCATION_INPUT',
                'zipCode': zip_code,
                'storeContext': 'office-products',
                'deviceType': 'web',
                'pageType': 'Detail',
                'actionSource': 'glow',
            },
            headers=headers
        )
        return response.status_code == 200
    except Exception:
        return False


def fetch_product_metadata(asin, zip_code=ZIP_CODE):
    driver = init_driver()
    wait = WebDriverWait(driver, 20)
    session = requests.Session()

    driver.get("https://www.amazon.com/")
    time.sleep(3)

    for cookie in driver.get_cookies():
        session.cookies.set(cookie['name'], cookie['value'])

    ajax_success = set_zip_code_via_ajax(session, zip_code)
    if ajax_success:
        for cname, cval in session.cookies.items():
            driver.add_cookie({'name': cname, 'value': cval})

    url = f"https://www.amazon.com/dp/{asin}"
    driver.get(url)
    time.sleep(3)

    product_data = {}
    product_data["ASIN"] = asin
    product_data["productURL"] = url


     # Title
    try:
        product_data["title"] = driver.find_element(By.ID, "productTitle").text.strip()
    except:
        product_data["title"] = ""

    # Breadcrumb
    try:
        breadcrumbs = driver.find_element(By.ID, "wayfinding-breadcrumbs_feature_div").text.strip()
        product_data["breadcrumb"] = {"breadcrumb": breadcrumbs}
    except:
        product_data["breadcrumb"] = {"breadcrumb": ""}

    # Features
    try:
        features = driver.find_elements(By.CSS_SELECTOR, "#feature-bullets ul li span")
        product_data["features"] = [f.text.strip() for f in features if f.text.strip()]
    except:
        product_data["features"] = []

    # Description
    try:
        product_data["productDescription"] = driver.find_element(By.ID, "productDescription").text.strip()
    except:
        product_data["productDescription"] = ""

    # Product Info Table - Try multiple locations for product information
    product_info = {}
    
    # Method 1: Try productOverview_feature_div (table format)
    try:
        overview_div = driver.find_element(By.ID, "productOverview_feature_div")
        rows = overview_div.find_elements(By.CSS_SELECTOR, "table tr")
        for row in rows:
            tds = row.find_elements(By.TAG_NAME, "td")
            if len(tds) >= 2:
                k = tds[0].text.strip()
                value = tds[1].text.strip()
                product_info[k] = value
    except:
        pass
    
    # Method 2: Try detail-bullet-list (list format) - this is what your HTML shows
    try:
        bullet_list = driver.find_element(By.CSS_SELECTOR, ".detail-bullet-list")
        list_items = bullet_list.find_elements(By.TAG_NAME, "li")
        for item in list_items:
            try:
                # Get the full item text
                full_item_text = item.text.strip()
                
                # Get all spans in the item
                spans = item.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 2:
                    # Look for the bold span with the key
                    bold_span = item.find_element(By.CSS_SELECTOR, ".a-text-bold")
                    bold_text = bold_span.text.strip()
                    
                    # Clean up the key (remove colons, special characters, and extra spaces)
                    key = bold_text.replace(":", "").replace("‏", "").replace("‎", "").strip()
                    
                    # Method 1: Extract value by removing bold text from full text
                    if bold_text in full_item_text:
                        value = full_item_text.replace(bold_text, "").strip()
                        # Clean up the value
                        value = value.replace(":", "").replace("‏", "").replace("‎", "").strip()
                    else:
                        # Method 2: Get the value from non-bold spans
                        value_spans = item.find_elements(By.CSS_SELECTOR, "span:not(.a-text-bold)")
                        value = ""
                        for span in value_spans:
                            span_text = span.text.strip()
                            # Skip empty spans and spans that just contain special characters
                            if span_text and span_text not in [":", "‏", "‎", ""]:
                                value = span_text
                                break
                    
                    # Only add if we have both key and value, and key is not empty
                    if key and value and len(key) > 1 and value not in [":", "‏", "‎"]:
                        product_info[key] = value
                        print(f"Extracted: '{key}' = '{value}'")  # Debug print
            except Exception as e:
                print(f"Error processing item: {e}")  # Debug print
                continue
    except Exception as e:
        print(f"Error finding bullet list: {e}")  # Debug print
        pass
    
    # Method 3: Try alternative selectors for product details
    try:
        # Look for any element with product details
        detail_elements = driver.find_elements(By.CSS_SELECTOR, "#detailBullets_feature_div li, #detail-bullets li, .detail-bullet-list li")
        for element in detail_elements:
            try:
                text = element.text.strip()
                if ":" in text and len(text.split(":")) >= 2:
                    parts = text.split(":", 1)
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key and value:
                        product_info[key] = value
            except:
                continue
    except:
        pass
    
    # Method 4: Try specific manufacturer extraction with better logic
    manufacturer = ""
    try:
        # Look for manufacturer in the bullet list specifically
        bullet_items = driver.find_elements(By.CSS_SELECTOR, ".detail-bullet-list li, #detailBullets_feature_div li")
        for item in bullet_items:
            try:
                # Get the full item text first
                full_item_text = item.text.strip()
                
                # Get the bold text (key)
                bold_element = item.find_element(By.CSS_SELECTOR, ".a-text-bold")
                bold_text = bold_element.text.strip()
                
                # Check if this is specifically the manufacturer field (case insensitive)
                if "manufacturer" in bold_text.lower() and "discontinued" not in bold_text.lower():
                    # Method A: Try to get value by removing the bold text from full text
                    if bold_text in full_item_text:
                        remaining_text = full_item_text.replace(bold_text, "").strip()
                        # Clean up remaining text - remove colons and special characters
                        remaining_text = remaining_text.replace(":", "").replace("‏", "").replace("‎", "").strip()
                        
                        if remaining_text and len(remaining_text) > 2 and remaining_text not in ["No", "Yes", "N/A"]:
                            manufacturer = remaining_text
                            print(f"Method A - Found manufacturer: {manufacturer}")  # Debug print
                            break
                    
                    # Method B: Try to get from non-bold spans as fallback
                    if not manufacturer:
                        value_spans = item.find_elements(By.CSS_SELECTOR, "span:not(.a-text-bold)")
                        for span in value_spans:
                            span_text = span.text.strip()
                            # Clean up span text
                            span_text = span_text.replace(":", "").replace("‏", "").replace("‎", "").strip()
                            
                            if span_text and span_text not in ["", "No", "Yes", "N/A"] and len(span_text) > 2:
                                manufacturer = span_text
                                print(f"Method B - Found manufacturer: {manufacturer}")  # Debug print
                                break
                    
                    if manufacturer:
                        break
            except Exception as inner_e:
                print(f"Error processing manufacturer item: {inner_e}")  # Debug print
                continue
    except Exception as e:
        print(f"Error extracting manufacturer: {e}")  # Debug print
        pass
    
    # Add manufacturer to product_info if found
    if manufacturer:
        product_info["Manufacturer"] = manufacturer
    
    product_data["productInformation"] = product_info

    # Manufacturer - try multiple sources with better validation and cleaning
    final_manufacturer = ""
    
    # Try to get from product_info with validation and cleaning
    if product_info.get("Manufacturer"):
        manufacturer_value = product_info["Manufacturer"]
        # Clean up manufacturer value - remove any remaining label text
        manufacturer_value = manufacturer_value.replace("Manufacturer", "").replace(":", "").strip()
        if manufacturer_value and manufacturer_value not in ["No", "Yes", "N/A", ""]:
            final_manufacturer = manufacturer_value
    
    # Fallback to Brand if manufacturer not found
    if not final_manufacturer and product_info.get("Brand"):
        brand_value = product_info["Brand"]
        # Clean up brand value
        brand_value = brand_value.replace("Brand", "").replace(":", "").strip()
        if brand_value and brand_value not in ["No", "Yes", "N/A", ""]:
            final_manufacturer = brand_value
    
    # Fallback to extracted manufacturer variable
    if not final_manufacturer and manufacturer:
        # Clean up manufacturer variable
        cleaned_manufacturer = manufacturer.replace("Manufacturer", "").replace(":", "").strip()
        if cleaned_manufacturer and cleaned_manufacturer not in ["No", "Yes", "N/A", ""]:
            final_manufacturer = cleaned_manufacturer
    
    product_data["manufacturer"] = final_manufacturer
    
    print(f"Final manufacturer set to: '{final_manufacturer}'")  # Debug print

    # Date First Available
    product_data["date_first_available"] = (
        product_info.get("Date First Available", "") or
        product_info.get("Date first available", "") or
        ""
    )

    try:
        symbol = ""
        whole = ""
        fraction = ""

        try:
            symbol = driver.find_element(By.CSS_SELECTOR, ".a-price-symbol").text.strip()
        except:
            pass

        try:
            whole = driver.find_element(By.CSS_SELECTOR, ".a-price-whole").text.strip()
        except:
            pass

        try:
            fraction = driver.find_element(By.CSS_SELECTOR, ".a-price-fraction").text.strip()
        except:
            pass

        if whole:  # If at least whole number exists
            # Remove any commas in whole
            whole_clean = whole.replace(",", "")
            if fraction:
                product_data["currentPrice"] = f"{whole_clean}.{fraction}"
            else:
                product_data["currentPrice"] = f"{whole_clean}"
        else:
            # Fallback to offscreen price (text already combined)
            try:
                product_data["currentPrice"] = driver.find_element(By.CSS_SELECTOR, ".a-price .a-offscreen").text.strip().replace("$", "")
            except:
                product_data["currentPrice"] = ""
    except Exception as e:
        print("Price extraction error:", e)
        product_data["currentPrice"] = ""


    # Rating
    try:
        product_data["rating"] = driver.find_element(By.CSS_SELECTOR, ".a-icon-alt").text.strip()
    except:
        product_data["rating"] = ""

    # Total Ratings
    try:
        product_data["totalRatings"] = driver.find_element(By.ID, "acrCustomerReviewText").text.strip()
    except:
        product_data["totalRatings"] = ""

    # Flags heuristics
    product_data["amazon_choice"] = bool(driver.find_elements(By.ID, "acBadge_feature_div"))
    product_data["best_seller"] = bool(driver.find_elements(By.CSS_SELECTOR, ".best-seller-badge"))
    product_data["free_delivery"] = bool(driver.find_elements(By.CSS_SELECTOR, ".freeShipping"))
    product_data["amazon_deleted"] = False

    # User Information & SEED (static)
    product_data["UserInformation"] = {
        "Login_Name": "Test Manager",
        "email": "",
        "velocity_user_id": 125,
        "role": "Manager",
        "source": "Velocity"
    }
    product_data["SEED"] = "Amazon"

    driver.quit()
    return product_data


import streamlit as st
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime
import zipfile
import io

# Set page config
st.set_page_config(
    page_title="Amazon Review Parser",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def parse_reviews_from_html_content(html_content, page_number):
    """Parse Amazon reviews from HTML content using BeautifulSoup"""
    
    if not html_content or len(html_content.strip()) < 100:
        return []
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find reviews using multiple selectors
    reviews_data = []
    
    # Try different selectors to find review containers
    review_selectors = [
        "li[data-hook='review']",
        "[data-hook='review']",
        ".review.aok-relative",
        "div[data-cel-widget*='customer_review']"
    ]
    
    reviews = []
    selected_selector = None
    for selector in review_selectors:
        found_reviews = soup.select(selector)
        if found_reviews:
            reviews = found_reviews
            selected_selector = selector
            break
    
    if not reviews:
        # Look for any elements that might contain review data
        potential_reviews = soup.find_all(attrs={'data-hook': lambda x: x and 'review' in x})
        if potential_reviews:
            reviews = potential_reviews
            selected_selector = "data-hook containing 'review'"
    
    if not reviews:
        return []
    
    # Extract data from each review
    for i, review in enumerate(reviews):
        try:
            # Extract reviewer name
            reviewerName = None
            reviewer_selectors = [
                "span.a-profile-name",
                ".a-profile-name",
                "[data-hook='review-author']",
                ".a-profile .a-profile-name"
            ]
            
            for selector in reviewer_selectors:
                reviewer_element = review.select_one(selector)
                if reviewer_element:
                    reviewerName = reviewer_element.get_text(strip=True)
                    if reviewerName:
                        break
            
            # Extract title
            reviewTitle = None
            title_selectors = [
                "a[data-hook='review-title'] span",
                "a[data-hook='review-title']",
                "[data-hook='review-title']",
                ".review-title",
                "h4 a span",
                "h4 span"
            ]
            
            for selector in title_selectors:
                title_element = review.select_one(selector)
                if title_element:
                    reviewTitle = title_element.get_text(strip=True)
                    if reviewTitle:
                        break
            
            # Extract rating
            rating = None
            rating_selectors = [
                "i[data-hook*='star-rating'] span",
                "i[data-hook*='star-rating']",
                ".a-icon-star span",
                "[class*='star'] span",
                "i.a-icon-star span.a-icon-alt"
            ]
            
            for selector in rating_selectors:
                rating_element = review.select_one(selector)
                if rating_element:
                    rating_text = rating_element.get_text(strip=True)
                    if rating_text and ("star" in rating_text.lower() or "out of" in rating_text.lower()):
                        rating = rating_text
                        break
            
            # Extract review body
            reviewText = None
            body_selectors = [
                "span[data-hook='review-body'] span",
                "span[data-hook='review-body']",
                "[data-hook='review-body']",
                ".review-text",
                ".review-body"
            ]
            
            for selector in body_selectors:
                body_element = review.select_one(selector)
                if body_element:
                    # Get the last span child if it exists, otherwise get the element text
                    spans = body_element.select('span')
                    if spans:
                        # Try to get the span with the actual review content
                        for span in reversed(spans):
                            span_text = span.get_text(strip=True)
                            if span_text and len(span_text) > 20:
                                reviewText = span_text
                                break
                    if not reviewText:
                        reviewText = body_element.get_text(strip=True)
                    if reviewText and len(reviewText) > 10:
                        break
            
            # Extract date
            reviewDate = None
            date_selectors = [
                "span[data-hook='review-date']",
                "[data-hook='review-date']",
                ".review-date",
                ".a-color-secondary.review-date"
            ]
            
            for selector in date_selectors:
                date_element = review.select_one(selector)
                if date_element:
                    reviewDate = date_element.get_text(strip=True)
                    if reviewDate:
                        break
            
            # Clean up the extracted data
            if reviewTitle:
                reviewTitle = reviewTitle.replace('\n', ' ').replace('\r', ' ').strip()
                # Remove common prefixes
                if reviewTitle.startswith('5.0 out of 5 stars'):
                    reviewTitle = reviewTitle.replace('5.0 out of 5 stars', '').strip()
                elif reviewTitle.startswith('4.0 out of 5 stars'):
                    reviewTitle = reviewTitle.replace('4.0 out of 5 stars', '').strip()
                elif reviewTitle.startswith('3.0 out of 5 stars'):
                    reviewTitle = reviewTitle.replace('3.0 out of 5 stars', '').strip()
                elif reviewTitle.startswith('2.0 out of 5 stars'):
                    reviewTitle = reviewTitle.replace('2.0 out of 5 stars', '').strip()
                elif reviewTitle.startswith('1.0 out of 5 stars'):
                    reviewTitle = reviewTitle.replace('1.0 out of 5 stars', '').strip()
            
            if reviewText:
                reviewText = reviewText.replace('\n', ' ').replace('\r', ' ').strip()
            if reviewDate:
                reviewDate = reviewDate.replace('\n', ' ').replace('\r', ' ').strip()
            if rating:
                rating = rating.replace('\n', ' ').replace('\r', ' ').strip()
            if reviewerName:
                reviewerName = reviewerName.replace('\n', ' ').replace('\r', ' ').strip()
            
            # Only add review if we have meaningful content
            if (reviewTitle and len(reviewTitle) > 3) or (reviewText and len(reviewText) > 10):
                review_data = {
                    "reviewerName": reviewerName or "",
                    "rating": rating or "",
                    "reviewTitle": reviewTitle or "",
                    "reviewDate": reviewDate or "",
                    "reviewText": reviewText or "",
                    "source_page": page_number
                }
                
                reviews_data.append(review_data)
        
        except Exception as e:
            st.warning(f"Error processing review {i+1} on page {page_number}: {str(e)}")
            continue
    
    return reviews_data


def create_product_json(asin, all_reviews):
    # Fetch metadata from Amazon
    product_data = fetch_product_metadata(asin, zip_code="10001")

    # Add reviews & summary
    product_data["reviews"] = all_reviews
    product_data["UserInformation"] = {
        "Login_Name": "Streamlit User",
        "email": "",
        "velocity_user_id": 0,
        "role": "User",
        "source": "Streamlit"
    }
    product_data["SEED"] = "Amazon"
    product_data["parsing_summary"] = {
        "total_reviews_parsed": len(all_reviews),
        "reviews_per_page": {},
        "parsing_timestamp": datetime.now().isoformat(),
        "rating_distribution": {}  # keep your logic for counts
    }
    return product_data


# Custom CSS for better JSON display
def inject_custom_css():
    st.markdown("""
    <style>
    .json-container {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        max-height: 400px;
        overflow-y: auto;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 12px;
        line-height: 1.4;
    }
    
    .json-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #dee2e6;
    }
    
    .copy-button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .copy-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .stat-value {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    </style>
    """, unsafe_allow_html=True)


# Copy to clipboard functionality
def copy_json_script(json_string):
    return f"""
    <script>
    function copyToClipboard() {{
        const jsonText = {json.dumps(json_string)};
        navigator.clipboard.writeText(jsonText).then(function() {{
            alert('JSON copied to clipboard!');
        }}, function(err) {{
            console.error('Could not copy text: ', err);
            // Fallback for older browsers
            const textArea = document.createElement("textarea");
            textArea.value = jsonText;
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                document.execCommand('copy');
                alert('JSON copied to clipboard!');
            }} catch (err) {{
                console.error('Fallback: Could not copy text: ', err);
            }}
            document.body.removeChild(textArea);
        }});
    }}
    </script>
    <button onclick="copyToClipboard()" class="copy-button">📋 Copy JSON to Clipboard</button>
    """


# Streamlit UI
def main():
    inject_custom_css()
    
    st.title("🛍️ Amazon Review Parser")
    st.markdown("Upload Amazon review page HTML files to extract and parse reviews into JSON format")
    
    # Sidebar for instructions
    with st.sidebar:
        st.header("📋 Instructions")
        st.markdown("""
        1. **Enter ASIN**: Product identifier from Amazon
        2. **Paste HTML content**: Copy-paste HTML from Amazon review pages
        3. **Click Parse**: Process all content
        4. **View Full JSON**: See complete parsed data
        5. **Copy/Download**: Get your JSON file
        
        ### 💡 How to get HTML:
        - Go to Amazon reviews page
        - Right-click → "View Page Source" (or Ctrl+U)
        - Select all (Ctrl+A) and copy (Ctrl+C)
        - Paste into the text boxes below
        - Repeat for up to 5 different review pages
        """)
        
        st.header("🔍 About")
        st.markdown("""
        This tool parses Amazon review pages and extracts:
        - Reviewer names
        - Ratings (stars)
        - Review titles
        - Review text
        - Review dates
        - Page source tracking
        - Product metadata
        """)
    
    # Main content area
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("⚙️ Configuration")
        
        # ASIN input
        asin = st.text_input(
            "Enter ASIN",
            placeholder="e.g., B00RF3TLIC",
            help="Amazon Standard Identification Number"
        ).strip()
        
        if asin:
            st.success(f"ASIN: {asin}")
            st.info(f"Product URL: https://www.amazon.com/dp/{asin}")
    
    with col2:
        st.header("📝 Paste HTML Content")
        
        # HTML content input boxes
        html_contents = {}
        
        for i in range(1, 6):
            html_content = st.text_area(
                f"Review Page HTML {i}",
                placeholder=f"Paste the HTML content of review page {i} here...\n\nTo get HTML content:\n1. Go to Amazon reviews page\n2. Right-click → 'View Page Source' or press Ctrl+U\n3. Select all (Ctrl+A) and copy (Ctrl+C)\n4. Paste here",
                height=150,
                key=f"html_{i}",
                help=f"Paste HTML source code for review page {i}"
            )
            if html_content and html_content.strip():
                html_contents[i] = html_content.strip()
        
        st.info(f"📄 Pages with content: {len(html_contents)}")
    
    # Show content details
    if html_contents:
        st.header("📊 Content Details")
        content_cols = st.columns(min(len(html_contents), 5))
        for idx, (page_num, content) in enumerate(html_contents.items()):
            if idx < len(content_cols):
                with content_cols[idx]:
                    content_size = len(content)
                    st.metric(
                        f"Page {page_num}", 
                        f"{content_size:,} chars",
                        help=f"HTML content length for page {page_num}"
                    )
                    # Show a preview of the content
                    preview = content[:100] + "..." if len(content) > 100 else content
                    with st.expander(f"Preview Page {page_num}"):
                        st.code(preview, language="html")
    
    # Parse button and processing
    if st.button("🚀 Parse Reviews", type="primary", disabled=not (asin and html_contents)):
        if not asin:
            st.error("Please enter an ASIN")
            return
        
        if not html_contents:
            st.error("Please paste HTML content for at least one review page")
            return
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_reviews = []
        parsing_stats = {}
        
        # Process each HTML content
        for i, (page_num, html_content) in enumerate(html_contents.items()):
            status_text.text(f"Processing page {page_num}...")
            progress_bar.progress((i + 1) / len(html_contents))
            
            try:
                # Parse reviews directly from content
                page_reviews = parse_reviews_from_html_content(html_content, page_num)
                all_reviews.extend(page_reviews)
                
                parsing_stats[f"page_{page_num}"] = {
                    "reviews_found": len(page_reviews),
                    "content_size": len(html_content),
                    "source": "pasted_content"
                }
                
                st.success(f"✅ Page {page_num}: Found {len(page_reviews)} reviews")
                
            except Exception as e:
                st.error(f"❌ Error processing page {page_num}: {str(e)}")
                parsing_stats[f"page_{page_num}"] = {
                    "reviews_found": 0,
                    "error": str(e),
                    "source": "pasted_content"
                }
        
        status_text.text("Creating final JSON...")
        
        # Calculate rating distribution
        rating_counts = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        total_ratings = 0
        
        for review in all_reviews:
            rating_text = review.get("rating", "")
            if "5.0" in rating_text or "5 out" in rating_text:
                rating_counts["5"] += 1
                total_ratings += 1
            elif "4.0" in rating_text or "4 out" in rating_text:
                rating_counts["4"] += 1
                total_ratings += 1
            elif "3.0" in rating_text or "3 out" in rating_text:
                rating_counts["3"] += 1
                total_ratings += 1
            elif "2.0" in rating_text or "2 out" in rating_text:
                rating_counts["2"] += 1
                total_ratings += 1
            elif "1.0" in rating_text or "1 out" in rating_text:
                rating_counts["1"] += 1
                total_ratings += 1
        
        # Create final product JSON
        product_data = create_product_json(asin, all_reviews)
        product_data["parsing_summary"]["reviews_per_page"] = parsing_stats
        product_data["parsing_summary"]["rating_distribution"] = rating_counts
        
        # Display results
        st.header("🎉 Parsing Complete!")
        
        # Enhanced statistics display
        st.markdown('<div class="stats-grid">', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'''
            <div class="stat-card">
                <div class="stat-value">{len(all_reviews)}</div>
                <div class="stat-label">Total Reviews</div>
            </div>
            ''', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'''
            <div class="stat-card">
                <div class="stat-value">{len(html_contents)}</div>
                <div class="stat-label">Pages Processed</div>
            </div>
            ''', unsafe_allow_html=True)
        
        with col3:
            avg_per_page = len(all_reviews) / len(html_contents) if html_contents else 0
            st.markdown(f'''
            <div class="stat-card">
                <div class="stat-value">{avg_per_page:.1f}</div>
                <div class="stat-label">Avg Reviews/Page</div>
            </div>
            ''', unsafe_allow_html=True)
        
        with col4:
            st.markdown(f'''
            <div class="stat-card">
                <div class="stat-value">{total_ratings}</div>
                <div class="stat-label">Rated Reviews</div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Show parsing breakdown
        st.subheader("📈 Parsing Breakdown")
        breakdown_data = []
        for page_num, content in html_contents.items():
            page_key = f"page_{page_num}"
            if page_key in parsing_stats:
                breakdown_data.append({
                    "Page": page_num,
                    "Reviews Found": parsing_stats[page_key]["reviews_found"],
                    "Content Size": f"{parsing_stats[page_key].get('content_size', 0):,} characters",
                    "Status": "✅ Success" if parsing_stats[page_key]["reviews_found"] > 0 else "⚠️ No reviews found"
                })
        
        if breakdown_data:
            st.dataframe(breakdown_data, use_container_width=True)
        
        # Rating distribution
        if any(count > 0 for count in rating_counts.values()):
            st.subheader("⭐ Rating Distribution")
            rating_col1, rating_col2 = st.columns([1, 2])
            
            with rating_col1:
                for rating, count in rating_counts.items():
                    if count > 0:
                        st.metric(f"{rating} Stars", count)
            
            with rating_col2:
                # Create a simple bar chart using st.bar_chart
                rating_df = {
                    "Rating": [f"{r} Stars" for r, c in rating_counts.items() if c > 0],
                    "Count": [c for c in rating_counts.values() if c > 0]
                }
                if rating_df["Count"]:
                    import pandas as pd
                    df = pd.DataFrame(rating_df)
                    st.bar_chart(df.set_index("Rating"))
        
        # Show sample reviews
        if all_reviews:
            st.subheader("📝 Sample Reviews")
            
            # Show first few reviews in an expandable section
            with st.expander(f"View Sample Reviews (showing first {min(3, len(all_reviews))} of {len(all_reviews)})"):
                for i, review in enumerate(all_reviews[:3]):
                    st.markdown(f"**Review {i+1}** (from page {review.get('source_page', 'unknown')})")
                    st.markdown(f"**Title:** {review.get('reviewTitle', 'N/A')}")
                    st.markdown(f"**Rating:** {review.get('rating', 'N/A')}")
                    st.markdown(f"**Author:** {review.get('reviewerName', 'N/A')}")
                    st.markdown(f"**Date:** {review.get('reviewDate', 'N/A')}")
                    st.markdown(f"**Review:** {review.get('reviewText', 'N/A')[:200]}...")
                    st.divider()
        
        # FULL JSON DISPLAY SECTION
        st.header("📋 Complete JSON Output")
        
        # Prepare JSON string
        json_string = json.dumps(product_data, indent=2, ensure_ascii=False)
        
        # JSON display with copy functionality
        st.markdown(
            f"""
            <div class="json-header">
                <h4>📄 Full JSON Data ({len(json_string):,} characters)</h4>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # Copy button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("📋 Copy Full JSON", type="secondary", help="Copy the complete JSON to clipboard"):
                # Use st.code to display and allow easy copying
                st.success("✅ Click the copy icon in the code block below to copy!")
        
        # Display full JSON in a code block (which has built-in copy functionality)
        st.code(json_string, language="json")
        
        # Alternative: Show JSON in expandable sections for better readability
        st.subheader("🔍 JSON Structure Explorer")
        
        # Product Information Section
        with st.expander("📦 Product Information", expanded=True):
            product_info = {
                "ASIN": product_data.get("ASIN", ""),
                "title": product_data.get("title", ""),
                "productURL": product_data.get("productURL", ""),
                "currentPrice": product_data.get("currentPrice", ""),
                "rating": product_data.get("rating", ""),
                "totalRatings": product_data.get("totalRatings", ""),
                "manufacturer": product_data.get("manufacturer", ""),
                "date_first_available": product_data.get("date_first_available", "")
            }
            st.json(product_info)
            if st.button("📋 Copy Product Info", key="copy_product"):
                st.code(json.dumps(product_info, indent=2), language="json")
        
        # Product Features and Description
        with st.expander("📝 Features & Description"):
            features_desc = {
                "features": product_data.get("features", []),
                "productDescription": product_data.get("productDescription", ""),
                "breadcrumb": product_data.get("breadcrumb", {}),
                "productInformation": product_data.get("productInformation", {})
            }
            st.json(features_desc)
            if st.button("📋 Copy Features", key="copy_features"):
                st.code(json.dumps(features_desc, indent=2), language="json")
        
        # Reviews Section
        with st.expander(f"⭐ Reviews Data ({len(all_reviews)} reviews)"):
            # Show reviews in batches for performance
            reviews_per_batch = 10
            total_batches = (len(all_reviews) + reviews_per_batch - 1) // reviews_per_batch
            
            if total_batches > 1:
                batch_num = st.selectbox(
                    "Select review batch to display:",
                    range(1, total_batches + 1),
                    format_func=lambda x: f"Reviews {(x-1)*reviews_per_batch + 1}-{min(x*reviews_per_batch, len(all_reviews))}"
                )
                start_idx = (batch_num - 1) * reviews_per_batch
                end_idx = min(start_idx + reviews_per_batch, len(all_reviews))
                reviews_to_show = all_reviews[start_idx:end_idx]
            else:
                reviews_to_show = all_reviews
            
            st.json(reviews_to_show)
            
            # Copy options for reviews
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 Copy Displayed Reviews", key="copy_reviews_batch"):
                    st.code(json.dumps(reviews_to_show, indent=2), language="json")
            with col2:
                if st.button("📋 Copy All Reviews", key="copy_all_reviews"):
                    st.code(json.dumps(all_reviews, indent=2), language="json")
        
        # Parsing Summary
        with st.expander("📊 Parsing Summary & Metadata"):
            summary_data = {
                "parsing_summary": product_data.get("parsing_summary", {}),
                "UserInformation": product_data.get("UserInformation", {}),
                "SEED": product_data.get("SEED", ""),
                "flags": {
                    "amazon_choice": product_data.get("amazon_choice", False),
                    "best_seller": product_data.get("best_seller", False),
                    "free_delivery": product_data.get("free_delivery", False),
                    "amazon_deleted": product_data.get("amazon_deleted", False)
                }
            }
            st.json(summary_data)
            if st.button("📋 Copy Summary", key="copy_summary"):
                st.code(json.dumps(summary_data, indent=2), language="json")
        
        # Download section
        st.header("💾 Download Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Single JSON download
            st.download_button(
                label="📥 Download Complete JSON",
                data=json_string,
                file_name=f"{asin}_complete_reviews.json",
                mime="application/json",
                help="Download the complete parsed data as JSON",
                type="primary"
            )
        
        with col2:
            # Reviews only JSON
            reviews_only_json = json.dumps(all_reviews, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download Reviews Only",
                data=reviews_only_json,
                file_name=f"{asin}_reviews_only.json",
                mime="application/json",
                help="Download only the reviews data as JSON"
            )
        
        with col3:
            # Create ZIP with multiple files
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add main JSON
                zip_file.writestr(f"{asin}_complete_data.json", json_string)
                
                # Add reviews only
                zip_file.writestr(f"{asin}_reviews_only.json", reviews_only_json)
                
                # Add product info only
                product_info_json = json.dumps({
                    k: v for k, v in product_data.items() 
                    if k not in ["reviews", "parsing_summary"]
                }, indent=2, ensure_ascii=False)
                zip_file.writestr(f"{asin}_product_info.json", product_info_json)
                
                # Add summary report
                summary_report = f"""Amazon Review Parsing Report
========================================
ASIN: {asin}
Product Title: {product_data.get('title', 'N/A')}
Product URL: {product_data.get('productURL', 'N/A')}
Parsing Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Reviews: {len(all_reviews)}
Pages Processed: {len(html_contents)}
Current Price: {product_data.get('currentPrice', 'N/A')}
Overall Rating: {product_data.get('rating', 'N/A')}
Total Ratings: {product_data.get('totalRatings', 'N/A')}

Page Breakdown:
{chr(10).join([f"- Page {k.replace('page_', '')}: {v['reviews_found']} reviews ({v.get('content_size', 0):,} characters)" for k, v in parsing_stats.items()])}

Rating Distribution:
{chr(10).join([f"- {rating} stars: {count} reviews" for rating, count in rating_counts.items() if count > 0])}

Product Features:
{chr(10).join([f"- {feature}" for feature in product_data.get('features', [])[:10]])}
{'... and more' if len(product_data.get('features', [])) > 10 else ''}

Flags:
- Amazon's Choice: {product_data.get('amazon_choice', False)}
- Best Seller: {product_data.get('best_seller', False)}
- Free Delivery: {product_data.get('free_delivery', False)}

Data Structure:
- Complete JSON: {len(json_string):,} characters
- Reviews Array: {len(all_reviews)} items
- Product Information: {len(product_data.get('productInformation', {}))} fields
- Features: {len(product_data.get('features', []))} items
"""
                zip_file.writestr("parsing_report.txt", summary_report)
            
            zip_buffer.seek(0)
            
            st.download_button(
                label="📦 Download Complete Package",
                data=zip_buffer.getvalue(),
                file_name=f"{asin}_complete_package.zip",
                mime="application/zip",
                help="Download everything: JSON files + summary report"
            )
        
        # Final success message with statistics
        st.success("✨ Processing complete!")
        
        # Quick stats summary
        st.info(f"""
        **📈 Final Summary:**
        - **{len(all_reviews)} reviews** extracted from **{len(html_contents)} pages**
        - **{total_ratings} reviews** have star ratings
        - **{len(json_string):,} characters** in complete JSON
        - **{len([r for r in all_reviews if r.get('reviewText') and len(r.get('reviewText', '')) > 100])} detailed reviews** (>100 characters)
        
        🎯 **Success Rate:** {(len(all_reviews) / sum(v['reviews_found'] for v in parsing_stats.values() if 'error' not in v) * 100) if any('error' not in v for v in parsing_stats.values()) else 100:.1f}% reviews successfully parsed
        """)

if __name__ == "__main__":
    main()
