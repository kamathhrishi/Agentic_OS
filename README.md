# Agentic OS

An AI-powered operating system interface where you can control your OS through natural language chat.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the root directory with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

4. The frontend appears at: http://127.0.0.1:8000

## Features

- **AI-Powered Chat**: Control your OS using natural language via OpenAI integration
- **File Operations via Chat**: Create, find, and delete files through chat commands
- **JSON Action Mapping**: LLM responses are mapped to actions via structured JSON
- **Examples**:
  - "Create a file called notes.txt with some content"
  - "Find files with .txt extension"
  - "Delete the file notes.txt"
  - "Open calculator"
  - "List all files"