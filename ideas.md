# Ideas Log

A running capture of ideas, experiments, and things worth returning to.
Updated collaboratively with Claude. Add anything — half-formed is fine.

---

<!-- IDEAS GO HERE -->

## Pi-hole Alerts via ntfy
*Added: 2026-09-23*

Get a push notification when the Pi-hole pair needs attention, instead of finding out when something stops resolving. Failover hides a dead node by design, so without alerts pihole1 could be down for weeks with nobody noticing.

**Three sources, one ntfy topic:**
1. **Nebula Sync failure webhook.** Two lines in `/etc/nebula-sync/nebula-sync.env` on pihole1 (`WEBHOOK_SYNC_FAILURE_URL` / `_BODY`). Fires when a sync fails.
2. **keepalived notify script.** Pings on any MASTER/BACKUP/FAULT transition, which is the "a node went down" alert. It notifies only; the old v1 notify script that restarted FTL is not coming back (Phase 3 proved it unnecessary).
3. **Daily check on each node,** via a systemd timer. It pings **only when something is wrong**: disk above 80%, `/var/run/reboot-required` present past the scheduled reboot, a Pi-hole update available (`pihole -v` vs latest), or `vcgencmd get_throttled` non-zero on the Pi 4.

**Security:** on public ntfy.sh the topic name works as a password. Keep it in root-only files on the nodes (same pattern as the Nebula Sync env file) and never in this repo or on the dashboard.

**Testing:** make each alert fire once on purpose. Break a sync password, stop FTL on pihole1, and fake a full-disk threshold. The Phase 3 lesson was that a check you haven't watched fail isn't trusted.

**Status:** Designed, not built. A short session of its own. Ties in with the Spotify project's ntfy setup.

---

## IoT VLAN Reply Loss
*Added: 2026-09-23*

During the Pi-hole Phase 4 cutover, an IoT-VLAN laptop lost roughly **1 in 10 DNS replies**, to the Pi-hole VIP, to pihole1 directly **and to 1.1.1.1** alike. Packet capture on pihole1 showed every lost query arriving and being answered within ~1.5 ms, so the replies are lost somewhere between the UniFi gateway and the client. It isn't the Pi-holes. Details are in the runbook's Phase 4 as-built.

**Caveat first:** the laptop was dual-homed during the test (Wi-Fi on IoT plus a wired `en5` on the main LAN). Retest on Wi-Fi only before believing the number.

**If it holds up:** check IoT SSID settings (2.4 GHz only? minimum data rates, band steering, DTIM or power-save related options), the AP's channel utilisation, and whether a wired IoT client shows the same loss.

**Possible link:** the five IoT clients that were retry-storming (192.168.16.25, .27, .28, .29, .164). Devices that lose replies retry.

**Status:** Observation. Not blocking; real clients retry past a single lost packet.

---

## Untrusted Device VLAN — Isolate Third-Party Telemetry
*Added: 2026-09-19*

Put any device running vendor-managed agents (device management, endpoint security, telemetry) on its own VLAN so those agents can't see or scan the rest of the home network, and route its DNS through Pi-hole for both filtering and visibility. Right now anything that enumerates the LAN gets a full inventory of the homelab, the Pis, the smart home devices, and every family machine.

**Goal state:** The isolated VLAN reaches the internet and the Pi-hole VIP. It cannot initiate connections to the main LAN or IoT VLAN. Nothing on the home network needs to reach it, so the rules can be one-way and strict — simpler than the IoT VLAN case, which needs Home Assistant to reach back.

**How to get a locked-down device onto it (the actual friction point):** A managed device usually can't be told to tag a VLAN itself. Two options that need zero changes on the device:
- **Wireless:** create a dedicated SSID in UniFi mapped to the isolated VLAN. Join it like any other network. Easiest path.
- **Wired:** set the untagged/native VLAN on the specific switch port the device docks into.

**DNS:** The isolated VLAN points at the Pi-hole VIP (192.168.1.2). Same pattern already in place for the IoT VLAN, so the nodes are used to serving multiple VLANs. Two payoffs: telemetry gets filtered, and the query log becomes a live record of what the agents actually contact.

