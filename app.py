"""AI Coach — Tennis Coaching App

Entry point. Run with: python app.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8501, reload=True)
