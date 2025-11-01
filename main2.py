from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import uvicorn
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator, Tuple, Dict, Any
import json
import asyncio
import logging
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
import base64 as b64
from voice_agent import initialize_voice_agent, get_voice_agent, VoiceConfig
from slide_templates import HTML_TEMPLATE, SLIDE_TEMPLATES, create_slide_content
from hyperspell_integration import (
    get_hyperspell_client,
    format_memories_for_prompt,
    HyperspellMemory,
)
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page
import base64
from io import BytesIO
import re
from urllib.parse import urljoin, urlparse, urlunparse
import time
import random
import string

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chat.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agentic OS")

# Load environment variables
load_dotenv()

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env file. Please create a .env file with your OpenAI API key.")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Hyperspell integration toggle
HYPERSPELL_API_KEY = os.getenv("HYPERSPELL_API_KEY", "").strip()
HYPERSPELL_ENABLED = bool(HYPERSPELL_API_KEY)

if HYPERSPELL_ENABLED:
    logger.info("Hyperspell integration enabled; context-aware responses will include Notion and calendar data." )
else:
    logger.info("Hyperspell integration disabled; set HYPERSPELL_API_KEY to enable contextual sync.")

# Initialize Voice Agent for STT → LLM → TTS pipeline
voice_config = VoiceConfig(
    tts_voice="nova",  # Options: alloy, echo, fable, onyx, nova, shimmer
    max_history=10,
    system_prompt="""You are an intelligent and charismatic AI assistant with personality.
You are helping users interact with their Agentic OS through voice.
Keep responses natural, engaging, and concise for voice conversations.
Be helpful, friendly, and show personality in your responses.
When users ask you to perform OS actions, acknowledge and help them naturally."""
)
initialize_voice_agent(OPENAI_API_KEY, voice_config)
logger.info("Voice Agent initialized successfully")

# Get the directory where main.py is located
BASE_DIR = Path(__file__).parent

# Create data directory for files
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Create Desktop directory
DESKTOP_DIR = DATA_DIR / "Desktop"
DESKTOP_DIR.mkdir(exist_ok=True)

# Serve static files (CSS, JS, images)
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates directory
templates_dir = BASE_DIR / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Conversation memory storage (in-memory, per session)
# Format: {session_id: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]}
conversation_history = {}

# Email storage (in-memory)
# Format: List of emails with latest first
email_inbox = []

# Email API endpoints
RAILWAY_EMAIL_API = "https://web-production-02ec.up.railway.app/compose-send"
RAILWAY_EMAIL_INBOX_API = "https://web-production-02ec.up.railway.app/emails"

# Browser instance (Playwright)
browser_instance: Optional[Browser] = None
browser_contexts = {}  # Store browser contexts per session

# Browser Agent Tasks - autonomous agents for each browser window
browser_agents = {}  # Format: {session_id: {"tasks": deque([...]), "status": "active/idle/thinking", "current_goal": "", "logs": [], "agent_task": None}}
agent_task_registry = {}  # Track running agent tasks

def get_conversation_history(session_id: str, max_pairs: int = 4):
    """Get conversation history for a session, limited to last max_pairs user-assistant pairs"""
    if session_id not in conversation_history:
        return []
    
    history = conversation_history[session_id]
    # Return last max_pairs * 2 messages (each pair has user + assistant)
    return history[-(max_pairs * 2):] if len(history) > max_pairs * 2 else history

def add_to_conversation_history(session_id: str, user_message: str, assistant_response: str):
    """Add a user-assistant pair to conversation history, maintaining max 4 pairs"""
    if session_id not in conversation_history:
        conversation_history[session_id] = []
    
    # Add new messages
    conversation_history[session_id].append({"role": "user", "content": user_message})
    conversation_history[session_id].append({"role": "assistant", "content": assistant_response})
    
    # Keep only last 4 pairs (8 messages total)
    max_messages = 4 * 2  # 4 pairs * 2 messages per pair
    if len(conversation_history[session_id]) > max_messages:
        conversation_history[session_id] = conversation_history[session_id][-max_messages:]


# Hyperspell context helpers
HYPERSPELL_CALENDAR_KEYWORDS = {
    "calendar",
    "schedule",
    "meeting",
    "meetings",
    "appointments",
    "appointment",
    "availability",
    "event",
    "events",
    "reminder",
    "reminders",
}

HYPERSPELL_NOTION_KEYWORDS = {
    "notion",
    "workspace",
    "wiki",
    "knowledge base",
    "knowledgebase",
    "notes",
    "note",
    "docs",
    "document",
    "documents",
    "page",
    "pages",
    "database",
    "roadmap",
    "spec",
    "specs",
    "project plan",
}


def detect_hyperspell_sources(
    user_message: str,
    recent_history: Optional[List[Dict[str, str]]] = None,
) -> List[str]:
    """Determine which Hyperspell sources should be queried for a request."""

    search_targets = [user_message]

    if recent_history:
        # Inspect the two most recent user messages to capture follow-ups like "what about tomorrow?"
        user_turns = [msg.get("content", "") for msg in recent_history if msg.get("role") == "user"]
        for content in reversed(user_turns[-2:]):
            search_targets.append(content)

    sources: List[str] = []
    for text in search_targets:
        lowered = text.lower()
        if any(keyword in lowered for keyword in HYPERSPELL_CALENDAR_KEYWORDS):
            if "calendar" not in sources:
                sources.append("calendar")
        if any(keyword in lowered for keyword in HYPERSPELL_NOTION_KEYWORDS):
            if "notion" not in sources:
                sources.append("notion")

    return sources


async def fetch_hyperspell_context(
    session_id: str,
    user_message: str,
    sources: List[str],
    *,
    limit: int = 5,
) -> List[HyperspellMemory]:
    """Fetch context from Hyperspell if integration is enabled."""

    if not (HYPERSPELL_ENABLED and sources):
        return []

    client = get_hyperspell_client()
    if not client.is_configured:
        return []

    return await client.fetch_context(
        session_id,
        user_message,
        sources=sources,
        limit=limit,
    )