**This requires an allow rule, not just a block rule.** "Isolated VLAN cannot reach the main LAN" would also block DNS to the VIP. Rule order needs to be: allow isolated VLAN → 192.168.1.2 on UDP/TCP 53, then block isolated VLAN → main VLAN and IoT VLAN. Allow rule above the block.

**Blocklist scoping:** Give the device its own Pi-hole client group with a lighter blocklist. SSO portals and SaaS apps lean on domains that aggressive lists sometimes catch, and a false positive on a machine someone depends on daily costs a whole day, not a nuisance. Start permissive, tighten by watching the log. Make group changes on the primary (192.168.1.129) — Nebula Sync is one-directional.

**VPN caveat:** When a VPN client is up, it will likely push its own DNS and bypass Pi-hole for the tunnel's duration. Expect gaps in the log, not breakage. If the network-wide port 53 block idea ever gets built, this VLAN doesn't need an exemption — VPN DNS rides inside the encrypted tunnel and never appears as port 53 at the gateway.

**Known limit:** DNS filtering only sees what uses DNS. Hardcoded IPs and DNS-over-HTTPS on 443 — which plenty of endpoint agents use deliberately — sail past Pi-hole entirely. The VLAN isolation is what's actually doing the work here. Pi-hole is the window, not the lock.

**Related:** IoT VLAN Firewall Rules entry (same UniFi mechanics, different trust direction). UniFi Internet Block + Network-Wide DNS Enforcement entry (the port 53 lockdown referenced above).

**Status:** Idea only. Low setup cost — SSID + VLAN + three firewall rules, maybe 30 minutes in the UniFi controller with no changes on the device itself. Test the allow-before-block rule order from the device with `nslookup google.com 192.168.1.2` before trusting it.

---

## UniFi Internet Block + Network-Wide DNS Enforcement
*Added: 2026-09-16*

Two related techniques for controlling what devices can reach outside the network.

**1. Per-device internet block.** For devices that need local network access but shouldn't reach the internet (e.g. a smart TV you want controllable via HomeKit), use a UniFi traffic/firewall rule to block the device's internet access while keeping LAN access. More complete than a Pi-hole DNS blocklist, which LG TVs can bypass by hardcoding public resolvers (8.8.8.8 / 1.1.1.1).

**2. Network-wide DNS enforcement.** Force all DNS through Pi-hole with a UniFi rule blocking outbound TCP/UDP 53 (and 853 for DNS-over-TLS) from all devices except the Pi-hole nodes (192.168.1.129, 192.168.1.13). Exempt the nodes, not the VIP, since Unbound needs direct access to root servers. Better version: DNAT-redirect port 53 to the VIP (192.168.1.2) so hardcoded-DNS devices get filtered answers instead of breaking. Does not catch DNS-over-HTTPS (port 443) or hardcoded IPs; those need technique 1.

**Testing:** Apply to IoT VLAN first, keep the rule toggle handy for rollback. Verify from a laptop with `dig @8.8.8.8 doubleclick.net` — should be blocked or answered by Pi-hole.

**Context:** Came up while deciding what to do about the LG TV after the Gamers Nexus data-collection investigation (Sept 2026). Decided to unplug the LG from the network entirely, since the Apple TV covers what HomeKit was used for via HDMI-CEC.

**Reference:** github.com/zzzpoint/lg-tv-blocklist (DNS blocklist approach and its caveats)

**Status:** Idea only. No device currently needs technique 1; technique 2 is an optional network hardening project.

---

## NUT — UPS-Triggered Clean Shutdown for the Pis
*Added: 2026-09-16*

Use Network UPS Tools (NUT) so the rack UPS can tell the Pis to shut down cleanly before its battery runs out, instead of cutting power mid-write. Prompted by the September outage: both Pi-hole nodes died with suspected SD card corruption, and a likely cause is an outage that outlasted the UPS battery, so everything powered off hard.

**How it would work:** UPS USB data cable → one always-on host runs the NUT server and watches battery level → Pis run NUT clients and shut down gracefully when the battery hits a low threshold.

