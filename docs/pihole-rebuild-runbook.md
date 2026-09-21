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

**Finding the address:** `pihole1.local` will not resolve. Raspberry Pi OS Lite does not run `avahi-daemon`, so mDNS is unavailable. Get the IP from the UniFi client list instead.

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
| 1.4 | Ethernet was not plugged in on first boot — the Lite image has no Wi-Fi, so the Pi was simply absent from the network. `pihole1.local` never resolves (no avahi on Lite). Upgrade pulled only 2 packages, no kernel, so no reboot was needed. |
| 1.5 | Applied with `ipv4.dns "9.9.9.11"` — see the correction above. Host key warning on reconnect, cleared with `ssh-keygen -R`. |
| 1.6 | **Skipped** — no RTC. |
| 1.7 | Unbound `1.26.1-0+deb13u1` from `trixie-security`. `dig` had to be installed separately. |
| 1.9 | Installer completed cleanly on Debian 13 — **no unsupported-OS warning**, despite trixie being newer than this runbook assumed. |
| 1.10 | `vcgencmd get_throttled` → `0x0`. Main LAN resolution and blocking both confirmed. |

**Environment as built:** Raspberry Pi OS Lite 64-bit on **Debian 13 (trixie)**, `multi-user.target`, user `pihole1admin`, hostname `pihole1`, MAC `dc:a6:32:19:7f:d3`, static `192.168.1.129`.

**Open item carried into the next session — IoT VLAN cannot reach DNS on .129.**

From a client at `192.168.16.188`:
- `ping 192.168.1.129` → **succeeds**, `ttl=63` (routed via the gateway)
- `dig @192.168.1.129` → **times out**

So this is *not* blanket inter-VLAN isolation, and not a Pi-hole misconfiguration — `listeningMode` is `ALL` and the main LAN resolves fine. Something blocks **port 53 specifically** while permitting ICMP. Candidates: a UniFi DNS-enforcement/redirect feature on the IoT network, or a zone policy scoped to DNS.

**This must be resolved before the Phase 4 cutover** — at cutover the IoT VLAN resolves against the VIP, and if port 53 is blocked the whole VLAN loses DNS. Note the old setup had IoT resolving against `.2` successfully, so whatever permits that may be scoped to the VIP alone.

Next diagnostic steps (untried):
```
# on the Pi — confirm FTL listens on all interfaces
sudo ss -tulnp | grep ':53'          # expect 0.0.0.0:53

# from an IoT client — control test on a non-DNS port
nc -vz 192.168.1.129 80              # if this connects but 53 does not, the block is DNS-specific
dig +tcp +short google.com @192.168.1.129
```

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
- **Check the UniFi reservation for .13 points at the Pi 3B's MAC** before setting the static IP.
- **The RTC matters less here** now that this is the backup node, but install it anyway while the Pi is open.

### Verify before moving on

```
dig +short google.com @192.168.1.13
```

Both nodes should now answer independently, each with its own Unbound. Neither is serving the network yet.

## Phase 3 — keepalived, the VIP, and the health check

### 3.1 Install on both nodes

```
sudo apt install keepalived -y
```

### 3.2 The health check script

This is the gap you identified: keepalived watches whether a node is *alive*, not whether DNS *works*. A broken-but-alive FTL never triggered failover. Put this on **both** nodes at `/usr/local/bin/dns_check.sh`:

```
#!/bin/bash
dig +short +time=2 +tries=1 @127.0.0.1 pi.hole | grep -q . || exit 1
exit 0
```

```
sudo chmod +x /usr/local/bin/dns_check.sh
/usr/local/bin/dns_check.sh; echo $?     # expect 0
```

### 3.3 keepalived config

In the global block on both nodes:

```
global_defs {
    enable_script_security
    script_user root
}
```

Without those two lines keepalived silently refuses to run the script — a quiet failure that looks like the check is passing.

The tracking block, on both nodes:

```
vrrp_script chk_dns {
    script "/usr/local/bin/dns_check.sh"
    interval 5
    timeout 3
    fall 3
    rise 2
    weight -50
}
```

The instance, with these values differing per node:

|  | pihole1 (Pi 4) | pihole2 (Pi 3B) |
| --- | --- | --- |
| state | MASTER | BACKUP |
| priority | 150 | 100 |
| unicast_src_ip | 192.168.1.129 | 192.168.1.13 |
| unicast_peer | 192.168.1.13 | 192.168.1.129 |

Shared across both: same `virtual_router_id`, same auth pass, `virtual_ipaddress 192.168.1.2`, `track_script { chk_dns }`, and the existing notify script that restarts pihole-FTL on MASTER transition.

Use **unicast** peers rather than multicast — more reliable across UniFi switches.

### 3.4 Test failover both directions

```
dig +short google.com @192.168.1.2          # VIP answers
ip addr show | grep 192.168.1.2             # on pihole1, VIP present
```

Then force a failover:

```
sudo systemctl stop pihole-FTL              # on pihole1
# wait ~20 seconds, then from your Mac:
dig +short google.com @192.168.1.2          # should still answer, via pihole2
```

Restart FTL on pihole1 and confirm the VIP comes back. **This test is the whole point of the phase** — it's what proves the health check works, and it's the thing that was silently broken before.

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

**Addressing and keepalived**

- On-device static beats a DHCP reservation for anything keepalived depends on. The Pi is briefly address-less during early boot otherwise.
- Current Pi OS uses NetworkManager and `nmcli` — not `dhcpcd.conf`.
- keepalived needs `enable_script_security` and `script_user root` or it won't run the health check, silently.

**Hardware**

- Pi 4 USB ports supply about 1.2A total. If the SSD misbehaves, `vcgencmd get_throttled` tells you whether voltage is the problem, and the UGREEN brick is the fix.
- Pi 3B has no battery-backed clock. Outages longer than ~15 minutes freeze the clock and break DNSSEC on boot — the DS3231 fixes this permanently.
- The UGREEN cable sleeps after a few idle minutes. Not an issue for a boot drive, but it's the first suspect if the Pi freezes after being quiet.

**Diagnostics**

- Heavy query rates can fill FTL capacity and make `dig +short` return empty, which looks like a resolver failure but isn't.
- Ping working while SSH is refused usually means a hung system, often a failing boot device.
- Cold boots expose latent config problems that a running system hides. If something changes, reboot and confirm it survives.
