#!/usr/bin/env python3
"""
Rate Limiter for Congress.gov API

Ensures prorated distribution with no more than 13 requests per minute (780/hour).
Includes request tracking, automatic delays, and recovery mechanisms.
"""

import time
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
import threading


@dataclass
class RateLimitStats:
    """Track rate limiting statistics"""

    requests_made: int = 0
    requests_remaining: int = 780  # 13 per minute * 60 minutes
    reset_time: Optional[datetime] = None
    last_request_time: Optional[datetime] = None
    hour_start: Optional[datetime] = None
    # Minute-based tracking for prorated distribution
    minute_requests: int = 0
    minute_start: Optional[datetime] = None


class CongressAPIRateLimiter:
    """
    Smart prorated rate limiter for Congress.gov API

    Features:
    - Ensures no more than 13 requests per minute (prorated)
    - Tracks both hourly (780) and minute (13) limits
    - Automatic delay calculation for even distribution
    - Request tracking persistence
    - Thread-safe operations
    """

    def __init__(
        self,
        max_requests_per_minute: int = 13,
        stats_file: str = "rate_limit_stats.json",
    ):
        """
        Initialize prorated rate limiter

        Args:
            max_requests_per_minute: Max requests per minute (default 13)
            stats_file: File to persist rate limiting stats
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_hour = max_requests_per_minute * 60  # 780 for 13/min
        self.stats_file = stats_file
        self.lock = threading.Lock()

        # Load or initialize stats
        self.stats = self._load_stats()

        # Calculate timing for prorated distribution
        self.min_delay = 60.0 / max_requests_per_minute  # Seconds between requests

        print(f"🛡️  Prorated Rate Limiter initialized:")
        print(f"   Max requests/minute: {max_requests_per_minute}")
        print(f"   Max requests/hour: {self.max_requests_per_hour}")
        print(f"   Min delay between requests: {self.min_delay:.2f}s")
        print(f"   Prorated for even distribution")

    def _load_stats(self) -> RateLimitStats:
        """Load rate limiting stats from file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    data = json.load(f)

                stats = RateLimitStats(**data)

                # Convert string timestamps back to datetime
                if stats.reset_time:
                    stats.reset_time = datetime.fromisoformat(str(stats.reset_time))
                if stats.last_request_time:
                    stats.last_request_time = datetime.fromisoformat(
                        str(stats.last_request_time)
                    )
                if stats.hour_start:
                    stats.hour_start = datetime.fromisoformat(str(stats.hour_start))
                if stats.minute_start:
                    stats.minute_start = datetime.fromisoformat(str(stats.minute_start))

                # Reset if hour has passed
                if stats.hour_start and datetime.now() - stats.hour_start > timedelta(
                    hours=1
                ):
                    print("⏰ Hour boundary crossed - resetting counters")
                    stats = self._reset_stats()

                # Reset minute counter if minute has passed
                if (
                    stats.minute_start
                    and datetime.now() - stats.minute_start > timedelta(minutes=1)
                ):
                    print("⏰ Minute boundary crossed - resetting minute counter")
                    stats.minute_requests = 0
                    stats.minute_start = datetime.now()

                return stats
            except Exception as e:
                print(f"⚠️  Error loading stats: {e}, creating new stats")

        return self._reset_stats()

    def _save_stats(self):
        """Save rate limiting stats to file"""
        try:
            # Convert datetime objects to strings for JSON
            stats_dict = asdict(self.stats)
            if stats_dict["reset_time"]:
                stats_dict["reset_time"] = self.stats.reset_time.isoformat()
            if stats_dict["last_request_time"]:
                stats_dict["last_request_time"] = (
                    self.stats.last_request_time.isoformat()
                )
            if stats_dict["hour_start"]:
                stats_dict["hour_start"] = self.stats.hour_start.isoformat()
            if stats_dict["minute_start"]:
                stats_dict["minute_start"] = self.stats.minute_start.isoformat()

            with open(self.stats_file, "w") as f:
                json.dump(stats_dict, f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving stats: {e}")

    def _reset_stats(self) -> RateLimitStats:
        """Reset stats for new period"""
        now = datetime.now()
        return RateLimitStats(
            requests_made=0,
            requests_remaining=self.max_requests_per_hour,
            reset_time=now + timedelta(hours=1),
            hour_start=now,
            minute_requests=0,
            minute_start=now,
        )

    def wait_if_needed(self) -> Dict[str, Any]:
        """
        Wait if needed to respect prorated rate limits

        Returns:
            Dict with timing and status information
        """
        with self.lock:
            now = datetime.now()

            # Check if we need to reset for new hour
            if self.stats.hour_start and now - self.stats.hour_start >= timedelta(
                hours=1
            ):
                print("⏰ Starting new hour - resetting all counters")
                self.stats = self._reset_stats()
                self._save_stats()

            # Check if we need to reset for new minute
            if self.stats.minute_start and now - self.stats.minute_start >= timedelta(
                minutes=1
            ):
                elapsed_minutes = (now - self.stats.minute_start).total_seconds() / 60
                print(
                    f"⏰ Minute boundary crossed (elapsed: {elapsed_minutes:.1f}min) - resetting minute counter"
                )
                self.stats.minute_requests = 0
                self.stats.minute_start = now
                self._save_stats()

            # Check hourly limit
            if self.stats.requests_made >= self.max_requests_per_hour:
                if self.stats.reset_time:
                    wait_time = (self.stats.reset_time - now).total_seconds()
                    if wait_time > 0:
                        print(
                            f"⛔ Hourly limit reached! Waiting {wait_time:.1f}s until reset..."
                        )
                        time.sleep(wait_time)
                        self.stats = self._reset_stats()
                        self._save_stats()

            # Check minute limit - this is the key prorated control
            if self.stats.minute_requests >= self.max_requests_per_minute:
                if self.stats.minute_start:
                    minute_wait = 60 - (now - self.stats.minute_start).total_seconds()
                    if minute_wait > 0:
                        print(
                            f"⛔ Minute limit reached ({self.max_requests_per_minute} requests)! Waiting {minute_wait:.1f}s..."
                        )
                        time.sleep(minute_wait)
                        self.stats.minute_requests = 0
                        self.stats.minute_start = datetime.now()
                        self._save_stats()

            # Calculate prorated delay since last request
            delay_needed = 0.0
            if self.stats.last_request_time:
                time_since_last = (now - self.stats.last_request_time).total_seconds()
                delay_needed = max(0.0, self.min_delay - time_since_last)

            # Apply prorated delay
            if delay_needed > 0:
                print(f"⏳ Prorated delay: {delay_needed:.2f}s (for even distribution)")
                time.sleep(delay_needed)
                now = datetime.now()

            # Update all counters
            self.stats.requests_made += 1
            self.stats.minute_requests += 1
            self.stats.requests_remaining = max(
                0, self.max_requests_per_hour - self.stats.requests_made
            )
            self.stats.last_request_time = now

            # Initialize timing if first request
            if not self.stats.hour_start:
                self.stats.hour_start = now
                self.stats.reset_time = now + timedelta(hours=1)

            if not self.stats.minute_start:
                self.stats.minute_start = now

            self._save_stats()

            return {
                "requests_made": self.stats.requests_made,
                "requests_remaining": self.stats.requests_remaining,
                "minute_requests": self.stats.minute_requests,
                "minute_remaining": self.max_requests_per_minute
                - self.stats.minute_requests,
                "delay_applied": delay_needed,
                "time_until_reset": (
                    (self.stats.reset_time - now).total_seconds()
                    if self.stats.reset_time
                    else 0
                ),
                "time_until_minute_reset": (
                    60 - (now - self.stats.minute_start).total_seconds()
                    if self.stats.minute_start
                    else 60
                ),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiting status"""
        now = datetime.now()

        return {
            "requests_made": self.stats.requests_made,
            "requests_remaining": self.stats.requests_remaining,
            "max_requests_per_hour": self.max_requests_per_hour,
            "minute_requests": self.stats.minute_requests,
            "max_requests_per_minute": self.max_requests_per_minute,
            "minute_remaining": self.max_requests_per_minute
            - self.stats.minute_requests,
            "min_delay_seconds": self.min_delay,
            "time_until_reset": (
                (self.stats.reset_time - now).total_seconds()
                if self.stats.reset_time
                else 0
            ),
            "time_until_minute_reset": (
                60 - (now - self.stats.minute_start).total_seconds()
                if self.stats.minute_start
                else 60
            ),
            "last_request": (
                self.stats.last_request_time.isoformat()
                if self.stats.last_request_time
                else None
            ),
            "hour_start": (
                self.stats.hour_start.isoformat() if self.stats.hour_start else None
            ),
            "minute_start": (
                self.stats.minute_start.isoformat() if self.stats.minute_start else None
            ),
        }

    def can_make_request(self) -> bool:
        """Check if we can make a request without waiting"""
        # Check hourly limit
        if self.stats.requests_made >= self.max_requests_per_hour:
            return False

        # Check minute limit (prorated control)
        if self.stats.minute_requests >= self.max_requests_per_minute:
            return False

        # Check if enough time has passed since last request for prorated distribution
        if self.stats.last_request_time:
            time_since_last = (
                datetime.now() - self.stats.last_request_time
            ).total_seconds()
            return time_since_last >= self.min_delay

        return True

    def reset_stats(self):
        """Manually reset stats (for testing)"""
        with self.lock:
            self.stats = self._reset_stats()
            self._save_stats()
            print("📊 Rate limiting stats reset manually")


def demo_prorated_rate_limiter():
    """Demo the prorated rate limiter functionality"""
    print("🚀 Testing Prorated Rate Limiter...")

    # Use very conservative settings for demo
    limiter = CongressAPIRateLimiter(max_requests_per_minute=3)  # Only 3/min for demo

    print(
        f"\n📊 Making 8 test requests (limit: 3/min, delay: {limiter.min_delay:.1f}s)..."
    )

    for i in range(8):
        start_time = time.time()
        status = limiter.wait_if_needed()
        elapsed = time.time() - start_time

        print(f"Request {i+1}: ✓ Complete")
        print(f"  - Hour: {status['requests_made']}/{limiter.max_requests_per_hour}")
        print(
            f"  - Minute: {status['minute_requests']}/{limiter.max_requests_per_minute}"
        )
        print(f"  - Delay applied: {status['delay_applied']:.2f}s")
        print(f"  - Total time: {elapsed:.2f}s")
        print()

    print(f"📈 Final status:")
    final_status = limiter.get_status()
    for key, value in final_status.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    demo_prorated_rate_limiter()
