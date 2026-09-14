import asyncio
import json
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8020/ws/simulation") as ws:
        await ws.send(json.dumps({"action": "tick", "tickMinutes": 5, "tickSeconds": 0.1, "seed": 7}))
        connected = json.loads(await ws.recv())
        tick = json.loads(await ws.recv())
        assert connected["type"] == "connected"
        assert tick["type"] == "tick"
        assert "queueMetrics" in tick["snapshot"]
        assert tick["snapshot"]["simulatedMinutes"] == 5
        print({"connected": connected["type"], "tick": tick["type"], "queue": tick["snapshot"]["queueMetrics"]})
        await ws.send(json.dumps({"action": "stop"}))
        stopped = json.loads(await ws.recv())
        assert stopped["type"] == "stopped"

asyncio.run(main())
