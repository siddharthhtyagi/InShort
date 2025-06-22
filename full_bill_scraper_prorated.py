#!/usr/bin/env python3
"""
Prorated Congress.gov Bills Scraper for InShort

This script pulls complete bill details from congress.gov with prorated rate limiting
ensuring no more than 13 requests per minute (780 per hour).

Usage:
    python3 full_bill_scraper_prorated.py --max-bills 100
"""

import requests
import json
import time
import argparse
from datetime import datetime
from typing import List, Dict, Optional
from rate_limiter import CongressAPIRateLimiter

API_KEY = "PObLUqeVATUsVD34EGwQagrnuQgBExKjtu1XR4Y6"


class ProratedBillScraper:
    """Scraper for complete bill details with prorated rate limiting"""

    BASE_URL = "https://api.congress.gov/v3"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "InShortBillScraper/1.0"})

        # Initialize prorated rate limiter (13 requests/minute max)
        self.rate_limiter = CongressAPIRateLimiter(max_requests_per_minute=13)

    def make_rate_limited_request(
        self, url: str, params: Dict
    ) -> Optional[requests.Response]:
        """Make a request with prorated rate limiting"""

        # Wait if needed to respect rate limits
        status = self.rate_limiter.wait_if_needed()

        # Show rate limiting status every 10 requests
        if status["requests_made"] % 10 == 0:
            print(f"  📊 Rate Limit Status:")
            print(
                f"     Hourly: {status['requests_made']}/{self.rate_limiter.max_requests_per_hour}"
            )
            print(
                f"     Minute: {status['minute_requests']}/{self.rate_limiter.max_requests_per_minute}"
            )
            print(f"     Delay: {status['delay_applied']:.2f}s")

        try:
            response = self.session.get(url, params=params)
            return response
        except Exception as e:
            print(f"  ⚠️  Request failed: {e}")
            return None

    def get_bills_list(self, offset: int = 0, limit: int = 50) -> Dict:
        """Get list of bills with rate limiting"""
        params = {
            "api_key": self.api_key,
            "format": "json",
            "offset": offset,
            "limit": limit,
        }

        url = f"{self.BASE_URL}/bill"
        response = self.make_rate_limited_request(url, params)

        if response and response.status_code == 200:
            return response.json()
        else:
            error_msg = f"API request failed: {response.status_code if response else 'No response'}"
            if response:
                error_msg += f" - {response.text}"
            raise Exception(error_msg)

    def get_full_bill_details(
        self, congress: int, bill_type: str, bill_number: str
    ) -> Optional[Dict]:
        """Get complete bill details including all endpoints with rate limiting"""

        bill_type_lower = bill_type.lower()
        base_url = f"{self.BASE_URL}/bill/{congress}/{bill_type_lower}/{bill_number}"

        # Get basic bill information
        basic_params = {"api_key": self.api_key, "format": "json"}

        try:
            print(f"    🔍 Fetching basic info...")

            # 1. Basic bill info
            response = self.make_rate_limited_request(base_url, basic_params)
            if not response or response.status_code != 200:
                print(
                    f"    ❌ Failed to get basic info: {response.status_code if response else 'No response'}"
                )
                return None

            bill_data = response.json()

            # Get additional details with rate limiting
            endpoints = [
                ("actions", "actions"),
                ("sponsors", "sponsors"),
                ("cosponsors", "cosponsors"),
                ("amendments", "amendments"),
                ("subjects", "subjects"),
                ("summaries", "summaries"),
                ("titles", "titles"),
                ("text", "text"),
                ("related", "related"),
                ("committees", "committees"),
                ("cbo-cost-estimates", "cbo"),
            ]

            print(f"    📋 Fetching {len(endpoints)} additional endpoints...")

            for endpoint, data_key in endpoints:
                endpoint_response = self.make_rate_limited_request(
                    f"{base_url}/{endpoint}", basic_params
                )
                if endpoint_response and endpoint_response.status_code == 200:
                    bill_data[f"{data_key}_details"] = endpoint_response.json()
                    print(f"      ✓ {endpoint}")
                else:
                    print(f"      ⚠️  {endpoint} (failed or unavailable)")

            return bill_data

        except Exception as e:
            print(f"    ❌ Error getting full details: {e}")
            return None


