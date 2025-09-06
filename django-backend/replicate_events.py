import asyncio
import websockets

async def main():
    events = []
    with open('test_events_1.log', 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(line.split('||'))

    uri = 'ws://localhost:8000/ws/media-stream/'
    async with websockets.connect(uri) as websocket:
        await websocket.send(str(events[0][1]))
        await asyncio.sleep(5)
        for dt, event in events[1:]:
            await websocket.send(str(event))
            print('send')
            await asyncio.sleep(float(dt)/(1_000_000))
            
            
            # Optionally, receive a response
            # response = await websocket.recv()
            # print(f"Received: {response}")

if __name__ == '__main__':
    asyncio.run(main())
