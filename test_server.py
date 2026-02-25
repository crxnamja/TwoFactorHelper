#!/usr/bin/env python3
"""
Test server that inserts fake messages into the iMessage database
so TwoFactorHelper can detect them.
"""

import http.server
import json
import os
import sqlite3
import time

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
PORT = 8234


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            with open(
                os.path.join(os.path.dirname(__file__), "test.html"), "rb"
            ) as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/send":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            message = body.get("message", "")

            result = insert_test_message(message)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"  {args[0]}")


def insert_test_message(text):
    """Insert a fake message into the Messages database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Current time as nanoseconds since 2001-01-01
        reference_epoch = 978307200
        now = time.time()
        date_ns = int((now - reference_epoch) * 1_000_000_000)

        # Insert a message: is_from_me=0 simulates an incoming message
        cursor.execute(
            """
            INSERT INTO message (guid, text, date, date_read, is_from_me, cache_roomnames)
            VALUES (?, ?, ?, 0, 0, NULL)
            """,
            (f"test-{date_ns}", text, date_ns),
        )
        conn.commit()
        conn.close()

        print(f"  Inserted: {text}")
        return {"ok": True, "date": date_ns}

    except sqlite3.Error as e:
        print(f"  DB Error: {e}")
        return {"ok": False, "error": str(e)}
    except Exception as e:
        print(f"  Error: {e}")
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    print(f"Test server running at http://localhost:{PORT}")
    print(f"DB: {DB_PATH}")
    print(f"DB accessible: {os.access(DB_PATH, os.W_OK)}")
    print()
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
