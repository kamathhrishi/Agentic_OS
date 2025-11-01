"""Hyperspell integration helpers for Agentic OS."""

from __future__ import annotations

import os
import logging
import textwrap
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel


logger = logging.getLogger(__name__)

# Load environment variables (no-op if already loaded by main application)
load_dotenv()


HYPERSPELL_API_KEY = os.getenv("HYPERSPELL_API_KEY", "").strip()
HYPERSPELL_AS_USER = os.getenv("HYPERSPELL_AS_USER", "").strip()
HYPERSPELL_USER_TOKEN = os.getenv("HYPERSPELL_USER_TOKEN", "").strip()
HYPERSPELL_BASE_URL = os.getenv("HYPERSPELL_BASE_URL", "https://api.hyperspell.com").rstrip("/")
HYPERSPELL_QUERY_PATH = os.getenv("HYPERSPELL_QUERY_PATH", "/memories/query")
HYPERSPELL_RECORD_PATH = os.getenv("HYPERSPELL_RECORD_PATH", "").strip()
HYPERSPELL_TIMEOUT = float(os.getenv("HYPERSPELL_TIMEOUT_SECONDS", "10"))


class HyperspellMemory(BaseModel):
    """Structured representation of a Hyperspell memory item."""

    source: str
    snippet: str
    title: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = {}

    def to_prompt_line(self) -> str:
        """Format the memory as a single prompt-compatible line."""

        label = self.title or "Untitled"
        snippet = textwrap.shorten(self.snippet.strip(), width=220, placeholder="…")
        segments = [f"[{self.source}] {label}: {snippet}"]

        if self.timestamp:
            segments.append(f"(timestamp: {self.timestamp})")
        if self.url:
            segments.append(f"(url: {self.url})")

        return " ".join(segments)


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


