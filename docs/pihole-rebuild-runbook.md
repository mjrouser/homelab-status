# Pi-hole Rebuild Runbook

Source of truth for the September 2026 Pi-hole rebuild. Mirrors the "Pi-hole Rebuild Runbook" doc in the Creativity Partner project.

## The plan at a glance

Four phases. Each one ends in a stable state you can walk away from.

| Phase | What | Rough time |
| --- | --- | --- |
| 1 | Pi 4 + SSD becomes **pihole1** (primary) | ~1 hr |
| 2 | Pi 3B + microSD becomes **pihole2** (backup) | ~1 hr |
| 3 | keepalived, VIP, DNS health check | ~45 min |
| 4 | Nebula Sync + cutover to 192.168.1.2 | ~30 min |

### The promotion

The Pi 4 with the SSD takes over as primary. Since both nodes are being flashed from scratch, identity follows role — the Pi 4 gets the primary's name and address, so every existing note, script, and dashboard reference stays true.

| Node | Hardware | Hostname | IP | Role |
| --- | --- | --- | --- | --- |
| 1 | Pi 4 + Kingston SSD | pihole1 | 192.168.1.129 | MASTER, sync source |
| 2 | Pi 3B + SanDisk Max Endurance | pihole2 | 192.168.1.13 | BACKUP, replica |

### What's different from the old setup

Five changes, all aimed at the failure modes that caused this rebuild:

- **SSD boot on the primary** — no SD card wear on the node that matters most
- **On-device static IPs** — closes the early-boot window where keepalived ran before the Pi had an address
- **DS3231 RTC on both nodes** — permanent fix for cold-boot DNSSEC failures after long outages
- **keepalived DNS health check** — failover triggers on broken DNS, not just a dead node
- **unattended-upgrades** — security patches land without you watching for them

### Done looks like

UniFi DHCP points at 192.168.1.2 on both networks, a client on the main LAN and a client on the IoT VLAN both resolve, failover works in both directions, and you have a backup image stored somewhere safe.

## Before you start

### Parts

- Kingston A400 SSD + UGREEN SATA-to-USB cable (try it **without** the 12V brick first)
- 2 × SanDisk Max Endurance microSD — one for pihole2, one for the deadbox
- 2 × DS3231 RTC modules + batteries (order if not yet on hand — the rebuild works without them, they just get installed later)
- microSD reader for the Mac
- Official power supplies: 5V 3A USB-C for the Pi 4, 5V 2.5A micro-USB for the Pi 3B

### Two things to do first

**1. Sort out the UniFi addressing.** *(Corrected 2026-09-20 — the original text assumed reservations already existed for .129 and .13. They did not.)*

UniFi has no central "DHCP reservations" page — a reservation is a per-client setting, visible only when you open that client, and **offline clients are hidden by default**. With both Pi-hole nodes down, the Pi 3B had aged out of the client list entirely, so there was nothing to "swap."

What actually matters: **the main LAN DHCP pool is `192.168.1.6 – 192.168.1.254`, so both .129 and .13 sit inside leasable space.** Neither address is safe on its own. For each node, boot it on DHCP first, read its MAC off the running system (`ip link show eth0`), then set the fixed IP in UniFi *before* setting the on-device static.

The VIP (192.168.1.2) is below .6 and therefore outside the pool — safe. See `ideas.md` → "DHCP Pool Narrowing" for the structural fix.

**2. Check the UPS.** Which outlet is the rack strip plugged into, is it battery-backed, and does the battery pass a self-test? Also look for a USB data port on the back, which decides whether the NUT idea is viable later.

### Ground rule for the whole rebuild

UniFi DHCP stays on **9.9.9.11 (Quad9)** until Phase 4 verification passes. Nothing you do in Phases 1–3 can take the house offline. That's the safety net — don't give it up early.

## Phase 1 — Pi 4 + SSD becomes pihole1

This phase alone restores DNS. Everything after it is redundancy.

### 1.1 Enable USB boot on the Pi 4

Boot the Pi 4 however it currently boots, then `sudo raspi-config` → Advanced Options → Boot Order → USB Boot.

If it won't boot at all: flash a spare card with Imager's Misc utility images → Bootloader → USB Boot, boot the Pi once from it, power off, remove the card.

### 1.2 Install the RTC (if the modules have arrived)

Power off, press the RTC module onto the GPIO header, insert the battery. Config comes after the OS is up, in 1.6.

