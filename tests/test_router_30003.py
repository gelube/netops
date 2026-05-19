import sys
sys.stdout.reconfigure(encoding='utf-8')
from netmiko import ConnectHandler

device = {
    'device_type': 'generic_termserver_telnet',
    'host': '127.0.0.1',
    'port': 30003,
    'timeout': 10,
}

try:
    conn = ConnectHandler(**device)
    # Send Ctrl+C to break auto-config
    conn.write_channel('\x03')
    import time
    time.sleep(1)
    output = conn.read_channel()
    print(f'After Ctrl+C: [{output[:200]}]')
    
    # Try a command
    conn.write_channel('screen-length disable\n')
    time.sleep(1)
    output = conn.read_channel()
    print(f'After screen-length: [{output[:200]}]')
    
    conn.write_channel('display version\n')
    time.sleep(2)
    output = conn.read_channel()
    print(f'Version: [{output[:300]}]')
    
    conn.disconnect()
except Exception as e:
    print(f'Error: {e}')
