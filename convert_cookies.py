import json
import os

def parse_netscape_cookies(filepath):
    cookies = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                domain = parts[0]
                # httpOnly is typically not in standard netscape format, defaulting to false or assuming
                secure = parts[3].upper() == 'TRUE'
                expires = int(parts[4])
                # If expires is 0, set it to -1 (session cookie)
                if expires == 0:
                    expires = -1
                name = parts[5]
                value = parts[6]
                
                cookie = {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": parts[2],
                    "expires": expires,
                    "httpOnly": False, # Just a default
                    "secure": secure,
                    "sameSite": "Lax"
                }
                cookies.append(cookie)
    return cookies

if __name__ == "__main__":
    cookie_list = parse_netscape_cookies("cookies.txt")
    state = {
        "cookies": cookie_list,
        "origins": []
    }
    with open("state.json", "w") as f:
        json.dump(state, f, indent=4)
    print(f"✅ ¡Convertidas {len(cookie_list)} cookies y guardadas en state.json!")