### 1.3 Flash the SSD

Connect the SSD to the Mac through the UGREEN cable. In Raspberry Pi Imager, pick **Raspberry Pi OS Lite (64-bit)**, then open the settings gear and set:

- hostname `pihole1`
- SSH enabled, with your public key
- your username
- locale and timezone

Double-check you've selected the SSD, not another external drive. This is the one step where a mistake costs you something.

### 1.4 First boot and patch

Plug the SSD into a **blue USB 3.0 port**, boot with no card inserted, then:

**Plug in Ethernet.** The Lite image has no Wi-Fi configured — Ethernet is the only way in.

**Finding the address:** `avahi-daemon` *is* present and running on Pi OS Lite (confirmed listening on 5353), so `pihole1.local` should resolve once the Pi is actually on the network. If it does not, suspect **no link** — unplugged Ethernet, no Wi-Fi configured — before suspecting mDNS. The UniFi client list is the reliable fallback.

```
ssh <user>@<whatever address DHCP gave it>
sudo apt update && sudo apt full-upgrade -y
date && timedatectl        # clock correct, NTP active
```

If the upgrade pulled a new kernel or `raspberrypi-firmware`, **reboot before continuing** — per the gotchas list, cold boots expose latent problems, and you want that now rather than after Pi-hole is layered on top.

Grab the MAC while you're here; the UniFi fixed IP needs it:

```
ip link show eth0 | grep ether
```

### 1.5 Static IP

This runs on the Pi itself. Current Pi OS uses NetworkManager — `dhcpcd.conf` no longer applies.

```
**Use `9.9.9.11` here, not `127.0.0.1`.** *(Corrected 2026-09-20.)* Nothing listens on port 53 until Unbound lands in 1.7, so setting `127.0.0.1` at this point leaves the Pi with no resolver and **`apt install unbound` in 1.7 fails**. Point at Quad9 for the build and flip to `127.0.0.1` only after Pi-hole is verified in 1.10.

```
sudo nmcli con show        # confirm the connection name
sudo nmcli con mod "Wired connection 1" ipv4.method manual \
  ipv4.addresses 192.168.1.129/24 ipv4.gateway 192.168.1.1 ipv4.dns "9.9.9.11"
sudo nmcli con up "Wired connection 1"
```

Your SSH session will drop. Reconnect to 192.168.1.129.

**Expect a host key warning** (`REMOTE HOST IDENTIFICATION HAS CHANGED`) — .129 previously belonged to the other node. Clear it with `ssh-keygen -R 192.168.1.129`.

Then prove the resolver works before going further:

```
ping -c 2 deb.debian.org
```

Keep the matching UniFi fixed IP in place so DHCP never hands .129 elsewhere.

### 1.6 Configure the RTC

```
sudo raspi-config          # Interface Options → I2C → enable
echo "dtoverlay=i2c-rtc,ds3231" | sudo tee -a /boot/firmware/config.txt
sudo apt -y remove fake-hwclock && sudo update-rc.d -f fake-hwclock remove
sudo reboot
# after reboot:
sudo hwclock -r            # should print the current time
```

### 1.7 Unbound

`dig` is **not installed** on Lite and is needed here and in 1.10 — install it alongside Unbound:

```
sudo apt install unbound bind9-dnsutils -y
unbound -V | head -1
```

**Checking the CVE status** *(corrected 2026-09-20)*: `apt changelog unbound` returns a 404 for recently-updated security packages. Use the local copy instead:

```
zcat /usr/share/doc/unbound/changelog.Debian.gz | head -40
apt-cache policy unbound
```

The original "expect 1.22.x, Debian backports" guidance is **inverted on trixie**. Debian explicitly chose *not* to backport — the changelog states the upstream changes were too tangled — and shipped current upstream instead. As built: `1.26.1-0+deb13u1` from `trixie-security`, carrying the September 2026 fixes including CVE-2026-81642 (CRITICAL, heap overflow / possible RCE on DNSKEY digest). `trixie/main` still offers the older 1.22.0; confirm via `apt-cache policy` that you are on the security-repo build.

Create `/etc/unbound/unbound.conf.d/pi-hole.conf` (port 5335, `do-ip6: no`, `prefetch: yes`):

```
sudo tee /etc/unbound/unbound.conf.d/pi-hole.conf > /dev/null <<'EOF'
server:
    verbosity: 0
    interface: 127.0.0.1
    port: 5335
    do-ip4: yes
    do-udp: yes
    do-tcp: yes
    do-ip6: no
    prefer-ip6: no
    harden-glue: yes
    harden-dnssec-stripped: yes
    use-caps-for-id: no
    edns-buffer-size: 1232
    prefetch: yes
    num-threads: 1
    so-rcvbuf: 1m
    private-address: 192.168.0.0/16
    private-address: 169.254.0.0/16
    private-address: 172.16.0.0/12
    private-address: 10.0.0.0/8
    private-address: fd00::/8
    private-address: fe80::/10
