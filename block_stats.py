#! /usr/bin/env python

import websockets
import json
import asyncio
import time
from collections import defaultdict

GATEWAY_URL = ''
GATEWAY_AUTH = ''

bnb48_miners = set(m.lower() for m in (                 # got from 0x5cc05fde1d231a840061c1a2d7e913cedc8eabaf
    '0x72b61c6014342d914470eC7aC2975bE345796c2b',
    '0xa6f79B60359f141df90A0C745125B131cAAfFD12',
    '0x0BAC492386862aD3dF4B666Bc096b0505BB694Da',
    '0xD1d6bF74282782B0b3eb1413c901D6eCF02e8e28',
    '0xb218C5D6aF1F979aC42BC68d98A5A0D796C6aB01',
    '0x4396e28197653d0C244D95f8C1E57da902A72b4e',
    '0x9bB832254BAf4E8B4cc26bD2B52B31389B56E98B',
    '0x9F8cCdaFCc39F3c7D6EBf637c9151673CBc36b88',))


tx_ts = defaultdict(float)
tx_delay = defaultdict(float)
tx_block = defaultdict(int)
last_block_ts = None
current_block = None


async def block_loop():
    global last_block_ts
    global current_block
    async with websockets.connect(GATEWAY_URL, extra_headers={'Authorization': GATEWAY_AUTH}) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "subscribe", 
            "params": ["newBlocks", {"include": ['header', 'future_validator_info', 'transactions']}]
        }))
        async for event in ws:
            event = json.loads(event)
            ts = time.time()
            if 'params' in event:
                try:
                    event = event['params']['result']
                    miner = event['header']['miner']
                    blockNum = int(event['header']['number'], 16)
                    private_txs = 0
                    for tx in event['transactions']:
                        h = tx['hash']
                        if ts - tx_ts[h] < 0.2:
                            private_txs += 1
                        print(f"{h}, {int(tx['gasPrice'], 16)/1e9:.03f} gwei, tx_delay={tx_delay[h]:.03f}s, tx_age={(ts - tx_ts[h]):.03f}s, block_diff={blockNum-tx_block[h]}")

                    print(f"BLOCK {blockNum}, miner={miner}, is_48={miner in bnb48_miners}, private_count={private_txs}, total_count={len(event['transactions'])}")
                    last_block_ts = ts
                    current_block = blockNum
                except Exception as e:
                    print(f"# {e}")

async def gateway_loop():
    global last_block_ts
    global current_block
    async with websockets.connect(GATEWAY_URL, extra_headers={'Authorization': GATEWAY_AUTH}) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "subscribe", 
            "params": ["newTxs", {"include": []}]
        }))
        async for event in ws:
            if not last_block_ts:
                continue
            ts = time.time()
            event = json.loads(event)
            if 'params' in event and 'result' in event['params'] and 'txContents' in event['params']['result']:
                tx_hash = event['params']['result']['txContents']['hash']
                tx_ts[tx_hash] = ts
                tx_delay[tx_hash] = ts - last_block_ts
                tx_block[tx_hash] = current_block
              
async def main():
    await asyncio.gather(
        gateway_loop(),   # TXs from bloXroute gateway
        block_loop(),     # Blocks from bloXroute gateway
    )

if __name__ == '__main__':
    asyncio.run(main())
