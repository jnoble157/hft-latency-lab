
import csv
import struct

def parse_lobster_message(line):
    """
    Parse a single line from LOBSTER message file.
    Format: Time(sec), EventType, OrderID, Size, Price, Direction
    """
    parts = line.strip().split(',')
    if len(parts) < 6:
        return None
    
    return {
        'time': float(parts[0]),
        'type': int(parts[1]),
        'id': int(parts[2]),
        'size': int(parts[3]),
        'price': int(parts[4]),
        'side': int(parts[5]) # 1=Buy, -1=Sell
    }

def load_lobster_snapshot(csv_path):
    """
    Parses a LOBSTER orderbook snapshot CSV.
    """
    asks = []
    bids = []
    
    with open(csv_path, 'r') as f:
        line = f.readline()
        if not line:
            return [], []
            
        parts = line.strip().split(',')
        num_levels = len(parts) // 4
        for i in range(num_levels):
            offset = i * 4
            if offset + 3 >= len(parts): break
            
            ask_p = int(parts[offset])
            ask_v = int(parts[offset+1])
            bid_p = int(parts[offset+2])
            bid_v = int(parts[offset+3])
            
            if ask_p > 0: asks.append((ask_p, ask_v))
            if bid_p > 0: bids.append((bid_p, bid_v))
            
    return asks, bids

def lobster_to_lob_packet(lob_msg, seq, t_send_ns):
    """
    Convert LOBSTER message dict to our UDP binary format.
    """
    # LOBSTER: 1=Add, 2=Cancel(Partial), 3=Delete(Total), 4=Exec(Vis), 5=Exec(Hid)
    
    # Mapping to our Action Codes:
    # 1 = Add (Add liquidity)
    # 3 = Delete (Remove/Reduce liquidity)
    
    # For Executions (4/5), they remove liquidity.
    # For Cancels (2), they remove liquidity.
    # For Deletes (3), they remove liquidity.
    
    action = 1 if lob_msg['type'] == 1 else 3
    
    # Side: LOBSTER 1=Buy(Bid), -1=Sell(Ask)
    # Ours: 0=Bid, 1=Ask
    side = 0 if lob_msg['side'] == 1 else 1
    
    hdr = struct.pack('>4sBBHHIQQH', b'LOB1', 1, 1, 0x8001, 32, seq, t_send_ns, 0, 0)
    
    delta = struct.pack('>iiHBBI', 
        lob_msg['price'], 
        lob_msg['size'], 
        0, 
        side, 
        action, 
        0
    )
    
    return hdr + delta
