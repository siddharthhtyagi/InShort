import json
import os
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# Initialize Pinecone
pc = Pinecone(
    api_key="pcsk_GNsF9_TsFND8SaQnpYVPFjibH7YjRGP2x2R6ALf4sfgFhArFKwnMt52m1zzFPATZGQ2sq"
)

# Initialize embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")


def create_index_if_not_exists(index_name, dimension=384):
    """Create Pinecone index if it doesn't exist"""
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"Created index: {index_name}")
    else:
        print(f"Index {index_name} already exists")

    return pc.Index(index_name)


def process_bill_data(bill_data):
    """Extract relevant text from bill data for embedding"""
    bill = bill_data.get("bill", {})

    # Extract key information
    title = bill.get("title", "")
    bill_number = f"{bill.get('type', '')}-{bill.get('number', '')}"
    sponsor_info = ""
    if bill.get("sponsors"):
        sponsor = bill["sponsors"][0]
        sponsor_info = f"Sponsored by {sponsor.get('fullName', '')}"

    policy_area = bill.get("policyArea", {}).get("name", "")
    latest_action = bill.get("latestAction", {}).get("text", "")

    # Create comprehensive text for embedding
    text_content = f"""
    Title: {title}
    Bill Number: {bill_number}
    {sponsor_info}
    Policy Area: {policy_area}
    Latest Action: {latest_action}
    """

    # Create metadata
    metadata = {
        "bill_number": bill_number,
        "title": title,
        "sponsor": sponsor_info,
        "policy_area": policy_area,
        "congress": bill.get("congress", ""),
        "introduced_date": bill.get("introducedDate", ""),
        "latest_action": latest_action,
        "origin_chamber": bill.get("originChamber", ""),
        "type": bill.get("type", ""),
    }

    return text_content.strip(), metadata


def upsert_bills_to_pinecone():
    """Main function to read JSON and upsert to Pinecone"""
    try:
        # Read JSON file
        print("Reading JSON file...")
        with open("inshort_bills.json", "r") as f:
            bills_data = json.load(f)

        print(f"Found {len(bills_data)} bills")

        # Create/connect to index
        index = create_index_if_not_exists("bills-index")

        # Process bills in batches
        batch_size = 100
        vectors = []

        for i, bill_data in enumerate(bills_data):
            try:
                # Process bill data
                text_content, metadata = process_bill_data(bill_data)

                # Generate embedding
                embedding = model.encode(text_content).tolist()

                # Create vector for upsert
                bill_id = f"bill_{i}"
                vectors.append(
                    {"id": bill_id, "values": embedding, "metadata": metadata}
                )

                # Upsert in batches
                if len(vectors) >= batch_size:
                    print(
                        f"Upserting batch {i//batch_size + 1} ({len(vectors)} vectors)..."
                    )
                    index.upsert(vectors)
                    vectors = []

            except Exception as e:
                print(f"Error processing bill {i}: {e}")
                continue

        # Upsert remaining vectors
        if vectors:
            print(f"Upserting final batch ({len(vectors)} vectors)...")
            index.upsert(vectors)

        # Check index stats
        print("\nIndex stats after upsert:")
        print(index.describe_index_stats())

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    upsert_bills_to_pinecone()