def schedule_hyperspell_record(
    session_id: str,
    user_message: str,
    assistant_message: str,
    *,
    sources: Optional[List[str]] = None,
    context_used: Optional[List[HyperspellMemory]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record the turn with Hyperspell without blocking the response."""

    if not HYPERSPELL_ENABLED:
        return

    client = get_hyperspell_client()
    if not client.supports_recording:
        return

    payload_metadata: Dict[str, Any] = {}
    if metadata:
        payload_metadata.update(metadata)
    if sources:
        payload_metadata.setdefault("sources", sources)
    if context_used:
        payload_metadata["context_used"] = [
            {
                "source": memory.source,
                "title": memory.title,
                "url": memory.url,
                "timestamp": memory.timestamp,
            }
            for memory in context_used
        ]

    async def _record():
        try:
            await client.record_interaction(
                session_id,
                user_message=user_message,
                assistant_message=assistant_message,
                sources=sources,
                metadata=payload_metadata or None,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to record interaction with Hyperspell: %s", exc)

    try:
        asyncio.create_task(_record())
    except RuntimeError:
        # Fallback: run synchronously as last resort
        asyncio.run(_record())

# Pydantic models
class FileContent(BaseModel):
    path: str
    content: str

class CreateFile(BaseModel):
    path: str
    content: str = ""

class CreateFolder(BaseModel):
    path: str

class DeleteItem(BaseModel):
    path: str

class ComposeEmail(BaseModel):
    instructions: str

class EmailResponse(BaseModel):
    agentmail_message_id: Optional[str] = None
    email: Optional[dict] = None
    status: Optional[str] = None

class BrowserNavigate(BaseModel):
    url: str
    session_id: Optional[str] = "default"
    agent_goal: Optional[str] = None

class BrowserNavigateMultiple(BaseModel):
    urls: List[str]
    session_ids: Optional[List[str]] = None
    agent_goals: Optional[List[str]] = []

class BrowserAction(BaseModel):
    action: str  # "click", "type", "scroll", etc.
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    session_id: Optional[str] = "default"

class BrowserControl(BaseModel):
    command: str  # Natural language command like "click the search button" or "scroll down"
    session_id: Optional[str] = "default"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main OS interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/voice", response_class=HTMLResponse)
async def voice_chat_page(request: Request):
    """Serve the voice chat interface"""
    return templates.TemplateResponse("voice_chat.html", {"request": request})

def get_available_files():
    """Get list of all files in the data directory"""
    files = []
    for root, dirs, filenames in os.walk(DATA_DIR):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), DATA_DIR)
            files.append({
                "name": filename,
                "path": rel_path.replace(os.sep, "/")
            })
    return files

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Handle chat messages using OpenAI with JSON action output"""
    data = await request.json()
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")  # Use session_id from request or default
    original_user_message = user_message  # Store for use in action handlers
    
    if not user_message:
        return JSONResponse(content={
            "response": "Please enter a command.",
        "action": None,
        "data": None
        })
    
    # Check if this is a compilation request - if so, use streaming endpoint
    user_lower = user_message.lower().strip()
    
    # Check conversation history for context (e.g., user might say "make a report of it" referring to previous search)
    recent_history = get_conversation_history(session_id, max_pairs=2)
    has_recent_find = any(
        msg.get("role") == "assistant" and 
        (msg.get("content", "").lower().find("found") >= 0 or 
         msg.get("content", "").lower().find("searching") >= 0 or
         "find_file" in str(msg))
        for msg in recent_history
    )
    
    compilation_keywords = [
        "compile", "create a report", "generate a report", "make a report", "make report",
        "analyze and create", "summarize", "create a summary", "generate a summary",
        "report of", "report from", "report on", "compile from", "compile all",
        "gather and compile", "collect and summarize", "report of it", "compile it",
        "make a report of", "create a report of", "summarize it", "compile them"
    ]
    
    # Check for explicit compilation keywords
    has_explicit_keyword = any(keyword in user_lower for keyword in compilation_keywords)
    
    # Check for patterns like "report of it", "compile it", "make report", etc.
    # These patterns should match even with prefixes like "no also"
    has_report_pattern = (
        ("report" in user_lower and ("of" in user_lower or "from" in user_lower or "on" in user_lower)) or
        ("make" in user_lower and "report" in user_lower) or
        ("compile" in user_lower and ("it" in user_lower or "them" in user_lower or "all" in user_lower)) or
        ("summarize" in user_lower and ("it" in user_lower or "them" in user_lower))
    )
    
    # Check for report/summary keywords combined with document references
    has_report_keyword = any(kw in user_lower for kw in ["report", "compile", "summarize", "summary"])
    has_document_trigger = any(trig in user_lower for trig in ["documents", "files", "it", "them", "those", "all"])
    
    # If user says something like "make a report of it" and there was recent file finding activity, trigger compilation
    is_compilation_request = has_explicit_keyword or has_report_pattern or (has_report_keyword and (has_document_trigger or has_recent_find))
    
    if is_compilation_request:
        # Use streaming endpoint for compilation requests
        async def generate():
            try:
                logger.info(f"Starting iterative workflow for: {user_message}")
                async for update in execute_iterative_workflow(user_message, session_id):
                    logger.info(f"Yielding update: {update}")
                    yield f"data: {json.dumps(update)}\n\n"
                    # Force flush
                    yield ""
            except Exception as e:
                logger.error(f"Error in streaming workflow: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Check if this is a slideshow creation request
    import re
    slideshow_keywords = ["create.*slideshow", "make.*presentation", "generate.*slideshow", "create.*presentation", "build.*presentation"]
    is_slideshow_request = any(re.search(keyword.replace("*", ".*"), user_lower) for keyword in slideshow_keywords)
    
    if is_slideshow_request:
        # Use streaming endpoint for slideshow creation
        async def generate():
            try:
                logger.info(f"Starting slideshow workflow for: {user_message}")
                async for update in execute_slideshow_workflow(user_message, session_id):
                    logger.info(f"Yielding update: {update}")
                    yield f"data: {json.dumps(update)}\n\n"
                    # Force flush
                    yield ""
            except Exception as e:
                logger.error(f"Error in streaming slideshow workflow: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Get current file list to help LLM understand available files
    available_files = get_available_files()
    files_context = "\n".join([f"- {f['path']}" for f in available_files[:20]])  # Limit to first 20 files
    
    # System prompt that allows both conversational and task-oriented interactions
    system_prompt = """You are a helpful and friendly OS assistant that can engage in natural conversation AND help users control their operating system through natural language.

You can have casual conversations with users - answer questions, provide explanations, chat about topics, etc. You're warm, intelligent, and engaging.

When users want to perform actions on the system, you can execute the following:
1. open_app - Open applications (file_manager, terminal, calculator, notepad, settings, mailbox, browser, slideshow)
   - You can open multiple browser windows simultaneously by calling open_app with "browser" multiple times
   - Each browser window operates independently and can navigate to different URLs
2. close_all - Close all windows
3. close_window - Close the topmost window
4. minimize_window - Minimize the topmost window
5. maximize_window - Maximize the topmost window
6. create_file - Create a new file (path and content required)
7. find_file - Find files by name pattern OR search within file contents (searches both in parallel)
8. read_files - Read one or more files and return their contents (paths array required). Use this to retrieve document contents before compiling reports.
9. delete_file - Delete a file by path
10. list_files - List files in a directory
11. compose_email - Compose and send an email using AI (instructions required)
12. navigate_browser - Navigate browser to a URL (url required) OR multiple URLs (urls as array required)
   - For single URL: {"url": "example.com"} - Opens one browser window
   - For multiple URLs: {"urls": ["google.com", "youtube.com"]} - Opens multiple browser windows simultaneously
   - IMPORTANT: When user requests multiple sites at once (e.g., "open google.com and youtube.com"), use the multiple URLs format with "urls" array in the data field
   - Each URL gets its own independent browser window
13. control_browser - Control browser actions using natural language (command required, session_id optional)
   - ONLY use this when user EXPLICITLY requests browser interaction or when a task REQUIRES it
   - Examples of when to use: "click the login button", "fill out this form", "search for something", "click on X", "type Y in the search box", "scroll down"
   - DO NOT use for simple navigation - use navigate_browser instead
   - The system will analyze the current page screenshot using AI vision and execute the action
   - Format: {"command": "natural language instruction", "session_id": "optional browser session"}
   - If no session_id provided, uses the most recently active browser window
   - IMPORTANT: Only use control_browser when the user explicitly asks for interaction OR when completing a task that requires page interaction

For file operations, always work within the data directory. Paths should be relative (e.g., "Desktop/myfile.txt" or "myfile.txt").
When creating files, if no path prefix is specified, create them in Desktop folder.

The find_file operation searches both filenames and file contents in parallel for fast results.
Use it like: "find recipes" (will search both filenames and contents), "find files containing chocolate", etc.

DOCUMENT RETRIEVAL AND REPORT COMPILATION:
When users ask to compile reports, analyze documents, or create summaries from multiple files:
1. First use find_file to locate relevant documents (e.g., "find financial reports", "find Q4 documents")
2. Then use read_files with the file paths found to retrieve their contents
3. Analyze the retrieved content and use create_file to compile a comprehensive report
4. The read_files action accepts an array of file paths and returns the full content of each file, which you can then synthesize into reports, summaries, or analyses.

Example workflow for "Compile a Q4 financial report":
- Step 1: find_file with pattern "Q4 financial" or "Q4 2024"
- Step 2: The system will return found file paths in the response. In the next turn, use read_files with the paths from step 1
- Step 3: After reading files, their contents will be in the conversation history. Use create_file to compile a comprehensive report synthesizing all the information

ITERATIVE WORKFLOW SUPPORT:
The system now supports automatic iterative workflows for document retrieval and report compilation. When users request:
- "Compile a [topic] report"
- "Create a summary of [documents]"
- "Analyze [documents] and create a report"

The system will automatically:
1. Find relevant documents using find_file
2. Read their contents using read_files
3. Compile a comprehensive report using create_file

You can also manually chain these actions across multiple turns using conversation history.

BROWSER USAGE GUIDELINES:
- Use navigate_browser for simple navigation (opening URLs, visiting sites)
- Use control_browser ONLY when:
  1. User EXPLICITLY requests interaction ("click X", "type Y", "scroll", "fill out form")
  2. A task REQUIRES page interaction to complete (e.g., "search for X", "find out about Y", "login to site", "submit form")
  3. User wants to find information ("find out about", "search for", "look up", "get information on") - this REQUIRES interaction
- DO NOT use control_browser for simple navigation tasks (just opening a URL)
- IMPORTANT: When user says "find out about X" or "search for Y":
  * This is a TASK that REQUIRES interaction, so use control_browser
  * OR use navigate_browser first, then control_browser to perform the search
- If user explicitly says "find out about A, B, and C in separate browsers":
  * Open multiple browsers (navigate_browser with multiple URLs)
  * The system will automatically perform searches in each browser (you don't need to chain actions)

Available files in the system:
""" + files_context + """

RESPONSE FORMAT - You must ALWAYS respond with ONLY a valid JSON object with this exact structure:

{
  "response": "string - Your conversational response to the user OR a helpful message explaining what action you took. Be natural and friendly.",
  "action": "string or null - Action name to perform, or null if just conversational. Must be one of: open_app, close_all, close_window, minimize_window, maximize_window, create_file, find_file, read_files, delete_file, list_files, compose_email, navigate_browser, control_browser, or null",
  "data": {
    // Action-specific data. Use empty object {} for conversational messages or when action is null.
    // For open_app: {"app": "string (required): file_manager, terminal, calculator, notepad, settings, mailbox, browser, or slideshow", "title": "string (optional): Window title"}
    // For create_file: {"path": "string (required): File path", "content": "string (required): File content"}
    // For delete_file: {"path": "string (required): File path to delete"}
    // For list_files: {"path": "string (required): Directory path to list"}
    // For find_file: {"pattern": "string (required): Search pattern", "search_content": "boolean (optional, defaults to true): Whether to search in file contents"}
    // For read_files: {"paths": "array of strings (required): Array of file paths to read. Returns full content of each file."}
    // For compose_email: {"instructions": "string (required): Natural language instructions describing the email to compose and send, including recipient email address, subject matter, and any specific requirements"}
    // For navigate_browser: 
    //   Single URL: {"url": "string (required): URL to navigate to (e.g., 'https://example.com' or 'example.com')"}
    //   Multiple URLs: {"urls": ["array of strings (required): Multiple URLs to open simultaneously, each in its own browser window"]}
    // For control_browser: {"command": "string (required): Natural language instruction for browser interaction (e.g., 'click the search button', 'type hello in the search box', 'scroll down')", "session_id": "string (optional): Browser session ID"}
    // For other actions: {} (empty object)
  }
}

EXAMPLES:
- User: "Hello!" 
  Response: {"response": "Hello! How can I help you today?", "action": null, "data": {}}

- User: "What's 2+2?" 
  Response: {"response": "2+2 equals 4! Is there anything else I can help you with?", "action": null, "data": {}}

- User: "Create a file called notes.txt" 
  Response: {"response": "I'll create that file for you!", "action": "create_file", "data": {"path": "Desktop/notes.txt", "content": ""}}

- User: "Open calculator" 
  Response: {"response": "Opening the calculator for you!", "action": "open_app", "data": {"app": "calculator", "title": "Calculator"}}

- User: "Find files with .txt extension" 
  Response: {"response": "Searching for files...", "action": "find_file", "data": {"pattern": ".txt", "search_content": true}}

- User: "Email Alex Johnson at zoebex01@gmail.com about the launch. Mention the roadmap deck and ask for feedback by Friday." 
  Response: {"response": "I'll compose and send that email for you!", "action": "compose_email", "data": {"instructions": "Email Alex Johnson at zoebex01@gmail.com about the launch. Mention the roadmap deck and ask for feedback by Friday."}}

- User: "Send an email to john@example.com saying hello" 
  Response: {"response": "Sending an email to john@example.com with a friendly hello message!", "action": "compose_email", "data": {"instructions": "Send an email to john@example.com saying hello"}}

- User: "Open google.com in the browser" 
  Response: {"response": "Opening browser and navigating to google.com!", "action": "navigate_browser", "data": {"url": "google.com"}}

- User: "Visit https://example.com" 
  Response: {"response": "Opening browser and navigating to https://example.com!", "action": "navigate_browser", "data": {"url": "https://example.com"}}

- User: "Open wikipedia.org and github.com" 
  Response: {"response": "Opening two browser windows - one for wikipedia.org and one for github.com!", "action": "navigate_browser", "data": {"urls": ["wikipedia.org", "github.com"]}}

- User: "Show me google.com and also open youtube.com" 
  Response: {"response": "Opening google.com and youtube.com in separate browser windows!", "action": "navigate_browser", "data": {"urls": ["google.com", "youtube.com"]}}

- User: "Open google.com, youtube.com, and github.com" 
  Response: {"response": "Opening three browser windows for google.com, youtube.com, and github.com!", "action": "navigate_browser", "data": {"urls": ["google.com", "youtube.com", "github.com"]}}

- User: "Open google.com and search for python" 
  Response: {"response": "Opening google.com and searching for python!", "action": "navigate_browser", "data": {"url": "google.com"}}
  IMPORTANT: After navigation completes, you should automatically follow up with control_browser to perform the search:
  Follow-up: {"response": "Searching for python on Google!", "action": "control_browser", "data": {"command": "type python in the search box and click the search button or press enter"}}

- User: "Find out about Tim Cook, Sundar Pichai, and Satya Nadella" 
  Response: {"response": "Opening three browser windows to search for Tim Cook, Sundar Pichai, and Satya Nadella!", "action": "navigate_browser", "data": {"urls": ["google.com", "google.com", "google.com"]}}
  IMPORTANT: This opens browsers but you MUST follow up with control_browser actions to actually search:
  Follow-up 1: {"response": "Searching for Tim Cook in the first browser!", "action": "control_browser", "data": {"command": "type Tim Cook in the search box and click search", "session_id": "browser_session_1"}}
  Follow-up 2: {"response": "Searching for Sundar Pichai in the second browser!", "action": "control_browser", "data": {"command": "type Sundar Pichai in the search box and click search", "session_id": "browser_session_2"}}
  Follow-up 3: {"response": "Searching for Satya Nadella in the third browser!", "action": "control_browser", "data": {"command": "type Satya Nadella in the search box and click search", "session_id": "browser_session_3"}}
  
  CRITICAL: When user asks to "find out about" or "search for" something, you MUST complete the task by actually performing the search, not just opening the browser!

- User: "Click the login button" (when browser is open and user explicitly requests interaction)
  Response: {"response": "I'll click the login button for you!", "action": "control_browser", "data": {"command": "click the login button"}}

- User: "Fill out the contact form with my email" (task requires interaction)
  Response: {"response": "I'll fill out the contact form for you!", "action": "control_browser", "data": {"command": "fill out the contact form email field"}}

- User: "Just open youtube.com" (simple navigation, no interaction needed)
  Response: {"response": "Opening youtube.com!", "action": "navigate_browser", "data": {"url": "youtube.com"}}

- User: "Tell me a joke" 
  Response: {"response": "Why don't scientists trust atoms? Because they make up everything! 😄", "action": null, "data": {}}

- User: "Compile a Q4 financial report from all the relevant documents"
  Response (Step 1): {"response": "I'll help you compile a Q4 financial report. Let me first find all Q4 financial documents.", "action": "find_file", "data": {"pattern": "Q4 financial", "search_content": true}}
  Response (Step 2, after files found): {"response": "Found relevant documents. Now reading them to compile the report.", "action": "read_files", "data": {"paths": ["corporate_documents/Reports/Q4_2024_Financial_Report.md", "corporate_documents/Financial/Income_Statement_Q4_2024.md", "corporate_documents/Financial/Balance_Sheet_Q4_2024.md"]}}
  Response (Step 3, after reading): {"response": "I've analyzed the financial documents. Now compiling a comprehensive Q4 financial report.", "action": "create_file", "data": {"path": "Desktop/Q4_Financial_Report_Compiled.md", "content": "[Compiled report content based on retrieved documents]"}}

- User: "Create a summary of all client status reports"
  Response (Step 1): {"response": "Finding all client status reports.", "action": "find_file", "data": {"pattern": "client status", "search_content": true}}
  Response (Step 2): {"response": "Reading the client status documents to create a summary.", "action": "read_files", "data": {"paths": ["corporate_documents/Clients/Client_Status_Report_December_2024.md"]}}
  Response (Step 3): {"response": "Creating a comprehensive summary of client status.", "action": "create_file", "data": {"path": "Desktop/Client_Status_Summary.md", "content": "[Summary content]"}}

- User: "Create a slideshow about Q4 financial results"
  Response: {"response": "Opening the slideshow app for you!", "action": "open_app", "data": {"app": "slideshow", "title": "Slideshow"}}
  NOTE: Once the slideshow app is open, the user can enter their prompt in the app to generate slides, OR you can automatically fill the prompt and trigger generation.

IMPORTANT: 
- Always return ONLY the JSON object, no other text before or after
- For conversational messages (no action needed), set "action" to null and "data" to {}
- Ensure all JSON is valid and properly formatted
- The "response" field is always required and must be a string
- The "action" field is always required and must be a string (one of the valid actions) or null
- The "data" field is always required and must be an object (empty {} for conversational messages)"""

    # Valid action names
    valid_actions = ["open_app", "close_all", "close_window", "minimize_window", "maximize_window", 
                     "create_file", "find_file", "read_files", "delete_file", "list_files", "compose_email", "navigate_browser", "control_browser"]
    
    def validate_response(response_dict):
        """Validate the LLM response structure and action"""
        # Check required fields exist
        if not isinstance(response_dict, dict):
            return False, "Response is not a dictionary"
        
        if "response" not in response_dict or not isinstance(response_dict["response"], str):
            return False, "Missing or invalid 'response' field"
        
        if "action" not in response_dict:
            return False, "Missing 'action' field"
        
        if "data" not in response_dict or not isinstance(response_dict["data"], dict):
            return False, "Missing or invalid 'data' field"
        
        # Validate action (can be null or a valid action string)
        action = response_dict.get("action")
        if action is not None:
            if not isinstance(action, str) or action not in valid_actions:
                return False, f"Invalid action: {action}. Must be one of {valid_actions} or null"
        
        return True, "Valid"
    
    hyperspell_sources: List[str] = []
    hyperspell_context_memories: List[HyperspellMemory] = []

    try:
        # Log the full system prompt
        logger.info("=" * 80)
        logger.info("SYSTEM PROMPT:")
        logger.info("=" * 80)
        logger.info(system_prompt)
        logger.info("=" * 80)
        logger.info(f"USER MESSAGE: {user_message}")
        logger.info("=" * 80)
        
        # Retry logic - up to 3 attempts
        max_retries = 3
        llm_response = None
        raw_response = None
        
        # Get conversation history (last 4 pairs = 8 messages)
        history_messages = get_conversation_history(session_id, max_pairs=4)

        # Hyperspell context enrichment
        hyperspell_sources = detect_hyperspell_sources(user_message, history_messages)
        if hyperspell_sources:
            hyperspell_context_memories = await fetch_hyperspell_context(
                session_id,
                user_message,
                hyperspell_sources,
                limit=6,
            )
            if hyperspell_context_memories:
                logger.info(
                    "Retrieved %d Hyperspell memories for session %s from sources: %s",
                    len(hyperspell_context_memories),
                    session_id,
                    ", ".join(hyperspell_sources),
                )

        formatted_hyperspell_context = ""
        if hyperspell_context_memories:
            formatted_hyperspell_context = format_memories_for_prompt(
                hyperspell_context_memories
            )

        # Build messages array with system prompt, optional Hyperspell context, history, and current user message
        messages = [{"role": "system", "content": system_prompt}]
        if formatted_hyperspell_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Context retrieved from Hyperspell "
                        f"(sources: {', '.join(hyperspell_sources)}):\n"
                        f"{formatted_hyperspell_context}"
                    ),
                }
            )
        messages.extend(history_messages)  # Add conversation history
        messages.append({"role": "user", "content": user_message})  # Add current user message
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"API Call Attempt {attempt}/{max_retries}")
                
                # Call OpenAI API (expecting JSON response based on prompt instructions)
                # Note: For vision tasks, we use gpt-5-2025-08-07 in the control_browser handler
                completion = openai_client.chat.completions.create(
                    model="gpt-4.1-2025-04-14",
                    messages=messages,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                
                # Get the raw response
                raw_response = completion.choices[0].message.content
                
                # Log the full LLM reply
                logger.info("=" * 80)
                logger.info(f"LLM REPLY (Attempt {attempt}):")
                logger.info("=" * 80)
                logger.info(raw_response)
                logger.info("=" * 80)
                
                # Parse the JSON response
                try:
                    llm_response = json.loads(raw_response)
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON on attempt {attempt}: {str(e)}"
                    logger.warning(error_msg)
                    if attempt < max_retries:
                        logger.info(f"Retrying... ({attempt + 1}/{max_retries})")
                        continue
                    else:
                        raise Exception(f"Failed to parse JSON after {max_retries} attempts: {str(e)}")
                
                # Validate response structure and action
                is_valid, validation_msg = validate_response(llm_response)
                if not is_valid:
                    error_msg = f"Invalid response on attempt {attempt}: {validation_msg}"
                    logger.warning(error_msg)
                    logger.warning(f"Response was: {json.dumps(llm_response, indent=2)}")
                    if attempt < max_retries:
                        logger.info(f"Retrying... ({attempt + 1}/{max_retries})")
                        continue
                    else:
                        # On final attempt, create a safe fallback response
                        logger.error(f"Failed validation after {max_retries} attempts. Using fallback.")
                        llm_response = {
                            "response": f"I encountered an error processing your request after {max_retries} attempts. Please try rephrasing your request.",
                            "action": None,
                            "data": {}
                        }
                        break
                
                # If we get here, response is valid
                logger.info(f"Valid response received on attempt {attempt}")
                break
            
            except Exception as e:
                error_msg = f"Error on attempt {attempt}: {str(e)}"
                logger.error(error_msg)
                if attempt < max_retries:
                    logger.info(f"Retrying... ({attempt + 1}/{max_retries})")
                    continue
                else:
                    # Final fallback on complete failure
                    raise Exception(f"Failed after {max_retries} attempts: {str(e)}")
        
        # Ensure we have a response (should always be set by this point)
        if llm_response is None:
            llm_response = {
                "response": "I encountered an error processing your request. Please try again.",
                "action": None,
                "data": {}
            }
        
        # Execute file operations if needed
        action = llm_response.get("action")
        action_data = llm_response.get("data", {})
        
        # Store user message for use in action handlers
        if 'user_message' not in locals():
            user_message = data.get("message", "").strip()
        
        if action == "create_file":
            try:
                file_path = action_data.get("path", "")
                file_content = action_data.get("content", "")
                
                if not file_path:
                    llm_response["response"] = "Error: No file path specified for file creation."
                    llm_response["action"] = None
                else:
                    # Ensure path is safe
                    safe_path = Path(file_path)
                    if ".." in str(safe_path) or safe_path.is_absolute():
                        llm_response["response"] = "Error: Invalid file path."
                        llm_response["action"] = None
                    else:
                        # If path doesn't start with Desktop/, create in Desktop folder
                        if not str(safe_path).startswith("Desktop/"):
                            safe_path = Path("Desktop") / safe_path
                        
                        target_file = DATA_DIR / safe_path
                        
                        if target_file.exists():
                            llm_response["response"] = f"Error: File '{safe_path}' already exists."
                            llm_response["action"] = None
                        else:
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            target_file.write_text(file_content, encoding='utf-8')
                            llm_response["response"] = f"Successfully created file '{safe_path}'."
            except Exception as e:
                llm_response["response"] = f"Error creating file: {str(e)}"
                llm_response["action"] = None
        
        elif action == "find_file":
            try:
                pattern = action_data.get("pattern", "")
                search_in_content = action_data.get("search_content", True)  # Default to searching content too
                
                if not pattern:
                    llm_response["response"] = "Error: No search pattern specified."
                    llm_response["action"] = None
                else:
                    # First, collect all file paths
                    all_files = []
                    for root, dirs, filenames in os.walk(DATA_DIR):
                        for filename in filenames:
                            full_path = os.path.join(root, filename)
                            rel_path = os.path.relpath(full_path, DATA_DIR)
                            all_files.append({
                                "path": rel_path.replace(os.sep, "/"),
                                "full_path": full_path
                            })
                    
                    found_files_by_name = []
                    found_files_by_content = []
                    
                    # Parse pattern into words for flexible matching
                    pattern_lower = pattern.lower()
                    pattern_words = pattern_lower.split()
                    
                    # Search by filename (fast, no parallel needed)
                    for file_info in all_files:
                        path_lower = file_info["path"].lower()
                        # Match if entire pattern is found OR all words are found
                        if pattern_lower in path_lower or (len(pattern_words) > 1 and all(word in path_lower for word in pattern_words)):
                            found_files_by_name.append({
                                "path": file_info["path"],
                                "match_type": "filename"
                            })
                    
                    # Search within file contents in parallel
                    if search_in_content:
                        def search_file_content(file_info):
                            """Search for pattern in file content"""
                            try:
                                with open(file_info["full_path"], 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    content_lower = content.lower()
                                    
                                    # Match if entire pattern is found OR all words are found
                                    matches_pattern = pattern_lower in content_lower
                                    matches_words = len(pattern_words) > 1 and all(word in content_lower for word in pattern_words)
                                    
                                    if matches_pattern or matches_words:
                                        # Find line numbers where pattern or words appear
                                        lines = content.split('\n')
                                        matching_lines = []
                                        for i, line in enumerate(lines, 1):
                                            line_lower = line.lower()
                                            if pattern_lower in line_lower or (len(pattern_words) > 1 and all(word in line_lower for word in pattern_words)):
                                                matching_lines.append(i)
                                        return {
                                            "path": file_info["path"],
                                            "match_type": "content",
                                            "line_count": len(matching_lines),
                                            "sample_lines": matching_lines[:3]  # Show first 3 matches
                                        }
                            except Exception:
                                pass
                            return None
                        
                        # Use ThreadPoolExecutor for parallel file reading
                        found_filename_paths = {f["path"] for f in found_files_by_name}
                        with ThreadPoolExecutor(max_workers=10) as executor:
                            futures = {executor.submit(search_file_content, file_info): file_info 
                                      for file_info in all_files 
                                      if file_info["path"] not in found_filename_paths}
                            
                            for future in as_completed(futures):
                                result = future.result()
                                if result:
                                    found_files_by_content.append(result)
                    
                    # Combine results (prioritize filename matches, avoid duplicates)
                    found_files = found_files_by_name.copy()
                    found_files_by_content_paths = {f["path"] for f in found_files_by_name}
                    
                    for content_match in found_files_by_content:
                        if content_match["path"] not in found_files_by_content_paths:
                            found_files.append(content_match)
                    
                    if found_files:
                        # Format results
                        results_text = []
                        for f in found_files[:15]:  # Limit to 15 results
                            if f["match_type"] == "filename":
                                results_text.append(f"- {f['path']} (filename match)")
                            else:
                                line_info = f" (found in content at lines {', '.join(map(str, f.get('sample_lines', [])))}" + \
                                          (f", and {f.get('line_count', 0) - len(f.get('sample_lines', []))} more" 
                                           if f.get('line_count', 0) > len(f.get('sample_lines', [])) else "") + ")"
                                results_text.append(f"- {f['path']}{line_info}")
                        
                        files_list = "\n".join(results_text)
                        total_count = len(found_files)
                        llm_response["response"] = f"Found {total_count} file(s) matching '{pattern}':\n{files_list}"
                        llm_response["data"] = {
                            "files": [f["path"] for f in found_files[:15]],
                            "details": found_files[:15]
                        }
                    else:
                        llm_response["response"] = f"No files found matching '{pattern}' in filename or content."
                        llm_response["data"] = {"files": [], "details": []}
            except Exception as e:
                llm_response["response"] = f"Error finding files: {str(e)}"
                llm_response["action"] = None
        
        elif action == "read_files":
            try:
                file_paths = action_data.get("paths", [])
                if not file_paths or not isinstance(file_paths, list):
                    llm_response["response"] = "Error: No file paths specified or paths must be an array."
                    llm_response["action"] = None
                else:
                    file_contents = []
                    errors = []
                    
                    for file_path in file_paths:
                        try:
                            # Ensure path is safe
                            safe_path = Path(file_path)
                            if ".." in str(safe_path) or safe_path.is_absolute():
                                errors.append(f"Invalid path: {file_path}")
                                continue
                            
                            target_file = DATA_DIR / safe_path
                            
                            if not target_file.exists() or not target_file.is_file():
                                errors.append(f"File not found: {file_path}")
                                continue
                            
                            # Read file content
                            content = target_file.read_text(encoding='utf-8', errors='ignore')
                            file_contents.append({
                                "path": file_path,
                                "content": content,
                                "size": len(content),
                                "lines": len(content.split('\n'))
                            })
                        except Exception as e:
                            errors.append(f"Error reading {file_path}: {str(e)}")
                    
                    # Format response
                    if file_contents:
                        response_parts = [f"Successfully read {len(file_contents)} file(s):"]
                        for fc in file_contents:
                            response_parts.append(f"\n--- {fc['path']} ({fc['lines']} lines, {fc['size']} chars) ---")
                            # Include full content in response for LLM to process
                            response_parts.append(fc['content'])
                        
                        if errors:
                            response_parts.append(f"\n\nErrors: {', '.join(errors)}")
                        
                        llm_response["response"] = "\n".join(response_parts)
                        llm_response["data"] = {
                            "files": file_contents,
                            "errors": errors
                        }
                    else:
                        llm_response["response"] = f"No files could be read. Errors: {', '.join(errors) if errors else 'All files were invalid or not found.'}"
                        llm_response["data"] = {"files": [], "errors": errors}
            except Exception as e:
                llm_response["response"] = f"Error reading files: {str(e)}"
                llm_response["action"] = None
        
        elif action == "delete_file":
            try:
                file_path = action_data.get("path", "")
                if not file_path:
                    llm_response["response"] = "Error: No file path specified for deletion."
                    llm_response["action"] = None
                else:
                    # Ensure path is safe
                    safe_path = Path(file_path)
                    if ".." in str(safe_path) or safe_path.is_absolute():
                        llm_response["response"] = "Error: Invalid file path."
                        llm_response["action"] = None
                    else:
                        target_file = DATA_DIR / safe_path
                        
                        if not target_file.exists():
                            llm_response["response"] = f"Error: File '{safe_path}' not found."
                            llm_response["action"] = None
                        else:
                            if target_file.is_file():
                                target_file.unlink()
                            else:
                                import shutil
                                shutil.rmtree(target_file)
                            llm_response["response"] = f"Successfully deleted '{safe_path}'."
            except Exception as e:
                llm_response["response"] = f"Error deleting file: {str(e)}"
                llm_response["action"] = None
        
        elif action == "list_files":
            try:
                list_path = action_data.get("path", "")
                if list_path:
                    safe_path = Path(list_path).name
                    target_dir = DATA_DIR / safe_path
                else:
                    target_dir = DATA_DIR
                
                if not target_dir.exists() or not target_dir.is_dir():
                    llm_response["response"] = f"Error: Directory '{list_path}' not found."
                    llm_response["action"] = None
                else:
                    items = []
                    for item in sorted(target_dir.iterdir()):
                        items.append({
                            "name": item.name,
                            "path": str(item.relative_to(DATA_DIR)),
                            "type": "folder" if item.is_dir() else "file"
                        })
                    
                    if items:
                        items_list = "\n".join([f"- {item['name']} ({item['type']})" for item in items[:20]])
                        llm_response["response"] = f"Files in '{list_path or 'root'}':\n{items_list}"
                        llm_response["data"] = {"items": items[:20]}
                    else:
                        llm_response["response"] = f"Directory '{list_path or 'root'}' is empty."
                        llm_response["data"] = {"items": []}
            except Exception as e:
                llm_response["response"] = f"Error listing files: {str(e)}"
                llm_response["action"] = None
        
        elif action == "compose_email":
            instructions = action_data.get("instructions", "")
            if not instructions:
                llm_response["response"] = "Error: No email instructions provided."
                llm_response["action"] = None
            else:
                # Send email via Railway API (using async since this is an async endpoint)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        RAILWAY_EMAIL_API,
                        json={"instructions": instructions},
                        headers={"Content-Type": "application/json"}
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Log the response from Railway API
                    print("Railway API Response:", json.dumps(result, indent=2))
                    logger.info(f"Railway API Response: {json.dumps(result, indent=2)}")
                    
                    # Store email in inbox (latest first)
                    email_entry = {
                        "id": result.get("agentmail_message_id", f"email_{len(email_inbox)}"),
                        "message_id": result.get("agentmail_message_id"),
                        "to": result.get("email", {}).get("to", ""),
                        "subject": result.get("email", {}).get("subject", ""),
                        "body": result.get("email", {}).get("body", ""),
                        "status": result.get("status", "sent"),
                        "timestamp": datetime.now().isoformat(),
                        "sent": True
                    }
                    email_inbox.insert(0, email_entry)
                    
                    recipient = email_entry.get("to", "recipient")
                    subject = email_entry.get("subject", "email")
                    llm_response["response"] = f"Email sent successfully to {recipient}!\nSubject: {subject}\nThe email has been added to your inbox."
                    llm_response["data"] = {"email": email_entry}
        
        elif action == "navigate_browser":
            try:
                # Check if multiple URLs are provided
                urls = action_data.get("urls", [])
                url = action_data.get("url", "")
                
                if urls and isinstance(urls, list) and len(urls) > 0:
                    # Multiple URLs - open multiple browser windows
                    if len(urls) == 1:
                        # Single URL in array format, treat as single
                        url = urls[0]
                        urls = []
                
                if urls and len(urls) > 1:
                    # Multiple URLs requested
                    url_list = [u.strip() for u in urls if u.strip()]
                    if not url_list:
                        llm_response["response"] = "Error: No valid URLs provided."
                        llm_response["action"] = None
                    else:
                        # Check if the user message contains search intent (for automatic follow-up)
                        search_terms = []
                        user_lower = original_user_message.lower()
                        # Common patterns: "find out about", "search for", "look up", "find information about"
                        search_patterns = ["find out about", "search for", "look up", "find information about", "get information on", "learn about"]
                        has_search_intent = any(pattern in user_lower for pattern in search_patterns)
                        
                        if has_search_intent:
                            # Extract search terms from user message
                            # Look for patterns like "find out about X, Y, Z" or "search for A, B, C"
                            # Also handle "in separate browsers find out about X, Y, Z"
                            patterns = [
                                r'(?:find out about|search for|look up|find information about|learn about)\s+(.+?)(?:\s+and\s+|\s*,\s*|\s*$|$)',
                                r'in separate browsers?\s+(?:find out about|search for|look up)?\s*(.+?)(?:\s+and\s+|\s*,\s*|\s*$)'
                            ]
                            
                            terms_str = ""
                            for pattern in patterns:
                                search_matches = re.findall(pattern, user_lower)
                                if search_matches:
                                    terms_str = search_matches[0]
                                    break
                            
                            if terms_str:
                                # Split by commas and "and"
                                # Handle both "tim cook, sundar pichai and satya nadella" and "tim cook and sundar pichai and satya nadella"
                                terms = re.split(r',|\sand\s+', terms_str)
                                search_terms = [t.strip() for t in terms if t.strip() and len(t.strip()) > 1][:len(url_list)]
                                
                                # If we still don't have enough terms, try extracting after "about"
                                if len(search_terms) < len(url_list):
                                    about_match = re.search(r'about\s+(.+)', user_lower)
                                    if about_match:
                                        terms_str = about_match.group(1)
                                        terms = re.split(r',|\sand\s+', terms_str)
                                        search_terms = [t.strip() for t in terms if t.strip() and len(t.strip()) > 1][:len(url_list)]
                        
                        # Create response for multiple browser windows
                        sites_list = ", ".join(url_list[:3])
                        if len(url_list) > 3:
                            sites_list += f" and {len(url_list) - 3} more"
                        response_msg = f"Opening {len(url_list)} browser windows with autonomous agents: {sites_list}!"
                        if has_search_intent and search_terms:
                            response_msg += f" Each agent will search for: {', '.join(search_terms)}"
                        llm_response["response"] = response_msg
                        llm_response["action"] = "open_app"
                        llm_response["data"] = {
                            "app": "browser",
                            "title": f"Browser - {url_list[0]}",
                            "navigate_to": url_list,  # Pass array of URLs
                            "multiple_urls": url_list,  # Also include for frontend
                            "search_terms": search_terms,  # Include search terms for automatic follow-up
                            "auto_search": has_search_intent,  # Flag to indicate searches should be performed
                            "agent_goals": search_terms if has_search_intent else []  # Goals for each agent
                        }
                elif url:
                    # Single URL - check if task requires agent work
                    user_lower = original_user_message.lower()
                    
                    # Detect complex tasks that require autonomous agent
                    # Ensure re module is available (already imported at top level)
                    task_patterns = [
                        r'extract.*(?:info|information|data|text|content)',
                        r'create.*(?:doc|document|file|word|txt)',
                        r'save.*(?:info|information|data|text|content)',
                        r'get.*(?:info|information|data).*(?:and|then).*(?:create|save|make|write)',
                        r'summarize.*(?:and|then).*(?:save|create|write)',
                        r'read.*(?:and|then).*(?:extract|save|create)'
                    ]
                    
                    has_task_intent = any(re.search(pattern, user_lower) for pattern in task_patterns)
                    agent_goal = None
                    
                    if has_task_intent:
                        # Extract the full task description for the agent
                        # Look for patterns like "extract X", "create Y", "extract X and create Y"
                        extract_match = re.search(r'(extract|get|read|save|summarize).*?(?:\sand\s|,\s|$|and\s+create|and\s+save|and\s+make|then)', user_lower)
                        create_match = re.search(r'(create|make|write|save).*?(?:doc|document|file|word|txt|\.docx|\.txt)', user_lower)
                        
                        if extract_match or create_match:
                            # Build comprehensive goal
                            task_parts = []
                            if extract_match:
                                task_parts.append(extract_match.group(0).strip())
                            if create_match:
                                task_parts.append(create_match.group(0).strip())
                            
                            agent_goal = " ".join(task_parts) if task_parts else original_user_message
                            # Clean up the goal text
                            agent_goal = re.sub(r'\s+', ' ', agent_goal).strip()
                        else:
                            # Fallback: use the full user message as goal
                            agent_goal = original_user_message
                    
                    # Extract domain for window title
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(url if url.startswith(('http://', 'https://')) else f"https://{url}")
                        domain = parsed.netloc or url.split('/')[0]
                        title = f"Browser - {domain}"
                    except:
                        title = f"Browser - {url[:30]}"
                    
                    # Open browser app and navigate
                    if agent_goal:
                        llm_response["response"] = f"Opening browser to {url} and starting an autonomous agent to complete the task. The agent will work in the background and provide progress updates."
                    else:
                        llm_response["response"] = f"Opening browser and navigating to {url}..."
                    
                    llm_response["action"] = "open_app"
                    llm_response["data"] = {
                        "app": "browser",
                        "title": title,
                        "navigate_to": url,  # Pass URL to be navigated after app opens
                        "agent_goal": agent_goal  # Pass agent goal if task detected
                    }
                else:
                    llm_response["response"] = "Error: No URL provided for navigation."
                    llm_response["action"] = None
            except Exception as e:
                llm_response["response"] = f"Error navigating browser: {str(e)}"
                llm_response["action"] = None
        
        elif action == "control_browser":
            try:
                command = action_data.get("command", "")
                session_id_param = action_data.get("session_id", None)
                
                if not command:
                    llm_response["response"] = "Error: No command provided for browser control."
                    llm_response["action"] = None
                else:
                    # Find the active browser session if not specified
                    # We'll try to get the most recent browser session from browser contexts
                    if not session_id_param or session_id_param == "default":
                        # Get the most recently used browser session (last key that's not a metadata key)
                        active_sessions = [k for k in browser_contexts.keys() if not k.endswith("_base_url") and not k.endswith("_current_url")]
                        if active_sessions:
                            session_id_param = active_sessions[-1]  # Use most recent
                        else:
                            session_id_param = "default"
                    
                    # Get browser page
                    page = await get_browser_page(session_id_param)
                    if not page:
                        llm_response["response"] = "Error: No browser window is currently open."
                        llm_response["action"] = None
                    else:
                        # Take screenshot for vision analysis
                        screenshot_bytes = await page.screenshot(full_page=False)
                        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                        
                        # Use GPT-4 Vision to analyze the screenshot and understand the command
                        vision_messages = [
                            {
                                "role": "system",
                                "content": """You are a browser automation assistant. Analyze the screenshot and user command to determine what action to take.

Available actions:
1. click - Click on an element (provide x, y coordinates)
2. type - Type text (provide text to type, and optionally x, y coordinates of input field)
3. scroll - Scroll the page (provide x, y scroll amounts)
4. wait - Wait for something (just return wait action)

Return ONLY a JSON object with this exact format:
{
  "action": "click" | "type" | "scroll" | "wait",
  "x": number (for click, or x scroll amount),
  "y": number (for click, or y scroll amount),
  "text": "string" (for type action only),
  "description": "brief description of what you're doing"
}

For clicking, identify the element described in the command and provide its approximate center coordinates.
For typing, identify the input field and provide coordinates to click it first, then the text to type.
For scrolling, provide appropriate scroll amounts (typically y: -300 to scroll down, y: 300 to scroll up).
Be precise with coordinates - they should match pixel positions in the 1280x720 viewport."""
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"User command: {command}\n\nAnalyze this browser screenshot and determine the appropriate action with coordinates."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{screenshot_base64}"
                                        }
                                    }
                                ]
                            }
                        ]
                        
                        try:
                            vision_response = openai_client.chat.completions.create(
                                model="gpt-5-2025-08-07",  # GPT-5 with vision support
                                messages=vision_messages,
                                reasoning_effort="medium",  # GPT-5 parameter: minimal, low, medium, high
                                verbosity="medium",  # GPT-5 parameter: low, medium, high
                                response_format={"type": "json_object"}
                            )
                            
                            vision_result = json.loads(vision_response.choices[0].message.content)
                            action_type = vision_result.get("action", "wait")
                            
                            # Execute the action
                            if action_type == "click":
                                x = vision_result.get("x", 0)
                                y = vision_result.get("y", 0)
                                await page.mouse.click(x, y)
                                await page.wait_for_timeout(500)
                                description = vision_result.get("description", "Clicked on the page")
                                llm_response["response"] = f"{description}. Action completed!"
                            elif action_type == "type":
                                text = vision_result.get("text", "")
                                x = vision_result.get("x")
                                y = vision_result.get("y")
                                
                                # If coordinates provided, click the input field first
                                if x is not None and y is not None:
                                    await page.mouse.click(x, y)
                                    await page.wait_for_timeout(300)
                                
                                # Type the text
                                if text:
                                    await page.keyboard.type(text)
                                    await page.wait_for_timeout(500)
                                description = vision_result.get("description", "Typed text")
                                llm_response["response"] = f"{description}. Action completed!"
                            elif action_type == "scroll":
                                scroll_x = vision_result.get("x", 0)
                                scroll_y = vision_result.get("y", 0)
                                await page.mouse.wheel(scroll_x, scroll_y)
                                await page.wait_for_timeout(500)
                                description = vision_result.get("description", "Scrolled the page")
                                llm_response["response"] = f"{description}. Action completed!"
                            else:
                                llm_response["response"] = "Waiting or no action needed."
                            
                            # Get updated screenshot and return proxy URL
                            current_url = page.url
                            title = await page.title()
                            
                            llm_response["data"] = {
                                "url": current_url,
                                "title": title,
                                "proxy_url": f"/api/browser/proxy/{session_id_param}/"
                            }
                            
                        except Exception as e:
                            logger.error(f"Error in vision analysis: {str(e)}")
                            llm_response["response"] = f"Error analyzing page: {str(e)}. Please try being more specific."
                            llm_response["action"] = None
                            
            except Exception as e:
                llm_response["response"] = f"Error controlling browser: {str(e)}"
                llm_response["action"] = None
        
        # Record interaction with Hyperspell memory layer (non-blocking)
        if llm_response:
            metadata: Dict[str, Any] = {}
            action_field = llm_response.get("action")
            if action_field is not None:
                metadata["action"] = action_field

            schedule_hyperspell_record(
                session_id,
                user_message,
                llm_response.get("response", ""),
                sources=hyperspell_sources or None,
                context_used=hyperspell_context_memories or None,
                metadata=metadata or None,
            )

        # Store conversation history (only if we got a successful response)
        if llm_response and raw_response:
            # Store the raw JSON response as assistant message for conversation context
            add_to_conversation_history(session_id, user_message, raw_response)
            logger.info(f"Stored conversation exchange for session: {session_id}")
        
        return JSONResponse(content=llm_response)
        
    except json.JSONDecodeError as e:
        return JSONResponse(content={
            "response": f"I encountered an error parsing the response. Please try again. Error: {str(e)}",
            "action": None,
            "data": None
        })
    except Exception as e:
        return JSONResponse(content={
            "response": f"I encountered an error: {str(e)}. Please make sure your OpenAI API key is valid.",
            "action": None,
            "data": None
        })

