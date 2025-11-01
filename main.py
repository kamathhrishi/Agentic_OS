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
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    
    # System prompt that instructs the LLM to return JSON actions
    system_prompt = """You are an OS assistant that helps users control their operating system through natural language.
    
You can perform the following actions:
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

You must respond with ONLY a valid JSON object in this exact format:
{
    "response": "A helpful message to the user explaining what you did or what you understood",
    "action": "action_name (one of: open_app, close_all, close_window, minimize_window, maximize_window, create_file, find_file, delete_file, list_files, or null)",
    "data": {
        // Action-specific data:
        // For open_app: {"app": "app_name", "title": "Window Title"}
        // For create_file: {"path": "file/path.txt", "content": "file content"}
        // For find_file: {"pattern": "search term", "search_content": true} (searches both filename and content)
        // For delete_file: {"path": "file/path.txt"}
        // For list_files: {"path": "directory/path"}
        // For other actions: can be null or empty object
    }
}

IMPORTANT: Only return the JSON object, no other text before or after."""

    try:
        # Call OpenAI API
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Using a cheaper model, can switch to gpt-4 if needed
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}  # Force JSON output
        )
        
        # Parse the JSON response
        llm_response = json.loads(completion.choices[0].message.content)
        
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
