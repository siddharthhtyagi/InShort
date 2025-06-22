#!/usr/bin/env python3
"""
Safe Complete 119th Congress Bills Scraper for InShort

This script safely scrapes ALL bills from the 119th Congress (2025-2026) with:
- Prorated rate limiting (13 requests/minute)
- Robust partial stoppage protection
- Atomic file operations
- Progress recovery
- Output to large_bills.json

Usage:
    python3 scrape_119th_congress_safe.py [--continue] [--batch-size 25]
"""

import requests
import json
import time
import argparse
import os
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from rate_limiter import CongressAPIRateLimiter

API_KEY = "PObLUqeVATUsVD34EGwQagrnuQgBExKjtu1XR4Y6"


class SafeCongress119Scraper:
    """Ultra-safe scraper for ALL 119th Congress bills"""

    BASE_URL = "https://api.congress.gov/v3"
    CONGRESS_NUMBER = 119

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "InShortSafe119thCongressScraper/1.0"}
        )

        # Initialize prorated rate limiter
        self.rate_limiter = CongressAPIRateLimiter(max_requests_per_minute=13)

        # File management - safe operations
        self.progress_file = "119th_congress_progress.json"
        self.output_file = "large_bills.json"
        self.temp_file = "large_bills_temp.json"
        self.backup_file = "large_bills_backup.json"

    def make_rate_limited_request(
        self, url: str, params: Dict
    ) -> Optional[requests.Response]:
        """Make a request with prorated rate limiting"""
        status = self.rate_limiter.wait_if_needed()

        # Show progress every 50 requests
        if status["requests_made"] % 50 == 0:
            print(f"  📊 API Progress: {status['requests_made']} requests made")
            print(f"     Current rate: {status['minute_requests']}/13 per minute")

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
            "limit": 1,
        }

        response = self.make_rate_limited_request(f"{self.BASE_URL}/bill", params)

        if response and response.status_code == 200:
            data = response.json()
            total = data.get("pagination", {}).get("count", 0)
            print(f"📊 Total bills in 119th Congress: {total:,}")
            return total
        else:
            print("⚠️  Could not get total count, using estimate")
            return 15000

    def get_bills_batch(self, offset: int = 0, limit: int = 250) -> Dict:
        """Get a batch of bills from 119th Congress"""
        params = {
            "api_key": self.api_key,
            "format": "json",
            "congress": self.CONGRESS_NUMBER,
            "offset": offset,
            "limit": limit,
            "sort": "updateDate+desc",
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

    def save_progress_safely(self, progress_data: Dict):
        """Save progress with atomic operations"""
        try:
            temp_progress = f"{self.progress_file}.temp"
            with open(temp_progress, "w") as f:
                json.dump(progress_data, f, indent=2)

            # Atomic rename
            if os.path.exists(self.progress_file):
                shutil.move(self.progress_file, f"{self.progress_file}.backup")
            shutil.move(temp_progress, self.progress_file)

            # Clean up backup
            backup_progress = f"{self.progress_file}.backup"
            if os.path.exists(backup_progress):
                os.remove(backup_progress)

        except Exception as e:
            print(f"⚠️  Warning: Could not save progress: {e}")

    def load_progress_safely(self) -> Dict:
        """Load progress with validation and recovery"""
        default_progress = {
            "bills_processed": [],
            "last_offset": 0,
            "total_collected": 0,
        }

        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r") as f:
                    progress = json.load(f)

                if not isinstance(progress, dict):
                    print("⚠️  Invalid progress file format, starting fresh")
                    return default_progress

                # Ensure required keys exist
                progress.setdefault("bills_processed", [])
                progress.setdefault("last_offset", 0)
                progress.setdefault("total_collected", 0)

                print(
                    f"📂 Loaded progress: {len(progress['bills_processed'])} bills processed"
                )
                return progress

            except Exception as e:
                print(f"⚠️  Could not load progress file: {e}")

                # Try backup
                backup_file = f"{self.progress_file}.backup"
                if os.path.exists(backup_file):
                    try:
                        with open(backup_file, "r") as f:
                            progress = json.load(f)
                        print("🔄 Recovered progress from backup")
                        return progress
                    except Exception:
                        pass

        return default_progress

    def save_bills_safely(self, bills: List[Dict]):
        """Save bills with atomic operations and validation"""
        try:
            print(f"  💾 Saving {len(bills)} bills to {self.output_file}...")

            # Save to temp file first
            with open(self.temp_file, "w") as f:
                json.dump(bills, f, indent=2)

            # Validate the temp file
            with open(self.temp_file, "r") as f:
                test_load = json.load(f)
                if not isinstance(test_load, list):
                    raise ValueError("Invalid JSON structure")

            # Create backup of existing file
            if os.path.exists(self.output_file):
                shutil.copy2(self.output_file, self.backup_file)

            # Atomic move
            shutil.move(self.temp_file, self.output_file)

            # Verify final file
            with open(self.output_file, "r") as f:
                json.load(f)

            print(f"  ✅ Successfully saved to {self.output_file}")

            # Clean up backup after successful save
            if os.path.exists(self.backup_file):
                os.remove(self.backup_file)

        except Exception as e:
            print(f"⚠️  Critical: Could not save bills safely: {e}")

            # Try to restore from backup
            if os.path.exists(self.backup_file) and not os.path.exists(
                self.output_file
            ):
                shutil.move(self.backup_file, self.output_file)
                print("🔄 Restored from backup file")

            # Clean up temp file
            if os.path.exists(self.temp_file):
                try:
                    os.remove(self.temp_file)
                except Exception:
                    pass

    def load_existing_bills_safely(self) -> List[Dict]:
        """Load existing bills with validation and recovery"""
        if not os.path.exists(self.output_file):
            return []

        try:
            with open(self.output_file, "r") as f:
                bills = json.load(f)

            if not isinstance(bills, list):
                print("⚠️  Invalid bills file format, starting fresh")
                return []

            print(f"📂 Loaded {len(bills)} existing bills from {self.output_file}")
            return bills

        except Exception as e:
            print(f"⚠️  Could not load existing bills: {e}")

            # Try to load from backup
            if os.path.exists(self.backup_file):
                try:
                    with open(self.backup_file, "r") as f:
                        bills = json.load(f)
                    if isinstance(bills, list):
                        print(f"🔄 Loaded {len(bills)} bills from backup file")
                        return bills
                except Exception:
                    pass

            return []


def scrape_all_119th_congress_safely(
    continue_previous: bool = False, batch_size: int = 25
):
    """Safely scrape all bills from 119th Congress with robust error handling"""

    scraper = SafeCongress119Scraper(API_KEY)

    print("🛡️  SAFE 119th Congress Complete Bill Scraper")
    print("=" * 65)
    print(f"📅 Target: All bills from 119th Congress (2025-2026)")
    print(f"⚡ Rate limit: 13 requests/minute (780/hour)")
    print(f"📦 Batch size: {batch_size} bills per batch")
    print(f"💾 Output file: {scraper.output_file}")
    print(f"🔐 Safe mode: Atomic saves, progress recovery enabled")
    print()

    # Load progress safely
    progress = (
        scraper.load_progress_safely()
        if continue_previous
        else {"bills_processed": [], "last_offset": 0, "total_collected": 0}
    )

    # Get total count
    total_bills = scraper.get_total_bill_count()

    # Estimate time
    requests_per_bill = 12
    total_requests = total_bills * requests_per_bill
    estimated_hours = total_requests / (13 * 60)

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
    response = input(
        "🚀 Ready to start SAFE scraping? This will take a LONG time. (y/N): "
    )
    if response.lower() != "y":
        print("❌ Scraping cancelled")
        return

    print("\n🚀 Starting SAFE comprehensive 119th Congress scraping...")
    start_time = time.time()

    # Load existing bills safely
    all_bills = []
    if continue_previous:
        all_bills = scraper.load_existing_bills_safely()

    offset = progress["last_offset"]
    processed_ids = set(progress["bills_processed"])

    # Save every N bills for maximum safety
    save_frequency = max(5, batch_size // 5)  # Save at least every 5 bills

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
                            all_bills.append(full_details)
                            processed_ids.add(bill_id)

                            elapsed = time.time() - start_time
                            total_collected = len(all_bills)
                            rate = (
                                total_collected / (elapsed / 3600) if elapsed > 0 else 0
                            )
                            remaining = total_bills - total_collected
                            eta_hours = remaining / rate if rate > 0 else 0

                            print(
                                f"         ✅ Success ({total_collected:,}/{total_bills:,}) - Rate: {rate:.1f}/hr - ETA: {eta_hours:.1f}h"
                            )

                            # Save frequently for safety
                            if len(batch_collected) % save_frequency == 0:
                                print(
                                    f"         💾 Intermediate save ({len(batch_collected)} bills in batch)..."
                                )
                                progress_update = {
                                    "bills_processed": list(processed_ids),
                                    "last_offset": offset,
                                    "total_collected": len(all_bills),
                                    "last_updated": datetime.now().isoformat(),
                                    "session_start": progress.get(
                                        "session_start", datetime.now().isoformat()
                                    ),
                                }
                                scraper.save_progress_safely(progress_update)
                                scraper.save_bills_safely(all_bills)
                        else:
                            print(f"         ❌ Failed to get details")

                # Save progress after each batch
                progress.update(
                    {
                        "bills_processed": list(processed_ids),
                        "last_offset": offset + batch_size,
                        "total_collected": len(all_bills),
                        "last_updated": datetime.now().isoformat(),
                        "session_start": progress.get(
                            "session_start", datetime.now().isoformat()
                        ),
                    }
                )

                print(
                    f"  💾 Batch complete: {len(batch_collected)} new bills, {len(all_bills):,} total"
                )
                scraper.save_progress_safely(progress)
                scraper.save_bills_safely(all_bills)

                offset += batch_size

            except Exception as e:
                print(f"❌ Error in batch: {e}")

                # Emergency save current progress
                emergency_progress = {
                    "bills_processed": list(processed_ids),
                    "last_offset": offset,  # Don't advance on error
                    "total_collected": len(all_bills),
                    "last_error": str(e),
                    "last_updated": datetime.now().isoformat(),
                }
                scraper.save_progress_safely(emergency_progress)

                print("⏸️  Emergency save completed. Waiting 60 seconds before retry...")
                if all_bills:
                    scraper.save_bills_safely(all_bills)

                time.sleep(60)
                continue

    except KeyboardInterrupt:
        print("\n⏸️  Scraping interrupted by user")
        print("💾 Performing emergency save...")

        # Emergency save
        final_progress = {
            "bills_processed": list(processed_ids),
            "last_offset": offset,
            "total_collected": len(all_bills),
            "last_updated": datetime.now().isoformat(),
            "interrupted": True,
        }
        scraper.save_progress_safely(final_progress)

        if all_bills:
            scraper.save_bills_safely(all_bills)

        print(f"✅ Emergency save completed!")
        print(f"Resume with: python3 scrape_119th_congress_safe.py --continue")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("💾 Performing emergency save...")

        try:
            emergency_progress = {
                "bills_processed": list(processed_ids),
                "last_offset": offset,
                "total_collected": len(all_bills),
                "last_error": str(e),
                "last_updated": datetime.now().isoformat(),
            }
            scraper.save_progress_safely(emergency_progress)

            if all_bills:
                scraper.save_bills_safely(all_bills)

            print("✅ Emergency save completed")
        except Exception as save_error:
            print(f"❌ Emergency save failed: {save_error}")
            print("⚠️  Some data may be lost!")

    finally:
        # Final save and report
        elapsed = time.time() - start_time

        print(f"\n🎯 Final Results:")
        print(f"   Bills collected: {len(all_bills):,}")
        print(f"   Time elapsed: {elapsed/3600:.1f} hours")
        print(f"   Average rate: {len(all_bills)/(elapsed/3600):.1f} bills/hour")
        print(f"   Output file: {scraper.output_file}")

        # Final save
        if all_bills:
            scraper.save_bills_safely(all_bills)

        if os.path.exists(scraper.output_file):
            file_size = os.path.getsize(scraper.output_file) / 1024 / 1024
            print(f"   File size: {file_size:.1f} MB")

        # Rate limiter status
        status = scraper.rate_limiter.get_status()
        print(f"\n📊 Rate Limiter Final Status:")
        print(f"   Total requests: {status['requests_made']:,}")
        print(f"   Remaining this hour: {status['requests_remaining']}")


def main():
    parser = argparse.ArgumentParser(
        description="SAFELY scrape ALL bills from 119th Congress"
    )
    parser.add_argument(
        "--continue",
        dest="continue_flag",
        action="store_true",
        help="Continue from previous run",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of bills per batch (default: 25)",
    )

    args = parser.parse_args()

    scrape_all_119th_congress_safely(
        continue_previous=args.continue_flag, batch_size=args.batch_size
    )


if __name__ == "__main__":
    main()
