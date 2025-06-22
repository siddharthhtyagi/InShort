#!/usr/bin/env python3
"""
Pinecone Upsert Script for InShort Bills

This script reads bill data from inshort_bills.json and upserts it to Pinecone
with embeddings for semantic search.
"""

import json
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pinecone import Pinecone
import requests
import time

# Load environment variables
load_dotenv()


class BillUpsertProcessor:
    """Processes bill data and upserts to Pinecone"""

    def __init__(self, pinecone_api_key: str, index_name: str = "bills"):
        """Initialize the processor with Pinecone connection"""
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index = self.pc.Index(index_name)

    def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text using OpenAI API"""
        try:
            import openai

            # Get OpenAI API key from environment
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                client = openai.OpenAI(api_key=openai_api_key)
                response = client.embeddings.create(
                    input=text,
                    model="text-embedding-3-small",
                    dimensions=1024,  # Match your Pinecone index dimension
                )
                return response.data[0].embedding
            else:
                print("Warning: OPENAI_API_KEY not found, using mock embeddings")

        except ImportError:
            print("Warning: OpenAI library not installed, using mock embeddings")
        except Exception as e:
            print(f"Warning: OpenAI API error ({e}), using mock embeddings")

        # Fallback to mock embeddings
        import hashlib
        import random

        # Create a deterministic seed from the text
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        random.seed(seed)

        # Generate a 1024-dimensional embedding to match Pinecone index
        embedding = [random.uniform(-1, 1) for _ in range(1024)]
        return embedding

    def extract_bill_text(self, bill_data: Dict) -> str:
        """Extract meaningful text content from bill data"""
        text_parts = []

        # Add bill title
        if "bill" in bill_data and "title" in bill_data["bill"]:
            text_parts.append(f"Title: {bill_data['bill']['title']}")

        # Add summary if available
        if (
            "summaries_details" in bill_data
            and "summaries" in bill_data["summaries_details"]
        ):
            for summary in bill_data["summaries_details"]["summaries"]:
                if "text" in summary:
                    # Clean HTML tags from summary text
                    import re

                    clean_text = re.sub(r"<[^>]+>", "", summary["text"])
                    text_parts.append(f"Summary: {clean_text}")

        # Add sponsor information
        if "bill" in bill_data and "sponsors" in bill_data["bill"]:
            sponsors = []
            for sponsor in bill_data["bill"]["sponsors"]:
                if "fullName" in sponsor:
                    sponsors.append(sponsor["fullName"])
            if sponsors:
                text_parts.append(f"Sponsors: {', '.join(sponsors)}")

        # Add policy area
        if (
            "bill" in bill_data
            and "policyArea" in bill_data["bill"]
            and "name" in bill_data["bill"]["policyArea"]
        ):
            text_parts.append(f"Policy Area: {bill_data['bill']['policyArea']['name']}")

        # Add latest action
        if (
            "bill" in bill_data
            and "latestAction" in bill_data["bill"]
            and "text" in bill_data["bill"]["latestAction"]
        ):
            text_parts.append(
                f"Latest Action: {bill_data['bill']['latestAction']['text']}"
            )

        return " | ".join(text_parts)

    def create_bill_metadata(self, bill_data: Dict) -> Dict:
        """Extract metadata for the bill"""
        metadata = {}

        if "bill" in bill_data:
            bill = bill_data["bill"]
            metadata.update(
                {
                    "bill_number": bill.get("number", ""),
                    "bill_type": bill.get("type", ""),
                    "congress": bill.get("congress", ""),
                    "introduced_date": bill.get("introducedDate", ""),
                    "origin_chamber": bill.get("originChamber", ""),
                    "title": bill.get("title", "")[
                        :500
                    ],  # Truncate to avoid metadata size limits
                }
            )

            # Add sponsor info
            if "sponsors" in bill and bill["sponsors"]:
                sponsor = bill["sponsors"][0]  # Primary sponsor
                metadata["primary_sponsor"] = sponsor.get("fullName", "")
                metadata["sponsor_party"] = sponsor.get("party", "")
                metadata["sponsor_state"] = sponsor.get("state", "")

            # Add policy area
            if "policyArea" in bill and "name" in bill["policyArea"]:
                metadata["policy_area"] = bill["policyArea"]["name"]

            # Add latest action date
            if "latestAction" in bill and "actionDate" in bill["latestAction"]:
                metadata["latest_action_date"] = bill["latestAction"]["actionDate"]

        return metadata

    def process_and_upsert_bills(self, json_file_path: str, batch_size: int = 100):
        """Process bills from JSON file and upsert to Pinecone"""
        print(f"Loading bills from {json_file_path}...")

        with open(json_file_path, "r") as f:
            bills_data = json.load(f)

        print(f"Found {len(bills_data)} bills to process")

        vectors = []
        processed_count = 0

        for i, bill_data in enumerate(bills_data):
            try:
                # Extract text content
                text_content = self.extract_bill_text(bill_data)

                if not text_content.strip():
                    print(f"  Skipping bill {i+1}: No text content found")
                    continue

                # Generate embedding
                embedding = self.generate_embeddings(text_content)

                # Create metadata
                metadata = self.create_bill_metadata(bill_data)

                # Create vector ID
                bill_id = f"bill_{metadata.get('congress', 'unknown')}_{metadata.get('bill_type', 'unknown')}{metadata.get('bill_number', i)}"

                # Add to vectors list
                vectors.append(
                    {"id": bill_id, "values": embedding, "metadata": metadata}
                )

                processed_count += 1
                print(
                    f"  Processed bill {processed_count}/{len(bills_data)}: {metadata.get('title', 'Unknown')[:80]}..."
                )

                # Batch upsert
                if len(vectors) >= batch_size:
                    print(f"  Upserting batch of {len(vectors)} vectors...")
                    self.index.upsert(vectors=vectors)
                    vectors = []
                    time.sleep(1)  # Rate limiting

            except Exception as e:
                print(f"  Error processing bill {i+1}: {e}")
                continue

        # Upsert remaining vectors
        if vectors:
            print(f"  Upserting final batch of {len(vectors)} vectors...")
            self.index.upsert(vectors=vectors)

        print(
            f"Successfully processed and upserted {processed_count} bills to Pinecone!"
        )

        # Show index stats
        stats = self.index.describe_index_stats()
        print(f"Index now contains {stats['total_vector_count']} vectors")


def main():
    """Main function"""
    print("InShort Bills Pinecone Upserter")
    print("=" * 40)

    # Get API key from environment
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_api_key:
        print("Error: PINECONE_API_KEY not found in environment variables")
        print("Please make sure you have a .env file with your Pinecone API key")
        return

    # Initialize processor
    processor = BillUpsertProcessor(pinecone_api_key)

    # Process bills
    json_file_path = "../inshort_bills.json"  # Relative to RAG directory
    if not os.path.exists(json_file_path):
        json_file_path = "inshort_bills.json"  # Try current directory

    if os.path.exists(json_file_path):
        processor.process_and_upsert_bills(json_file_path)
    else:
        print(f"Error: Could not find inshort_bills.json file")
        print(
            "Please make sure the file exists in the current directory or parent directory"
        )


if __name__ == "__main__":
    main()