def get_prorated_bills(max_bills: int = 100) -> List[Dict]:
    """Get complete details for bills with prorated rate limiting"""

    scraper = ProratedBillScraper(API_KEY)
    full_bills = []
    offset = 0
    limit = 10  # Small batches for better control

    print(
        f"🚀 Fetching complete details for {max_bills} bills with prorated rate limiting..."
    )
    print(f"   Max rate: 13 requests/minute (780/hour)")
    print(f"   Delay between requests: {scraper.rate_limiter.min_delay:.2f}s")
    print()

    start_time = time.time()

    while len(full_bills) < max_bills:
        print(f"📦 Fetching bills {offset} to {offset + limit}...")

        try:
            # Get list of bills
            response = scraper.get_bills_list(offset, limit)
            bills = response.get("bills", [])

            if not bills:
                print("  ℹ️  No more bills to process")
                break

            for bill in bills:
                if len(full_bills) >= max_bills:
                    break

                bill_type = bill.get("type")
                bill_number = bill.get("number")
                congress = bill.get("congress")
                title = bill.get("title", "N/A")

                if bill_type and bill_number and congress:
                    print(
                        f"  🏛️  Processing {bill_type.upper()}{bill_number} ({congress}th Congress)"
                    )
                    print(f"      Title: {title[:80]}...")

                    # Get complete bill details
                    full_details = scraper.get_full_bill_details(
                        congress, bill_type, bill_number
                    )

                    if full_details:
                        full_bills.append(full_details)
                        elapsed = time.time() - start_time
                        rate = len(full_bills) / (elapsed / 60) if elapsed > 0 else 0
                        print(
                            f"      ✅ Success ({len(full_bills)}/{max_bills}) - Rate: {rate:.1f} bills/min"
                        )
                    else:
                        print(f"      ❌ Failed to get full details")

                    print()
                else:
                    print(f"  ⚠️  Skipping bill with missing fields: {bill}")

            offset += limit

        except Exception as e:
            print(f"❌ Error fetching bills: {e}")
            break

    elapsed = time.time() - start_time
    avg_rate = len(full_bills) / (elapsed / 60) if elapsed > 0 else 0

    print(f"🎯 Collection Summary:")
    print(f"   Total bills collected: {len(full_bills)}")
    print(f"   Total time: {elapsed / 60:.1f} minutes")
    print(f"   Average rate: {avg_rate:.1f} bills/minute")
    print(f"   Rate limiter status:")

    status = scraper.rate_limiter.get_status()
    print(f"     Requests made: {status['requests_made']}")
    print(f"     Minute requests: {status['minute_requests']}")

    return full_bills


def save_prorated_bills(bills: List[Dict], filename: str):
    """Save full bill details to JSON file"""
    with open(filename, "w") as f:
        json.dump(bills, f, indent=2)

    file_size = len(json.dumps(bills)) / 1024 / 1024
    print(f"💾 Saved {len(bills)} bills to {filename} ({file_size:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(
        description="Get complete bill details with prorated rate limiting"
    )
    parser.add_argument(
        "--max-bills", type=int, default=100, help="Maximum number of bills to retrieve"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="inshort_bills_prorated.json",
        help="Output filename",
    )

    args = parser.parse_args()

    print("🛡️  Prorated Congress.gov Bill Scraper")
    print("=" * 50)

    # Get full bill details with prorated rate limiting
    full_bills = get_prorated_bills(args.max_bills)

    if full_bills:
        save_prorated_bills(full_bills, args.output)

        print(f"\n📊 Data Collection Summary:")
        print(f"   Bills collected: {len(full_bills)}")
        print(f"   Output file: {args.output}")

        # Show sample of data types collected
        if full_bills:
            sample_bill = full_bills[0]
            data_types = []
            for key in sample_bill.keys():
                if key.endswith("_details"):
                    data_types.append(key.replace("_details", ""))

            print(f"   Data types per bill: {', '.join(data_types)}")

            # Show title of first bill
            bill_info = sample_bill.get("bill", {})
            sample_title = bill_info.get("title", "N/A")
            print(f"   Sample bill: {sample_title[:100]}...")
    else:
        print("❌ No bills collected")


if __name__ == "__main__":
    main()