# File Operations Endpoints
@app.get("/api/files/list")
async def list_files(path: str = ""):
    """List files and folders in a directory"""
    try:
        if path:
            # Validate path to prevent directory traversal
            safe_path = Path(path).name
            target_dir = DATA_DIR / safe_path
        else:
            target_dir = DATA_DIR
        
        if not target_dir.exists() or not target_dir.is_dir():
            raise HTTPException(status_code=404, detail="Directory not found")
        
        items = []
        for item in sorted(target_dir.iterdir()):
            items.append({
                "name": item.name,
                "path": str(item.relative_to(DATA_DIR)),
                "type": "folder" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
                "modified": item.stat().st_mtime
            })
        
        return JSONResponse(content={"items": items, "path": path})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/read")
async def read_file(path: str):
    """Read a text file"""
    try:
        # Validate path
        safe_path = Path(path)
        if ".." in str(safe_path) or safe_path.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid path")
        
        target_file = DATA_DIR / safe_path
        
        if not target_file.exists() or not target_file.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        
        content = target_file.read_text(encoding='utf-8')
        return JSONResponse(content={"content": content, "path": path})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/write")
async def write_file(file_data: FileContent):
    """Write content to a text file"""
    try:
        safe_path = Path(file_data.path)
        if ".." in str(safe_path) or safe_path.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid path")
        
        target_file = DATA_DIR / safe_path
        
        # Create parent directories if they don't exist
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        target_file.write_text(file_data.content, encoding='utf-8')
        return JSONResponse(content={"success": True, "path": file_data.path})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/create")
