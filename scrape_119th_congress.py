#!/usr/bin/env python3
"""
Complete 119th Congress Bills Scraper for InShort

This script scrapes ALL bills from the 119th Congress (2025-2026) with prorated rate limiting.
Estimates: ~15,000+ bills total, ~32+ hours of scraping time at 13 requests/minute.

Usage:
    python3 scrape_119th_congress.py [--continue] [--batch-size 50]
"""

import requests
import json
import time
import argparse
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from rate_limiter import CongressAPIRateLimiter

API_KEY = "PObLUqeVATUsVD34EGwQagrnuQgBExKjtu1XR4Y6"


class Congress119Scraper:
    """Specialized scraper for ALL 119th Congress bills"""

    BASE_URL = "https://api.congress.gov/v3"
    CONGRESS_NUMBER = 119

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "InShort119thCongressScraper/1.0"})

        # Initialize prorated rate limiter
        self.rate_limiter = CongressAPIRateLimiter(max_requests_per_minute=13)

        # Progress tracking
        self.progress_file = "119th_congress_progress.json"
        self.output_file = "large_bills.json"
        self.temp_file = "large_bills_temp.json"

    def make_rate_limited_request(
        self, url: str, params: Dict
    ) -> Optional[requests.Response]:
        """Make a request with prorated rate limiting"""
        status = self.rate_limiter.wait_if_needed()

        # Show progress every 50 requests
        if status["requests_made"] % 50 == 0:
            print(f"  📊 Progress: {status['requests_made']} requests made")
            print(f"     Rate: {status['minute_requests']}/13 per minute")

        try:
            response = self.session.get(url, params=params, timeout=30)
            return response
        except Exception as e:
            print(f"  ⚠️  Request failed: {e}")
            return None

    def get_total_bill_count(self) -> int:
        """Get the total number of bills in 119th Congress"""
        print("🔍 Getting total bill count for 119th Congress...")

        params = {
            "api_key": self.api_key,
            "format": "json",
            "congress": self.CONGRESS_NUMBER,
            "limit": 1,  # Just need the count
        }

        response = self.make_rate_limited_request(f"{self.BASE_URL}/bill", params)

        if response and response.status_code == 200:
            data = response.json()
            total = data.get("pagination", {}).get("count", 0)
            print(f"📊 Total bills in 119th Congress: {total:,}")
            return total
        else:
            print("⚠️  Could not get total count, using estimate")
            return 15000  # Conservative estimate

    def get_bills_batch(self, offset: int = 0, limit: int = 250) -> Dict:
        """Get a batch of bills from 119th Congress"""
        params = {
            "api_key": self.api_key,
            "format": "json",
            "congress": self.CONGRESS_NUMBER,
            "offset": offset,
            "limit": limit,
            "sort": "updateDate+desc",  # Most recent first
        }

        response = self.make_rate_limited_request(f"{self.BASE_URL}/bill", params)

        if response and response.status_code == 200:
            return response.json()
        else:
            error_msg = f"API request failed: {response.status_code if response else 'No response'}"
            if response:
                error_msg += f" - {response.text[:200]}"
            raise Exception(error_msg)

    def get_full_bill_details(
        self, congress: int, bill_type: str, bill_number: str
    ) -> Optional[Dict]:
        """Get complete bill details with all endpoints"""
        bill_type_lower = bill_type.lower()
        base_url = f"{self.BASE_URL}/bill/{congress}/{bill_type_lower}/{bill_number}"

        basic_params = {"api_key": self.api_key, "format": "json"}

        try:
            # 1. Basic bill info
            response = self.make_rate_limited_request(base_url, basic_params)
            if not response or response.status_code != 200:
                return None

            bill_data = response.json()

            # 2. Get all additional endpoints
            endpoints = [
                "actions",
                "sponsors",
                "cosponsors",
                "amendments",
                "subjects",
                "summaries",
                "titles",
                "text",
                "related",
                "committees",
                "cbo-cost-estimates",
            ]

            for endpoint in endpoints:
                try:
                    endpoint_response = self.make_rate_limited_request(
                        f"{base_url}/{endpoint}", basic_params
                    )
                    if endpoint_response and endpoint_response.status_code == 200:
                        bill_data[f'{endpoint.replace("-", "_")}_details'] = (
                            endpoint_response.json()
                        )
                except Exception:
                    pass  # Continue if endpoint fails

            return bill_data

        except Exception as e:
            print(f"    ❌ Error getting details for {bill_type}{bill_number}: {e}")
            return None

    def save_progress(self, progress_data: Dict):
        """Save progress to file"""
        with open(self.progress_file, "w") as f:
            json.dump(progress_data, f, indent=2)

    def load_progress(self) -> Dict:
        """Load progress from file"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"bills_processed": [], "last_offset": 0, "total_collected": 0}

    def save_bills_batch(self, bills: List[Dict], append: bool = True):
        """Save bills to output file"""
        mode = "a" if append and os.path.exists(self.output_file) else "w"

        # If appending, we need to handle JSON array properly
        if append and os.path.exists(self.output_file):
            try:
                with open(self.output_file, "r") as f:
                    existing_bills = json.load(f)
                bills = existing_bills + bills
            except Exception:
                pass  # Start fresh if can't read existing

        with open(self.output_file, "w") as f:
            json.dump(bills, f, indent=2)


def scrape_all_119th_congress(continue_previous: bool = False, batch_size: int = 50):
    """Scrape all bills from 119th Congress"""

    scraper = Congress119Scraper(API_KEY)

    print("🏛️  119th Congress Complete Bill Scraper")
    print("=" * 60)
    print(f"📅 Target: All bills from 119th Congress (2025-2026)")
    print(f"⚡ Rate limit: 13 requests/minute (780/hour)")
    print(f"📦 Batch size: {batch_size} bills per batch")
    print()

    # Load progress if continuing
    progress = (
        scraper.load_progress()
        if continue_previous
        else {"bills_processed": [], "last_offset": 0, "total_collected": 0}
    )

    # Get total count
    total_bills = scraper.get_total_bill_count()

    # Estimate time
    requests_per_bill = 12  # 1 basic + ~11 endpoints on average
    total_requests = total_bills * requests_per_bill
    estimated_hours = total_requests / (13 * 60)  # 13 requests per minute

    print(f"📊 Scraping Estimates:")
    print(f"   Total bills: {total_bills:,}")
    print(f"   Estimated requests: {total_requests:,}")
    print(
        f"   Estimated time: {estimated_hours:.1f} hours ({estimated_hours/24:.1f} days)"
    )
    print(f"   Bills per hour: ~{780/requests_per_bill:.0f}")
    print()

    if continue_previous:
        print(f"🔄 Continuing from: {progress['total_collected']} bills collected")
        print(f"   Last offset: {progress['last_offset']}")
        print()

    # Confirm with user
    response = input("🚀 Ready to start scraping? This will take a LONG time. (y/N): ")
    if response.lower() != "y":
        print("❌ Scraping cancelled")
        return

    print("\n🚀 Starting comprehensive 119th Congress scraping...")
    start_time = time.time()
    all_bills = []

    # Load existing bills if continuing
    if continue_previous and os.path.exists(scraper.output_file):
        try:
            with open(scraper.output_file, "r") as f:
                all_bills = json.load(f)
            print(f"📂 Loaded {len(all_bills)} existing bills")
        except Exception:
            all_bills = []

    offset = progress["last_offset"]
    processed_ids = set(progress["bills_processed"])

    try:
        while offset < total_bills:
            print(f"\n📦 Fetching bills {offset:,} to {offset + batch_size:,}...")

            try:
                # Get batch of bills
                response = scraper.get_bills_batch(offset, batch_size)
                bills_batch = response.get("bills", [])

                if not bills_batch:
                    print("  ℹ️  No more bills found")
                    break

                print(f"  📋 Processing {len(bills_batch)} bills in this batch...")

                batch_collected = []
                for i, bill in enumerate(bills_batch):
                    bill_type = bill.get("type")
                    bill_number = bill.get("number")
                    congress = bill.get("congress")
                    bill_id = f"{congress}-{bill_type}-{bill_number}"

                    # Skip if already processed
                    if bill_id in processed_ids:
                        print(
                            f"    ⏭️  Skipping {bill_type.upper()}{bill_number} (already processed)"
                        )
                        continue

                    if (
                        bill_type
                        and bill_number
                        and congress == scraper.CONGRESS_NUMBER
                    ):
                        title = bill.get("title", "N/A")
                        print(
                            f"    🏛️  [{i+1}/{len(bills_batch)}] {bill_type.upper()}{bill_number}"
                        )
                        print(f"         {title[:60]}...")

                        # Get complete details
                        full_details = scraper.get_full_bill_details(
                            congress, bill_type, bill_number
                        )

                        if full_details:
                            batch_collected.append(full_details)
                            processed_ids.add(bill_id)
                            elapsed = time.time() - start_time
                            total_collected = len(all_bills) + len(batch_collected)
                            rate = (
                                total_collected / (elapsed / 3600) if elapsed > 0 else 0
                            )
                            remaining = total_bills - total_collected
                            eta_hours = remaining / rate if rate > 0 else 0

                            print(
                                f"         ✅ Success ({total_collected:,}/{total_bills:,}) - Rate: {rate:.1f}/hr - ETA: {eta_hours:.1f}h"
                            )
                        else:
                            print(f"         ❌ Failed to get details")

                # Add batch to main collection
                all_bills.extend(batch_collected)

                # Save progress every batch
                progress.update(
                    {
                        "bills_processed": list(processed_ids),
                        "last_offset": offset + batch_size,
                        "total_collected": len(all_bills),
                        "last_updated": datetime.now().isoformat(),
                    }
                )
                scraper.save_progress(progress)
                scraper.save_bills_batch(all_bills, append=False)

                print(
                    f"  💾 Saved batch: {len(batch_collected)} new bills, {len(all_bills):,} total"
                )

                offset += batch_size

            except Exception as e:
                print(f"❌ Error in batch: {e}")

                # Save current progress before retry
                progress.update(
                    {
                        "bills_processed": list(processed_ids),
                        "last_offset": offset,  # Don't advance offset on error
                        "total_collected": len(all_bills),
                        "last_error": str(e),
                        "last_updated": datetime.now().isoformat(),
                    }
                )
                scraper.save_progress(progress)

                print(
                    "⏸️  Saving current progress and waiting 60 seconds before retry..."
                )
                if all_bills:  # Only save if we have bills to save
                    scraper.save_bills_safely(all_bills)

                time.sleep(60)
                continue

        except KeyboardInterrupt:
        print("\n⏸️  Scraping interrupted by user")
        print("💾 Saving current progress...")
        
        # Save current state
        progress.update({
            'bills_processed': list(processed_ids),
            'last_offset': offset,
            'total_collected': len(all_bills),
            'last_updated': datetime.now().isoformat(),
            'interrupted': True
        })
        scraper.save_progress(progress)
        
        if all_bills:
            scraper.save_bills_safely(all_bills)
        
        print(f"✅ Progress saved. Resume with: python3 scrape_119th_congress.py --continue")
    
    except Exception as e:
        print(f"\n❌ Unexpected scraping error: {e}")
        print("💾 Attempting to save current progress...")
        
        # Try to save current state
        try:
            progress.update({
                'bills_processed': list(processed_ids),
                'last_offset': offset,
                'total_collected': len(all_bills),
                'last_error': str(e),
                'last_updated': datetime.now().isoformat()
            })
            scraper.save_progress(progress)
            
            if all_bills:
                scraper.save_bills_safely(all_bills)
            
            print("✅ Emergency save completed")
        except Exception as save_error:
            print(f"❌ Could not save progress: {save_error}")
            print("⚠️  Data may be lost")

    finally:
        # Final save
        elapsed = time.time() - start_time

        print(f"\n🎯 Final Results:")
        print(f"   Bills collected: {len(all_bills):,}")
        print(f"   Time elapsed: {elapsed/3600:.1f} hours")
        print(f"   Average rate: {len(all_bills)/(elapsed/3600):.1f} bills/hour")
        print(f"   Output file: {scraper.output_file}")

        # Save final results safely
        scraper.save_bills_safely(all_bills)

        file_size = (
            os.path.getsize(scraper.output_file) / 1024 / 1024
            if os.path.exists(scraper.output_file)
            else 0
        )
        print(f"   File size: {file_size:.1f} MB")

        # Rate limiter final status
        status = scraper.rate_limiter.get_status()
        print(f"\n📊 Rate Limiter Final Status:")
        print(f"   Total requests made: {status['requests_made']:,}")
        print(f"   Requests remaining this hour: {status['requests_remaining']}")


def main():
    parser = argparse.ArgumentParser(description="Scrape ALL bills from 119th Congress")
    parser.add_argument(
        "--continue",
        dest="continue_flag",
        action="store_true",
        help="Continue from previous run",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of bills per batch (default: 50)",
    )

    args = parser.parse_args()

    scrape_all_119th_congress(
        continue_previous=args.continue_flag, batch_size=args.batch_size
    )


if __name__ == "__main__":
    main()
