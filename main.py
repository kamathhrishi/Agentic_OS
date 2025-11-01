from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import uvicorn
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main OS interface"""
    return templates.TemplateResponse("index.html", {"request": request})

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
    
    if not user_message:
        return JSONResponse(content={
            "response": "Please enter a command.",
        "action": None,
        "data": None
        })
    
    # Get current file list to help LLM understand available files
    available_files = get_available_files()
    files_context = "\n".join([f"- {f['path']}" for f in available_files[:20]])  # Limit to first 20 files
    
    # Define explicit JSON schema for the response
    response_schema = {
        "type": "object",
        "properties": {
            "response": {
                "type": "string",
                "description": "Your conversational response to the user OR a helpful message explaining what action you took. Be natural and friendly in conversational mode."
            },
            "action": {
                "type": ["string", "null"],
                "enum": ["open_app", "close_all", "close_window", "minimize_window", "maximize_window", "create_file", "find_file", "delete_file", "list_files"],
                "description": "Action name to perform, or null if just conversational. Must be one of: open_app, close_all, close_window, minimize_window, maximize_window, create_file, find_file, delete_file, list_files, or null."
            },
            "data": {
                "type": "object",
                "description": "Action-specific data. Empty object {} for conversational messages or when action is null.",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "App name (required for open_app): file_manager, terminal, calculator, notepad, or settings"
                    },
                    "title": {
                        "type": "string",
                        "description": "Window title (optional for open_app)"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path (required for create_file, delete_file, list_files)"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content (required for create_file)"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (required for find_file)"
                    },
                    "search_content": {
                        "type": "boolean",
                        "description": "Whether to search in file contents (for find_file, defaults to true)"
                    }
                }
            }
        },
        "required": ["response", "action", "data"],
        "additionalProperties": False
    }
    
    # System prompt that allows both conversational and task-oriented interactions
    system_prompt = """You are a helpful and friendly OS assistant that can engage in natural conversation AND help users control their operating system through natural language.

You can have casual conversations with users - answer questions, provide explanations, chat about topics, etc. You're warm, intelligent, and engaging.

When users want to perform actions on the system, you can execute the following:
1. open_app - Open applications (file_manager, terminal, calculator, notepad, settings)
2. close_all - Close all windows
3. close_window - Close the topmost window
4. minimize_window - Minimize the topmost window
5. maximize_window - Maximize the topmost window
6. create_file - Create a new file (path and content required)
7. find_file - Find files by name pattern OR search within file contents (searches both in parallel)
8. delete_file - Delete a file by path
9. list_files - List files in a directory

For file operations, always work within the data directory. Paths should be relative (e.g., "Desktop/myfile.txt" or "myfile.txt").
When creating files, if no path prefix is specified, create them in Desktop folder.

The find_file operation searches both filenames and file contents in parallel for fast results. 
Use it like: "find recipes" (will search both filenames and contents), "find files containing chocolate", etc.

Available files in the system:
""" + files_context + """

RESPONSE FORMAT - JSON SCHEMA:
You must ALWAYS respond with ONLY a valid JSON object that conforms to this exact schema:

""" + json.dumps(response_schema, indent=2) + """

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

- User: "Tell me a joke" 
  Response: {"response": "Why don't scientists trust atoms? Because they make up everything! 😄", "action": null, "data": {}}

IMPORTANT: 
- Always return ONLY the JSON object, no other text before or after
- For conversational messages (no action needed), set "action" to null and "data" to {}
- Ensure all JSON is valid and matches the schema exactly"""

    # Valid action names
    valid_actions = ["open_app", "close_all", "close_window", "minimize_window", "maximize_window", 
                     "create_file", "find_file", "delete_file", "list_files"]
    
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
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"API Call Attempt {attempt}/{max_retries}")
                
                # Call OpenAI API with explicit JSON schema
                completion = openai_client.chat.completions.create(
                    model="gpt-4.1-2025-04-14",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.7,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "chat_response",
                            "strict": True,
                            "schema": response_schema,
                            "description": "Response schema for OS assistant chat interface"
                        }
                    }
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
                    
                    # Search by filename (fast, no parallel needed)
                    for file_info in all_files:
                        if pattern.lower() in file_info["path"].lower():
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
                                    if pattern.lower() in content.lower():
                                        # Find line numbers where pattern appears
                                        lines = content.split('\n')
                                        matching_lines = []
                                        for i, line in enumerate(lines, 1):
                                            if pattern.lower() in line.lower():
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