class HyperspellClient:
    """Lightweight HTTP client wrapper for the Hyperspell API."""

    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()
        self.base_url = HYPERSPELL_BASE_URL
        self.query_path = HYPERSPELL_QUERY_PATH
        self.record_path = HYPERSPELL_RECORD_PATH

    @property
    def is_configured(self) -> bool:
        """Return True when a real API key is available."""

        return bool(self.api_key and not self.api_key.startswith("mock"))

    @property
    def supports_recording(self) -> bool:
        """Return True when ingest endpoints are available."""

        return self.is_configured and bool(self.record_path)

    def _headers(self, override_key: Optional[str] = None) -> Dict[str, str]:
        token = (override_key or self.api_key).strip()
        if HYPERSPELL_USER_TOKEN:
            token = HYPERSPELL_USER_TOKEN
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if HYPERSPELL_AS_USER and not HYPERSPELL_USER_TOKEN:
            headers["X-As-User"] = HYPERSPELL_AS_USER
        return headers

    async def fetch_context(
        self,
        user_id: str,
        query: str,
        *,
        sources: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[HyperspellMemory]:
        """Fetch contextual memories from Hyperspell for the given query."""

        if not self.is_configured:
            return []

        payload: Dict[str, Any] = {"query": query, "answer": False}
        if sources:
            payload["sources"] = sources
        if limit:
            payload["max_results"] = limit

        try:
            async with httpx.AsyncClient(timeout=HYPERSPELL_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}{self.query_path}",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Hyperspell context request failed (%s): %s",
                exc.response.status_code,
                exc.response.text,
            )
            return []
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Hyperspell context request error: %s", exc)
            return []

        return self._parse_memories(data)

    async def record_interaction(
        self,
        user_id: str,
        *,
        user_message: str,
        assistant_message: str,
        sources: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Push the conversation turn to Hyperspell for future recall."""

        if not self.supports_recording:
            return

        payload: Dict[str, Any] = {
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ],
        }

        if sources:
            payload["sources"] = sources
        if metadata:
            payload["metadata"] = metadata

        try:
            async with httpx.AsyncClient(timeout=HYPERSPELL_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}{self.record_path}",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Hyperspell ingest request failed (%s): %s",
                exc.response.status_code,
                exc.response.text,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Hyperspell ingest request error: %s", exc)

    def _parse_memories(self, payload: Any) -> List[HyperspellMemory]:
        """Normalise API responses into HyperspellMemory objects."""

        if payload is None:
            return []

        if isinstance(payload, dict):
            if "documents" in payload:
                payload = payload.get("documents")
            else:
                for key in ("memories", "items", "results", "data"):
                    value = payload.get(key)
                    if value:
                        payload = value
                        break

        if not isinstance(payload, list):
            return []

        memories: List[HyperspellMemory] = []
        for item in payload:
            if not isinstance(item, dict):
                continue

            metadata = item.get("metadata") or {}
            snippet = (
                item.get("snippet")
                or item.get("summary")
                or item.get("content")
                or metadata.get("summary")
                or metadata.get("description")
                or metadata.get("notes")
                or item.get("title")
                or metadata.get("url")
                or ""
            )

            if not snippet:
                continue

            memory = HyperspellMemory(
                source=item.get("source")
                or item.get("integration")
                or item.get("type")
                or "unknown",
                title=item.get("title") or item.get("name"),
                snippet=snippet,
                url=item.get("url") or item.get("link") or metadata.get("url"),
                timestamp=item.get("timestamp")
                or item.get("created_at")
                or metadata.get("last_modified")
                or metadata.get("created_at"),
                metadata=metadata,
            )
            memories.append(memory)

        return memories

    def generate_user_token(self, user_id: str) -> str:
        """Generate a mock user token (replace with official SDK when available)."""

        import time
        import jwt

        payload = {
            "user_id": user_id,
            "app_token": (self.api_key or "mock")[:10] + "...",
            "iat": int(time.time()),
            "exp": int(time.time()) + (24 * 60 * 60),
        }

        return jwt.encode(payload, "mock-secret-key", algorithm="HS256")

    def get_user_info(self, user_token: str) -> Dict[str, Any]:
        """Return mock user info (replace with live call when SDK is available)."""

        return {"user_id": "user_123", "connected_integrations": []}

    def list_integrations(self) -> List[Dict[str, Any]]:
        """Return mocked integration catalogue."""

        return [
            {
                "id": "google_calendar",
                "name": "Google Calendar",
                "description": "Sync your Google Calendar events and meetings",
                "icon": "fa-calendar",
                "category": "productivity",
            },
            {
                "id": "notion",
                "name": "Notion",
                "description": "Access your Notion workspace and pages",
                "icon": "fa-book",
                "category": "productivity",
            },
            {
                "id": "slack",
                "name": "Slack",
                "description": "Connect to Slack channels and messages",
                "icon": "fa-slack",
                "category": "communication",
            },
            {
                "id": "gmail",
                "name": "Gmail",
                "description": "Sync your Gmail inbox and emails",
                "icon": "fa-envelope",
                "category": "communication",
            },
            {
                "id": "google_drive",
                "name": "Google Drive",
                "description": "Access files from Google Drive",
                "icon": "fa-google-drive",
                "category": "storage",
            },
            {
                "id": "dropbox",
                "name": "Dropbox",
                "description": "Sync files from Dropbox",
                "icon": "fa-dropbox",
                "category": "storage",
            },
            {
                "id": "github",
                "name": "GitHub",
                "description": "Access repositories and code",
                "icon": "fa-github",
                "category": "development",
            },
            {
                "id": "linear",
                "name": "Linear",
                "description": "Sync Linear issues and projects",
                "icon": "fa-tasks",
                "category": "productivity",
            },
        ]

    def get_integration_link(
        self, integration_id: str, user_token: str, redirect_uri: Optional[str] = None
    ) -> str:
        """Return mocked integration link for local testing."""

        params = f"?token={user_token}"
        if redirect_uri:
            params += f"&redirect_uri={redirect_uri}"
        return f"https://connect.hyperspell.com/link/{integration_id}{params}"


def format_memories_for_prompt(
    memories: List[HyperspellMemory], max_items: int = 5
) -> str:
    """Format memories into a concise context block."""

    if not memories:
        return ""

    lines = [memory.to_prompt_line() for memory in memories[:max_items]]
    return "\n".join(lines)


_hyperspell_client: Optional[HyperspellClient] = None


def get_hyperspell_client() -> HyperspellClient:
    """Return a cached Hyperspell client instance."""

    global _hyperspell_client

    if _hyperspell_client is None:
        if not HYPERSPELL_API_KEY:
            logger.warning("HYPERSPELL_API_KEY not set; using mock client")
            _hyperspell_client = HyperspellClient(api_key="mock-api-key")
        else:
            _hyperspell_client = HyperspellClient(api_key=HYPERSPELL_API_KEY)

    return _hyperspell_client


def hyperspell_is_configured() -> bool:
    """Convenience helper to check whether Hyperspell is ready."""

    return get_hyperspell_client().is_configured
