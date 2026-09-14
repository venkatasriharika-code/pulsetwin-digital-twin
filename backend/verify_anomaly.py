import asyncio
import json
import websockets

async def main():
    async with websockets.connect('ws://127.0.0.1:8040/ws/simulation') as ws:
        await ws.send(json.dumps({'action':'tick','tickMinutes':5,'tickSeconds':0.1,'seed':3,'demandMultiplier':4.0}))
        await ws.recv()
        alerts = []
        for _ in range(4):
            message = json.loads(await ws.recv())
            if message['type'] == 'tick':
                alerts.extend(message['snapshot'].get('anomaly', {}).get('alerts', []))
                await ws.send(json.dumps({'action':'tick'}))
        assert alerts, 'expected a high-demand anomaly alert'
        print({'alerts': len(alerts), 'first': alerts[0]['title'], 'probability': alerts[0]['predictedSurgeProbability']})
        await ws.send(json.dumps({'action':'stop'}))

asyncio.run(main())
