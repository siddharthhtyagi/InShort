import requests
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from langchain_core.tools import tool

# Configuration
API_KEY = "AJU2VngV3zS2RHP7qj557OWiyzQPj4PhEAeluBrL"
BASE_URL = "https://api.congress.gov/v3/bill"

@tool
def fetch_congress_bills(limit: int = 20, congress: int = 118, bill_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch Congress bills from the Congress.gov API.
    
    Args:
        limit: Number of bills to fetch (default 20, max 250)
        congress: Congress number (default 118 for current Congress)
        bill_type: Filter by bill type ('hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres')
    
    Returns:
        List of bill dictionaries with details
    """
    
    # Build parameters
    params = {
        'api_key': API_KEY,
        'limit': min(limit, 250),  # API limit is 250
        'format': 'json'
    }
    
    # Add optional filters
    if congress:
        params['congress'] = congress
    if bill_type:
        params['type'] = bill_type
    
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        
        data = response.json()
        bills = data.get('bills', [])
        
        # Format bills for easier consumption
        formatted_bills = []
        for bill in bills:
            formatted_bill = {
                'title': bill.get('title', 'No title'),
                'number': bill.get('number', 'N/A'),
                'type': bill.get('type', 'N/A'),
                'congress': bill.get('congress', 'N/A'),
                'url': bill.get('url', 'N/A'),
                'latest_action': {},
                'sponsor': {}
            }
            
            # Get latest action if available
            latest_action = bill.get('latestAction', {})
            if latest_action:
                formatted_bill['latest_action'] = {
                    'date': latest_action.get('actionDate', 'N/A'),
                    'text': latest_action.get('text', 'N/A')
                }
            
            # Get sponsor info if available
            sponsors = bill.get('sponsors', [])
            if sponsors:
                sponsor = sponsors[0]  # Primary sponsor
                formatted_bill['sponsor'] = {
                    'name': sponsor.get('fullName', 'N/A'),
                    'party': sponsor.get('party', 'N/A'),
                    'state': sponsor.get('state', 'N/A')
                }
            
            formatted_bills.append(formatted_bill)
        
        return formatted_bills
        
    except requests.exceptions.RequestException as e:
        return [{'error': f'Request failed: {str(e)}'}]
    except json.JSONDecodeError as e:
        return [{'error': f'JSON parsing failed: {str(e)}'}]

@tool
def search_bills_by_keyword(keyword: str, limit: int = 10, congress: int = 118) -> List[Dict[str, Any]]:
    """
    Search for bills containing specific keywords.
    
    Args:
        keyword: Search term to look for in bill titles and content
        limit: Number of bills to return (default 10, max 250)
        congress: Congress number to search in (default 118)
    
    Returns:
        List of matching bill dictionaries
    """
    
    params = {
        'api_key': API_KEY,
        'limit': min(limit, 250),
        'format': 'json',
        'q': keyword,
        'congress': congress
    }
    
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        
        data = response.json()
        bills = data.get('bills', [])
        
        # Format search results
        search_results = []
        for bill in bills:
            result = {
                'title': bill.get('title', 'No title'),
                'bill_number': f"{bill.get('type', '')}{bill.get('number', '')}",
                'type': bill.get('type', 'N/A'),
                'congress': bill.get('congress', 'N/A'),
                'url': bill.get('url', 'N/A'),
                'search_keyword': keyword
            }
            
            # Add sponsor if available
            sponsors = bill.get('sponsors', [])
            if sponsors:
                sponsor = sponsors[0]
                result['sponsor'] = f"{sponsor.get('fullName', 'N/A')} ({sponsor.get('party', 'N/A')}-{sponsor.get('state', 'N/A')})"
            
            search_results.append(result)
        
        return search_results
        
    except requests.exceptions.RequestException as e:
        return [{'error': f'Search failed: {str(e)}'}]

@tool
def get_bill_details(congress: str, bill_type: str, bill_number: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific Congressional bill using the Congress.gov API.
    
    Args:
        congress: Congress number (e.g., '117', '118')
        bill_type: Type of bill ('hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres')
        bill_number: Bill number (e.g., '3076')
    
    Returns:
        Dictionary with detailed bill information including title, sponsors, actions, summary, etc.
    
    Example:
        get_congress_bill_details("117", "hr", "3076")
    """
    
    # Construct the API URL
    url = f"{BASE_URL}/{congress}/{bill_type}/{bill_number}"
    
    params = {
        'api_key': API_KEY,
        'format': 'json'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # Check if response has content
        if not response.content:
            return {'error': 'Empty response from API'}
        
        # Parse JSON response
        try:
            data = response.json()
        except ValueError as json_error:
            return {'error': f'Invalid JSON response: {str(json_error)}'}
        
        # Debug: Log the response structure
        print(f"API Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # Validate response structure
        if not isinstance(data, dict):
            return {'error': f'Unexpected response format: {type(data).__name__}, content: {str(data)[:200]}'}
        
        bill = data.get('bill')
        if not bill:
            return {'error': f'No bill data found. Available keys: {list(data.keys())}'}
        
        if not isinstance(bill, dict):
            return {'error': f'Bill data is not a dictionary: {type(bill).__name__}, content: {str(bill)[:200]}'}
        
        # Extract and structure bill information with safe access
        bill_details = {}
        
        try:
            bill_details = {
                'bill_id': f"{bill.get('type', '').upper()}{bill.get('number', '')}",
                'congress': bill.get('congress'),
                'title': bill.get('title', 'No title available'),
                'bill_type': bill.get('type', '').upper(),
                'bill_number': bill.get('number'),
                'introduced_date': bill.get('introducedDate'),
                'origin_chamber': bill.get('originChamber'),
                'url': bill.get('url'),
                'sponsors': [],
                'cosponsors_count': 0,
                'committees': [],
                'latest_action': {},
                'summary': 'No summary available'
            }
            
            # Extract policy area safely
            policy_area = bill.get('policyArea')
            if isinstance(policy_area, dict):
                bill_details['policy_area'] = policy_area.get('name')
            else:
                bill_details['policy_area'] = None
                
        except Exception as e:
            return {'error': f'Error extracting basic bill info: {str(e)}'}
        
        # Extract sponsor information safely
        try:
            sponsors = bill.get('sponsors', [])
            if isinstance(sponsors, list):
                for sponsor in sponsors:
                    if isinstance(sponsor, dict):
                        sponsor_info = {
                            'name': sponsor.get('fullName', 'N/A'),
                            'party': sponsor.get('party', 'N/A'),
                            'state': sponsor.get('state', 'N/A'),
                            'district': sponsor.get('district'),
                            'bioguide_id': sponsor.get('bioguideId')
                        }
                        bill_details['sponsors'].append(sponsor_info)
        except Exception as e:
            print(f"Error extracting sponsors: {e}")
        
        # Extract cosponsor count safely
        try:
            cosponsors = bill.get('cosponsors')
            if isinstance(cosponsors, dict):
                bill_details['cosponsors_count'] = cosponsors.get('count', 0)
        except Exception as e:
            print(f"Error extracting cosponsors: {e}")
        
        # Extract latest action safely
        try:
            latest_action = bill.get('latestAction')
            if isinstance(latest_action, dict):
                bill_details['latest_action'] = {
                    'date': latest_action.get('actionDate', 'N/A'),
                    'text': latest_action.get('text', 'N/A')
                }
        except Exception as e:
            print(f"Error extracting latest action: {e}")
        
        return bill_details
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {'error': f'Bill not found: {congress}/{bill_type}/{bill_number}'}
        else:
            return {'error': f'HTTP error {e.response.status_code}: {str(e)}'}
    except requests.exceptions.RequestException as e:
        return {'error': f'Request failed: {str(e)}'}
    except ValueError as e:
        return {'error': f'Failed to parse JSON response: {str(e)}'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}
    
@tool
def get_bills_by_sponsor(sponsor_name: str, limit: int = 10, congress: int = 118) -> List[Dict[str, Any]]:
    """
    Find bills sponsored by a specific member of Congress.
    
    Args:
        sponsor_name: Full name or last name of the sponsor
        limit: Number of bills to return (default 10)
        congress: Congress number (default 118)
    
    Returns:
        List of bills sponsored by the specified person
    """
    
    # First get a larger set of bills to search through
    bills = fetch_congress_bills(limit=250, congress=congress)
    
    if bills and 'error' in bills[0]:
        return bills
    
    # Filter bills by sponsor name
    sponsored_bills = []
    sponsor_name_lower = sponsor_name.lower()
    
    for bill in bills:
        sponsor = bill.get('sponsor', {})
        sponsor_full_name = sponsor.get('name', '').lower()
        
        if sponsor_name_lower in sponsor_full_name:
            sponsored_bills.append({
                'title': bill['title'],
                'bill_number': f"{bill['type']}{bill['number']}",
                'sponsor': sponsor.get('name', 'N/A'),
                'party': sponsor.get('party', 'N/A'),
                'state': sponsor.get('state', 'N/A'),
                'latest_action_date': bill.get('latest_action', {}).get('date', 'N/A'),
                'url': bill['url']
            })
            
            if len(sponsored_bills) >= limit:
                break
    
    return sponsored_bills

@tool
def get_bills_by_subject(subject: str, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Get bills related to a specific subject area.
    
    Args:
        subject: Subject to search for (e.g., 'healthcare', 'education', 'defense', 'immigration')
        limit: Number of bills to return (default 15)
    
    Returns:
        List of bills related to the subject
    """
    
    # Use the search function with subject-related keywords
    subject_bills = search_bills_by_keyword(subject, limit=limit)
    
    if subject_bills and 'error' in subject_bills[0]:
        return subject_bills
    
    # Enhance results with subject classification
    for bill in subject_bills:
        bill['subject_area'] = subject
        bill['relevance'] = 'keyword_match'
    
    return subject_bills

# Tool list for easy import
congress_tools = [
    fetch_congress_bills,
    search_bills_by_keyword,
    get_bill_details,
    get_bills_by_sponsor,
    get_bills_by_subject
]

# Example usage in a LangGraph workflow
if __name__ == "__main__":
    # Test the tools
    print("=== Testing Congress Bills Tools ===")
    
    # Test 1: Fetch recent bills
    print("\n1. Recent Bills:")
    recent = fetch_congress_bills(limit=3)
    for bill in recent[:2]:
        print(f"- {bill['title'][:100]}...")
    
    # Test 2: Search by keyword
    print("\n2. Healthcare Bills:")
    healthcare = search_bills_by_keyword("healthcare", limit=2)
    for bill in healthcare:
        print(f"- {bill['title'][:80]}...")
    
    # Test 3: Bills by subject
    print("\n3. Education Bills:")
    education = get_bills_by_subject("education", limit=2)
    for bill in education:
        print(f"- {bill['title'][:80]}...")