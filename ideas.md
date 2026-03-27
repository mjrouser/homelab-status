# Ideas Log

A running capture of ideas, experiments, and things worth returning to.
Updated collaboratively with Claude. Add anything — half-formed is fine.

---

<!-- IDEAS GO HERE -->

## Dead & Phish Time Machine — Gift Box
*Added: 2026-03-15*

A physical box for a Grateful Dead/Phish superfan: set a date with knobs (day/month/year), and it finds the closest show from that date and streams it to his stereo. The conceptual model is a time machine — you're not just playing music, you're traveling to a specific night. Inspired closely by the [deadstream project](https://eichblatt.github.io/deadstream/), which already handles GD archive.org playback with physical knobs and an intentionally simple, distraction-free UI. Phish has a similar deep archive at phish.net / phish.in.

**Key details:** Music comes from archive.org (Grateful Dead collection) and phish.in (Phish). The deadstream project is open source and designed to be built — strong starting point. Physical knobs, minimal buttons, no menus. HiFiBerry DAC+ Pro is a natural fit for audio output on a Pi.

**Hardware candidates:** Pi 3B + HiFiBerry DAC+ Pro. Rotary encoders for date selection. Small display for showing the show date/venue.

**Status:** Priority project. Target: ready before April 17th. Research deadstream build instructions before any hardware decisions.

**Reference:** https://eichblatt.github.io/deadstream/ | https://eichblatt.github.io/deadstream/BuildYourOwn

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

**Status:** Early idea, seasonal. No urgency — plan ahead for next Halloween.

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
- Stand up fresh PiHole v6 + Unbound on a Pi 3B
- Validate it, then rebuild Pi 4 as second PiHole v6 node
- Use Keepalived for failover, Gravity Sync for config mirroring
- Don't touch the working Pi 4 PiHole v5 until replacement is ready

**Status:** Planning complete. Hardware inventoried. Ready to start on PiHole migration or Home Assistant install as separate focused chats.

---

## Daily History Playlist — Spotify Automation
*Added: 2026-03-07*

A Python script that runs at 6am daily (via cron on Raspberry Pi) and creates a Spotify playlist of songs with meaningful connections to that specific date — artist birthdays, album release anniversaries, historic chart milestones, cultural anniversaries, and more. Sends a push notification via ntfy.sh when ready.

**Conceptual territory:** music history, automation, personal curation, serendipity, cultural memory.

**Tech involved:** Python, Spotify API (spotipy), ntfy.sh for push notifications, cron scheduling, Raspberry Pi (primary) / Mac (dev/test).

**Status:** Significantly developed. Spotify Developer credentials obtained, ntfy.sh chosen for notifications, full Claude Code prompt written and ready to paste. Mac-compatible version specified for local testing while away from Pi. Blocked on: actually running the Claude Code session to build it.

**Chat reference:** https://claude.ai/chat/bbcacce9-beb7-4b33-a2d2-8331d2422550