EOF
unbound-checkconf
```

Then:

```
sudo systemctl restart unbound
dig +short google.com @127.0.0.1 -p 5335
```

**Do not continue until that returns an address.**

### 1.8 Automatic security updates

```
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

`dpkg-reconfigure` can exit silently without prompting. Verify it actually took:

```
cat /etc/apt/apt.conf.d/20auto-upgrades   # both lines should be "1"
```

This is the real fix for the Unbound CVEs. Manual patch-watching doesn't survive a busy month.

### 1.8b Hardware watchdog

Both Pis have a watchdog built into the SoC. Turning it on costs nothing and covers the failure that started all this — pihole1 hung while still answering pings, so nothing noticed.

First confirm the hardware watchdog device exists — without it the systemd setting is a silent no-op:

```
ls -l /dev/watchdog*
```

Use a **drop-in** rather than editing `/etc/systemd/system.conf` directly *(corrected 2026-09-20)*. Same effect, but it survives package upgrades instead of triggering a modified-conffile prompt on every systemd update — which matters once unattended-upgrades is running unsupervised:

```
sudo mkdir -p /etc/systemd/system.conf.d
sudo tee /etc/systemd/system.conf.d/watchdog.conf > /dev/null <<'EOF'
[Manager]
RuntimeWatchdogSec=15
RebootWatchdogSec=2min
EOF
sudo systemctl daemon-reexec
systemctl show | grep -i watchdog     # want RuntimeWatchdogUSec=15s
```

A live `WatchdogLastPingTimestamp` in that output is the real confirmation — it means systemd is actively petting the device, not merely holding the setting.

If the kernel stops responding for 15 seconds, the Pi resets itself. It won't catch a broken-but-running FTL — that's what the keepalived health check in Phase 3 is for — but it does catch a genuine hang.

### 1.9 Pi-hole

```
curl -sSL https://install.pi-hole.net | bash
```

Choose Custom upstream, enter `127.0.0.1#5335`, **once** — the duplicate entry was on your cleanup list.

Then the two flags that bit you before:

```
sudo pihole-FTL --config dns.dnssec false        # Unbound already validates
sudo pihole-FTL --config dns.listeningMode ALL   # serves the IoT VLAN
sudo systemctl restart pihole-FTL
```

Optionally trim database retention to cut writes:

```
sudo pihole-FTL --config database.maxDBdays 30
```

### 1.10 Verify

```
vcgencmd get_throttled                      # want 0x0 — if not, plug in the 12V brick
dig +short google.com @192.168.1.129        # from your Mac
```

Then the same dig from a device on the IoT VLAN. If the LAN works but the VLAN doesn't, it's a UniFi firewall rule, not Pi-hole: the IoT VLAN needs to reach .129 and .2 on port 53.

**Stopping point.** If you want blocking back now, point UniFi DHCP at 192.168.1.129 and pick this up another day.

### Phase 1 as-built — 2026-09-20

Completed and verified. Deviations from the plan as written:

| Step | What actually happened |
| --- | --- |
| 1.1 | Pi 4 would not boot its existing microSD (suspected corrupt). Used the Imager bootloader-utility route instead — flashed **Bootloader → USB Boot** to a spare card, booted once, removed it. EEPROM boot order set; no OS required. |
| 1.2 | **Skipped** — RTC modules not yet ordered. |
| 1.3 | Kingston A400 240GB. Enumerated over the UGREEN cable on Mac bus power, **no 12V brick**. Confirmed target with `diskutil list external physical`. |
| 1.4 | Ethernet was not plugged in on first boot — the Lite image has no Wi-Fi, so the Pi was simply absent from the network. This also explains the `pihole1.local` failure: avahi *is* running on this image, there was just no link. Upgrade pulled only 2 packages, no kernel, so no reboot was needed. |
| 1.5 | Applied with `ipv4.dns "9.9.9.11"` — see the correction above. Host key warning on reconnect, cleared with `ssh-keygen -R`. |
| 1.6 | **Skipped** — no RTC. |
| 1.7 | Unbound `1.26.1-0+deb13u1` from `trixie-security`. `dig` had to be installed separately. |
| 1.9 | Installer completed cleanly on Debian 13 — **no unsupported-OS warning**, despite trixie being newer than this runbook assumed. |
| 1.10 | `vcgencmd get_throttled` → `0x0`. Main LAN resolution and blocking both confirmed. |