**Open questions:**
- Does the UPS have a USB data port, and is its model supported by NUT?
- Which machine hosts the NUT server? It needs to be the most reliable box on the rack.
- Is the power strip on a battery-backed outlet, and does the UPS battery pass a self-test? (Check first.)
- Could the deadbox or other Pis join later?

**Status:** Idea. Do after the Pi-hole rebuild, not before.

**Update 2026-09-23:** the rack PDU and the Pis are on the UPS's battery-backed outlets. The September outage lasted **92 hours**, so the nodes died hard when the battery ran out, which is exactly the case NUT exists for. Still to check: the battery self-test and the USB data port.

**Related:** Pi-hole rebuild (Kingston A400 SSD for pihole1, SanDisk Max Endurance card for pihole2).

---

## Tailscale — homelab mesh VPN

*Captured June 1, 2026*

Set up Tailscale (WireGuard-based mesh VPN) for secure remote access to the homelab without port forwarding or firewall changes. Worth exploring for:

- Remote access to the Pi fleet, PiHole admin, and dashboards from anywhere
- Using PiHole as the tailnet DNS server → ad-blocking on every device, everywhere, including cellular
- Subnet routing to reach the whole LAN through one node
- Low setup overhead: single binary per device, free tier covers a personal homelab

**Note 2026-09-23:** Tailscale is on the MacBook with MagicDNS active (`100.100.100.100`). It forwards ordinary lookups to the DHCP-provided DNS, so Pi-hole filtering does reach the laptop (verified: `doubleclick.net` → `0.0.0.0`). It can lag briefly after a lease renew.

---

## Network Switch Upgrade — Multi-Gig
*Added: 2026-05-30*

Full device inventory pulled via UniFi API (script: `unifi_inventory.py` in this repo). Network has 10 devices: Cloud Gateway Fiber, Trunk Switch (US16P150, 16-port PoE), 4x USW Flex Minis, 3x APs, and a USP Plug.

**Bottleneck:** Trunk Switch (US16P150) is 1G-only. The CGF already has a 10G SFP+ port available for LAN uplink. The 4 Flex Minis are fine for now — edge switches serving workstations, APs, and consumer devices.

**Trigger conditions (either one):**
- NAS purchase — local transfer speed becomes meaningful
- ISP upgrade past 1G — 2.5G fiber is available in the area

**Recommended upgrade when triggered:** Replace US16P150 with **USW Pro Max 16** (~$400–500). Gives 16x 2.5G PoE ports and 2x 10G SFP+ uplinks. Connect to CGF via SFP+ DAC cable. Flex Minis stay as-is unless specific workstations need 2.5G (unlikely without a NAS).

**No action needed now** — current 1G setup matches 1G WAN and no local high-speed transfer workloads.

## PiHole — Top Clients Hostname Resolution
*Added: 2026-04-04*

The top clients list in the PiHole dashboard shows raw IP addresses instead of hostnames or friendly client names, making it hard to tell which device is which at a glance.

**What's needed:** Configure PiHole to resolve client IPs to hostnames — either via local DNS entries, DHCP hostnames from the router, or manually defined client names in the PiHole admin UI. Unifi should be able to push DHCP hostnames; worth checking whether PiHole can pick those up automatically or if they need to be added manually.

**Status:** Not started. Low urgency — cosmetic/usability improvement.

---

## IPv6 Virtual IP for PiHole / Keepalived
*Added: 2026-04-03*

IPv6 DNS is working but there is no IPv6 VIP configured. The IPv4 redundancy setup (Keepalived VIP 192.168.1.2) has no IPv6 equivalent — clients using IPv6 DNS are hitting individual node addresses directly rather than a shared virtual IP.

**What's needed:** A dedicated session covering Keepalived IPv6 VIP configuration and Unifi DHCPv6/SLAAC DNS settings. The complication is ISP dynamic IPv6 prefix behavior — the prefix may change, which affects how a stable VIP can be assigned and whether ULA (Unique Local Address) prefixes are a better fit than GUA (Global Unicast) for internal VIP use.

**Depends on:** Understanding the ISP's IPv6 prefix assignment behavior before committing to an approach.

**Status:** Not started. Low urgency — IPv6 DNS works, just not redundant.

---