async def create_file(create_data: CreateFile):
    """Create a new file"""
    try:
        safe_path = Path(create_data.path)
        if ".." in str(safe_path) or safe_path.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid path")
        
        # If path doesn't start with Desktop, create in Desktop folder
        if not str(safe_path).startswith("Desktop/"):
            safe_path = Path("Desktop") / safe_path
        
        target_file = DATA_DIR / safe_path
        
        if target_file.exists():
            raise HTTPException(status_code=400, detail="File already exists")
        
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(create_data.content, encoding='utf-8')
        return JSONResponse(content={"success": True, "path": str(safe_path)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/folder")
async def create_folder(folder_data: CreateFolder):
    """Create a new folder"""
    try:
        safe_path = Path(folder_data.path)
        if ".." in str(safe_path) or safe_path.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid path")
        
        # If path doesn't start with Desktop, create in Desktop folder
        if not str(safe_path).startswith("Desktop/"):
            safe_path = Path("Desktop") / safe_path
        
        target_folder = DATA_DIR / safe_path
        
        if target_folder.exists():
            raise HTTPException(status_code=400, detail="Folder already exists")
        
        target_folder.mkdir(parents=True, exist_ok=True)
        return JSONResponse(content={"success": True, "path": str(safe_path)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/files/delete")
async def delete_item(path: str):
    """Delete a file or folder"""
    try:
        safe_path = Path(path)
        if ".." in str(safe_path) or safe_path.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid path")
        
        target_item = DATA_DIR / safe_path
        
        if not target_item.exists():
            raise HTTPException(status_code=404, detail="Item not found")
        
        if target_item.is_file():
            target_item.unlink()
        else:
            import shutil
            shutil.rmtree(target_item)
        
        return JSONResponse(content={"success": True, "path": path})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Email endpoints
@app.post("/api/email/compose-send")
async def compose_and_send_email(email_data: ComposeEmail):
    """Compose and send email via Railway API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            RAILWAY_EMAIL_API,
            json={"instructions": email_data.instructions},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        
        # Log the response from Railway API
        print("Railway API Response:", json.dumps(result, indent=2))
        logger.info(f"Railway API Response: {json.dumps(result, indent=2)}")
        
        # Store email in inbox (latest first)
        email_entry = {
            "id": result.get("agentmail_message_id", f"email_{len(email_inbox)}"),
            "message_id": result.get("agentmail_message_id"),
            "to": result.get("email", {}).get("to", ""),
            "subject": result.get("email", {}).get("subject", ""),
            "body": result.get("email", {}).get("body", ""),
            "status": result.get("status", "sent"),
            "timestamp": datetime.now().isoformat(),
            "sent": True
        }
        email_inbox.insert(0, email_entry)
        
        return JSONResponse(content={
            "success": True,
            "email": email_entry,
            "response": result
        })

@app.get("/api/email/inbox")
async def get_inbox(page: int = 1, per_page: int = 20, summaries: bool = True):
    """Get inbox emails from external API with pagination (latest first)"""
    try:
        # Fetch up to 100 emails from external Railway API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                RAILWAY_EMAIL_INBOX_API,
                params={"limit": 100, "summaries": summaries}
            )
            response.raise_for_status()
            result = response.json()
            
            # Process emails from external API
            received_emails = []
            if result.get("status") == "ok" and result.get("emails"):
                for email in result.get("emails", []):
                    email_entry = {
                        "id": email.get("message_id", f"email_{len(received_emails)}"),
                        "message_id": email.get("message_id"),
                        "from": email.get("from", ""),
                        "subject": email.get("subject", "(No subject)"),
                        "body": email.get("text", email.get("html", "")),
                        "html": email.get("html", ""),
                        "text": email.get("text", ""),
                        "thread_id": email.get("thread_id"),
                        "timestamp": email.get("received_at", datetime.now().isoformat()),
                        "received_at": email.get("received_at"),
                        "sent": False,  # These are received emails
                        "status": "received"
                    }
                    received_emails.append(email_entry)
            
            # Combine with locally stored sent emails (include all sent emails)
            all_emails = received_emails + email_inbox
            
            # Sort by timestamp (most recent first)
            # Use received_at if available, otherwise timestamp
            def get_sort_key(email):
                ts = email.get("received_at") or email.get("timestamp", "")
                return ts if ts else "1970-01-01T00:00:00"
            all_emails.sort(key=get_sort_key, reverse=True)
            
            # Calculate pagination
            total_count = len(all_emails)
            total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 1
            page = max(1, min(page, total_pages))  # Ensure page is in valid range
            
            # Calculate slice indices
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            
            # Get paginated emails
            paginated_emails = all_emails[start_idx:end_idx]
            
            return JSONResponse(content={
                "success": True,
                "emails": paginated_emails,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                },
                "received_count": len(received_emails),
                "sent_count": len(email_inbox)
            })
    except Exception as e:
        logger.error(f"Error fetching inbox: {str(e)}")
        # Fallback to local emails if external API fails
        total_count = len(email_inbox)
        per_page = max(1, per_page)
        total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 1
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        return JSONResponse(content={
            "success": True,
            "emails": email_inbox[start_idx:end_idx],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "received_count": 0,
            "sent_count": len(email_inbox),
            "error": str(e)
        })

@app.get("/api/email/last")
async def get_last_email():
    """Get the most recent email from the inbox"""
    try:
        if not email_inbox or len(email_inbox) == 0:
            return JSONResponse(content={
                "success": True,
                "email": None,
                "message": "No emails in inbox"
            })
        
        # Return the first email (most recent since inbox is latest first)
        return JSONResponse(content={
            "success": True,
            "email": email_inbox[0],
            "count": len(email_inbox)
        })
    except Exception as e:
        logger.error(f"Error fetching last email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# ============================================
# Hyperspell Integration Endpoints
# ============================================

from hyperspell_integration import (
    get_hyperspell_client,
    UserTokenRequest,
    UserTokenResponse,
    IntegrationInfo,
    UserInfo
)

@app.post("/api/hyperspell/user-token", response_model=UserTokenResponse)
async def generate_user_token(request: UserTokenRequest):
    """
    Generate a Hyperspell user token for the given user ID
    This token is used to access Hyperspell Connect
    """
    try:
        client = get_hyperspell_client()
        token = client.generate_user_token(request.user_id)

        return UserTokenResponse(
            token=token,
            user_id=request.user_id
        )
    except Exception as e:
        logger.error(f"Error generating user token: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hyperspell/integrations")
async def list_integrations():
    """
    List all available Hyperspell integrations
    """
    try:
        client = get_hyperspell_client()
        integrations = client.list_integrations()

        return {
            "success": True,
            "integrations": integrations
        }
    except Exception as e:
        logger.error(f"Error listing integrations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hyperspell/user/{user_id}")
async def get_user_info(user_id: str):
    """
    Get user information including connected integrations
    """
    try:
        client = get_hyperspell_client()
        # In production, would pass user_token instead of generating here
        user_token = client.generate_user_token(user_id)
        user_info = client.get_user_info(user_token)

        return {
            "success": True,
            "user": user_info
        }
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hyperspell/integration-link")
async def get_integration_link(request: dict):
    """
    Generate a link to connect a specific integration
    """
    try:
        integration_id = request.get("integration_id")
        user_id = request.get("user_id", "default_user")
        redirect_uri = request.get("redirect_uri")

        if not integration_id:
            raise HTTPException(status_code=400, detail="integration_id is required")

        client = get_hyperspell_client()
        user_token = client.generate_user_token(user_id)
        link = client.get_integration_link(integration_id, user_token, redirect_uri)

        return {
            "success": True,
            "link": link,
            "integration_id": integration_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating integration link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# Browser initialization
async def init_browser():
    """Initialize Playwright browser"""
    global browser_instance
    try:
        playwright = await async_playwright().start()
        browser_instance = await playwright.chromium.launch(headless=True)
        logger.info("Playwright browser initialized")
    except Exception as e:
        logger.error(f"Failed to initialize browser: {str(e)}")
        browser_instance = None

async def get_browser_page(session_id: str = "default") -> Optional[Page]:
    """Get or create a browser page for a session"""
    global browser_instance
    if not browser_instance:
        await init_browser()
    
    if not browser_instance:
        return None
    
    # Get or create context for session
    if session_id not in browser_contexts:
        browser_contexts[session_id] = await browser_instance.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    
    context = browser_contexts[session_id]
    pages = context.pages
    if len(pages) > 0:
        return pages[0]
    else:
        return await context.new_page()

async def browser_agent_worker(session_id: str):
    """Autonomous browser agent that processes tasks independently and generates new ones"""
    logger.info(f"🤖 Browser agent [{session_id}] STARTED - Running autonomously")
    
    try:
        while True:
            # Check if agent exists and has tasks/goals
            if session_id not in browser_agents:
                await asyncio.sleep(1)
                continue
            
            agent = browser_agents[session_id]
            
            # If agent has no goal/tasks, wait
            if not agent.get("current_goal") and len(agent.get("tasks", deque())) == 0:
                agent["status"] = "idle"
                await asyncio.sleep(1)
                continue
            
            # If agent has a goal, work on it
            if agent.get("current_goal"):
                agent["status"] = "thinking"
                
                page = await get_browser_page(session_id)
                if not page:
                    logger.warning(f"⚠️  Agent [{session_id}]: No browser page available")
                    await asyncio.sleep(2)
                    continue
                
                # Log current state
                current_url = page.url
                logger.info(f"🤖 Agent [{session_id}] at {current_url} - Goal: {agent['current_goal']}")
                
                # Take screenshot for analysis
                agent["status"] = "analyzing"
                agent_log = {"timestamp": datetime.now().isoformat(), "action": "analyzing", "message": f"Analyzing page at {current_url}"}
                agent["logs"].append(agent_log)
                logger.info(f"📸 Agent [{session_id}]: Taking screenshot for analysis")
                
                await asyncio.sleep(1)  # Wait for page to stabilize
                screenshot_bytes = await page.screenshot(full_page=False)
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                # Use LLM to decide next action based on goal
                agent["status"] = "planning"
                agent_log = {"timestamp": datetime.now().isoformat(), "action": "planning", "message": "Planning next action to achieve goal"}
                agent["logs"].append(agent_log)
                
                system_prompt = f"""You are an autonomous browser agent working on a specific task.

YOUR CURRENT GOAL: {agent.get('current_goal', 'Unknown')}

You must analyze the current page and decide what action to take next. Available actions:
1. click - Click on an element (provide x, y coordinates)
2. type - Type text in an input field (provide text and coordinates)
3. scroll - Scroll the page (provide x, y scroll amounts)
4. done - Mark task as complete if goal is achieved

IMPORTANT: If your goal involves extracting information and creating/saving files:
- Read the page content carefully
- Extract all relevant information systematically
- When ready to save, you can indicate completion and the system will help create the file
- Be thorough - extract all requested information before marking as done

You should:
- Work systematically toward your goal
- Read and understand page content thoroughly
- Extract information comprehensively if extraction is part of the goal
- Navigate pages as necessary (click links, scroll to see more content)
- Continue working until goal is achieved or you determine it cannot be completed
- Provide detailed progress updates

Return ONLY a JSON object:
{{
  "action": "click" | "type" | "scroll" | "done",
  "x": number (for click/scroll),
  "y": number (for click/scroll),
  "text": "string" (for type action),
  "description": "brief description of what you're doing",
  "goal_progress": "what progress have you made toward the goal? Include specific details of what information you've found.",
  "next_steps": "what will you do next?"
}}

Be precise with coordinates for the 1280x720 viewport."""
                
                vision_messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Current URL: {current_url}\n\nAnalyze this page screenshot and determine the next action to work toward: {agent.get('current_goal', 'Unknown')}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}
                            }
                        ]
                    }
                ]
                
                try:
                    vision_response = openai_client.chat.completions.create(
                        model="gpt-5-2025-08-07",
                        messages=vision_messages,
                        reasoning_effort="medium",  # GPT-5 parameter: minimal, low, medium, high
                        verbosity="medium",  # GPT-5 parameter: low, medium, high
                        response_format={"type": "json_object"}
                    )
                    
                    vision_result = json.loads(vision_response.choices[0].message.content)
                    action_type = vision_result.get("action", "wait")
                    description = vision_result.get("description", "")
                    goal_progress = vision_result.get("goal_progress", "")
                    next_steps = vision_result.get("next_steps", "")
                    
                    # Log the decision
                    agent_log = {
                        "timestamp": datetime.now().isoformat(),
                        "action": action_type,
                        "message": description,
                        "progress": goal_progress,
                        "next": next_steps
                    }
                    agent["logs"].append(agent_log)
                    logger.info(f"🎯 Agent [{session_id}]: {description}")
                    if goal_progress:
                        logger.info(f"   📊 Progress: {goal_progress}")
                    if next_steps:
                        logger.info(f"   ➡️  Next: {next_steps}")
                    
                    # Execute the action
                    agent["status"] = "executing"
                    
                    if action_type == "done":
                        logger.info(f"✅ Agent [{session_id}]: Task complete! Goal achieved.")
                        
                        # If goal involves extraction/document creation, extract content and create file
                        goal_lower = agent.get('current_goal', '').lower()
                        if 'extract' in goal_lower or 'create' in goal_lower or 'save' in goal_lower or 'doc' in goal_lower:
                            try:
                                # Extract text content from page
                                page_text = await page.evaluate("""() => {
                                    // Get main content, excluding scripts, styles, nav, footer
                                    const content = document.querySelector('main') || 
                                                   document.querySelector('article') || 
                                                   document.querySelector('#content') ||
                                                   document.querySelector('.mw-parser-output') ||
                                                   document.body;
                                    return content.innerText || content.textContent || '';
                                }""")
                                
                                if page_text:
                                    # Use LLM to format and extract relevant info
                                    extraction_prompt = f"""Extract and format the information from this webpage content according to the goal: {agent.get('current_goal', '')}

Content:
{page_text[:15000]}  # Limit to avoid token limits

Format the extracted information clearly and comprehensively. If creating a document, structure it appropriately."""
                                    
                                    extraction_response = openai_client.chat.completions.create(
                                        model="gpt-4.1-2025-04-14",
                                        messages=[
                                            {"role": "system", "content": "You are a document extraction assistant. Extract and format information clearly."},
                                            {"role": "user", "content": extraction_prompt}
                                        ],
                                        temperature=0.7
                                    )
                                    
                                    extracted_content = extraction_response.choices[0].message.content
                                    
                                    # Get page title for filename
                                    page_title = await page.title()
                                    # Use re module (imported at top level)
                                    safe_title = re.sub(r'[^\w\s-]', '', page_title)[:30].replace(' ', '_')
                                    
                                    # Determine filename from goal or page title
                                    filename = "extracted_info.txt"
                                    if 'word' in goal_lower or 'doc' in goal_lower:
                                        filename = f"{safe_title}_info.txt"
                                    else:
                                        filename = f"{safe_title}_extracted.txt"

                                    # Create file
                                    safe_path = Path("Desktop") / filename
                                    target_file = DATA_DIR / safe_path
                                    target_file.parent.mkdir(parents=True, exist_ok=True)
                                    target_file.write_text(extracted_content, encoding='utf-8')
                                    
                                    logger.info(f"📄 Agent [{session_id}]: Created file {filename} with extracted content")
                                    agent_log = {
                                        "timestamp": datetime.now().isoformat(), 
                                        "action": "done", 
                                        "message": f"Task completed successfully. Created file: {filename}"
                                    }
                                    agent["logs"].append(agent_log)
                                else:
                                    agent_log = {"timestamp": datetime.now().isoformat(), "action": "done", "message": "Task completed successfully"}
                                    agent["logs"].append(agent_log)
                            except Exception as e:
                                logger.error(f"❌ Agent [{session_id}] error creating file: {str(e)}")
                                agent_log = {"timestamp": datetime.now().isoformat(), "action": "error", "message": f"Error creating file: {str(e)}"}
                                agent["logs"].append(agent_log)
                        else:
                            agent_log = {"timestamp": datetime.now().isoformat(), "action": "done", "message": "Task completed successfully"}
                            agent["logs"].append(agent_log)
                        
                        agent["current_goal"] = None
                        agent["status"] = "completed"
                        await asyncio.sleep(5)  # Wait before checking for new tasks
                    elif action_type == "click":
                        x = vision_result.get("x", 0)
                        y = vision_result.get("y", 0)
                        logger.info(f"🖱️  Agent [{session_id}]: Clicking at ({x}, {y})")
                        await page.mouse.click(x, y)
                        await page.wait_for_timeout(1500)
                    elif action_type == "type":
                        text = vision_result.get("text", "")
                        x = vision_result.get("x")
                        y = vision_result.get("y")
                        
                        logger.info(f"⌨️  Agent [{session_id}]: Typing '{text}'")
                        if x is not None and y is not None:
                            await page.mouse.click(x, y)
                            await page.wait_for_timeout(300)
                        
                        if text:
                            await page.keyboard.type(text, delay=50)
                            await page.wait_for_timeout(800)
                            
                            # Auto-press Enter if it's a search
                            if "search" in agent.get('current_goal', '').lower() or page.url == "https://www.google.com/" or "google.com" in page.url:
                                logger.info(f"🔍 Agent [{session_id}]: Pressing Enter to search")
                                await page.keyboard.press('Enter')
                                await page.wait_for_timeout(3000)
                    elif action_type == "scroll":
                        scroll_x = vision_result.get("x", 0)
                        scroll_y = vision_result.get("y", 0)
                        logger.info(f"📜 Agent [{session_id}]: Scrolling ({scroll_x}, {scroll_y})")
                        await page.mouse.wheel(scroll_x, scroll_y)
                        await page.wait_for_timeout(1000)
                    
                    # Update page info after action
                    await page.wait_for_timeout(1000)
                    agent["status"] = "idle"
                    await asyncio.sleep(1)  # Brief pause between actions
                    
                except Exception as e:
                    logger.error(f"❌ Agent [{session_id}] error during action: {str(e)}")
                    agent_log = {"timestamp": datetime.now().isoformat(), "action": "error", "message": f"Error: {str(e)}"}
                    agent["logs"].append(agent_log)
                    agent["status"] = "error"
                    await asyncio.sleep(2)
                    
            else:
                # Process queued tasks
                if len(agent.get("tasks", deque())) > 0:
                    task = agent["tasks"].popleft()
                    agent["current_goal"] = task.get("goal", task.get("command", ""))
                    logger.info(f"📋 Agent [{session_id}]: New task queued - {agent['current_goal']}")
                else:
                    agent["status"] = "idle"
                    await asyncio.sleep(1)
                
    except asyncio.CancelledError:
        logger.info(f"🛑 Browser agent [{session_id}] STOPPED")
    except Exception as e:
        logger.error(f"💥 Agent [{session_id}] FATAL ERROR: {str(e)}")
        if session_id in browser_agents:
            browser_agents[session_id]["status"] = "error"
            browser_agents[session_id]["logs"].append({
                "timestamp": datetime.now().isoformat(),
                "action": "fatal_error",
                "message": f"Fatal error: {str(e)}"
            })

def start_browser_agent(session_id: str, initial_goal: str = None):
    """Start an autonomous browser agent for a session with an optional goal"""
    if session_id in agent_task_registry:
        # Agent already running, add goal if provided
        if initial_goal and session_id in browser_agents:
            browser_agents[session_id]["current_goal"] = initial_goal
            if "logs" not in browser_agents[session_id]:
                browser_agents[session_id]["logs"] = []
            browser_agents[session_id]["logs"].append({
                "timestamp": datetime.now().isoformat(),
                "action": "goal_set",
                "message": f"New goal set: {initial_goal}"
            })
            logger.info(f"📝 Agent [{session_id}]: Goal updated to '{initial_goal}'")
        return
    
    async def run_agent():
        await browser_agent_worker(session_id)
    
    # Create task but don't await it - let it run in background
    task = asyncio.create_task(run_agent())
    agent_task_registry[session_id] = task
    browser_agents[session_id] = {
        "tasks": deque(),
        "status": "starting",
        "current_goal": initial_goal or "",
        "logs": [{"timestamp": datetime.now().isoformat(), "action": "started", "message": f"Agent started with goal: {initial_goal or 'No initial goal'}"}]
    }
    logger.info(f"🚀 Started browser agent [{session_id}] with goal: {initial_goal or 'No initial goal'}")

@app.on_event("startup")
async def startup_event():
    """Initialize browser on startup"""
    await init_browser()

@app.get("/api/browser/agent/{session_id}")
async def get_browser_agent_status(session_id: str):
    """Get status and logs for a browser agent"""
    if session_id not in browser_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = browser_agents[session_id]
    return JSONResponse(content={
        "session_id": session_id,
        "status": agent.get("status", "unknown"),
        "current_goal": agent.get("current_goal", ""),
        "logs": agent.get("logs", [])[-50:],  # Last 50 log entries
        "task_count": len(agent.get("tasks", deque()))
    })

@app.get("/api/browser/agents")
async def get_all_browser_agents():
    """Get status of all browser agents"""
    agents_status = {}
    for session_id, agent in browser_agents.items():
        agents_status[session_id] = {
            "status": agent.get("status", "unknown"),
            "current_goal": agent.get("current_goal", ""),
            "log_count": len(agent.get("logs", [])),
            "latest_log": agent.get("logs", [])[-1] if agent.get("logs") else None
        }
    return JSONResponse(content={"agents": agents_status})

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up browser on shutdown"""
    global browser_instance
    # Cancel all agent tasks
    for session_id, task in agent_task_registry.items():
        task.cancel()
    agent_task_registry.clear()
    
    if browser_instance:
        await browser_instance.close()
        logger.info("Browser closed")

# Browser endpoints
@app.post("/api/browser/navigate-multiple")
async def browser_navigate_multiple(nav_data: BrowserNavigateMultiple):
    """Navigate multiple browsers to URLs - supports agent goals"""
    try:
        urls = nav_data.urls or []
        agent_goals = nav_data.agent_goals or []
        
        if not urls:
            raise HTTPException(status_code=400, detail="No URLs provided")
        
        results = []
        
        for idx, target_url in enumerate(urls):
            # Normalize URL
            if not target_url.startswith(('http://', 'https://')):
                target_url = f"https://{target_url}"
            
            # Generate unique session ID for each browser window
            session_id = f"browser_{int(time.time() * 1000)}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}"
            
            page = await get_browser_page(session_id)
            if not page:
                raise HTTPException(status_code=500, detail="Browser not available")
            
            # Navigate to URL
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            
            current_url = page.url
            title = await page.title()
            proxy_url = f"/api/browser/proxy/{session_id}/"
            
            # Start autonomous agent with goal if provided
            agent_goal = None
            if idx < len(agent_goals) and agent_goals[idx]:
                agent_goal = f"Search for and find information about {agent_goals[idx]}"
                start_browser_agent(session_id, initial_goal=agent_goal)
                logger.info(f"🤖 Started agent [{session_id}] with goal: {agent_goal}")
            
            results.append({
                "session_id": session_id,
                "url": current_url,
                "title": title,
                "proxy_url": proxy_url,
                "agent_goal": agent_goal
            })
        
        return JSONResponse(content={
            "success": True,
            "results": results,
            "multiple": len(results) > 1
        })
    except Exception as e:
        logger.error(f"Error navigating multiple browsers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/browser/navigate")
async def browser_navigate(nav_data: BrowserNavigate):
    """Navigate to a URL and return page info"""
    try:
        page = await get_browser_page(nav_data.session_id)
        if not page:
            raise HTTPException(status_code=500, detail="Browser not available")
        
        url = nav_data.url
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Navigate to URL
        await page.goto(url, wait_until='networkidle', timeout=30000)
        
        # Wait a bit for page to fully render
        await page.wait_for_timeout(1000)
        
        # Get current URL (in case of redirects)
        current_url = page.url
        
        # Get page title
        title = await page.title()
        
        # Store the base URL for this session for proxying
        parsed_url = urlparse(current_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        browser_contexts[nav_data.session_id + "_base_url"] = base_url
        browser_contexts[nav_data.session_id + "_current_url"] = current_url
        
        # Check if agent goal was provided (for single URL navigation with tasks)
        agent_goal = nav_data.agent_goal
        if agent_goal:
            start_browser_agent(nav_data.session_id, initial_goal=agent_goal)
            logger.info(f"🤖 Started agent [{nav_data.session_id}] with goal: {agent_goal}")
        
        return JSONResponse(content={
            "success": True,
            "url": current_url,
            "title": title,
            "proxy_url": f"/api/browser/proxy/{nav_data.session_id}/",
            "agent_goal": agent_goal
        })
    except Exception as e:
        logger.error(f"Error navigating browser: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/api/browser/proxy/{session_id}/")
async def browser_proxy_page(session_id: str, request: Request):
    """Proxy the rendered page HTML"""
    try:
        page = await get_browser_page(session_id)
        if not page:
            raise HTTPException(status_code=500, detail="Browser not available")
        
        # Get the HTML content
        html_content = await page.content()
        current_url = page.url
        base_url = browser_contexts.get(session_id + "_base_url", current_url)
        
        # Rewrite URLs in HTML to use our proxy
        # Import re inside function to ensure it's accessible in closure
        import re as re_module
        def rewrite_url(match):
            attr = match.group(1)  # src or href
            quote = match.group(2)  # " or '
            url = match.group(3)  # the URL
            
            if not url:
                return match.group(0)
            
            # Skip data URLs, javascript:, mailto:, # anchors, etc.
            if url.startswith(('data:', 'javascript:', 'mailto:', '#', 'about:', '{')):
                return match.group(0)
            
            # Convert relative URLs to absolute
            if url.startswith('//'):
                url = urlparse(current_url).scheme + ':' + url
            elif url.startswith('/'):
                url = base_url + url
            elif not url.startswith(('http://', 'https://')):
                url = urljoin(current_url, url)
            
            # Create proxy URL (URL encode the target URL)
            from urllib.parse import quote as url_quote
            proxy_path = f"/api/browser/resource/{session_id}"
            encoded_url = url_quote(url, safe='')
            return f'{attr}={quote}{proxy_path}?url={encoded_url}{quote}'
        
        # Rewrite src and href attributes with quotes
        html_content = re_module.sub(r'(src|href)=(["\'])([^"\']+)\2', rewrite_url, html_content)
        
        # Inject base tag to help with relative URLs
        if '<head>' in html_content:
            html_content = html_content.replace('<head>', f'<head><base href="{current_url}">')
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error proxying page: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/api/browser/resource/{session_id}")
async def browser_proxy_resource(session_id: str, url: str, request: Request):
    """Proxy resources (CSS, JS, images) from the original site"""
    try:
        page = await get_browser_page(session_id)
        if not page:
            raise HTTPException(status_code=500, detail="Browser not available")
        
        # Fetch the resource using Playwright's context
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # Use the same cookies/headers as the browser page
            headers = {}
            cookies = await page.context.cookies()
            for cookie in cookies:
                client.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
            
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # Determine content type
            content_type = response.headers.get('content-type', 'application/octet-stream')
            
            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                }
            )
    except Exception as e:
        logger.error(f"Error proxying resource {url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/browser/control")
async def browser_control(control_data: BrowserControl):
    """Control browser using natural language - simplified endpoint for automatic searches"""
    try:
        command = control_data.command
        session_id_param = control_data.session_id or "default"
        
        page = await get_browser_page(session_id_param)
        if not page:
            raise HTTPException(status_code=500, detail="Browser not available")
        
        # Take screenshot for vision analysis
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # Use GPT-4 Vision to analyze the screenshot and understand the command
        vision_messages = [
            {
                "role": "system",
                "content": """You are a browser automation assistant. Analyze the screenshot and user command to determine what action to take.

Available actions:
1. click - Click on an element (provide x, y coordinates)
2. type - Type text (provide text to type, and optionally x, y coordinates of input field)
3. scroll - Scroll the page (provide x, y scroll amounts)

Return ONLY a JSON object with this exact format:
{
  "action": "click" | "type" | "scroll",
  "x": number (for click, or x scroll amount),
  "y": number (for click, or y scroll amount),
  "text": "string" (for type action only),
  "description": "brief description of what you're doing"
}

For clicking, identify the element described in the command and provide its approximate center coordinates.
For typing, identify the input field and provide coordinates to click it first, then the text to type.
For scrolling, provide appropriate scroll amounts (typically y: -300 to scroll down, y: 300 to scroll up).
Be precise with coordinates - they should match pixel positions in the 1280x720 viewport."""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"User command: {command}\n\nAnalyze this browser screenshot and determine the appropriate action with coordinates."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_base64}"
                        }
                    }
                ]
            }
        ]
        
        vision_response = openai_client.chat.completions.create(
            model="gpt-5-2025-08-07",
            messages=vision_messages,
            reasoning_effort="medium",  # GPT-5 parameter: minimal, low, medium, high
            verbosity="medium",  # GPT-5 parameter: low, medium, high
            response_format={"type": "json_object"}
        )
        
        vision_result = json.loads(vision_response.choices[0].message.content)
        action_type = vision_result.get("action", "wait")
        
        # Execute the action
        if action_type == "click":
            x = vision_result.get("x", 0)
            y = vision_result.get("y", 0)
            await page.mouse.click(x, y)
            await page.wait_for_timeout(500)
        elif action_type == "type":
            text = vision_result.get("text", "")
            x = vision_result.get("x")
            y = vision_result.get("y")
            
            if x is not None and y is not None:
                await page.mouse.click(x, y)
                await page.wait_for_timeout(300)
            
            if text:
                await page.keyboard.type(text)
                await page.wait_for_timeout(500)
        elif action_type == "scroll":
            scroll_x = vision_result.get("x", 0)
            scroll_y = vision_result.get("y", 0)
            await page.mouse.wheel(scroll_x, scroll_y)
            await page.wait_for_timeout(500)
        
        # Wait for page to update
        await page.wait_for_timeout(1000)
        
        # Get updated page info
        current_url = page.url
        title = await page.title()
        
        return JSONResponse(content={
            "success": True,
            "url": current_url,
            "title": title,
            "proxy_url": f"/api/browser/proxy/{session_id_param}/"
        })
    except Exception as e:
        logger.error(f"Error in browser control: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/browser/action")