**Environment as built:** Raspberry Pi OS Lite 64-bit on **Debian 13 (trixie)**, `multi-user.target`, user `pihole1admin`, hostname `pihole1`, MAC `dc:a6:32:19:7f:d3`, static `192.168.1.129`.

**IoT VLAN verification — passed, after a false alarm worth recording.**

The first IoT test appeared to fail and looked convincingly like a UniFi firewall block. It was not. Sequence:

| Time | From | Test | Result |
| --- | --- | --- | --- |
| 23:24 | IoT `192.168.16.188` | `dig @192.168.1.129` (UDP) | **timed out** |
| 23:27 | IoT | `ping 192.168.1.129` | succeeded, `ttl=63` |
| 23:41 | IoT `192.168.16.192` | `nc -vz 192.168.1.129 80` | succeeded |
| 23:41 | IoT | `dig @1.1.1.1` (UDP 53) | succeeded |
| 23:41 | IoT | `dig +tcp @192.168.1.129` | succeeded |
| 23:45 | IoT | `dig @192.168.1.129` (UDP) | **`0.0.0.0` — passes** |

**Cause:** `listeningMode ALL` had been written to the config but FTL had not yet restarted. Until it does, FTL runs in `LOCAL` mode and **silently drops queries from off-subnet clients** — no refusal, no log entry the client can see, just a timeout. From the client side that is indistinguishable from a VLAN firewall block.

**What made it misleading:** ICMP, TCP/22 and TCP/80 all reached `.129` normally, so the evidence looked like "port 53 specifically is blocked," which is a very plausible-sounding firewall rule. The `dig @1.1.1.1` control test is what broke the theory — it proved UDP 53 left the IoT VLAN fine.

**Lesson for Phase 2:** restart FTL and confirm it is listening before running any cross-VLAN test.

```
sudo systemctl restart pihole-FTL
sudo ss -tulnp | grep -E ':53\s'     # want 0.0.0.0:53 on both udp and tcp
```

*(Corrected 2026-09-21 — `grep ':53'` as a plain substring also matches Unbound's `:5335` and avahi's `:5353`, burying the real port-53 lines in noise and producing a false "nothing's listening" read. The `\s` anchor after `53` excludes those.)*

No UniFi firewall change was needed. Inter-VLAN DNS to the Pi-hole nodes works as-is, so the Phase 4 cutover prerequisite is already satisfied — though it should be re-verified against the **VIP** (192.168.1.2) once keepalived is up in Phase 3.

**Ground rule held:** UniFi DHCP remained on 9.9.9.11 (Quad9) throughout. The runbook's optional "point DHCP at .129 now" stopping point was **deliberately declined** — with IoT unable to reach .129 on port 53, an early cutover would have taken the IoT VLAN's DNS offline.

## Phase 2 — Pi 3B + microSD becomes pihole2

Same build as Phase 1 with three differences. Everything else is identical, so work from the Phase 1 steps.

|  | Phase 1 (Pi 4) | Phase 2 (Pi 3B) |
| --- | --- | --- |
| Hostname | pihole1 | **pihole2** |
| Static IP | 192.168.1.129 | **192.168.1.13** |
| Boot media | SSD via USB | **SanDisk Max Endurance microSD** |

Skip steps 1.1 (no USB boot) and the `vcgencmd` check in 1.10. Run everything else in order: RTC install, flash, patch, static IP, RTC config, Unbound, unattended-upgrades, watchdog, Pi-hole, the two config flags, verify.

### Notes specific to this node

- **Flash with Raspberry Pi OS Lite (64-bit)** — the Pi 3B supports it and Lite keeps the 1GB of RAM comfortable.
- **There is no existing UniFi reservation for .13** *(corrected 2026-09-21 — the original text assumed one existed.)* The Pi 3B has aged out of UniFi's client list, so its MAC cannot be looked up in advance, and `.13` sits inside the DHCP pool (`192.168.1.6 – 192.168.1.254`) unprotected. Boot the Pi on DHCP first, read the MAC with `ip link show eth0`, create the fixed IP in UniFi, and only **then** set the on-device static.
- **The RTC matters less here** now that this is the backup node, but install it anyway while the Pi is open.

