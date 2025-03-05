# uMail (MicroMail) for MicroPython
# Copyright (c) 2018 Shawwwn <shawwwn1@gmail.com>
# Enhanced by Justin <justin.a.laviolette@gmail.com>, 2025# License: MIT
# Description: A lightweight SMTP client for sending emails/SMS from MicroPython devices.
# Features: Error handling with exceptions, retries, configurable timeout, MIME support, memory-efficient.

import socket
import time


# Constants
LOCAL_DOMAIN = '127.0.0.1'
CMD_EHLO = 'EHLO'
CMD_STARTTLS = 'STARTTLS'
CMD_AUTH = 'AUTH'
CMD_MAIL = 'MAIL'
AUTH_PLAIN = 'PLAIN'
AUTH_LOGIN = 'LOGIN'

class SMTP:
    """
    SMTP client for MicroPython to send emails or SMS via email-to-SMS gateways.
    Supports PLAIN/LOGIN auth, STARTTLS, retries, and MIME headers.
    Usage:
        smtp = SMTP('smtp.gmail.com', 587, ssl=True, username='user@gmail.com', password='app_password', timeout=30)
        smtp.to('recipient@example.com')
        smtp.write('Subject: Test\n\nHello!')
        smtp.send()
        smtp.quit()
    """
    
    def cmd(self, cmd_str):
        """Send an SMTP command and return response code and lines."""
        sock = self._sock
        sock.write(f'{cmd_str}\r\n')
        code = sock.read(3)
        if not code:
            raise Exception("No SMTP response")
        code = int(code)
        resp = sock.readline().strip().decode()
        while sock.read(1) == b'-':  # Handle multi-line responses efficiently
            resp += ' ' + sock.readline().strip().decode()
        print(f"SMTP: {cmd_str} -> {code} {resp}")  # Debug log
        return code, [resp]  # Single string list for memory efficiency

    def __init__(self, host, port, ssl=False, username=None, password=None, timeout=10):
        """
        Initialize SMTP connection.
        Args:
            host (str): SMTP server hostname (e.g., 'smtp.gmail.com').
            port (int): SMTP server port (e.g., 587 for TLS).
            ssl (bool): Use SSL/TLS (True for STARTTLS, False for plain).
            username (str): SMTP username (e.g., Gmail email).
            password (str): SMTP password (e.g., Gmail app password).
            timeout (int): Socket timeout in seconds (default 10).
        """
        import ssl
        self.username = username
        addr = socket.getaddrinfo(host, port)[0][-1]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(addr)
        except Exception as e:
            raise Exception(f"Connect failed: {e}")
        if ssl:
            sock = ssl.wrap_socket(sock)
        code = int(sock.read(3))
        sock.readline()
        if code != 220:
            raise Exception(f"SMTP connect failed: {code}")
        self._sock = sock

        code, resp = self.cmd(CMD_EHLO + ' ' + LOCAL_DOMAIN)
        if code != 250:
            raise Exception(f"EHLO failed: {code}, {resp}")
        if not ssl and CMD_STARTTLS in resp:
            code, resp = self.cmd(CMD_STARTTLS)
            if code != 220:
                raise Exception(f"STARTTLS failed: {code}, {resp}")
            self._sock = ssl.wrap_socket(sock)

        if username and password:
            self.login(username, password)

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

        from ubinascii import b2a_base64 as b64 # type: ignore
        if AUTH_PLAIN in auths:
            cren = b64(f"\0{username}\0{password}")[:-1].decode()
            code, resp = self.cmd(f'{CMD_AUTH} {AUTH_PLAIN} {cren}')
        elif AUTH_LOGIN in auths:
            code, resp = self.cmd(f"{CMD_AUTH} {AUTH_LOGIN} {b64(username)[:-1].decode()}")
            if code != 334:
                raise Exception(f"Username failed: {code}, {resp}")
            code, resp = self.cmd(b64(password)[:-1].decode())
        else:
            raise Exception(f"Auth methods not supported: {', '.join(auths)}")

        if code not in (235, 503):
            raise Exception(f"Auth failed: {code}, {resp}")
        return code, resp

    def to(self, addrs, mail_from=None, retries=3):
        """
        Set email recipients with retry logic.
        Args:
            addrs (str or list): Recipient email(s) or SMS gateway(s).
            mail_from (str): Sender email (defaults to username).
            retries (int): Number of retry attempts (default 3).
        """
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
        """Write email content to the socket."""
        self._sock.write(content)

    def send(self, content='', mime=False):
        """
        Send email with optional MIME headers.
        Args:
            content (str): Email body.
            mime (bool): Add MIME headers if True (default False).
        """
        if mime:
            self.write("MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n")
        if content:
            self.write(content)
        self._sock.write('\r\n.\r\n')
        line = self._sock.readline()
        if not line:
            raise Exception("No SMTP send response")
        code = int(line[:3])
        resp = line[4:].strip().decode()
        print(f"SMTP: SEND -> {code} {resp}")
        return code, resp

    def quit(self):
        """Close SMTP connection cleanly."""
        try:
            self.cmd("QUIT")
        except Exception as e:
            print(f"QUIT failed: {e}")
        self._sock.close()