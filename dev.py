import uvicorn
import debugpy
import os
from dotenv import load_dotenv

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Enable remote debugging on port 5678
    if os.getenv("ENABLE_DEBUGGER", "").lower() == "true":
        debugpy.listen(("0.0.0.0", 5678))
        print("⏳ Debugger is listening on port 5678, waiting for client to attach...")
        debugpy.wait_for_client()
        print("🔍 Debugger attached!")

    # Run the FastAPI application with hot reload
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable hot reload
        reload_dirs=["./"],  # Watch these directories for changes
        workers=1  # Use single worker for debugging
    )

if __name__ == "__main__":
    main() 