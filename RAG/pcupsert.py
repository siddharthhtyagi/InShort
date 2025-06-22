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

    def __init__(self, pinecone_api_key: str, index_name: str = "bills-index"):
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
                    dimensions=384,  # Match the Pinecone index dimension
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

        # Generate a 384-dimensional embedding to match Pinecone index
        embedding = [random.uniform(-1, 1) for _ in range(384)]
        return embedding

    def extract_bill_text(self, bill_data: Dict) -> str:
        """Extract rich text content from bill data for semantic embedding"""
        import re
        text_parts = []

        bill = bill_data.get("bill", {})

        # Title
        if title := bill.get("title"):
            text_parts.append(f"Title: {title}")

        # Summary
        summaries = bill_data.get("summaries_details", {}).get("summaries", [])
        for summary in summaries:
            summary_text = summary.get("text", "")
            clean_text = re.sub(r"<[^>]+>", "", summary_text)
            if clean_text.strip():
                text_parts.append(f"Summary: {clean_text}")

        # Sponsors
        sponsors = bill.get("sponsors", [])
        sponsor_names = [s.get("fullName") for s in sponsors if s.get("fullName")]
        if sponsor_names:
            text_parts.append(f"Sponsors: {', '.join(sponsor_names)}")

        # Cosponsors
        cosponsors = bill_data.get("cosponsors_details", {}).get("cosponsors", [])
        cosponsor_list = [
            f"{c['fullName']} ({c['party']}-{c['state']})"
            for c in cosponsors if "fullName" in c
        ]
        if cosponsor_list:
            text_parts.append(f"Cosponsors: {', '.join(cosponsor_list)}")

        # Policy Area
        if policy := bill.get("policyArea", {}).get("name"):
            text_parts.append(f"Policy Area: {policy}")

        # Subjects
        subjects = bill_data.get("subjects_details", {}).get("subjects", {}).get("legislativeSubjects", [])
        subject_names = [s.get("name") for s in subjects if s.get("name")]
        if subject_names:
            text_parts.append(f"Subjects: {', '.join(subject_names)}")

        # Latest Action
        if latest_action := bill.get("latestAction", {}).get("text"):
            text_parts.append(f"Latest Action: {latest_action}")

        # Action history
        actions = bill_data.get("actions_details", {}).get("actions", [])
        action_descriptions = []
        for act in actions:
            action_text = act.get("text")
            action_date = act.get("actionDate")
            if action_text and action_date:
                action_descriptions.append(f"[{action_date}] {action_text}")
        if action_descriptions:
            text_parts.append(f"Action History: {' | '.join(action_descriptions)}")

        return "\n".join(text_parts)

    def create_bill_metadata(self, bill_data: Dict) -> Dict:
        """Extract metadata for the bill"""
        metadata = {}

        if "bill" in bill_data:
            bill = bill_data["bill"]
            metadata.update(
                {
                    "bill_number": f"{bill.get('type', '')}-{bill.get('number', '')}",
                    "type": bill.get("type", ""),
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
                metadata["sponsor"] = f"Sponsored by {sponsor.get('fullName', '')}"
                metadata["sponsor_party"] = sponsor.get("party", "")
                metadata["sponsor_state"] = sponsor.get("state", "")

            # Add policy area
            if "policyArea" in bill and "name" in bill["policyArea"]:
                metadata["policy_area"] = bill["policyArea"]["name"]

            # Add latest action
            if "latestAction" in bill:
                metadata["latest_action"] = bill["latestAction"].get("text", "")
                metadata["latest_action_date"] = bill["latestAction"].get("actionDate", "")

            # Add summary if available
            summary = ""
            if 'summaries_details' in bill_data:
                summaries = bill_data['summaries_details'].get('summaries', [])
                if summaries:
                    summary_text = summaries[0].get('text', '')
                    # Clean HTML tags from summary
                    import re
                    summary = re.sub(r"<[^>]+>", "", summary_text)
            metadata["summary"] = summary

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
                bill_id = f"bill_{metadata.get('congress', 'unknown')}_{metadata.get('type', 'unknown')}{metadata.get('bill_number', i)}"

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
    processor = BillUpsertProcessor(pinecone_api_key, index_name="bills-index")

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