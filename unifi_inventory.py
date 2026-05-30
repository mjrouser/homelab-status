#!/usr/bin/env python3
# unifi_inventory.py — Pulls device inventory from a local UniFi OS controller.
# Usage: python unifi_inventory.py
# Requires: pip install requests python-dotenv

import os
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

HOST     = os.getenv("UNIFI_HOST", "192.168.1.1")
USERNAME = os.getenv("UNIFI_USERNAME")
PASSWORD = os.getenv("UNIFI_PASSWORD")

BASE_URL = f"https://{HOST}"


def login(session):
    preflight = session.get(f"{BASE_URL}/")
    csrf = preflight.headers.get("X-CSRF-Token") or preflight.cookies.get("csrf_token", "")

    payload = {"username": USERNAME, "password": PASSWORD}
    resp = session.post(
        f"{BASE_URL}/api/auth/login",
        json=payload,
        headers={"X-CSRF-Token": csrf} if csrf else {},
    )

    # If MFA is required, prompt for the code and retry immediately
    if resp.status_code == 499 and resp.json().get("code") == "MFA_AUTH_REQUIRED":
        token = input("MFA code: ").strip()
        payload["token"] = token
        resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json=payload,
            headers={"X-CSRF-Token": csrf} if csrf else {},
        )

    resp.raise_for_status()


def get_devices(session):
    resp = session.get(f"{BASE_URL}/proxy/network/api/s/default/stat/device")
    resp.raise_for_status()
    return resp.json().get("data", [])


def print_device(d):
    name    = d.get("name") or d.get("hostname", "unnamed")
    model   = d.get("model", "unknown")
    dtype   = d.get("type", "unknown")
    ip      = d.get("ip", "")
    version = d.get("version", "")

    print(f"  Name:  {name}")
    print(f"  Model: {model}  Type: {dtype}  IP: {ip}  FW: {version}")

    port_table = d.get("port_table", [])
    active = [p for p in port_table if p.get("up")]
    if active:
        print(f"  Active ports ({len(active)}/{len(port_table)}):")
        for p in active:
            pname = p.get("name") or f"Port {p.get('port_idx', '?')}"
            speed = p.get("speed", 0)
            poe   = " [PoE]" if p.get("poe_enable") else ""
            print(f"    {pname}: {speed} Mbps{poe}")
    print()


def main():
    if not USERNAME or not PASSWORD:
        print("ERROR: Set UNIFI_USERNAME and UNIFI_PASSWORD in .env")
        return

    session = requests.Session()
    session.verify = False  # local UniFi devices use self-signed certs

    print(f"Connecting to {BASE_URL} ...")
    login(session)
    print("Logged in.\n")

    devices = get_devices(session)
    print(f"=== UniFi Devices ({len(devices)} found) ===\n")
    for d in sorted(devices, key=lambda x: x.get("type", "")):
        print_device(d)

    session.post(f"{BASE_URL}/api/auth/logout")


if __name__ == "__main__":
    main()
