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

app = FastAPI(title="Agentic OS")

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

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Handle chat messages for agentic OS control"""
    data = await request.json()
    user_message = data.get("message", "").strip().lower()
    
    response = {
        "response": "",
        "action": None,
        "data": None
    }
    
    # Process commands
    if not user_message:
        response["response"] = "Please enter a command."
    elif "open" in user_message or "launch" in user_message or "start" in user_message:
        # Open an app or window
        if "file" in user_message or "explorer" in user_message:
            response["response"] = "Opening File Manager..."
            response["action"] = "open_app"
            response["data"] = {"app": "file_manager", "title": "File Manager"}
        elif "terminal" in user_message or "cmd" in user_message:
            response["response"] = "Opening Terminal..."
            response["action"] = "open_app"
            response["data"] = {"app": "terminal", "title": "Terminal"}
        elif "settings" in user_message or "config" in user_message:
            response["response"] = "Opening Settings..."
            response["action"] = "open_app"
            response["data"] = {"app": "settings", "title": "Settings"}
        elif "calculator" in user_message:
            response["response"] = "Opening Calculator..."
            response["action"] = "open_app"
            response["data"] = {"app": "calculator", "title": "Calculator"}
        elif "notepad" in user_message or "note" in user_message:
            response["response"] = "Opening Notepad..."
            response["action"] = "open_app"
            response["data"] = {"app": "notepad", "title": "Notepad"}
        else:
            response["response"] = "Opening application..."
            response["action"] = "open_app"
            response["data"] = {"app": "default", "title": "Application"}
    elif "close" in user_message:
        if "all" in user_message:
            response["response"] = "Closing all windows..."
            response["action"] = "close_all"
        else:
            response["response"] = "Closing window..."
            response["action"] = "close_window"
    elif "minimize" in user_message or "min" in user_message:
        response["response"] = "Minimizing window..."
        response["action"] = "minimize_window"
    elif "maximize" in user_message or "max" in user_message:
        response["response"] = "Maximizing window..."
        response["action"] = "maximize_window"
    elif "time" in user_message or "clock" in user_message:
        from datetime import datetime
        current_time = datetime.now().strftime("%I:%M %p")
        response["response"] = f"Current time is {current_time}"
    elif "date" in user_message:
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        response["response"] = f"Today is {current_date}"
    elif "help" in user_message:
        response["response"] = """Available commands:
        - Open [app name]: Launch an application
        - Close/Close all: Close window(s)
        - Minimize/Maximize: Control windows
        - Time/Date: Get current time or date
        - Help: Show this help message"""
    elif "hello" in user_message or "hi" in user_message:
        response["response"] = "Hello! I'm your OS assistant. How can I help you?"
    else:
        response["response"] = f"I understand you said: '{data.get('message', '')}'. You can try commands like 'open calculator', 'close all', or 'help' for more options."
    
    return JSONResponse(content=response)

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
