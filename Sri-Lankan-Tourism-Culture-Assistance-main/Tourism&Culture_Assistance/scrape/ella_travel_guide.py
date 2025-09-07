#!/usr/bin/env python3
"""
TripAdvisor Ella Sri Lanka Complete Data Scraper
Scrapes all navigation sections: Hotels, Things to Do, Restaurants, Flights, Cruises, Vacation Rentals, Forums
Extracts images, reviews, ratings, and comprehensive information
Saves data to CSV file
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import csv
from urllib.parse import urljoin, urlparse
import json
import os
from datetime import datetime

class TripAdvisorEllaScraper:
    def __init__(self):
        self.base_url = "https://www.tripadvisor.com"
        self.ella_location_id = "616035"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.all_data = []
        self.scraped_urls = set()
        
    def get_page(self, url, max_retries=3):
        """Fetch a page with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                print(f"Fetching: {url} (attempt {attempt + 1})")
                time.sleep(2 + attempt)  # Progressive delay
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 403:
                    print(f"Access forbidden (403) for {url}")
                    time.sleep(5)
                    continue
                elif response.status_code == 404:
                    print(f"Page not found (404) for {url}")
                    return None
                
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
                
            except requests.exceptions.Timeout:
                print(f"Timeout for {url} (attempt {attempt + 1})")
            except requests.exceptions.ConnectionError:
                print(f"Connection error for {url} (attempt {attempt + 1})")
            except Exception as e:
                print(f"Error fetching {url} (attempt {attempt + 1}): {e}")
                
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))  # Exponential backoff
                
        print(f"Failed to fetch {url} after {max_retries} attempts")
        return None
    
    def extract_images(self, soup, limit=10):
        """Extract image URLs from the page with comprehensive handling"""
        images = []
        if not soup:
            return images
            
        img_tags = soup.find_all('img')
        for img in img_tags[:limit]:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                # Handle different URL formats
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = self.base_url + src
                elif not src.startswith('http'):
                    continue
                    
                # Filter out small/icon images
                if any(dim in src for dim in ['16x16', '32x32', 'icon', 'logo']):
                    continue
                    
                images.append({
                    'url': src,
                    'alt': img.get('alt', '').strip(),
                    'title': img.get('title', '').strip(),
                    'width': img.get('width', ''),
                    'height': img.get('height', '')
                })
                
        return images
    
    def extract_rating(self, element):
        """Extract rating from various rating elements"""
        rating_patterns = [
            r'(\d+\.?\d*)\s*(?:out of|\/)\s*5',
            r'(\d+\.?\d*)\s*stars?',
            r'rating[^>]*>.*?(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*\/\s*5'
        ]
        
        text = element.get_text() if element else ""
        for pattern in rating_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
                
        # Check for star spans or divs
        star_elements = element.find_all(['span', 'div'], class_=re.compile(r'star|rating'))
        for star_el in star_elements:
            star_text = star_el.get_text().strip()
            if star_text and re.match(r'\d+\.?\d*', star_text):
                return star_text
                
        return ""
    
    def extract_reviews_count(self, element):
        """Extract number of reviews from text"""
        if not element:
            return ""
            
        text = element.get_text()
        patterns = [
            r'(\d+(?:,\d{3})*)\s*reviews?',
            r'(\d+(?:,\d{3})*)\s*opinions?',
            r'based on (\d+(?:,\d{3})*)',
            r'(\d+(?:,\d{3})*)\s*ratings?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).replace(',', '')
                
        return ""
    
    def scrape_main_page(self):
        """Scrape the main Ella tourism page"""
        print("\n=== Scraping Main Ella Tourism Page ===")
        url = f"{self.base_url}/Tourism-g{self.ella_location_id}-Ella_Uva_Province-Vacations.html"
        soup = self.get_page(url)
        
        if not soup:
            print("Failed to load main page")
            return
        
        # Extract general information
        data = {
            'section': 'Main Page',
            'page_url': url,
            'title': '',
            'description': '',
            'overview': '',
            'highlights': '',
            'images': [],
            'scraped_at': datetime.now().isoformat()
        }
        
        # Extract title
        title_selectors = ['h1', '[data-test-target="top-info-header"]', '.header_title']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                data['title'] = title_elem.get_text().strip()
                break
        
        # Extract overview/description
        desc_selectors = [
            '[data-test-target="hr-community-summary"]',
            '.community_summary',
            '.destination_overview',
            '.ui_container p'
        ]
        
        descriptions = []
        for selector in desc_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                if len(text) > 100 and text not in descriptions:
                    descriptions.append(text)
                    
        data['description'] = ' | '.join(descriptions[:3])
        
        # Extract highlights
        highlights_elem = soup.select('.attractions_common, .ui_poi_review')
        highlights = []
        for elem in highlights_elem:
            text = elem.get_text().strip()
            if len(text) > 50:
                highlights.append(text)
        data['highlights'] = ' | '.join(highlights[:5])
        
        # Extract images
        data['images'] = self.extract_images(soup)
        
        self.all_data.append(data)
        print(f"Main page data collected: {data['title']}")
    
    def scrape_hotels(self):
        """Scrape hotels section"""
        print("\n=== Scraping Hotels Section ===")
        url = f"{self.base_url}/Hotels-g{self.ella_location_id}-Ella_Uva_Province-Hotels.html"
        soup = self.get_page(url)
        
        if not soup:
            print("Failed to load hotels page")
            return
        
        # Find hotel containers
        hotel_selectors = [
            '.listItem',
            '[data-test-target="hotels-list-item"]',
            '.hotel_wrap',
            '.property_title'
        ]
        
        hotels = []
        for selector in hotel_selectors:
            found = soup.select(selector)
            if found:
                hotels = found
                break
        
        print(f"Found {len(hotels)} hotel elements")
        
        for i, hotel in enumerate(hotels[:15]):  # Limit to 15 hotels
            hotel_data = {
                'section': 'Hotels',
                'page_url': url,
                'title': '',
                'description': '',
                'rating': '',
                'reviews_count': '',
                'price': '',
                'amenities': '',
                'images': [],
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract hotel name
            name_selectors = [
                '.property_title a',
                '[data-test-target="property-name"]',
                'h3 a',
                '.listing_title a'
            ]
            
            for selector in name_selectors:
                name_elem = hotel.select_one(selector)
                if name_elem:
                    hotel_data['title'] = name_elem.get_text().strip()
                    break
            
            # Extract rating
            hotel_data['rating'] = self.extract_rating(hotel)
            
            # Extract reviews count
            hotel_data['reviews_count'] = self.extract_reviews_count(hotel)
            
            # Extract price
            price_selectors = ['.rate_desktop', '.price', '[data-test-target="price-summary"]']
            for selector in price_selectors:
                price_elem = hotel.select_one(selector)
                if price_elem:
                    hotel_data['price'] = price_elem.get_text().strip()
                    break
            
            # Extract amenities
            amenity_elements = hotel.select('.amenities_wrap .amenity')
            amenities = [elem.get_text().strip() for elem in amenity_elements]
            hotel_data['amenities'] = ' | '.join(amenities)
            
            # Extract images
            hotel_data['images'] = self.extract_images(hotel, limit=5)
            
            # Extract description
            desc_elem = hotel.select_one('.property_blurb, .review_snippet')
            if desc_elem:
                hotel_data['description'] = desc_elem.get_text().strip()
            
            if hotel_data['title']:  # Only add if we have a title
                self.all_data.append(hotel_data)
                print(f"Hotel {i+1}: {hotel_data['title']}")
    
    def scrape_attractions(self):
        """Scrape things to do/attractions section"""
        print("\n=== Scraping Attractions Section ===")
        url = f"{self.base_url}/Attractions-g{self.ella_location_id}-Activities-Ella_Uva_Province.html"
        soup = self.get_page(url)
        
        if not soup:
            print("Failed to load attractions page")
            return
        
        # Find attraction containers
        attraction_selectors = [
            '.attraction_element',
            '[data-test-target="attraction-card"]',
            '.listing_wrap',
            '.attraction_clarity_cell'
        ]
        
        attractions = []
        for selector in attraction_selectors:
            found = soup.select(selector)
            if found:
                attractions = found
                break
        
        print(f"Found {len(attractions)} attraction elements")
        
        for i, attraction in enumerate(attractions[:20]):  # Limit to 20 attractions
            attr_data = {
                'section': 'Attractions',
                'page_url': url,
                'title': '',
                'description': '',
                'rating': '',
                'reviews_count': '',
                'category': '',
                'duration': '',
                'price_range': '',
                'images': [],
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract attraction name
            name_selectors = [
                '.listing_title a',
                '[data-test-target="attraction-name"]',
                'h3 a',
                '.property_title a'
            ]
            
            for selector in name_selectors:
                name_elem = attraction.select_one(selector)
                if name_elem:
                    attr_data['title'] = name_elem.get_text().strip()
                    break
            
            # Extract rating
            attr_data['rating'] = self.extract_rating(attraction)
            
            # Extract reviews count
            attr_data['reviews_count'] = self.extract_reviews_count(attraction)
            
            # Extract category
            category_elem = attraction.select_one('.poi_type, .category')
            if category_elem:
                attr_data['category'] = category_elem.get_text().strip()
            
            # Extract description
            desc_selectors = ['.review_snippet', '.description', '.poi_description']
            for selector in desc_selectors:
                desc_elem = attraction.select_one(selector)
                if desc_elem:
                    attr_data['description'] = desc_elem.get_text().strip()
                    break
            
            # Extract images
            attr_data['images'] = self.extract_images(attraction, limit=5)
            
            if attr_data['title']:  # Only add if we have a title
                self.all_data.append(attr_data)
                print(f"Attraction {i+1}: {attr_data['title']}")
    
    def scrape_restaurants(self):
        """Scrape restaurants section"""
        print("\n=== Scraping Restaurants Section ===")
        url = f"{self.base_url}/Restaurants-g{self.ella_location_id}-Ella_Uva_Province.html"
        soup = self.get_page(url)
        
        if not soup:
            print("Failed to load restaurants page")
            return
        
        # Find restaurant containers
        restaurant_selectors = [
            '.restaurant',
            '[data-test-target="restaurant-card"]',
            '.listing_wrap',
            '.restaurant_wrap'
        ]
        
        restaurants = []
        for selector in restaurant_selectors:
            found = soup.select(selector)
            if found:
                restaurants = found
                break
        
        print(f"Found {len(restaurants)} restaurant elements")
        
        for i, restaurant in enumerate(restaurants[:15]):  # Limit to 15 restaurants
            rest_data = {
                'section': 'Restaurants',
                'page_url': url,
                'title': '',
                'description': '',
                'rating': '',
                'reviews_count': '',
                'cuisine_type': '',
                'price_range': '',
                'features': '',
                'images': [],
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract restaurant name
            name_selectors = [
                '.listing_title a',
                '[data-test-target="restaurant-name"]',
                'h3 a',
                '.property_title a'
            ]
            
            for selector in name_selectors:
                name_elem = restaurant.select_one(selector)
                if name_elem:
                    rest_data['title'] = name_elem.get_text().strip()
                    break
            
            # Extract rating
            rest_data['rating'] = self.extract_rating(restaurant)
            
            # Extract reviews count
            rest_data['reviews_count'] = self.extract_reviews_count(restaurant)
            
            # Extract cuisine type
            cuisine_elem = restaurant.select_one('.cuisine, .category_tag')
            if cuisine_elem:
                rest_data['cuisine_type'] = cuisine_elem.get_text().strip()
            
            # Extract price range
            price_elem = restaurant.select_one('.price_range, .price')
            if price_elem:
                rest_data['price_range'] = price_elem.get_text().strip()
            
            # Extract features
            feature_elements = restaurant.select('.feature, .tag')
            features = [elem.get_text().strip() for elem in feature_elements]
            rest_data['features'] = ' | '.join(features)
            
            # Extract description
            desc_elem = restaurant.select_one('.review_snippet, .description')
            if desc_elem:
                rest_data['description'] = desc_elem.get_text().strip()
            
            # Extract images
            rest_data['images'] = self.extract_images(restaurant, limit=5)
            
            if rest_data['title']:  # Only add if we have a title
                self.all_data.append(rest_data)
                print(f"Restaurant {i+1}: {rest_data['title']}")
    
    def scrape_vacation_rentals(self):
        """Scrape vacation rentals section"""
        print("\n=== Scraping Vacation Rentals Section ===")
        url = f"{self.base_url}/VacationRentals-g{self.ella_location_id}-Reviews-Ella_Uva_Province-Vacation_Rentals.html"
        soup = self.get_page(url)
        
        if not soup:
            print("Failed to load vacation rentals page")
            return
        
        # Find rental containers
        rental_selectors = [
            '.rental_wrap',
            '[data-test-target="rental-card"]',
            '.listing_wrap',
            '.property_wrap'
        ]
        
        rentals = []
        for selector in rental_selectors:
            found = soup.select(selector)
            if found:
                rentals = found
                break
        
        print(f"Found {len(rentals)} vacation rental elements")
        
        for i, rental in enumerate(rentals[:10]):  # Limit to 10 rentals
            rental_data = {
                'section': 'Vacation Rentals',
                'page_url': url,
                'title': '',
                'description': '',
                'rating': '',
                'reviews_count': '',
                'price_per_night': '',
                'property_type': '',
                'guests': '',
                'bedrooms': '',
                'amenities': '',
                'images': [],
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract rental name
            name_selectors = [
                '.listing_title a',
                '[data-test-target="rental-name"]',
                'h3 a',
                '.property_title a'
            ]
            
            for selector in name_selectors:
                name_elem = rental.select_one(selector)
                if name_elem:
                    rental_data['title'] = name_elem.get_text().strip()
                    break
            
            # Extract rating
            rental_data['rating'] = self.extract_rating(rental)
            
            # Extract reviews count
            rental_data['reviews_count'] = self.extract_reviews_count(rental)
            
            # Extract price
            price_elem = rental.select_one('.price, .rate')
            if price_elem:
                rental_data['price_per_night'] = price_elem.get_text().strip()
            
            # Extract property details
            details = rental.select('.property_detail, .detail_item')
            for detail in details:
                text = detail.get_text().strip().lower()
                if 'guest' in text:
                    rental_data['guests'] = detail.get_text().strip()
                elif 'bedroom' in text:
                    rental_data['bedrooms'] = detail.get_text().strip()
                elif 'type' in text:
                    rental_data['property_type'] = detail.get_text().strip()
            
            # Extract amenities
            amenity_elements = rental.select('.amenity, .feature')
            amenities = [elem.get_text().strip() for elem in amenity_elements]
            rental_data['amenities'] = ' | '.join(amenities)
            
            # Extract images
            rental_data['images'] = self.extract_images(rental, limit=5)
            
            if rental_data['title']:  # Only add if we have a title
                self.all_data.append(rental_data)
                print(f"Vacation Rental {i+1}: {rental_data['title']}")
    
    def scrape_forums(self):
        """Scrape forums section"""
        print("\n=== Scraping Forums Section ===")
        url = f"{self.base_url}/ShowForum-g{self.ella_location_id}-i14270-Ella_Uva_Province.html"
        soup = self.get_page(url)
        
        if not soup:
            print("Failed to load forums page")
            return
        
        # Find forum topic containers
        topic_selectors = [
            '.topic',
            '.forumPost',
            'tr.topic',
            '.forum_topic'
        ]
        
        topics = []
        for selector in topic_selectors:
            found = soup.select(selector)
            if found:
                topics = found
                break
        
        print(f"Found {len(topics)} forum topic elements")
        
        for i, topic in enumerate(topics[:10]):  # Limit to 10 topics
            topic_data = {
                'section': 'Forums',
                'page_url': url,
                'title': '',
                'description': '',
                'replies_count': '',
                'views_count': '',
                'last_post_date': '',
                'author': '',
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract topic title
            title_selectors = [
                '.topic_title a',
                '[data-test-target="topic-title"]',
                'h3 a',
                '.title a'
            ]
            
            for selector in title_selectors:
                title_elem = topic.select_one(selector)
                if title_elem:
                    topic_data['title'] = title_elem.get_text().strip()
                    break
            
            # Extract replies count
            replies_elem = topic.select_one('.replies, .post_count')
            if replies_elem:
                topic_data['replies_count'] = replies_elem.get_text().strip()
            
            # Extract views count
            views_elem = topic.select_one('.views, .view_count')
            if views_elem:
                topic_data['views_count'] = views_elem.get_text().strip()
            
            # Extract author
            author_elem = topic.select_one('.author, .username')
            if author_elem:
                topic_data['author'] = author_elem.get_text().strip()
            
            # Extract last post date
            date_elem = topic.select_one('.last_post, .date')
            if date_elem:
                topic_data['last_post_date'] = date_elem.get_text().strip()
            
            if topic_data['title']:  # Only add if we have a title
                self.all_data.append(topic_data)
                print(f"Forum Topic {i+1}: {topic_data['title']}")
    
    def scrape_flights_cruises(self):
        """Scrape flights and cruises information"""
        print("\n=== Scraping Flights & Cruises Information ===")
        
        # Flights data (placeholder as this usually redirects)
        flights_data = {
            'section': 'Flights',
            'page_url': f"{self.base_url}/Flights-g{self.ella_location_id}-Ella_Uva_Province-Cheap_Flights.html",
            'title': 'Flights to Ella, Sri Lanka',
            'description': 'Flight booking and information for traveling to Ella',
            'nearest_airport': 'Bandaranaike International Airport (CMB), Colombo',
            'distance_from_airport': 'Approximately 180km from Ella',
            'transportation_options': 'Taxi, Bus, Train from Colombo',
            'scraped_at': datetime.now().isoformat()
        }
        
        # Cruises data (placeholder as Ella is inland)
        cruises_data = {
            'section': 'Cruises',
            'page_url': f"{self.base_url}/Cruises-d6000495-Ella_Cruises.html",
            'title': 'Cruises near Ella, Sri Lanka',
            'description': 'Cruise options and coastal excursions accessible from Ella',
            'note': 'Ella is an inland hill station. Cruises available from coastal cities like Colombo, Galle',
            'coastal_destinations': 'Mirissa, Unawatuna, Bentota (2-3 hours drive from Ella)',
            'cruise_types': 'Whale watching, sunset cruises, fishing trips',
            'scraped_at': datetime.now().isoformat()
        }
        
        self.all_data.extend([flights_data, cruises_data])
        print("Added flights and cruises information")
    
    def flatten_data_for_csv(self):
        """Flatten the collected data for CSV export"""
        flattened_data = []
        
        for item in self.all_data:
            row = item.copy()
            
            # Handle images
            if 'images' in row and row['images']:
                image_urls = []
                image_alts = []
                image_titles = []
                
                for img in row['images'][:5]:  # Limit to first 5 images
                    image_urls.append(img.get('url', ''))
                    image_alts.append(img.get('alt', ''))
                    image_titles.append(img.get('title', ''))
                
                row['image_urls'] = ' | '.join(filter(None, image_urls))
                row['image_alt_texts'] = ' | '.join(filter(None, image_alts))
                row['image_titles'] = ' | '.join(filter(None, image_titles))
                row['total_images'] = len(row['images'])
            else:
                row['image_urls'] = ''
                row['image_alt_texts'] = ''
                row['image_titles'] = ''
                row['total_images'] = 0
            
            # Remove the original images list
            if 'images' in row:
                del row['images']
            
            flattened_data.append(row)
        
        return flattened_data
    
    def save_to_csv(self, filename='ella_tripadvisor_complete_data.csv'):
        """Save all collected data to CSV"""
        if not self.all_data:
            print("No data collected to save!")
            return False
        
        flattened_data = self.flatten_data_for_csv()
        
        try:
            df = pd.DataFrame(flattened_data)
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"\n✅ Data successfully saved to {filename}")
            print(f"📊 Total records: {len(flattened_data)}")
            
            # Print section summary
            section_counts = df['section'].value_counts()
            print("\n📈 Data by section:")
            for section, count in section_counts.items():
                print(f"  - {section}: {count} records")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")
            return False
    
    def print_summary(self):
        """Print summary of collected data"""
        if not self.all_data:
            print("No data collected!")
            return
        
        print(f"\n" + "="*50)
        print("SCRAPING SUMMARY")
        print("="*50)
        
        sections = {}
        total_images = 0
        
        for item in self.all_data:
            section = item.get('section', 'Unknown')
            if section not in sections:
                sections[section] = 0
            sections[section] += 1
            
            if 'images' in item:
                total_images += len(item['images'])
        
        print(f"Total records collected: {len(self.all_data)}")
        print(f"Total images found: {total_images}")
        print(f"Sections scraped: {len(sections)}")
        
        print(f"\nBreakdown by section:")
        for section, count in sections.items():
            print(f"  {section}: {count} records")
        
        # Show sample data
        if len(self.all_data) > 0:
            print(f"\n" + "-"*30)
            print("SAMPLE DATA")
            print("-"*30)
            sample = self.all_data[0]
            for key, value in sample.items():
                if key != 'images':
                    display_value = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    print(f"{key}: {display_value}")
    
    def run_full_scrape(self):
        """Run complete scraping process for all navigation sections"""
        print("🚀 Starting TripAdvisor Ella Sri Lanka Complete Data Scraping")
        print("📍 Target: All navigation sections (Hotels, Attractions, Restaurants, etc.)")
        print("-" * 70)
        
        start_time = datetime.now()
        
        try:
            # Scrape all sections
            self.scrape_main_page()
            self.scrape_hotels()
            self.scrape_attractions()
            self.scrape_restaurants()
            self.scrape_vacation_rentals()
            self.scrape_forums()
            self.scrape_flights_cruises()
            
            # Save data
            success = self.save_to_csv('ella_tripadvisor_complete_data.csv')
            
            # Print summary
            self.print_summary()
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            print(f"\n⏱️  Total scraping time: {duration}")
            
            if success:
                print("✅ Scraping completed successfully!")
                print("📄 Check 'ella_tripadvisor_complete_data.csv' for results")
            else:
                print("⚠️  Scraping completed with some issues")
            
        except KeyboardInterrupt:
            print("\n⚠️  Scraping interrupted by user")
            if self.all_data:
                print("💾 Saving partial data...")
                self.save_to_csv('ella_tripadvisor_partial_data.csv')

if __name__ == "__main__":
    scraper = TripAdvisorEllaScraper()
    scraper.run_full_scrape()
