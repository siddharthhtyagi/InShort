import json
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
    
    # Extract summary if available
    summary = ""
    if 'summaries_details' in bill_data:
        summaries = bill_data['summaries_details'].get('summaries', [])
        if summaries:
            summary = summaries[0].get('text', '')

    # Create comprehensive text for embedding
    text_content = f"""
    Title: {title}
    Bill Number: {bill_number}
    {sponsor_info}
    Policy Area: {policy_area}
    Latest Action: {latest_action}
    Summary: {summary}
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
        "summary": summary,  # Include summary in metadata
    }

    return text_content.strip(), metadata


def debug_upsert_bills_to_pinecone():
    """Debug version to identify upsert issues"""
    try:
        # Read JSON file
        print("Reading JSON file...")
        with open("inshort_bills.json", "r") as f:
            bills_data = json.load(f)

        print(f"Found {len(bills_data)} bills")

        # Create/connect to index
        index = create_index_if_not_exists("bills-index")
        
        # Check initial stats
        print("\nInitial index stats:")
        print(index.describe_index_stats())

        # Process just the first 5 bills for debugging
        print("\nProcessing first 5 bills for debugging...")
        
        for i, bill_data in enumerate(bills_data[:5]):
            try:
                print(f"\nProcessing bill {i+1}...")
                
                # Process bill data
                text_content, metadata = process_bill_data(bill_data)
                print(f"  Title: {metadata.get('title', 'Unknown')[:50]}...")
                print(f"  Text content length: {len(text_content)}")
                
                # Generate embedding
                embedding = model.encode(text_content).tolist()
                print(f"  Embedding dimension: {len(embedding)}")
                
                # Create vector for upsert
                bill_id = f"bill_{i}"
                vector_data = {"id": bill_id, "values": embedding, "metadata": metadata}
                print(f"  Vector ID: {bill_id}")
                
                # Try to upsert single vector
                print(f"  Attempting to upsert...")
                try:
                    result = index.upsert(vectors=[vector_data])
                    print(f"  ✅ Upsert successful: {result}")
                except Exception as upsert_error:
                    print(f"  ❌ Upsert failed: {upsert_error}")
                    continue
                
                # Check stats after each upsert
                stats = index.describe_index_stats()
                print(f"  Index stats after upsert: {stats['total_vector_count']} vectors")

            except Exception as e:
                print(f"  ❌ Error processing bill {i}: {e}")
                continue

        # Final stats check
        print("\nFinal index stats:")
        final_stats = index.describe_index_stats()
        print(final_stats)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    debug_upsert_bills_to_pinecone() 