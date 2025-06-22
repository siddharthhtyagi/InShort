#!/usr/bin/env python3
"""
Pinecone Search Script for InShort Bills

This script allows you to search through the bills stored in Pinecone
using semantic similarity search.
"""

import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pinecone import Pinecone
import argparse

# Load environment variables
load_dotenv()


class BillSearcher:
    """Searches bill data in Pinecone using semantic similarity"""

    def __init__(self, pinecone_api_key: str, index_name: str = "bills"):
        """Initialize the searcher with Pinecone connection"""
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index = self.pc.Index(index_name)

    def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text using OpenAI API (same as upsert)"""
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

    def search_bills(
        self, query: str, top_k: int = 5, min_score: float = 0.0
    ) -> List[Dict]:
        """Search for bills similar to the query"""
        print(f"🔍 Searching for: '{query}'")
        print("-" * 50)

        # Generate embedding for query
        query_embedding = self.generate_embeddings(query)

        # Search Pinecone index
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            include_values=False,
        )

        # Filter results by minimum score
        filtered_results = [
            match for match in results["matches"] if match["score"] >= min_score
        ]

        return filtered_results

    def format_search_results(self, results: List[Dict]) -> str:
        """Format search results for display"""
        if not results:
            return "❌ No bills found matching your query.\n"

        output = f"✅ Found {len(results)} relevant bills:\n\n"

        for i, match in enumerate(results, 1):
            metadata = match.get("metadata", {})
            score = match.get("score", 0)

            # Extract key information
            title = metadata.get("title", "Unknown Title")
            bill_number = metadata.get("bill_number", "N/A")
            bill_type = metadata.get("bill_type", "N/A")
            congress = metadata.get("congress", "N/A")
            sponsor = metadata.get("primary_sponsor", "N/A")
            party = metadata.get("sponsor_party", "N/A")
            state = metadata.get("sponsor_state", "N/A")
            policy_area = metadata.get("policy_area", "N/A")
            latest_action_date = metadata.get("latest_action_date", "N/A")

            # Format bill identifier
            bill_id = (
                f"{bill_type.upper()}{bill_number}"
                if bill_type != "N/A" and bill_number != "N/A"
                else "Unknown"
            )

            output += f"#{i} - {bill_id} (Score: {score:.3f})\n"
            output += f"📋 Title: {title}\n"
            output += f"👤 Sponsor: {sponsor}"
            if party != "N/A" and state != "N/A":
                output += f" ({party}-{state})"
            output += f"\n🏛️  Congress: {congress}"
            if policy_area != "N/A":
                output += f" | Policy Area: {policy_area}"
            if latest_action_date != "N/A":
                output += f"\n📅 Latest Action: {latest_action_date}"
            output += f"\n{'-' * 50}\n"

        return output

    def interactive_search(self):
        """Run interactive search mode"""
        print("🏛️  InShort Bills Search Interface")
        print("=" * 50)
        print("Enter your search queries to find relevant bills.")
        print("Type 'quit' or 'exit' to stop.\n")

        while True:
            try:
                query = input("Enter search query: ").strip()

                if query.lower() in ["quit", "exit", "q"]:
                    print("👋 Goodbye!")
                    break

                if not query:
                    print("Please enter a search query.\n")
                    continue

                # Parse optional parameters
                top_k = 5
                min_score = 0.0

                # Check for parameters in query
                if " --top" in query:
                    parts = query.split(" --top")
                    query = parts[0].strip()
                    try:
                        top_k = int(parts[1].strip())
                    except:
                        print("Invalid --top parameter, using default (5)")

                if " --min-score" in query:
                    parts = query.split(" --min-score")
                    query = parts[0].strip()
                    try:
                        min_score = float(parts[1].strip())
                    except:
                        print("Invalid --min-score parameter, using default (0.0)")

                # Search and display results
                results = self.search_bills(query, top_k=top_k, min_score=min_score)
                formatted_results = self.format_search_results(results)
                print(formatted_results)

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error during search: {e}\n")

    def single_search(self, query: str, top_k: int = 5, min_score: float = 0.0):
        """Perform a single search and return formatted results"""
        results = self.search_bills(query, top_k=top_k, min_score=min_score)
        return self.format_search_results(results)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Search bills in Pinecone index")
    parser.add_argument("--query", "-q", type=str, help="Search query")
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)",
    )
    parser.add_argument(
        "--min-score",
        "-s",
        type=float,
        default=0.0,
        help="Minimum similarity score (default: 0.0)",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run in interactive mode"
    )

    args = parser.parse_args()

    # Get API key from environment
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_api_key:
        print("❌ Error: PINECONE_API_KEY not found in environment variables")
        print("Please make sure you have a .env file with your Pinecone API key")
        return

    # Initialize searcher
    try:
        searcher = BillSearcher(pinecone_api_key)

        # Check index stats
        stats = searcher.index.describe_index_stats()
        print(f"📊 Index contains {stats['total_vector_count']} bills\n")

        if args.query:
            # Single search mode
            results = searcher.single_search(
                args.query, top_k=args.top_k, min_score=args.min_score
            )
            print(results)
        elif args.interactive:
            # Interactive mode
            searcher.interactive_search()
        else:
            # Default to interactive mode
            searcher.interactive_search()

    except Exception as e:
        print(f"❌ Error initializing searcher: {e}")
        print("Make sure your Pinecone API key is correct and the index exists.")


if __name__ == "__main__":
    main()