## "What Now?" — Decision Fatigue App
*Added: 2026-04-02*

A mobile-first app to help Matthew and his wife cut through decision fatigue at the end of the day. Three use cases, to be built one at a time.

**Use case 1: What to watch** (first to build)
You describe your mood ("spy thriller," "cozy British mystery," "something funny") and the app asks a question or two, then returns a short list of suggestions pulled from your actual watchlist. The core value is **mood matching** — not just a random picker, but something that understands what you're in the mood for tonight.

**Watchlist source:** Streaming service API sync (not manual entry). Volume of content makes manual maintenance too burdensome, and a future feature — "is this show on one of my services, and can I add it?" — requires real integration to work. This is a first-class requirement, not a nice-to-have.

**Use case 2: Where to eat** (second)
Same mood-matching flow, applied to restaurants.

**Use case 3: What to make for dinner** (third)
Same flow, applied to home cooking / meal options.

**Status:** Concept defined, use cases sequenced. Ready to spec use case 1 in detail and begin BRD development.

**Next step:** When picking this back up, start by speccing the TV use case — user flow, mood-matching mechanic, streaming API candidates (JustWatch API or service-specific), and MVP scope. Note: major streaming services don't have public watchlist APIs — JustWatch aggregation is the likely path, worth researching before committing to an approach.

---

## Dead & Phish Time Machine — Gift Box
*Added: 2026-03-15*

