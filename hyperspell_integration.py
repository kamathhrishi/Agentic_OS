"""
Hyperspell Integration Module for Agentic OS
Handles authentication, user token generation, and integration management
"""

import os
import logging
from typing import List, Optional, Dict
from pydantic import BaseModel
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Hyperspell API Configuration
HYPERSPELL_API_KEY = os.getenv("HYPERSPELL_API_KEY", "")
HYPERSPELL_BASE_URL = "https://api.hyperspell.com"

# Pydantic models
class UserTokenRequest(BaseModel):
    user_id: str

class UserTokenResponse(BaseModel):
    token: str
    user_id: str
    expires_at: Optional[str] = None

class IntegrationInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: Optional[str] = None
    connected: bool = False

class UserInfo(BaseModel):
    user_id: str
    connected_integrations: List[str] = []

# Mock Hyperspell Client (replace with actual hyperspell SDK when available)
class HyperspellClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = HYPERSPELL_BASE_URL

    def generate_user_token(self, user_id: str) -> str:
        """
        Generate a user token for Hyperspell Connect
        In production, this would call: client.auth.user_token(user_id=user_id)
        """
        # For now, return a mock token
        # TODO: Replace with actual Hyperspell SDK call when installed
        import jwt
        import time

        payload = {
            "user_id": user_id,
            "app_token": self.api_key[:10] + "...",  # Partial token for security
            "iat": int(time.time()),
            "exp": int(time.time()) + (24 * 60 * 60)  # 24 hours
        }

        # Generate a mock JWT token
        token = jwt.encode(payload, "mock-secret-key", algorithm="HS256")
        return token

    def get_user_info(self, user_token: str) -> Dict:
        """
        Get user information including connected integrations
        In production: GET /auth/me with user token
        """
        # Mock response
        return {
            "user_id": "user_123",
            "connected_integrations": []
        }

    def list_integrations(self) -> List[Dict]:
        """
        List all available integrations
        In production: GET /integrations/list
        """
        # Mock integrations based on Hyperspell's typical offerings
        return [
            {
                "id": "google_calendar",
                "name": "Google Calendar",
                "description": "Sync your Google Calendar events and meetings",
                "icon": "fa-calendar",
                "category": "productivity"
            },
            {
                "id": "notion",
                "name": "Notion",
                "description": "Access your Notion workspace and pages",
                "icon": "fa-book",
                "category": "productivity"
            },
            {
                "id": "slack",
                "name": "Slack",
                "description": "Connect to Slack channels and messages",
                "icon": "fa-slack",
                "category": "communication"
            },
            {
                "id": "gmail",
                "name": "Gmail",
                "description": "Sync your Gmail inbox and emails",
                "icon": "fa-envelope",
                "category": "communication"
            },
            {
                "id": "google_drive",
                "name": "Google Drive",
                "description": "Access files from Google Drive",
                "icon": "fa-google-drive",
                "category": "storage"
            },
            {
                "id": "dropbox",
                "name": "Dropbox",
                "description": "Sync files from Dropbox",
                "icon": "fa-dropbox",
                "category": "storage"
            },
            {
                "id": "github",
                "name": "GitHub",
                "description": "Access repositories and code",
                "icon": "fa-github",
                "category": "development"
            },
            {
                "id": "linear",
                "name": "Linear",
                "description": "Sync Linear issues and projects",
                "icon": "fa-tasks",
                "category": "productivity"
            }
        ]

    def get_integration_link(self, integration_id: str, user_token: str, redirect_uri: Optional[str] = None) -> str:
        """
        Generate a link to connect an integration
        In production: GET /integrations/{integration_id}/link
        """
        params = f"?token={user_token}"
        if redirect_uri:
            params += f"&redirect_uri={redirect_uri}"

        return f"https://connect.hyperspell.com/link/{integration_id}{params}"


# Initialize client
hyperspell_client = None

def get_hyperspell_client() -> HyperspellClient:
    """Get or create Hyperspell client instance"""
    global hyperspell_client

    if hyperspell_client is None:
        if not HYPERSPELL_API_KEY:
            logger.warning("HYPERSPELL_API_KEY not set in environment variables")
            # Return a mock client for development
            hyperspell_client = HyperspellClient(api_key="mock-api-key")
        else:
            hyperspell_client = HyperspellClient(api_key=HYPERSPELL_API_KEY)

    return hyperspell_client
