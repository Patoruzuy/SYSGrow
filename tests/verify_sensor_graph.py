import requests
import sys
import json

def verify_sensor_graph():
    url = "http://127.0.0.1:5000/api/analytics/sensors/history"
    try:
        print(f"Requesting {url}...")
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"❌ Failed: Status code {response.status_code}")
            print(response.text)
            return False
            
        data = response.json()
        
        if data.get("status") != "success":
            print(f"❌ Failed: API returned status {data.get('status')}")
            return False
            
        payload = data.get("data", {})
        
        if "timestamps" not in payload:
            print("❌ Failed: 'timestamps' missing from response")
            return False
            
        if "readings" not in payload:
            print("❌ Failed: 'readings' missing from response")
            return False
            
        readings = payload["readings"]
        required_keys = ["temperature", "humidity", "soil_moisture", "co2", "voc"]
        
        for key in required_keys:
            if key not in readings:
                print(f"❌ Failed: Reading type '{key}' missing")
                return False
            if not isinstance(readings[key], list):
                print(f"❌ Failed: Reading type '{key}' is not a list")
                return False
                
        print(f"✅ Success: Received {len(payload['timestamps'])} timestamps")
        for key in required_keys:
            print(f"   - {key}: {len(readings[key])} data points")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if verify_sensor_graph():
        sys.exit(0)
    else:
        sys.exit(1)