A physical box for a Grateful Dead/Phish superfan: set a date with knobs (day/month/year), and it finds the closest show from that date and streams it to his stereo. The conceptual model is a time machine — you're not just playing music, you're traveling to a specific night. Inspired closely by the [deadstream project](https://eichblatt.github.io/deadstream/), which already handles GD archive.org playback with physical knobs and an intentionally simple, distraction-free UI. Phish has a similar deep archive at phish.net / phish.in.

**Key details:** Music comes from archive.org (Grateful Dead collection) and phish.in (Phish). The deadstream project is open source and designed to be built — strong starting point. Physical knobs, minimal buttons, no menus. HiFiBerry DAC+ Pro is a natural fit for audio output on a Pi.

**Hardware candidates:** Pi 3B + HiFiBerry DAC+ Pro. Rotary encoders for date selection. Small display for showing the show date/venue.

**Status:** Software fully working as of 2026-06-17. Target date passed (was June 1 housewarming); gift not yet shipped. Still active.

**What's done:**
- Pi OS Bookworm flashed, deadstream venv installed
- InnoMaker HiFi DAC confirmed (ALSA hw:1,0, speaker-test passed)
- Significant runtime bugs fixed in Archivary.py: infinite archive download loop, collection field type mismatch, cross-device tempfile rename failure
- Display shows date-picker UI ("8/13/75" etc.) — full software stack working

**What's left:**
- Create ~/.timemachine_options.txt on Pi (set PULSEAUDIO_ENABLE=false)
- Wire encoders and buttons per PINOUT.md
- End-to-end audio test: pick a date, stream a show
- Box assembly

**Reference:** https://eichblatt.github.io/deadstream/ | https://eichblatt.github.io/deadstream/BuildYourOwn

### Version 2 / Future Ideas

**Sonos streaming via Icecast**
The deadbox could expose its current stream as a local HTTP audio stream using Icecast, making it available to Sonos as a custom radio source. Flow: archive.org → Pi (deadstream) → Icecast → Sonos (custom radio URL). This sidesteps Sonos's proprietary source discovery protocol entirely. The DAC+ Pro handles local audio; Icecast handles network broadcast. No hardware changes required — pure software addition deployable via SSH post-gifting.

---

## IoT VLAN Firewall Rules
*Added: 2026-03-15*

Set up proper firewall rules on the Ubiquiti router to isolate the IoT VLAN from trusted devices. Goal: IoT devices can reach the internet but cannot initiate connections to the trusted LAN. Trusted devices can optionally reach IoT for control (Home Assistant, etc.) but IoT cannot reach back unprompted.

**Tech involved:** UniFi Network controller, firewall rule configuration, VLAN segmentation.

**Status:** Not started. Prerequisite: Home Assistant should probably be running first so firewall rules don't break HA ↔ device communication unexpectedly.

---

## ISS Tracker — Physical Display
*Added: 2026-03-15*

A small physical device that tracks the International Space Station in real-time and shows its current position — either on a world map display or as a simple pass-predictor (next time it's overhead). Inspired by a Reddit build. A Pi Zero or Pi 3B with a small screen would work well. ISS position data is freely available from open APIs (e.g., Open Notify).

**Hardware candidates:** Pi Zero 2 W + small TFT/e-ink display. Could also be a wall-mounted screen.

**Status:** Early idea, no experimentation yet.

---

## Star Trek Communicator Pin — Home Assistant Voice Control
*Added: 2026-03-15*

A wearable or desk prop that looks like a Star Trek communicator badge and triggers Home Assistant voice commands when tapped or pressed. Inspired by a Reddit build. Combines the fun of prop-making with practical smart home control. Wyoming protocol (local voice pipeline in HA) is the likely software layer.

**Hardware candidates:** Small ESP32 board, small speaker/mic, 3D-printed or found enclosure shaped like a commbadge.

**Tech involved:** Home Assistant, Wyoming protocol (local voice), ESPHome, ESP32, 3D printing or prop fabrication.

**Status:** Early idea. Depends on Home Assistant being set up first.

---

## Home Dashboard — E-Ink Display
*Added: 2026-03-15*

A wall-mounted e-ink display showing a glanceable home dashboard: calendar events, weather, reminders, and optionally smart home status or controls. The [esphome-weatherman-dashboard](https://github.com/Madelena/esphome-weatherman-dashboard) project is a direct reference — it uses a Waveshare 7.5" e-paper screen driven by an ESP32, framed in an IKEA RIBBA frame, and pulls data from Home Assistant via ESPHome.

**Hardware candidates:** Waveshare 7.5" e-paper + ESP32 driver board, IKEA RIBBA frame. Low power, always-on, blends into the wall.

**Tech involved:** ESPHome, Home Assistant, e-ink display, Google Calendar integration.

**Status:** Early idea. Depends on Home Assistant being set up. No hardware purchased yet.

**Reference:** https://github.com/Madelena/esphome-weatherman-dashboard

---

## WiiM Now Playing Display — Touch Screen
*Added: 2026-03-15*

A dedicated touch display showing what's currently streaming on the WiiM — album art, track info, and playback controls (skip/pause/play). Service-agnostic by design so it works when moving away from Spotify to another streaming service. WiiM has a local API and supports OpenHome/UPnP, which makes this tractable without cloud dependency.

**Hardware candidates:** Pi with small touchscreen, or a repurposed tablet. Could also be a web app served locally.

**Tech involved:** WiiM local API or UPnP/OpenHome, Pi or small screen, possibly Home Assistant media player integration.

**Status:** Early idea, no experimentation yet.

---

## VU Meters — HiFi Aesthetic
*Added: 2026-03-15*

Purely aesthetic analog-style VU meters for the home HiFi setup. Could be real analog meters driven by audio signal, or a display (Pi + screen) rendering a convincing VU animation. The HiFiBerry DAC+ Pro can capture audio signal for the latter approach.

**Conceptual territory:** Analog warmth, visual music, retro HiFi aesthetics.

**Hardware candidates:** Physical analog VU meters wired to audio output, OR Pi + HiFiBerry DAC+ Pro + screen showing animated meters.

**Status:** Early idea. Purely for fun/aesthetics.

---

## Halloween Eye Windows — Dual Monitor Installation
*Added: 2026-03-15*

Place two old monitors in front-facing windows to make the house appear to have glowing eyes at night. Each monitor plays a looping animation of a large eye. Ideally the eyes blink, shift gaze slowly, or react to motion (camera module is available for this). A fun seasonal installation with room to grow into something interactive.

**Hardware candidates:** Two old monitors + any Pi or Mac Mini that can drive them. Pi Camera Module for optional motion reactivity.

**Tech involved:** Video looping (VLC, mpv, or browser fullscreen), optional OpenCV for motion detection, Pi or Mac Mini.

**Status:** **Active project — now lives at `~/repos/halloween-eyes`.** Designed and in build as of 2026-09-20; targeting Halloween, Sat 2026-10-31. Scope settled as two procedurally animated eyes on a single Raspberry Pi 5 driving both monitors — not looping video. Motion reactivity via the camera module is explicitly deferred as the growth path. See that repo's `docs/DESIGN.md` and `docs/PLAN.md`. 2026-09-23: hardware spike passed on the bench — one Pi 5 drives both monitors, one window each, ~1–2% CPU.

---

## PicThere — Mobile App
*Added: 2026-03-07*

Stand in a spot, take a picture, and see all the photos other people have taken from that exact location. An AR layer helps users find and align to established "spots."

**Conceptual territory:** space and place, assigned meaning, change over time, collective visual memory, the palimpsest quality of a location accumulating history.

**Tech involved:** geolocation, augmented reality, mobile platforms.

**Status:** Early idea, no experimentation yet.

---

## Seamless Context Handoff Between Claude Modes
*Added: 2026-03-08*

Right now, moving from "thinking" (Claude.ai project) to "doing" (Claude Code / Cowork) requires manually copy-pasting context. The ideal future state is one continuous AI collaborator that knows your full context AND can act on files and systems — no human as messenger between modes. The infrastructure is mostly there; it's just not wired together for end users yet. Worth watching as Cowork's global/folder instructions and persistent memory mature.

**Status:** Observation, not an actionable project yet. Revisit in 6 months.

---

## Bitaxe Gamma 601 — Bitcoin Lottery Miner
*Added: 2026-03-10*

Set up a Bitaxe Gamma 601 (currently in the box) as a solo or pool Bitcoin miner. The Bitaxe is a small open-source ASIC miner — "lottery mining" refers to solo mining where the odds are long but the full block reward is yours if you hit it.

**Key decision to make:** Solo vs pool mining. Solo is the lottery ticket approach — statistically unlikely but a fun experiment. Pool mining gives small, steady payouts but takes a cut. Worth researching both before committing.

**Status:** Hardware in hand, not yet unboxed. No setup started.

---

## Homelab & Smart Home Build-Out
*Added: 2026-03-08*

A phased build-out of homelab services and smart home infrastructure using existing hardware.

**Hardware allocation:**
- Pi 5 → Home Assistant OS + Zigbee/Z-wave USB dongle
- Pi 4 → keep running PiHole v5 during migration, then rebuild as PiHole v6 node 2
- Pi 3B → new PiHole v6 primary (with Unbound baked in from the start)
- Mac Mini 2014 → Docker host (Plex first tenant)
- Dell R410 → back-burner, heavy-lift when ready

**Smart home north star:** Home Assistant as the hub for everything. Lutron Caseta, Zigbee devices, and eventually Z-wave all feeding into it. Meross WiFi plugs to be replaced with Zigbee/Z-wave over time. Nest thermostat to be replaced (decision TBD).

**DNS/networking plan:**
*(Rebuilt September 2026 with the roles swapped. See docs/pihole-rebuild-runbook.md.)*
- Pi 4 + SSD: pihole1, PiHole v6 + Unbound primary (192.168.1.129) — live ✓
- Pi 3B + Max Endurance microSD: pihole2, PiHole v6 + Unbound backup (192.168.1.13) — live ✓
- Nebula Sync (binary + systemd timer on pihole1): every 6h, pihole1 → pihole2 — live ✓
- Keepalived: VIP 192.168.1.2 with a DNS health check, failover verified from IoT with live traffic ✓
- UniFi DHCP DNS → VIP on main LAN and IoT VLAN (cut over 2026-09-23) ✓
- PiHole pause tool (:8080): **not rebuilt**. It only exists on the old SD cards.
- Note: always make blocklist/config changes on the primary (192.168.1.129). Nebula Sync is one-directional and overwrites pihole2.

**Status:** Operational after the rebuild. Open: disk images, ntfy alerts, IPv6 VIP (see separate entries).

---

## Daily History Playlist — Spotify Automation
*Added: 2026-03-07*

A Python script that runs at 6am daily (via cron on Raspberry Pi) and creates a Spotify playlist of songs with meaningful connections to that specific date — artist birthdays, album release anniversaries, historic chart milestones, cultural anniversaries, and more. Sends a push notification via ntfy.sh when ready.

**Conceptual territory:** music history, automation, personal curation, serendipity, cultural memory.

**Tech involved:** Python, Spotify API (spotipy), ntfy.sh for push notifications, cron scheduling, Raspberry Pi (primary) / Mac (dev/test).

**Status:** Significantly developed. Spotify Developer credentials obtained, ntfy.sh chosen for notifications, full Claude Code prompt written and ready to paste. Mac-compatible version specified for local testing while away from Pi. Blocked on: actually running the Claude Code session to build it.

**Chat reference:** https://claude.ai/chat/bbcacce9-beb7-4b33-a2d2-8331d2422550


## Hardware RTC Module — Pi 3B Clock Persistence
*Added: 2026-07-07*

Both PiHole nodes lack a battery-backed clock (after the September 2026 rebuild: pihole1 = Pi 4, pihole2 = Pi 3B; neither has an RTC). After a 4+ day power outage, both booted with stale clocks, causing Unbound DNSSEC validation to reject all signed responses as not-yet-valid → SERVFAIL on every query → whole network DNS down. Manual `date -s` on both nodes broke the deadlock. fake-hwclock only covers short outages (stale-by-days still fails DNSSEC), so a hardware RTC is the real fix.

**What's needed:**
1. **Find/buy** — DS3231 RTC module (~$5, coin-cell backed, I2C). One per node = 2 units. Verify battery included (CR2032 or LIR2032).
2. **Install** — clip onto GPIO header (I2C pins: 3.3V, GND, SDA=GPIO2, SCL=GPIO3). NOTE: check for pin conflicts — deadbox uses these for HiFiBerry, but the PiHole Pis are display/HAT-free so should be clear.
3. **Configure** — add `dtoverlay=i2c-rtc,ds3231` to /boot/firmware/config.txt, disable fake-hwclock, set time once via NTP so the module gets seeded, verify with `hwclock -r` and `timedatectl`.

**Why it matters:** Length of outage becomes irrelevant — module tracks real elapsed time on battery, boots to correct time every time. Prevents the DNSSEC deadlock permanently.

**Status:** Not started. Low urgency but high value — this failure recurs after every long outage until fixed.

## DHCP Pool Narrowing — Separate Static and Dynamic Address Space
*Added: 2026-09-20*

The main LAN DHCP pool spans `192.168.1.6 – 192.168.1.254` — nearly the whole subnet. Every hand-assigned infrastructure static (pihole1 at .129, pihole2 at .13, and anything else set on-device) therefore sits *inside* the range the gateway hands out automatically. Nothing structurally prevents the gateway from leasing one of those addresses to a new device while the intended host is powered off, producing an address conflict that presents as intermittent, device-specific breakage rather than a clean failure.

Surfaced during the September 2026 Pi-hole rebuild: with both Pi-hole nodes down, `.13` had aged out of the client list entirely and was sitting unprotected in leasable space. Per-client fixed IP reservations close the hole one device at a time, but only if you remember to create one for every static host.

**What's needed:**
1. **Inventory** — list every host currently using a hand-assigned static, plus the VIP (192.168.1.2) and gateway (192.168.1.1).
2. **Pick a boundary** — e.g. infrastructure below `.100`, DHCP pool `.100 – .254`. Requires renumbering pihole1 off `.129` to something below the line.
3. **Renumber** — update on-device statics, keepalived `unicast_src_ip`/`unicast_peer`, Nebula Sync endpoints, and any dashboard/script references.
4. **Shrink the pool** in UniFi, then let existing leases below the boundary expire and move.

**Why it matters:** Makes static/dynamic collision impossible by construction instead of by discipline. Removes a latent, hard-to-diagnose failure class from the whole homelab, not just the Pi-hole nodes.

**Status:** Not started. Deliberately deferred out of the Pi-hole rebuild — it touches the live network and would mean renumbering nodes mid-rebuild. Revisit once DNS has been stable for a few days. Note the renumbering cost is lowest right after a rebuild, while config is fresh.
