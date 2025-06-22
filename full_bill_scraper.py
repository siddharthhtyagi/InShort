#!/usr/bin/env python3
"""
Full Congress.gov Bills Scraper for InShort

This script pulls complete bill details from congress.gov including all context,
sponsors, actions, amendments, text, and other comprehensive information.

Usage:
    python3 full_bill_scraper.py --max-bills 100
"""

import requests
import json
import time
import argparse
from datetime import datetime
from typing import List, Dict, Optional

API_KEY = "PObLUqeVATUsVD34EGwQagrnuQgBExKjtu1XR4Y6"

class FullBillScraper:
    """Scraper for complete bill details"""
    
    BASE_URL = "https://api.congress.gov/v3"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'InShortBillScraper/1.0'
        })
    
    def get_bills_list(self, offset: int = 0, limit: int = 50) -> Dict:
        """Get list of bills"""
        params = {
            'api_key': self.api_key,
            'format': 'json',
            'offset': offset,
            'limit': limit
        }
        
        url = f"{self.BASE_URL}/bill"
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")
    
    def get_full_bill_details(self, congress: int, bill_type: str, bill_number: str) -> Optional[Dict]:
        """Get complete bill details including all endpoints"""
        
        bill_type_lower = bill_type.lower()
        base_url = f"{self.BASE_URL}/bill/{congress}/{bill_type_lower}/{bill_number}"
        
        # Get basic bill information
        basic_params = {
            'api_key': self.api_key,
            'format': 'json'
        }
        
        try:
            # 1. Basic bill info
            response = self.session.get(base_url, params=basic_params)
            if response.status_code != 200:
                print(f"  Failed to get basic info for {bill_type}{bill_number}: {response.status_code}")
                return None
            
            bill_data = response.json()
            
            # 2. Get actions
            actions_response = self.session.get(f"{base_url}/actions", params=basic_params)
            if actions_response.status_code == 200:
                bill_data['actions_details'] = actions_response.json()
            
            # 3. Get sponsors
            sponsors_response = self.session.get(f"{base_url}/sponsors", params=basic_params)
            if sponsors_response.status_code == 200:
                bill_data['sponsors_details'] = sponsors_response.json()
            
            # 4. Get cosponsors
            cosponsors_response = self.session.get(f"{base_url}/cosponsors", params=basic_params)
            if cosponsors_response.status_code == 200:
                bill_data['cosponsors_details'] = cosponsors_response.json()
            
            # 5. Get amendments
            amendments_response = self.session.get(f"{base_url}/amendments", params=basic_params)
            if amendments_response.status_code == 200:
                bill_data['amendments_details'] = amendments_response.json()
            
            # 6. Get subjects
            subjects_response = self.session.get(f"{base_url}/subjects", params=basic_params)
            if subjects_response.status_code == 200:
                bill_data['subjects_details'] = subjects_response.json()
            
            # 7. Get summaries
            summaries_response = self.session.get(f"{base_url}/summaries", params=basic_params)
            if summaries_response.status_code == 200:
                bill_data['summaries_details'] = summaries_response.json()
            
            # 8. Get titles
            titles_response = self.session.get(f"{base_url}/titles", params=basic_params)
            if titles_response.status_code == 200:
                bill_data['titles_details'] = titles_response.json()
            
            # 9. Get text (if available)
            text_response = self.session.get(f"{base_url}/text", params=basic_params)
            if text_response.status_code == 200:
                bill_data['text_details'] = text_response.json()
            
            # 10. Get related bills
            related_response = self.session.get(f"{base_url}/related", params=basic_params)
            if related_response.status_code == 200:
                bill_data['related_details'] = related_response.json()
            
            # 11. Get committees
            committees_response = self.session.get(f"{base_url}/committees", params=basic_params)
            if committees_response.status_code == 200:
                bill_data['committees_details'] = committees_response.json()
            
            # 12. Get cbo cost estimates
            cbo_response = self.session.get(f"{base_url}/cbo-cost-estimates", params=basic_params)
            if cbo_response.status_code == 200:
                bill_data['cbo_details'] = cbo_response.json()
            
            return bill_data
            
        except Exception as e:
            print(f"  Error getting full details for {bill_type}{bill_number}: {e}")
            return None

def get_full_bills(max_bills: int = 100) -> List[Dict]:
    """Get complete details for bills"""
    
    scraper = FullBillScraper(API_KEY)
    full_bills = []
    offset = 0
    limit = 10  # Small batches to avoid rate limits
    
    print(f"Fetching complete details for {max_bills} bills for InShort...")
    
    while len(full_bills) < max_bills:
        print(f"\nFetching bills {offset} to {offset + limit}...")
        
        try:
            # Get list of bills
            response = scraper.get_bills_list(offset, limit)
            bills = response.get('bills', [])
            
            if not bills:
                print("No more bills to process")
                break
            
            for bill in bills:
                if len(full_bills) >= max_bills:
                    break
                
                bill_type = bill.get('type')
                bill_number = bill.get('number')
                congress = bill.get('congress')
                title = bill.get('title', 'N/A')
                
                if bill_type and bill_number and congress:
                    print(f"  Getting full details for {bill_type}{bill_number} ({congress}th Congress)...")
                    print(f"    Title: {title[:80]}...")
                    
                    # Get complete bill details
                    full_details = scraper.get_full_bill_details(congress, bill_type, bill_number)
                    
                    if full_details:
                        full_bills.append(full_details)
                        print(f"    ✓ Successfully collected full details ({len(full_bills)}/{max_bills})")
                    else:
                        print(f"    ✗ Failed to get full details")
                    
                    # Rate limiting - be very respectful
                    time.sleep(1)  # 1 second between requests
                else:
                    print(f"  Skipping bill with missing fields: {bill}")
            
            offset += limit
            
        except Exception as e:
            print(f"Error fetching bills: {e}")
            break
    
    print(f"\nTotal bills with full details collected: {len(full_bills)}")
    return full_bills

def save_full_bills(bills: List[Dict], filename: str):
    """Save full bill details to JSON file"""
    with open(filename, 'w') as f:
        json.dump(bills, f, indent=2)
    print(f"Saved {len(bills)} bills with full details to {filename}")

def main():
    parser = argparse.ArgumentParser(description='Get complete bill details from Congress.gov for InShort')
    parser.add_argument('--max-bills', type=int, default=100, help='Maximum number of bills to retrieve')
    
    args = parser.parse_args()
    
    # Get full bill details
    full_bills = get_full_bills(args.max_bills)
    
    if full_bills:
        # Save as inshort_bills.json (single file for InShort)
        filename = "inshort_bills.json"
        save_full_bills(full_bills, filename)
        
        # Show summary of what was collected
        print(f"\nInShort Bills Summary:")
        print(f"Total bills collected: {len(full_bills)}")
        print(f"File saved as: {filename}")
        print(f"File size: {len(json.dumps(full_bills)) / 1024 / 1024:.1f} MB")
        
        # Show sample of data types collected
        if full_bills:
            sample_bill = full_bills[0]
            data_types = []
            for key in sample_bill.keys():
                if key.endswith('_details'):
                    data_types.append(key.replace('_details', ''))
            
            print(f"Data types collected per bill: {', '.join(data_types)}")
            print(f"Sample bill: {sample_bill.get('bill', {}).get('title', 'N/A')[:100]}...")
    else:
        print("No bills found")

if __name__ == "__main__":
    main() 