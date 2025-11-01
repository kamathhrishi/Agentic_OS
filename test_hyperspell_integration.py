"""
Test script for Hyperspell integration in Agentic OS
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hyperspell_integration import get_hyperspell_client

def test_user_token_generation():
    """Test user token generation"""
    print("Testing user token generation...")
    client = get_hyperspell_client()
    token = client.generate_user_token("test_user_123")
    print(f"✓ User token generated: {token[:50]}...")
    return True

def test_list_integrations():
    """Test listing integrations"""
    print("\nTesting integration listing...")
    client = get_hyperspell_client()
    integrations = client.list_integrations()
    print(f"✓ Found {len(integrations)} integrations:")
    for integration in integrations:
        print(f"  - {integration['name']}: {integration['description']}")
    return True

def test_integration_link():
    """Test generating integration link"""
    print("\nTesting integration link generation...")
    client = get_hyperspell_client()
    user_token = client.generate_user_token("test_user_123")
    link = client.get_integration_link("google_calendar", user_token)
    print(f"✓ Integration link generated: {link}")
    return True

def test_user_info():
    """Test getting user info"""
    print("\nTesting user info retrieval...")
    client = get_hyperspell_client()
    user_token = client.generate_user_token("test_user_123")
    user_info = client.get_user_info(user_token)
    print(f"✓ User info retrieved: {user_info}")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Hyperspell Integration Test Suite")
    print("=" * 60)

    try:
        test_user_token_generation()
        test_list_integrations()
        test_integration_link()
        test_user_info()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print("\nThe Hyperspell integration is ready to use!")
        print("\nTo start the Agentic OS:")
        print("  1. Make sure all dependencies are installed:")
        print("     pip install -r requirements.txt")
        print("\n  2. Set your API keys in .env file:")
        print("     OPENAI_API_KEY=your_key_here")
        print("     HYPERSPELL_API_KEY=your_hyperspell_key  (optional for testing)")
        print("\n  3. Run the application:")
        print("     python main.py")
        print("\n  4. Open your browser and navigate to:")
        print("     http://localhost:8000")
        print("\n  5. Click on the 'Sync' icon on the desktop to test!")

    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
