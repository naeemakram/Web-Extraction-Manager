# Entry point for the Flask development server.
# Imports the app factory from app/__init__.py and starts the server.

import argparse
from app import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app = create_app()
    app.run(debug=True, port=args.port)