### Verify before moving on

```
dig +short google.com @192.168.1.13
```

Both nodes should now answer independently, each with its own Unbound. Neither is serving the network yet.

### Phase 2 as-built — 2026-09-21

Completed and verified. Deviations from the plan as written:

| Step | What actually happened |
| --- | --- |
| 1.1 | Skipped — no USB boot on a Pi 3B. |
| 1.2 | Skipped — RTC modules still not ordered. |
| 1.3 | SanDisk Max Endurance microSD, hostname `pihole2`, user `pihole2admin`. |
| 1.4 | `apt full-upgrade` pulled no kernel/firmware update — no reboot needed. MAC `b8:27:eb:8f:97:03`. |
| — | **UniFi reservation confirmed absent** as predicted by the 2026-09-21 correction above — the Pi 3B had aged out of the client list. Fixed IP for `.13` created from the MAC read in 1.4, before any on-device static was set. |
| 1.5 | Applied with `ipv4.dns "9.9.9.11"`. Host key warning on reconnect to `.13` (this MAC previously held `.129` in the old topology, and `.13` itself was the Pi 4's old address before the swap) — cleared with `ssh-keygen -R`, run on the Mac, not over the Pi's own SSH session. |
| 1.6 | Skipped — no RTC. |
| 1.7 | Unbound `1.26.1-0+deb13u1` from `trixie-security` — matches pihole1 exactly. |
| 1.8, 1.8b | unattended-upgrades confirmed (`20auto-upgrades` both lines `"1"`). Watchdog confirmed live — `RuntimeWatchdogUSec=15s` and a current `WatchdogLastPingTimestamp`. |
| 1.9 | Installer completed cleanly, same as pihole1. |
| 1.10 | `dns.dnssec false`, `dns.listeningMode ALL`, FTL restarted, `ss -tulnp` confirmed `pihole-FTL` bound on `udp 0.0.0.0:53`, `udp *:53`, `tcp 0.0.0.0:53`, `tcp [::]:53` — clean on the first check, no repeat of the Phase 1 false alarm. (The plain `grep ':53'` this runbook used to suggest here briefly hid those lines behind Unbound's `:5335` and avahi's `:5353` — see the correction above.) `vcgencmd get_throttled` was skipped deliberately: it checks USB-boot undervoltage, which doesn't apply to a Pi 3B on microSD. |

**Environment as built:** Raspberry Pi OS Lite 64-bit on Debian 13 (trixie), user `pihole2admin`, hostname `pihole2` (confirmed via `hostnamectl`: `Static hostname: pihole2`), MAC `b8:27:eb:8f:97:03`, static `192.168.1.13`.

**Side issue, resolved:** After the static IP was set, UniFi's client list displayed this device's **name** as `pihole1`, not `pihole2` — alarming at a glance, but `hostnamectl` on the Pi confirmed the real system hostname was correct throughout. Working theory: this exact Pi 3B was the old primary under the v1 setup and carried a manual `pihole1` alias in UniFi from before the rebuild, which resurfaced with the new DHCP lease rather than being overwritten. Fix is cosmetic — rename the client's display name in UniFi — and does not affect DNS, the fixed-IP binding, or anything else already verified.

**Verification:** `dig +short google.com @192.168.1.13` succeeded both from the Pi itself and from the Mac (off-node, matching the runbook's specified check). Cross-VLAN (IoT) verification for pihole2 individually was not run — Phase 1's IoT test already confirmed inter-VLAN reachability to this subnet in general, and the real cross-VLAN check that matters is against the **VIP** once keepalived is up in Phase 3, per the note already on that Phase 1 result.

**Ground rule held:** UniFi DHCP remained on 9.9.9.11 (Quad9) throughout.

## Phase 3 — keepalived, the VIP, and the health check

### 3.1 Install on both nodes

```
sudo apt install keepalived -y
```

### 3.2 The health check script

This is the gap you identified: keepalived watches whether a node is *alive*, not whether DNS *works*. A broken-but-alive FTL never triggered failover. Put this on **both** nodes at `/usr/local/bin/dns_check.sh`:

```
#!/bin/bash
# dns_check.sh — keepalived health check.
# Exits 0 only if the local pihole-FTL returns an IPv4 answer for pi.hole.
answer=$(dig +short +time=2 +tries=1 @127.0.0.1 pi.hole A) || exit 1
echo "$answer" | grep -qE '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' || exit 1
exit 0
```

*(Corrected 2026-09-23. The original check was `dig ... | grep -q .`, and it **passed with FTL stopped**. dig on trixie prints its failures to stdout even with `+short` (`;; communications error to 127.0.0.1#53: connection refused`, `;; no servers could be reached`, exit 9), so "any output" matched the error text. The check now needs both a zero exit from dig **and** an answer that looks like an IPv4 address.)*

```
sudo chmod 755 /usr/local/bin/dns_check.sh
ls -l /usr/local/bin/dns_check.sh          # root root, -rwxr-xr-x
/usr/local/bin/dns_check.sh; echo $?       # expect 0
```

**Also test that it fails.** Run this on a node that isn't serving the network. A check that has never been seen failing hasn't been tested:

```
sudo systemctl stop pihole-FTL; /usr/local/bin/dns_check.sh; echo $?; sudo systemctl start pihole-FTL   # expect 1
```

### 3.3 keepalived config

Write the full config to `/etc/keepalived/keepalived.conf` on each node. It looks like this on pihole1:

```
global_defs {
    router_id pihole1
    enable_script_security
    script_user root
}

vrrp_script chk_dns {
    script "/usr/local/bin/dns_check.sh"
    interval 5
    timeout 3
    fall 3
    rise 2
    weight -60
}

vrrp_instance PIHOLE {
    state MASTER
    interface eth0
    virtual_router_id 53
    priority 150
    advert_int 1
    unicast_src_ip 192.168.1.129
    unicast_peer {
        192.168.1.13
    }
    authentication {
        auth_type PASS
        auth_pass CHANGEME
    }
    virtual_ipaddress {
        192.168.1.2/24
    }
    track_script {
        chk_dns
    }
}
```

These values differ per node. Everything else is identical:

|  | pihole1 (Pi 4) | pihole2 (Pi 3B) |
| --- | --- | --- |
| router_id | pihole1 | pihole2 |
| state | MASTER | BACKUP |
| priority | 150 | 100 |
| unicast_src_ip | 192.168.1.129 | 192.168.1.13 |
| unicast_peer | 192.168.1.13 | 192.168.1.129 |

`enable_script_security` and `script_user root` in `global_defs` are required. Without those two lines keepalived silently refuses to run the script — a quiet failure that looks like the check is passing.

**Auth pass:** generate it on the Mac with `openssl rand -hex 4` (8 characters, the PASS maximum). Put it into both configs with `sudo sed -i 's/CHANGEME/<value>/' /etc/keepalived/keepalived.conf`. It is never committed here.

Use **unicast** peers rather than multicast — more reliable across UniFi switches.

*(Corrected 2026-09-23: **weight is `-60`, not `-50`.** With `-50`, a pihole1 with failed DNS drops from 150 to 100, which ties pihole2's 100. VRRP breaks a tie by the higher primary IP, and `.129` beats `.13`, so pihole1 would have **kept the VIP with broken DNS**. `-60` drops it to 90. The rule is that primary priority minus weight must be strictly less than the backup's priority. Confirmed in the 3.4 log: `Changing effective priority from 150 to 90` → `received advert from 192.168.1.13 with higher priority 100, ours 90` → `Entering BACKUP STATE`.)*

*(Corrected 2026-09-23: **no notify script.** The original plan reused the old notify script that restarts pihole-FTL on the MASTER transition. That script exists only on the set-aside SD cards. It turned out to be unnecessary: with `listeningMode ALL`, FTL binds `0.0.0.0:53` and answers on the VIP the moment keepalived adds it. Step 3.4 proved this in both directions, including failback, where FTL started **before** the VIP existed on the node.)*

Check the config before starting it:

```
sudo keepalived --config-test; echo $?     # expect 0
```

Then start pihole1 first, so it takes the VIP from the start:

```
sudo systemctl enable --now keepalived
ip -4 addr show eth0 | grep inet                             # pihole1: .129 and .2; pihole2: .13 only
sudo journalctl -u keepalived -b --no-pager | tail -15       # want "VRRP_Script(chk_dns) succeeded"
```

The `chk_dns succeeded` line is the proof that script security is set up right. The Debian package enables the service on install, so once a config exists **keepalived starts on its own at boot**. The `NOTICE: setting config option max_auto_priority...` line is a harmless performance tip.

### 3.4 Test failover both directions

Baseline:

```
dig +short google.com @192.168.1.2          # VIP answers
ip -4 addr show eth0 | grep inet            # on pihole1, .2 present
```

**This test is the whole point of the phase** — it's what proves the health check works, and it's the thing that was silently broken before. Run the full cycle hands-off, **from an IoT VLAN client**, not only the main LAN. IoT traffic reaches the VIP through the UniFi gateway, so it also proves the gateway follows the VIP when it moves.

Tab A, on the IoT client (runs about 2 minutes, then stops):

```
for i in {1..50}; do printf '%s ' "$(date +%T)"; dig +short +time=1 +tries=1 google.com @192.168.1.2 | head -1; sleep 2; done
```

Tab B, on pihole1, started right after Tab A:

```
echo "stop  $(date +%T)"; sudo systemctl stop pihole-FTL; sleep 45; sudo systemctl start pihole-FTL; echo "start $(date +%T)"
```

**Pass:** one gap of about 10–16 seconds just after `stop` (3 failed checks at 5-second intervals), then answers all the way through, including after `start`. The failback costs no gap at all, because pihole2 keeps answering until pihole1 takes over. Afterwards, check with `journalctl -u keepalived` on pihole1 that `Entering MASTER STATE` falls inside the Tab A window. Otherwise the failback wasn't actually observed.

The automated Tab B command replaces doing stop/start by hand. Forgetting the `start` during a manual run produced a confusing double transition in the log.

### Phase 3 as-built — 2026-09-23

Completed and verified. Deviations from the plan as written:

| Step | What actually happened |
| --- | --- |
| 3.1 | keepalived **v2.3.3** (03/30,2025) on both nodes. `dig` already present from Phase 1/2. |
| 3.2 | The original script **passed with FTL stopped** (`exit=0`). Caught only by the negative test, run on pihole2. Cause: dig's error text on stdout. Rewritten as above; after the fix, pihole2 with FTL stopped gave `exit=1`. |
| 3.3 | Weight corrected to `-60` before it was deployed. `virtual_router_id 53`, VIP `192.168.1.2/24`, no notify script. `--config-test` passed on both. |
| — | **Nodes moved from the bench to the rack before keepalived was first started.** A clean `poweroff` on pihole2 initially didn't happen (the command never reached the node — `systemctl is-system-running` still said `running`). Re-sent with `ssh -t pihole2admin@192.168.1.13 'sudo poweroff'`. Both nodes cold-booted in the rack. Static IP, Unbound, FTL and keepalived all came up unaided, with pihole1 MASTER holding `.2` and pihole2 BACKUP. |
| 3.4 | Main LAN: failover and failback both clean. pihole1 log: `150 → 90`, BACKUP about 13 seconds after the first failed check. `90 → 150`, MASTER 3 seconds after recovery. IoT VLAN (hands-off cycle, 10:02–10:04): one 12-second gap on failover, **zero gap on failback**. |

**Unexplained, not reproduced:** the very first IoT → VIP queries, a few minutes after a manual failback at 09:49, **timed out twice**, about 2 minutes apart. Meanwhile `dig @192.168.1.129` from the same client worked. The first `ping 192.168.1.2` afterwards took 74 ms (a fresh ARP), and from then on the VIP answered over UDP and TCP. The leading theory was a stale ARP entry for `.2` on the UniFi gateway, still pointing at pihole2. Two further full cycles watched from IoT showed no such delay, so it's recorded rather than fixed. If it recurs, the likely fix is `garp_master_refresh` in the keepalived instance, which re-announces the VIP periodically. **Watch for it during Phase 4.3.**

**Cross-VLAN prerequisite for Phase 4:** confirmed against the VIP. IoT clients resolve through `192.168.1.2` over UDP and TCP.

**RTC reminder, observed:** after the cold boot, both nodes' journal timestamps started from the time saved at shutdown (about 9 minutes behind) until NTP corrected them. That's harmless at this size; after a long outage it's the DNSSEC failure mode the DS3231 fixes.

**Ground rule held:** UniFi DHCP remained on 9.9.9.11 (Quad9) throughout. The VIP was only ever tested directly.

## Phase 4 — Nebula Sync and cutover

### 4.1 Nebula Sync

One direction only: **pihole1 (Pi 4) → pihole2 (Pi 3B)**. Configure the primary as pihole1 at 192.168.1.129 and the replica as pihole2 at 192.168.1.13.

This direction is now the opposite of the old setup, since the roles swapped. All future Pi-hole config changes get made on the Pi 4.

After the first sync run, confirm it propagated:

```
# on pihole2
pihole-FTL --config dns.dnssec        # expect false
pihole-FTL --config dns.listeningMode # expect ALL
```

### 4.2 Cutover

In UniFi, set DHCP DNS back to **192.168.1.2** on **both** the main LAN and the IoT VLAN. Then renew a client on each network and confirm resolution:

```
nslookup google.com
nslookup doubleclick.net      # should return 0.0.0.0 — blocking is live
```

### 4.3 Post-cutover watch

Over the next few minutes, check the Pi-hole query log for the five IoT clients that were retry-storming (192.168.16.25, .27, .28, .29, .164). If the storm resumes, note it but don't chase it now — it's a separate thread.

One last failover test with real traffic flowing is worth doing: stop FTL on pihole1 and confirm the house stays online.

## After the rebuild

### Do these while you're still in it

- **Teleporter backup on both nodes** — `pihole -a -t`, then copy the files off the Pis
- **Clone the SSD and the pihole2 card** to image files on the Mac. This is the single highest-value safeguard: recovery becomes a 10-minute re-flash instead of a rebuild.
- **Update the dashboards** — homelab-status `index.html` and the life-dashboard entry, reflecting the role swap

### Check back in a week

```
apt changelog unbound | grep -i -m5 "CVE-2026"
```

If the September fixes still haven't landed via apt, that's worth a look. unattended-upgrades should have taken care of it.

### Still open after this

- **NUT / UPS clean shutdown** — captured in `ideas.md`, gated on whether the UPS has a USB data port
- **IoT retry storm** — five clients, revisit once DNS has been stable a few days
- **IPv6 VIP** — deferred from before, still deferred
- **Deadbox card** — the second Max Endurance card is for that build, whenever you get back to it

## Reference — gotchas, collected

Everything that has cost time before, in one place.

**DNS and DNSSEC**

- `dns.dnssec` must be `false` in pihole-FTL when Unbound validates upstream. Double validation causes SERVFAIL on cold boot.
- `dns.listeningMode ALL` is required to serve more than one VLAN. Pi-hole v6 defaults to LOCAL.
- Only one `127.0.0.1#5335` entry in `dns.upstreams`. Duplicates have crept in before.
- After a WAN outage, `sudo systemctl restart unbound` clears cached upstream failures.
- `dns.listeningMode ALL` does not take effect until **pihole-FTL restarts**. Before that, FTL silently drops off-subnet queries — no error, just a timeout — which looks exactly like a VLAN firewall block. Always restart FTL and confirm `0.0.0.0:53` in `ss -tulnp` before concluding the network is at fault.

**Addressing and keepalived**

- On-device static beats a DHCP reservation for anything keepalived depends on. The Pi is briefly address-less during early boot otherwise.
- Current Pi OS uses NetworkManager and `nmcli` — not `dhcpcd.conf`.
- keepalived needs `enable_script_security` and `script_user root` or it won't run the health check, silently.
- A health-check weight must drop the primary **strictly below** the backup. A tie goes to the higher IP, and `.129` beats `.13`, so a tie means no failover.
- `dig` prints failures (`;; communications error`, `;; no servers could be reached`) to **stdout**, even with `+short`. Never test "did dig print anything". Check its exit code and the shape of the answer. And always watch a health check fail at least once before trusting it.

**Hardware**

- Pi 4 USB ports supply about 1.2A total. If the SSD misbehaves, `vcgencmd get_throttled` tells you whether voltage is the problem, and the UGREEN brick is the fix.
- Pi 3B has no battery-backed clock. Outages longer than ~15 minutes freeze the clock and break DNSSEC on boot — the DS3231 fixes this permanently.
- The UGREEN cable sleeps after a few idle minutes. Not an issue for a boot drive, but it's the first suspect if the Pi freezes after being quiet.

**Diagnostics**

- Heavy query rates can fill FTL capacity and make `dig +short` return empty, which looks like a resolver failure but isn't.
- Ping working while SSH is refused usually means a hung system, often a failing boot device.
- Cold boots expose latent config problems that a running system hides. If something changes, reboot and confirm it survives.