async def browser_action(action_data: BrowserAction):
    """Perform an action on the browser page"""
    try:
        page = await get_browser_page(action_data.session_id)
        if not page:
            raise HTTPException(status_code=500, detail="Browser not available")
        
        if action_data.action == "click":
            if action_data.x is not None and action_data.y is not None:
                await page.mouse.click(action_data.x, action_data.y)
            else:
                raise HTTPException(status_code=400, detail="x and y coordinates required for click")
        elif action_data.action == "type":
            if action_data.text:
                await page.keyboard.type(action_data.text)
            else:
                raise HTTPException(status_code=400, detail="text required for type action")
        elif action_data.action == "scroll":
            scroll_x = action_data.x or 0
            scroll_y = action_data.y or 0
            await page.mouse.wheel(scroll_x, scroll_y)
        elif action_data.action == "back":
            await page.go_back()
        elif action_data.action == "forward":
            await page.go_forward()
        elif action_data.action == "reload":
            await page.reload()
            # Update stored URLs
            current_url = page.url
            parsed_url = urlparse(current_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            browser_contexts[action_data.session_id + "_base_url"] = base_url
            browser_contexts[action_data.session_id + "_current_url"] = current_url
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action_data.action}")
        
        # Wait for page to update
        await page.wait_for_timeout(500)
        
        # Return updated page info
        current_url = page.url
        title = await page.title()
        
        return JSONResponse(content={
            "success": True,
            "url": current_url,
            "title": title,
            "proxy_url": f"/api/browser/proxy/{action_data.session_id}/"
        })
    except Exception as e:
        logger.error(f"Error performing browser action: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# Voice Agent Endpoints for STT → LLM → TTS Pipeline
@app.post("/api/voice/process")
async def process_voice(request: Request):
    """
    Process voice input through the complete pipeline:
    Speech-to-Text → Language Model → Text-to-Speech

    Expects JSON body with base64-encoded audio data
    """
    try:
        data = await request.json()
        audio_base64 = data.get("audio")
        audio_format = data.get("format", "webm")

        if not audio_base64:
            raise HTTPException(status_code=400, detail="No audio data provided")

        # Decode base64 audio
        audio_bytes = b64.b64decode(audio_base64)

        # Get voice agent and process
        agent = get_voice_agent()
        result = await agent.process_voice_input(audio_bytes, audio_format)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Voice processing error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing voice: {str(e)}")


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice streaming
    Supports continuous conversation with the voice agent
    """
    await websocket.accept()
    logger.info("Voice WebSocket connection established")

    try:
        agent = get_voice_agent()

        while True:
            # Receive message from client
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "audio":
                # Process voice input
                audio_base64 = message.get("audio")
                audio_format = message.get("format", "webm")

                if not audio_base64:
                    await websocket.send_json({
                        "type": "error",
                        "error": "No audio data provided"
                    })
                    continue

                # Send acknowledgment
                await websocket.send_json({
                    "type": "processing",
                    "status": "transcribing"
                })

                # Decode audio
                audio_bytes = b64.b64decode(audio_base64)

                # Step 1: Transcribe
                transcription = await agent.transcribe_audio(audio_bytes, audio_format)

                if not transcription:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Could not transcribe audio"
                    })
                    continue

                # Send transcription to client
                await websocket.send_json({
                    "type": "transcription",
                    "text": transcription
                })

                # Send status update
                await websocket.send_json({
                    "type": "processing",
                    "status": "thinking"
                })

                # Step 2: Get LLM response (streaming)
                response_text = ""
                async for chunk in agent.stream_llm_response(transcription):
                    response_text += chunk
                    await websocket.send_json({
                        "type": "response_chunk",
                        "chunk": chunk
                    })

                # Send status update
                await websocket.send_json({
                    "type": "processing",
                    "status": "speaking"
                })

                # Step 3: Synthesize speech
                response_audio = await agent.synthesize_speech(response_text)

                if response_audio:
                    # Send audio back to client
                    audio_base64 = b64.b64encode(response_audio).decode('utf-8')
                    await websocket.send_json({
                        "type": "audio_response",
                        "audio": audio_base64,
                        "format": "mp3",
                        "text": response_text
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Failed to synthesize speech"
                    })

                # Send completion
                await websocket.send_json({
                    "type": "complete",
                    "transcription": transcription,
                    "response": response_text
                })

            elif message_type == "clear_history":
                # Clear conversation history
                agent.clear_history(keep_system_prompt=True)
                await websocket.send_json({
                    "type": "history_cleared",
                    "message": "Conversation history cleared"
                })

            elif message_type == "get_history":
                # Get conversation summary
                history = agent.get_conversation_summary()
                await websocket.send_json({
                    "type": "history",
                    "data": history
                })

            elif message_type == "ping":
                # Keepalive ping
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "error": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        logger.info("Voice WebSocket connection closed")
    except Exception as e:
        logger.error(f"Voice WebSocket error: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
        except:
            pass


@app.post("/api/voice/synthesize")
async def synthesize_speech(request: Request):
    """
    Text-to-Speech endpoint
    Converts text to speech audio
    """
    try:
        data = await request.json()
        text = data.get("text")

        if not text:
            raise HTTPException(status_code=400, detail="No text provided")

        agent = get_voice_agent()
        audio_bytes = await agent.synthesize_speech(text)

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Failed to synthesize speech")

        # Return audio as base64
        audio_base64 = b64.b64encode(audio_bytes).decode('utf-8')

        return JSONResponse(content={
            "audio": audio_base64,
            "format": "mp3",
            "text": text
        })

    except Exception as e:
        logger.error(f"TTS error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error synthesizing speech: {str(e)}")


@app.post("/api/voice/transcribe")
async def transcribe_audio_endpoint(request: Request):
    """
    Speech-to-Text endpoint
    Converts audio to text
    """
    try:
        data = await request.json()
        audio_base64 = data.get("audio")
        audio_format = data.get("format", "webm")

        if not audio_base64:
            raise HTTPException(status_code=400, detail="No audio data provided")

        # Decode audio
        audio_bytes = b64.b64decode(audio_base64)

        agent = get_voice_agent()
        transcription = await agent.transcribe_audio(audio_bytes, audio_format)

        if not transcription:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio")

        return JSONResponse(content={
            "transcription": transcription
        })

    except Exception as e:
        logger.error(f"STT error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")


@app.get("/api/voice/conversation")
async def get_conversation():
    """Get current conversation history"""
    try:
        agent = get_voice_agent()
        history = agent.get_conversation_summary()

        return JSONResponse(content={
            "history": history,
            "count": len(history)
        })
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/voice/conversation")
async def clear_conversation():
    """Clear conversation history"""
    try:
        agent = get_voice_agent()
        agent.clear_history(keep_system_prompt=True)

        return JSONResponse(content={
            "message": "Conversation history cleared",
            "success": True
        })
    except Exception as e:
        logger.error(f"Error clearing conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def execute_iterative_workflow(user_message: str, session_id: str):
    """
    Execute iterative workflow for document compilation tasks.
    Automatically chains: find_file -> read_files -> create_file
    Yields progress updates at each step.
    This is an async generator that yields dict updates.
    """
    compilation_keywords = ["compile", "create a report", "generate a report", "analyze and create", "summarize", "create a summary"]
    user_lower = user_message.lower()
    is_compilation_request = any(keyword in user_lower for keyword in compilation_keywords)
    
    if not is_compilation_request:
        yield {"type": "error", "message": "Not a compilation request"}
        return
    
    try:
        # Step 1: Find files
        yield {"type": "progress", "message": "🔍 Step 1: Finding relevant documents...", "step": 1}
        await asyncio.sleep(0.1)  # Small delay to ensure message is sent
    
        # Use LLM to determine search pattern
        search_prompt = f"""Based on this user request: "{user_message}"
Extract the key search terms for finding relevant documents. Return only a comma-separated list of search terms.
Examples: "Q4 financial" -> "Q4,financial", "client status reports" -> "client,status"
Search terms:"""
        
        try:
            yield {"type": "progress", "message": "🔍 Analyzing request to determine search terms...", "step": 1}
            completion = openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[{"role": "user", "content": search_prompt}],
                temperature=0.3,
                max_tokens=50
            )
            search_terms = completion.choices[0].message.content.strip()
            pattern = search_terms.split(',')[0].strip() if ',' in search_terms else search_terms
        except Exception as e:
            logger.error(f"Error extracting search pattern: {e}")
            # Fallback: extract keywords from user message
            pattern = " ".join([word for word in user_lower.split() if len(word) > 3][:3])
        
        yield {"type": "progress", "message": f"🔍 Searching for documents matching: '{pattern}'...", "step": 1}
        await asyncio.sleep(0.1)
    
        # Execute find_file - run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        def search_files():
            all_files = []
            for root, dirs, filenames in os.walk(DATA_DIR):
                for filename in filenames:
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, DATA_DIR)
                    all_files.append({
                        "path": rel_path.replace(os.sep, "/"),
                        "full_path": full_path
                    })
            
            pattern_lower = pattern.lower()
            pattern_words = pattern_lower.split()
            found_files = []
            
            for file_info in all_files:
                path_lower = file_info["path"].lower()
                if pattern_lower in path_lower or (len(pattern_words) > 1 and all(word in path_lower for word in pattern_words)):
                    found_files.append(file_info["path"])
            
            def search_content(file_info):
                try:
                    with open(file_info["full_path"], 'r', encoding='utf-8', errors='ignore') as f:
                        content_lower = f.read().lower()
                        if pattern_lower in content_lower or (len(pattern_words) > 1 and all(word in content_lower for word in pattern_words)):
                            return file_info["path"]
                except:
                    pass
                return None
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(search_content, file_info): file_info for file_info in all_files if file_info["path"] not in found_files}
                for future in as_completed(futures):
                    result = future.result()
                    if result and result not in found_files:
                        found_files.append(result)
            
            return found_files
        
        found_files = await loop.run_in_executor(None, search_files)
        
        if not found_files:
            yield {"type": "error", "message": f"No documents found matching '{pattern}'"}
            return
        
        yield {"type": "progress", "message": f"✅ Found {len(found_files)} relevant document(s): {', '.join([f.split('/')[-1] for f in found_files[:5]])}{'...' if len(found_files) > 5 else ''}", "step": 1, "files": found_files[:10]}
        await asyncio.sleep(0.1)
    
        # Step 2: Read files
        yield {"type": "progress", "message": f"📖 Step 2: Reading {min(len(found_files), 10)} document(s)...", "step": 2}
        await asyncio.sleep(0.1)
        
        def read_files_sync():
            file_contents = []
            for file_path in found_files[:10]:
                try:
                    safe_path = Path(file_path)
                    if ".." not in str(safe_path) and not safe_path.is_absolute():
                        target_file = DATA_DIR / safe_path
                        if target_file.exists() and target_file.is_file():
                            content = target_file.read_text(encoding='utf-8', errors='ignore')
                            file_contents.append({"path": file_path, "content": content})
                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")
            return file_contents
        
        file_contents = await loop.run_in_executor(None, read_files_sync)
        
        if not file_contents:
            yield {"type": "error", "message": "Could not read any documents"}
            return
        
        yield {"type": "progress", "message": f"✅ Successfully read {len(file_contents)} document(s) ({sum(len(fc['content']) for fc in file_contents)} total characters)", "step": 2}
        await asyncio.sleep(0.1)
    
        # Step 3: Compile report
        yield {"type": "progress", "message": "🤖 Step 3: Analyzing documents and compiling comprehensive report...", "step": 3}
        await asyncio.sleep(0.1)
        
        documents_text = "\n\n".join([f"=== {fc['path']} ===\n{fc['content']}" for fc in file_contents])
        
        compile_prompt = f"""Based on the user request: "{user_message}"

Here are the relevant documents:

{documents_text}

Create a comprehensive, well-structured report that synthesizes all the information from these documents. The report should be professional, detailed, and include all key findings, metrics, and insights.

Return the compiled report content:"""
        
        yield {"type": "progress", "message": "🤖 Generating report with AI (this may take a moment)...", "step": 3}
        
        try:
            completion = await asyncio.to_thread(
                openai_client.chat.completions.create,
                model="gpt-4.1-2025-04-14",
                messages=[{"role": "user", "content": compile_prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            compiled_content = completion.choices[0].message.content
            
            output_name = "Compiled_Report.md"
            if "Q4" in user_message or "quarter" in user_lower:
                output_name = "Q4_Financial_Report_Compiled.md"
            elif "client" in user_lower:
                output_name = "Client_Status_Summary.md"
            
            output_path = f"Desktop/{output_name}"
            target_file = DATA_DIR / output_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(compiled_content, encoding='utf-8')
            
            yield {
                "type": "complete",
                "message": f"✅ Successfully compiled report!\n\n📄 File: {output_path}\n📊 Size: {len(compiled_content)} characters\n\nPreview:\n{compiled_content[:300]}...",
                "step": 3,
                "output_file": output_path,
                "preview": compiled_content[:500] + "..." if len(compiled_content) > 500 else compiled_content
            }
        except Exception as e:
            logger.error(f"Error compiling report: {e}")
            yield {"type": "error", "message": f"Error compiling report: {str(e)}"}
    except Exception as e:
        logger.error(f"Error in iterative workflow: {e}")
        yield {"type": "error", "message": f"Workflow error: {str(e)}"}


async def execute_slideshow_workflow(user_message: str, session_id: str):
    """
    Execute iterative workflow for slideshow creation.
    Gathers information from documents, then creates presentation.
    Yields progress updates at each step.
    """
    try:
        # Step 1: Find relevant documents (if the request suggests gathering info)
        yield {"type": "progress", "message": "🔍 Step 1: Finding relevant documents and information...", "step": 1}
        await asyncio.sleep(0.1)
        
        # Use LLM to determine if we need to search for documents and what to search for
        search_decision_prompt = f"""Based on this user request: "{user_message}"
Determine if we should search for relevant documents to gather information.
If the request mentions specific topics, data, reports, or suggests using existing documents, return "YES" followed by search terms.
If it's a general creative request, return "NO".
Examples:
- "Create a presentation about Q4 financial results" -> "YES:Q4,financial,results"
- "Make a slideshow about our company" -> "YES:company,about"
- "Create a fun presentation about cats" -> "NO"

Response:"""
        
        try:
            yield {"type": "progress", "message": "🔍 Analyzing request to determine information sources...", "step": 1}
            completion = openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[{"role": "user", "content": search_decision_prompt}],
                temperature=0.3,
                max_tokens=50
            )
            search_decision = completion.choices[0].message.content.strip()
            should_search = search_decision.upper().startswith("YES")
            if should_search:
                pattern = search_decision.split(":")[-1].strip() if ":" in search_decision else " ".join([word for word in user_message.lower().split() if len(word) > 3][:3])
            else:
                pattern = None
        except Exception as e:
            logger.error(f"Error in search decision: {e}")
            # Default: try to extract search terms from user message
            pattern = " ".join([word for word in user_message.lower().split() if len(word) > 3][:3]) if len(user_message.split()) > 3 else None
            should_search = pattern is not None
        
        file_contents = []
        documents_text = ""
        
        if should_search and pattern:
            yield {"type": "progress", "message": f"🔍 Searching for documents matching: '{pattern}'...", "step": 1}
            await asyncio.sleep(0.1)
            
            # Execute file search
            loop = asyncio.get_event_loop()
            def search_files():
                all_files = []
                for root, dirs, filenames in os.walk(DATA_DIR):
                    for filename in filenames:
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, DATA_DIR)
                        all_files.append({
                            "path": rel_path.replace(os.sep, "/"),
                            "full_path": full_path
                        })
                
                pattern_lower = pattern.lower()
                pattern_words = pattern_lower.split()
                found_files = []
                
                for file_info in all_files:
                    path_lower = file_info["path"].lower()
                    if pattern_lower in path_lower or (len(pattern_words) > 1 and all(word in path_lower for word in pattern_words)):
                        found_files.append(file_info["path"])
                
                def search_content(file_info):
                    try:
                        with open(file_info["full_path"], 'r', encoding='utf-8', errors='ignore') as f:
                            content_lower = f.read().lower()
                            if pattern_lower in content_lower or (len(pattern_words) > 1 and all(word in content_lower for word in pattern_words)):
                                return file_info["path"]
                    except:
                        pass
                    return None
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {executor.submit(search_content, file_info): file_info for file_info in all_files if file_info["path"] not in found_files}
                    for future in as_completed(futures):
                        result = future.result()
                        if result and result not in found_files:
                            found_files.append(result)
                
                return found_files
            
            found_files = await loop.run_in_executor(None, search_files)
            
            if found_files:
                yield {"type": "progress", "message": f"✅ Found {len(found_files)} relevant document(s)", "step": 1, "files": found_files[:10]}
                await asyncio.sleep(0.1)
                
                # Step 2: Read files
                yield {"type": "progress", "message": f"📖 Step 2: Reading {min(len(found_files), 10)} document(s)...", "step": 2}
                await asyncio.sleep(0.1)
                
                def read_files_sync():
                    contents = []
                    for file_path in found_files[:10]:
                        try:
                            safe_path = Path(file_path)
                            if ".." not in str(safe_path) and not safe_path.is_absolute():
                                target_file = DATA_DIR / safe_path
                                if target_file.exists() and target_file.is_file():
                                    content = target_file.read_text(encoding='utf-8', errors='ignore')
                                    contents.append({"path": file_path, "content": content})
                        except Exception as e:
                            logger.error(f"Error reading {file_path}: {e}")
                    return contents
                
                file_contents = await loop.run_in_executor(None, read_files_sync)
                
                if file_contents:
                    documents_text = "\n\n".join([f"=== {fc['path']} ===\n{fc['content']}" for fc in file_contents])
                    yield {"type": "progress", "message": f"✅ Successfully gathered information from {len(file_contents)} document(s)", "step": 2}
                    await asyncio.sleep(0.1)
        else:
            yield {"type": "progress", "message": "ℹ️ Creating presentation from your description (no document search needed)", "step": 1}
            await asyncio.sleep(0.1)
        
        # Step 3: Generate slideshow
        yield {"type": "progress", "message": "🎨 Step 3: Generating professional presentation slides...", "step": 3}
        await asyncio.sleep(0.1)
        
        # Create enhanced prompt with document context
        enhanced_prompt = user_message
        if documents_text:
            enhanced_prompt = f"""{user_message}

Use the following information gathered from documents to create an accurate and comprehensive presentation:

{documents_text}

Create a professional presentation that incorporates this information."""
        
        yield {"type": "progress", "message": "🤖 Using AI to design slides and generate content...", "step": 3}
        await asyncio.sleep(0.1)
        
        slideshow_response = await generate_slideshow_internal(enhanced_prompt)
        
        if not slideshow_response.get("success"):
            yield {"type": "error", "message": f"Error generating slideshow: {slideshow_response.get('error', 'Unknown error')}"}
            return
        
        # Step 4: Save file
        yield {"type": "progress", "message": "💾 Step 4: Saving presentation file...", "step": 4}
        await asyncio.sleep(0.1)
        
        title = slideshow_response.get("title", "Presentation")
        safe_filename = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title)
        safe_filename = safe_filename.replace(' ', '_')[:50]
        if not safe_filename:
            safe_filename = "Slideshow"
        
        output_path = f"Desktop/{safe_filename}.html"
        target_file = DATA_DIR / output_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(slideshow_response.get("html"), encoding='utf-8')
        
        yield {
            "type": "complete",
            "message": f"✅ Successfully created presentation!\n\n📄 File: {output_path}\n📊 Slides: {slideshow_response.get('slide_count', 0)}\n📝 Title: {title}\n\nDouble-click the file to open it in the browser.",
            "step": 4,
            "output_file": output_path,
            "slide_count": slideshow_response.get('slide_count', 0),
            "title": title
        }
        
    except Exception as e:
        logger.error(f"Error in slideshow workflow: {e}", exc_info=True)
        yield {"type": "error", "message": f"Workflow error: {str(e)}"}


@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: Request):
    """Streaming endpoint for iterative workflows"""
    data = await request.json()
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")
    
    if not user_message:
        return JSONResponse(content={"error": "No message provided"})
    
    async def generate():
        async for update in execute_iterative_workflow(user_message, session_id):
            yield f"data: {json.dumps(update)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


class SlideshowRequest(BaseModel):
    prompt: str
    template_style: Optional[str] = None

async def generate_slideshow_internal(prompt: str, template_style: Optional[str] = None):
    """Internal function to generate slideshow HTML"""
    try:
        
        # Use LLM to generate slide structure
        system_prompt = """You are an expert slideshow designer and HTML/CSS developer. 
Given a user's request, create a professional slideshow presentation.

Return a JSON object with this structure:
{
  "title": "Presentation Title",
  "template_style": "modern|minimal|dark|corporate|creative",
  "slides": [
    {
      "type": "title|content|list|stats|image|chart",
      "title": "Slide Title",
      "content": "Main content text (can include HTML for formatting)",
      "items": ["List item 1", "List item 2"] (for list type),
      "stats": [{"value": "12.5M", "label": "Revenue"}] (for stats type),
      "chart_data": {
        "type": "bar|line|pie|doughnut",
        "labels": ["Label1", "Label2", "Label3"],
        "datasets": [{
          "label": "Dataset Label",
          "data": [10, 20, 30],
          "backgroundColor": ["#667eea", "#764ba2", "#f093fb"] (for pie/doughnut) or "#667eea" (for bar/line)
        }]
      } (for chart type - use when user requests charts or visualizations)
    }
  ]
}

Guidelines:
- Create 5-10 slides for comprehensive presentations
- Use appropriate slide types: title slide, content slides, list slides, stats slides, charts
- When user requests "charts", "visualizations", "graphs", or "pie charts", use type "chart" with chart_data
- For chart_data: use "pie" or "doughnut" for pie charts, "bar" for bar charts, "line" for line charts
- Chart colors should match the template style (use gradients for modern/creative, solid colors for corporate)
- For financial/business presentations, use "corporate" style with bar or line charts
- For creative/pitch presentations, use "modern" or "creative" style
- For technical presentations, use "minimal" or "dark" style
- Make content professional, engaging, and well-structured
- Include relevant metrics and data when appropriate
- Use clear, concise language"""
        
        try:
            completion = openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create a slideshow presentation for: {prompt}"}
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
                max_tokens=3000
            )
            
            slideshow_data = json.loads(completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error generating slideshow structure: {e}")
            return {
                "success": False,
                "error": f"Error generating slideshow structure: {str(e)}"
            }
        
        # Extract slideshow data
        title = slideshow_data.get("title", "Presentation")
        # Use provided template_style or let LLM choose
        final_template_style = template_style or slideshow_data.get("template_style", "modern")
        slides_data = slideshow_data.get("slides", [])
        
        if not slides_data:
            return {
                "success": False,
                "error": "No slides generated"
            }
        
        # Generate HTML for each slide
        slides_html = []
        for i, slide_data in enumerate(slides_data):
            slide_content = create_slide_content(slide_data, final_template_style)
            slide_html = SLIDE_TEMPLATES.get(final_template_style, SLIDE_TEMPLATES["modern"]).format(
                slide_class="slide",
                content=slide_content
            )
            slides_html.append(slide_html)
        
        # Combine into full HTML document
        full_html = HTML_TEMPLATE.format(
            title=title,
            slides="\n".join(slides_html),
            slide_count=len(slides_html)
        )
        
        # Add JavaScript for slide navigation
        navigation_js = """
        <script>
            let currentSlide = 0;
            const slides = document.querySelectorAll('.slide');
            const indicator = document.querySelector('.slide-indicator');
            const totalSlides = slides.length;
            
            function showSlide(index) {
                if (index < 0 || index >= totalSlides) return;
                slides.forEach((slide, i) => {
                    slide.style.display = i === index ? 'flex' : 'none';
                });
                currentSlide = index;
                if (indicator) {
                    indicator.textContent = `${currentSlide + 1} / ${totalSlides}`;
                }
            }
            
            function nextSlide() {
                showSlide(Math.min(currentSlide + 1, totalSlides - 1));
            }
            
            function previousSlide() {
                showSlide(Math.max(currentSlide - 1, 0));
            }
            
            document.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowRight' || e.key === ' ') {
                    e.preventDefault();
                    nextSlide();
                } else if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    previousSlide();
                } else if (e.key === 'Escape') {
                    // Fullscreen toggle could go here
                }
            });
            
            // Touch/swipe support for mobile
            let touchStartX = 0;
            let touchEndX = 0;
            
            document.addEventListener('touchstart', (e) => {
                touchStartX = e.changedTouches[0].screenX;
            });
            
            document.addEventListener('touchend', (e) => {
                touchEndX = e.changedTouches[0].screenX;
                handleSwipe();
            });
            
            function handleSwipe() {
                const swipeThreshold = 50;
                const diff = touchStartX - touchEndX;
                if (Math.abs(diff) > swipeThreshold) {
                    if (diff > 0) {
                        nextSlide();
                    } else {
                        previousSlide();
                    }
                }
            }
            
            // Chart initialization map
            const chartInstances = new Map();
            
            // Initialize all charts when page loads
            function initializeCharts() {
                if (typeof Chart === 'undefined') {
                    setTimeout(initializeCharts, 100);
                    return;
                }
                
                document.querySelectorAll('canvas[id^="chart_"]').forEach(canvas => {
                    const chartId = canvas.id;
                    if (!chartInstances.has(chartId)) {
                        try {
                            // Get chart config from data attribute or find script tag
                            const scriptTag = document.querySelector(`script[data-chart-id="${chartId}"]`);
                            if (scriptTag) {
                                const config = JSON.parse(scriptTag.textContent);
                                const chart = new Chart(canvas, config);
                                chartInstances.set(chartId, chart);
                            }
                        } catch (e) {
                            console.error('Error initializing chart:', e);
                        }
                    }
                });
            }
            
            // Show first slide
            showSlide(0);
            
            // Initialize charts after a short delay to ensure Chart.js is loaded
            setTimeout(initializeCharts, 500);
            
            // Auto-hide controls after 3 seconds of inactivity (on desktop)
            let hideControlsTimer;
            function resetHideTimer() {
                clearTimeout(hideControlsTimer);
                const controls = document.querySelector('.slide-controls');
                if (controls) controls.style.opacity = '1';
                hideControlsTimer = setTimeout(() => {
                    if (controls) controls.style.opacity = '0.3';
                }, 3000);
            }
            
            document.addEventListener('mousemove', resetHideTimer);
            resetHideTimer();
        </script>
        """
        
        full_html = full_html.replace("</body>", navigation_js + "\n</body>")
        
        return {
            "success": True,
            "html": full_html,
            "slide_count": len(slides_html),
            "title": title
        }
        
    except Exception as e:
        logger.error(f"Error generating slideshow: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/slideshow/generate")
async def generate_slideshow(request_data: SlideshowRequest):
    """Generate HTML/CSS slideshow from user prompt using AI codegen agent"""
    result = await generate_slideshow_internal(
        request_data.prompt, 
        request_data.template_style
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    
    return JSONResponse(content=result)


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)