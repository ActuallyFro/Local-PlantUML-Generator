import os
import time
import http.server
import socketserver
import threading
import subprocess
import sys
from datetime import datetime
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
import asyncio
# import websockets
import json

# Configuration
PORT = 8000
WEBSOCKET_PORT = 8765
CHECK_INTERVAL = 5
PlantUMLPath = os.path.expanduser("~/.local/plantuml/plantuml-1.2024.5.jar")

# Check if 'watchdog' is installed
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ModuleNotFoundError:
    print("Error: 'watchdog' module not found.")
    print("Please install it by running: pip install watchdog")
    sys.exit(1)

# Check if 'websockets' is installed
try:
    import websockets
except ModuleNotFoundError:
    print("Error: 'websockets' module not found.")
    print("Please install it by running: pip install websockets")
    sys.exit(1)

# ======
# FIXME: 
# ======
# #Check if Java is installed
# try:
#     subprocess.run(["java", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# except FileNotFoundError:
#     print("Error: Java is not installed.")
#     print("Please install Java from https://www.oracle.com/java/technologies/javase-jdk11-downloads.html")
#     sys.exit(1)

# # Check if PlantUML is installed
# try:
#     subprocess.run(["java", "-jar", PlantUMLPath, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# except FileNotFoundError:
#     print("Error: PlantUML is not installed.")
#     print("Please download PlantUML from https://plantuml.com/download and set the path in the configuration.")
#     sys.exit(1)

# Store file modification times
file_mod_times = {}

# WebSocket clients
clients = set()

# Function to generate index.html with embedded PNG/SVG images and download links
def generate_index_html():
    files = [f for f in os.listdir('.') if f.endswith('.puml')]
    with open("index.html", "w") as f:
        f.write("""
            <html>
            <head>
                <script>
                    let socket = new WebSocket("ws://localhost:{WEBSOCKET_PORT}");
                    socket.onmessage = function(event) {
                        let data = JSON.parse(event.data);
                        if (data.action === "reload") {
                            location.reload();
                        }
                    };
                </script>
            </head>
            <body>
                <h1>PlantUML Files</h1><ul>
        """.replace("{WEBSOCKET_PORT}", str(WEBSOCKET_PORT)))

        for file in files:
            png_file = file.replace(".puml", ".png")
            if os.path.exists(png_file):
                last_update = datetime.fromtimestamp(os.path.getmtime(png_file)).strftime('%Y-%m-%d @%H:%M:%S')
                f.write(f'<li><h2>{png_file} (Last Update: {last_update})</h2>')
                f.write(f'<img src="{png_file}?t=' + str(int(time.time())) + f'" alt="{png_file}" style="max-width: 100%; height: auto;"><br>')
                f.write(f'<a href="{png_file}" download>Download {png_file}</a><br></li>')
        f.write("</ul></body></html>")

# Watchdog EventHandler for detecting file changes
class ChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".puml"):
            file_mod_times[event.src_path] = os.path.getmtime(event.src_path)
            print(f"[LPG] [NOTICE] Detected change in {event.src_path}. Rendering...")
            subprocess.run(["java", "-Djava.awt.headless=true", "-jar", PlantUMLPath, event.src_path])
            print(f"[LPG] [NOTICE] {event.src_path} has been updated and rendered.")
            generate_index_html()  # Update index.html
            asyncio.run(notify_clients(event.src_path))  # Notify clients to refresh

# WebSocket server to notify clients
async def websocket_handler(websocket, path):
    clients.add(websocket)
    try:
        async for message in websocket:
            pass
    except:
        pass
    finally:
        clients.remove(websocket)

async def notify_clients(changed_file):
    if clients:
        message = json.dumps({"action": "reload"})
        await asyncio.wait([client.send(message) for client in clients])

# HTTP Server to serve files
class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

# Background server thread
def start_http_server():
    handler = SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"Serving at port {PORT}")
        httpd.serve_forever()

# Background WebSocket server thread
def start_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        websockets.serve(websocket_handler, "localhost", WEBSOCKET_PORT)
    )
    loop.run_forever()

# Function to monitor and auto-generate PlantUML files
def monitor_files():
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# Main function
def main():
    # Start HTTP server in background
    server_thread = threading.Thread(target=start_http_server)
    server_thread.daemon = True
    server_thread.start()

    # Start WebSocket server in background
    websocket_thread = threading.Thread(target=start_websocket_server)
    websocket_thread.daemon = True
    websocket_thread.start()

    # Generate index.html on start
    generate_index_html()

    print("App is running... Press Enter to quit")
    
    # Start monitoring files
    monitor_thread = threading.Thread(target=monitor_files)
    monitor_thread.daemon = True
    monitor_thread.start()

    # Wait for user to quit
    input()
    print("Shutting down...")

if __name__ == "__main__":
    main()
