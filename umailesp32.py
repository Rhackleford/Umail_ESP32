# uMail (MicroMail) for MicroPython
# Copyright (c) 2018 Shawwwn <shawwwn1@gmail.com>
# Enhanced by Justin <justin.a.laviolette@gmail.com>, 2024
# License: MIT
# Description: A lightweight SMTP client for sending emails/SMS from MicroPython devices.

import socket
import time
import ssl as ssl_module  # Rename import to avoid shadowing

# Constants
LOCAL_DOMAIN = '127.0.0.1'
CMD_EHLO = 'EHLO'
CMD_STARTTLS = 'STARTTLS'
CMD_AUTH = 'AUTH'
CMD_MAIL = 'MAIL'
AUTH_PLAIN = 'PLAIN'
AUTH_LOGIN = 'LOGIN'

class SMTP:
    def __init__(self, host, port, use_ssl=False, username=None, password=None, timeout=10):
        """Initialize the SMTP client and connect to the server."""
        self.username = username
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        print(f"Socket initialized: {type(self._sock)}")
        
        addr = socket.getaddrinfo(host, port)[0][-1]
        print(f"Connecting to {host}:{port} at {addr}")
        try:
            self._sock.connect(addr)
            print("Connected successfully")
        except Exception as e:
            raise Exception(f"Connect failed: {e}")
        
        if use_ssl:  # Direct SSL connection (e.g., port 465)
            try:
                self._sock = ssl_module.wrap_socket(self._sock)  # Use ssl_module explicitly
                print("Direct SSL connection established")
            except Exception as e:
                raise Exception(f"SSL wrap failed: {e}")
        
        # Read the greeting immediately after SSL wrap
        greeting = self._sock.readline()
        if not greeting:
            raise Exception("No initial greeting received from server")
        greeting_str = greeting.decode('utf-8', 'replace').rstrip('\r\n')
        code = int(greeting_str[:3])
        resp = [greeting_str[4:]]
        print(f"SMTP: Initial greeting -> {code} {resp}")
        if code != 220:
            raise Exception(f"SMTP connect failed: {code}")
        
        code, resp = self.cmd(CMD_EHLO + ' ' + LOCAL_DOMAIN)
        if code != 250:
            raise Exception(f"EHLO failed: {code}, {resp}")
        
        # STARTTLS only if use_ssl=False and server supports it (e.g., port 587)
        if not use_ssl and CMD_STARTTLS in resp:
            code, resp = self.cmd(CMD_STARTTLS)
            if code != 220:
                raise Exception(f"STARTTLS failed: {code}, {resp}")
            time.sleep(1)
            print(f"Before SSL wrap: Socket type = {type(self._sock)}")
            if not hasattr(self._sock, 'connect'):
                raise Exception("Socket object invalid before SSL wrap")
            try:
                wrapped_sock = ssl_module.wrap_socket(self._sock)  # Use ssl_module explicitly
                if not hasattr(wrapped_sock, 'read'):
                    raise Exception(f"SSL wrap failed: returned {type(wrapped_sock)} instead of socket")
                self._sock = wrapped_sock
                print("STARTTLS completed")
            except Exception as e:
                raise Exception(f"STARTTLS SSL wrap failed: {e}")
            
            code, resp = self.cmd(CMD_EHLO + ' ' + LOCAL_DOMAIN)
            if code != 250:
                raise Exception(f"EHLO after STARTTLS failed: {code}, {resp}")
        
        if username and password:
            self.login(username, password)

    def cmd(self, cmd_str):
        """Send an SMTP command and return the response code and lines."""
        if cmd_str != "Initial greeting":
            self._sock.write(f'{cmd_str}\r\n'.encode())
            time.sleep(0.3)
        
        all_lines = []
        code = None
        
        while True:
            line = self._sock.readline()
            if not line:
                raise Exception(f"No response from server for '{cmd_str}' (connection closed?).")
            
            line_str = line.decode('utf-8', 'replace').rstrip('\r\n')
            if len(line_str) < 3:
                raise Exception(f"Invalid SMTP response line for '{cmd_str}': {line_str}")
            
            try:
                code = int(line_str[:3])
            except ValueError:
                raise Exception(f"Invalid SMTP response code for '{cmd_str}': {line_str[:3]!r}")
            
            text_after_code = line_str[3:].lstrip('- ')
            all_lines.append(text_after_code)
            
            if len(line_str) < 4 or line_str[3] != '-':
                break
        
        print(f"SMTP: {cmd_str} -> {code} {all_lines}")
        return code, all_lines

    def login(self, username, password):
        """Authenticate with SMTP server using PLAIN or LOGIN."""
        self.username = username
        code, resp = self.cmd(CMD_EHLO + ' ' + LOCAL_DOMAIN)
        if code != 250:
            raise Exception(f"EHLO failed: {code}, {resp}")

        auths = None
        for feature in resp:
            if feature[:4].upper() == CMD_AUTH:
                auths = feature[4:].strip('=').upper().split()
        if not auths:
            raise Exception("No auth methods available")

        from ubinascii import b2a_base64 as b64
        if AUTH_PLAIN in auths:
            cren = b64(f"\0{username}\0{password}").decode().strip()
            code, resp = self.cmd(f'{CMD_AUTH} {AUTH_PLAIN} {cren}')
        elif AUTH_LOGIN in auths:
            code, resp = self.cmd(f"{CMD_AUTH} {AUTH_LOGIN}")
            if code != 334:
                raise Exception(f"Username prompt failed: {code}, {resp}")
            code, resp = self.cmd(b64(username).decode().strip())
            if code != 334:
                raise Exception(f"Username failed: {code}, {resp}")
            code, resp = self.cmd(b64(password).decode().strip())
        else:
            raise Exception(f"Auth methods not supported: {', '.join(auths)}")

        if code not in (235, 503):
            raise Exception(f"Auth failed: {code}, {resp}")
        return code, resp

    def to(self, addrs, mail_from=None, retries=3):
        """Set the sender and recipients for the email."""
        mail_from = self.username if mail_from is None else mail_from
        for attempt in range(retries):
            try:
                code, resp = self.cmd(f'MAIL FROM: <{mail_from}>')
                if code != 250:
                    raise Exception(f"Sender refused: {code}, {resp}")
                if isinstance(addrs, str):
                    addrs = [addrs]
                count = 0
                for addr in addrs:
                    code, resp = self.cmd(f'RCPT TO: <{addr}>')
                    if code not in (250, 251):
                        print(f'{addr} refused: {resp}')
                        count += 1
                if count == len(addrs):
                    raise Exception(f"All recipients refused: {code}, {resp}")
                code, resp = self.cmd('DATA')
                if code != 354:
                    raise Exception(f"Data refused: {code}, {resp}")
                return code, resp
            except Exception as e:
                print(f"SMTP attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    raise e

    def write(self, content):
        """Write content to the email body."""
        self._sock.write(content.encode())
        print(f"Writing: {content}")

    def send(self, content='', mime=False):
        """Send the email with optional MIME headers."""
        if mime:
            self.write("MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n")
            self.write("\r\n")
        if content:
            self.write(content)
        self._sock.write(b'\r\n.\r\n')
        time.sleep(0.1)
        line = self._sock.readline().strip().decode()
        if not line:
            raise Exception("No SMTP send response")
        code = int(line[:3])
        resp = line[4:]
        print(f"SMTP: SEND -> {code} {resp}")
        return code, resp

    def quit(self):
        """Close the SMTP connection."""
        try:
            self.cmd("QUIT")
        except Exception as e:
            print(f"QUIT failed: {e}")
        self._sock.close()
