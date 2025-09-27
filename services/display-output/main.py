import asyncio
import tkinter as tk
import websockets
import json

TRANSCRIBE_WS_URL = "ws://localhost:8002/transcribe"

class DisplayApp:
    def __init__(self, root):
        self.root = root
        self.text = tk.StringVar()
        tk.Label(root, textvariable=self.text, font=("Arial", 24)).pack(padx=20, pady=20)
        root.after(100, self.start_ws)

    async def ws_loop(self):
        async with websockets.connect(TRANSCRIBE_WS_URL) as ws:
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if "partial" in data:
                    self.text.set(data["partial"])
                if "final" in data:
                    self.text.set(data["final"])

    def start_ws(self):
        asyncio.create_task(self.ws_loop())

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Transcription Display")
    app = DisplayApp(root)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))
    root.mainloop()