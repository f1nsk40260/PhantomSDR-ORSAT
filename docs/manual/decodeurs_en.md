---
pdf: guideDecodeursEN.pdf
pdf_title: PhantomSDR-ORSAT — Decoders guide
title: The ORSAT decoders
subtitle: Complete guide — digital modes, telegraphy, images, maritime and aeronautical messages
url: https://orsat.ddns.net
cover: en_p18_0.jpg
cover_caption: The FT8 decoder: audio waveform, decode markers and message table.
summary: This guide describes, one by one, every decoder built into ORSAT: what it is for, where to listen, how to set it up and how to read what it displays. It ends with the signal identification tools and a troubleshooting chapter.
edition: English version — October 2026 edition — ORSAT 1.0
credits: Decoders integrated by **F1NSK** for ORSAT, based on PhantomSDR-Plus by **SV1BTL**. Signal database: **Artemis** (AresValley) and **Signal Identification Wiki**.
header_left: ORSAT — Decoders guide
header_right: ORSAT 1.0
page: Page
toc: Contents
cover_note: The screenshots show the interface in French; the button names in the text are those of the English interface.
---

# 1. Common principles

## 1.1 Where the decoders are

All the decoders are grouped in the **Decoders Control** row, in the right-hand column, below the scanner. Each button starts a decoder; a second click on the same button stops it. **Only one decoder runs at a time**: starting another one stops the previous one.

![The “Decoders Control” row and its eleven buttons.](images/dec_rangee.jpg){w=380}

| Button | Decoder | Chapter |
| FT8 / FT4 / FT2 | WSJT weak-signal modes | 2 |
| JS8 | JS8Call | 3 |
| CW | Morse telegraphy | 4 |
| WSPR | WSPR-2 beacons | 5 |
| FAX | HF weather facsimile (WEFAX) | 6 |
| SSTV | Slow-scan television | 7 |
| NAVTX | NAVTEX (navigational warnings) | 8 |
| HFDL | HF Data Link (aviation) | 9 |
| FLDIGI | fldigi family: RTTY, SITOR, PSK31, Olivia, MFSK… | 10 |

The **RADE (FreeDV)** digital voice modes are not in this row: they have their own **RADEL / RADEU** buttons in the mode selector (chapter 11).

## 1.2 What a decoder does when it starts

A decoder does more than listen to the audio: it **takes control of the receiver** to put itself in the right conditions.

- **Demodulation mode** — FT8, FT4, FT2, JS8 and WSPR switch the receiver to **USB**, whatever the band's usual mode. FAX and NAVTEX also work in USB. SSTV picks the customary sideband (see chapter 7).
- **IF filter** — the passband is set to the mode's: the whole 3 kHz sub-band for FT8/FT4/FT2/JS8, the narrow beacon window for WSPR.
- **Back to normal** — when the decoder stops, the receiver returns to the **band's default mode** (LSB, CW, AM…).
- **Automatic analysis** — if the “Digital signal analysis” module was running, it stops: it has done its job, which was to help choose a decoder.

> [Tip] The decoders work on the receiver's **raw** audio, before noise reduction, audio AGC and volume. Muting the sound or lowering the volume therefore does not stop decoding.

## 1.3 Shared tools

**Known frequencies.** The FT8/FT4, JS8, WSPR and SSTV panels have a **Known frequencies** menu: choosing a band tunes the receiver straight to the mode's usual dial frequency. FAX, NAVTEX, HFDL and FLDIGI have their own station lists, described in their chapters.

**Station map.** FT8/FT4/FT2, JS8 and WSPR have a **🗺 Map (n)** button: every station whose message contains a locator is placed on it. **⤢ Large view** opens the map in a floating window that can be moved and resized. Hovering over a dot shows the callsign and the message; a click opens the station's QRZ page.

![Map of the stations heard, in large view.](images/dec_carte.jpg){w=380}

**Decoder audio spectrum.** FT8/FT4/FT2, JS8 and WSPR show, below their settings, an **audio waterfall** of the passband: signals can be seen arriving, and each decode is marked on it.

**Time synchronisation.** Fixed-slot modes (FT8, FT4, FT2, JS8, WSPR) depend on UTC time. ORSAT compensates for the delay of the audio stream between the server and your browser with the **Sync offset** setting (section 2.4).

# 2. FT8, FT4 and FT2

## 2.1 The three modes

These three WSJT-X modes carry short standardised messages (callsigns, locator, report) with very high sensitivity. They work in **slots** synchronised to UTC.

| Mode | Slot length | Use |
| FT8 | 15 s | The most widespread: DX, propagation, everyday operating |
| FT4 | 7.5 s | Faster, mainly in contests |
| FT2 | 3.75 s | Very fast variant, still little used |

## 2.2 Getting started

1. Click **FT8**, **FT4** or **FT2**.
2. In **Known frequencies**, choose a band (FT8 and FT4; FT2 has no list yet). The receiver tunes in USB.
3. Wait for the current slot to end: the first decodes appear after 15 s (FT8), 7.5 s (FT4) or 3.75 s (FT2).

| Band | FT8 (kHz) | FT4 (kHz) |
| 160 m | 1,840.0 | — |
| 80 m | 3,573.0 | 3,575.0 |
| 60 m | 5,357.0 | — |
| 40 m | 7,074.0 | 7,047.5 |
| 30 m | 10,136.0 | 10,140.0 |
| 20 m | 14,074.0 | 14,080.0 |
| 17 m | 18,100.0 | 18,104.0 |
| 15 m | 21,074.0 | 21,140.0 |
| 12 m | 24,915.0 | 24,919.0 |
| 10 m | 28,074.0 | 28,180.0 |
| 6 m | 50,313.0 | 50,318.0 |

## 2.3 Reading the panel

![FT8 panel: waveform, sync setting and message table.](images/en_p18_0.jpg){w=375}

- **Farthest** — distance of the farthest station heard since the start of the session.
- **Audio waveform** — the markers show each decoded signal within the passband.
- **Message table** — one row per decode:

| Column | Content |
| Mode | FT8, FT4 or FT2 |
| dB | Estimated signal-to-noise ratio (a signal at −20 dB still decodes) |
| Hz | Audio frequency of the signal within the passband |
| DT | Time offset, in seconds |
| Message | The text: CQ F1ABC JN03, F1ABC DL1XYZ -12, RR73… |
| Locator / Dist | The station's Maidenhead locator and estimated distance from ORSAT |

## 2.4 Sync offset and Auto

The audio takes a little time to reach you. **Sync offset** delays the start of the capture after the start of the UTC slot to compensate for that delay (value shown in seconds).

- **Auto** ticked (recommended) — ORSAT adjusts the offset itself from the **DT** values measured by the decoder.
- **Auto** unticked — set the slider by hand: if most DT values are strongly positive or negative, move it the same way.

> [Tip] DT values all close to 0 (between −0.5 and +0.5 s) mean the timing is right. DT values scattered beyond ±1 s lose decodes.

# 3. JS8 (JS8Call)

## 3.1 The mode

JS8 uses FT8's modulation but carries **free text**: keyboard messaging, relaying between stations, presence beacons. A long message is split into several frames.

## 3.2 Settings

- **Speed** — the JS8 speed being received. All stations in a QSO use the same one; **Normal** is the usual calling speed.

| Speed | Slot |
| Normal | 15 s |
| Fast | 10 s |
| Turbo | 6 s |
| Slow | 30 s |
| Ultra | 4 s |

- **Known frequencies** — 160 m 1,842.0 · 80 m 3,578.0 · 40 m 7,078.0 · 30 m 10,130.0 · 20 m 14,078.0 · 17 m 18,104.0 · 15 m 21,078.0 · 12 m 24,922.0 · 10 m 28,078.0 kHz.
- **Progress bar** — progress of the current slot.
- **Sync offset / Auto** — as for FT8 (section 2.4).
- **Clear** — clears the messages.

![JS8 panel: speed, slot progress and messages.](images/dec_js8.jpg){w=375}

## 3.3 Reading the messages

Each row shows the mode, the SNR and the message, with the **sender's callsign highlighted**. A message being received is shown **as it arrives**, followed by a ▌ cursor, before being completed by the next frames. If the last frame does not arrive, the row says so (timed out).

> [Tip] “Listening on the Normal cycle…” means the decoder is waiting. On a quiet band it can take several minutes before the first message.

# 4. CW (Morse telegraphy)

## 4.1 How it works

The CW decoder **finds the signal's tone** in the passband on its own and **measures the speed** on its own. It follows speeds of roughly **5 to 65 words per minute**.

- **≈ … Hz** — audio frequency of the note being decoded.
- **· … WPM** — measured speed.
- **scanning…** — no note has been caught yet.
- **🔓 Lock tone** — holds the decoder on the current note: it no longer goes looking for a nearby signal. A second click releases it.
- The text is written continuously; a **───** line marks a silence (end of transmission).
- **Clear** clears the text.

![CW panel: detected note, speed and decoded text.](images/dec_cw.jpg){w=375}

## 4.2 Setting up reception

1. Listen in **CW** mode with a narrow filter (300 to 500 Hz).
2. Put **a single signal** in the passband: two notes at once make the decoder lose sync.
3. Wait a few characters while the speed is measured.

## 4.3 Regular CW stations

Below the decoded text, a table lists the **scheduled CW transmissions** (Paris time, daylight-saving change handled), with a button to tune straight to them:

| Station | Frequencies | Schedule |
| FAV22 (French Navy) | 3,881 and 6,825 kHz | weekdays 10:30–11:00 and 13:30–14:00; weekends 09:00–09:30 and 10:20–10:55 |
| F9TM | 3,536 kHz | Thursday from 19:15 |

> [Tip] FAV22's transmissions are ideal for practice: steady speed and well-formed text.

# 5. WSPR

## 5.1 The mode

WSPR (“whisper”) is a mode for **very low-power beacons** used to study propagation. Each transmission lasts almost 2 minutes and starts at the beginning of an **even UTC minute**. ORSAT's decoder receives classic WSPR-2.

## 5.2 Getting started

1. Click **WSPR**.
2. Choose a band in **Known frequencies**:

| Band | kHz | Band | kHz |
| 2200 m | 136.0 | 30 m | 10,138.7 |
| 630 m | 474.2 | 20 m | 14,095.6 |
| 160 m | 1,836.6 | 17 m | 18,104.6 |
| 80 m | 3,568.6 | 15 m | 21,094.6 |
| 80 m EU | 3,592.6 | 12 m | 24,924.6 |
| 60 m | 5,287.2 | 10 m | 28,124.6 |
| 40 m | 7,038.6 | | |

3. Wait: “Waiting for next even UTC minute slot…” is shown until the next slot starts, then the progress bar moves during reception. The results arrive **at the end** of the slot.

## 5.3 Reading the table

![WSPR panel: slot progress and decoded beacons.](images/dec_wspr.jpg){w=375}

- **UTC** — time of the slot;
- **Callsign** and **Grid** — the beacon's callsign and locator;
- **Power** — declared power (in dBm: 37 dBm = 5 W, 30 dBm = 1 W, 23 dBm = 200 mW);
- **Freq** — exact frequency of the beacon;
- **SNR** — signal-to-noise ratio (WSPR decodes down to about −28 dB).

> [Tip] The **WSPR log** and **WSPR map** buttons in the “External links” section of the Information menu show the beacons received by ORSAT on the reference websites.

# 6. FAX (HF weather facsimile)

## 6.1 The mode

Meteorological and military stations broadcast **weather charts** (analyses, forecasts, sea state, ice) by radio facsimile. Each image is preceded by a start and phasing signal and ended by a stop signal.

## 6.2 Choosing a station

- **Station** — choose a station from the list, then a **Frequency**, and click **▶ Tune**.

| Station | Frequencies (kHz) |
| GYA — Northwood (United Kingdom) | 2,618.5 · 4,610 · 8,040 · 11,086.5 |
| DDH3 / DDK6 — Hamburg (Germany) | 3,855 · 7,880 · 13,882.5 |
| SVJ4 — Athens (Greece) | 4,482.9 · 8,106.9 |
| RBW41 — Murmansk (Russia) | 5,336 · 6,445.5 · 7,908.8 · 8,444 · 10,130 |
| HLL2 — Seoul (South Korea) | 3,585 · 5,857.5 · 7,433.5 · 9,165 · 13,570 |
| JMH — Tokyo (Japan) | 3,622.5 · 7,795 · 13,988.5 |
| JFX — Kagoshima (Japan) | 4,274 · 8,658 · 13,074 · 16,907.5 · 22,559.6 |

- **Next Transmissions · UTC** — the chosen station's next transmissions, with a countdown. A transmission **in progress** is shown in green (●), an **imminent** one in red. The **FAX transmission schedules** link opens the full schedules.

## 6.3 Image settings

| Setting | Values | Default |
| LPM (lines per minute) | 100 · 120 · 240 | 120 |
| IOC (index of cooperation) | 288 · 576 | 576 |
| Shift (black/white) | 400 Hz · 800 Hz | 800 Hz |

The values marked ★ in the menus are the standard; almost every station uses it. The information line shows the **black** (1,500 Hz) and **white** (2,300 Hz) frequencies, the resolution in pixels per line and the duration of a line.

- **⇔ Auto-align** — automatically aligns the lines on the sync pulses: the image no longer slants.
- **⇅ Invert** — swaps black and white (LSB reception or a station with reversed polarity).

## 6.4 During reception

![FAX panel: station, schedule, settings and image being received.](images/dec_fax.jpg){w=375}

- The **300 Hz phasing** and **450 Hz stop** lights come on during phasing and the stop signal; the header shows **[PHASING]**, **[STOP]** and the number of lines received (**Lines**).
- The image builds line by line, **newest lines at the bottom**.
- **↺ Reset** clears the image and resets the decoder: use it between two transmissions or if the image tears.
- **⤓ Save PNG** saves the image.

> [Tip] Start the decoder a minute or two before the scheduled time: you will catch the phasing and the image will start properly aligned.

# 7. SSTV (slow-scan television)

## 7.1 The mode

Radio amateurs exchange **still images** in SSTV; the International Space Station also broadcasts them during special events. An image takes from 36 seconds to several minutes depending on the mode.

## 7.2 Sideband

By convention, SSTV is worked in **LSB on 80 and 40 m** and in **USB from 30 m up**. On start-up, the decoder picks the matching sideband. If a station does not follow the convention, change the sideband by hand: ORSAT respects your choice. On the wrong sideband, nothing decodes.

## 7.3 Settings

- **Known frequencies** — 80 m 3,730.0 (Europe) and 3,845.0 (Americas) · 40 m 7,171.0 · 20 m 14,230.0 (main) and 14,233.0 · 17 m 18,160.0 · 15 m 21,340.0 · 12 m 24,975.0 · 10 m 28,680.0 kHz.
- **Mode** — **Auto** (recommended) recognises the mode from the VIS header sent at the start of each image. A mode can also be forced: Martin M1, Martin M2, Scottie S1, Scottie S2, Scottie DX, Robot 36, Robot 72.
- **▶ Start** / **■ Stop** — starts or stops reception.
- **↺ Reset** — clears the image.
- **⏺ Force** — starts decoding at once in the chosen mode, without waiting for the VIS header. Useful when joining in the middle of an image. Does not work in Auto mode.
- **💾 Save** — saves the image.

## 7.4 Indicators

![SSTV panel: detected mode, sync status and received image.](images/dec_sstv.jpg){w=375}

- **[detected mode]** — for example [Martin M1].
- **hard sync lock** — firm sync on the line pulses; **soft sync hold** — sync held despite a weak signal.
- **Running / Stopped** and **Lines** — status and number of lines received out of the image total.

> [Tip] A slanted image comes from poor sync; an image with wrong colours, from the wrong mode or the wrong sideband.

# 8. NAVTEX

## 8.1 The mode

NAVTEX broadcasts **navigational warnings**, marine weather and distress alerts to ships. Each coast station has an **identification letter** (A to Z) and 10-minute transmission slots repeated every 4 hours. Transmission: 100-baud FSK, 170 Hz shift, SITOR-B code.

- **518 kHz** — international NAVTEX, in English;
- **490 kHz** — national NAVTEX, in the country's language.

## 8.2 Getting started

1. Click **NAVTX**: the receiver switches to USB.
2. Choose a station and click **⇒ Tune & Set IF**: the receiver tunes 500 Hz below the channel (the signal falls at 500 Hz audio) and the IF filter is set.
3. The header shows “waiting for phasing…” until a transmission starts.

## 8.3 The broadcast table

![NAVTEX panel: next broadcasts and messages received.](images/dec_navtex.jpg){w=375}

**Next Broadcasts · UTC** lists the stations in the order of their next transmissions: flag, identification letter, name, area, UTC time and countdown. The station **currently transmitting** is shown in green, the next one in red when it is imminent.

- A button **arms the decoder immediately**, without waiting for the phasing.
- **NAVTEX Maps Stations** opens the station map.
- **Clear** and **Save Text** clear or save the received text.

> [Tip] At night, 518 kHz carries far: stations from all over Western Europe and the Mediterranean are regularly received.

# 9. HFDL (HF Data Link)

## 9.1 The mode

Aircraft flying over the oceans exchange **ACARS** messages with HF ground stations around the world. ORSAT's decoder is **dumphfdl**, compiled to run in your browser.

## 9.2 Settings and reading

![HFDL receiver: ground station, indicators and messages.](images/en_p20_1.jpg){w=204,side}
- **HFDL ground station** — Shannon, Reykjavik, Canarias, Riverhead, Johannesburg… then one of its frequencies and tune to it, which also sets the IF.
- **Dial** — shows whether you are off an HFDL frequency.
- **Noise**, **Frames**, **Rate** — reception quality.
- **Messages** and **Squitters** — counters; tick **Squitters** to show the ground station beacons as well.
- Hover over a message to see the full frame; the save and clear buttons manage the log.

**Clickable identifiers.** The aircraft's **flight number**, **registration** and **ICAO code** open its FlightAware page in a new tab.

**Aircraft map.** **🗺 Map** shows the aircraft whose position has been received; **⤢ Large view** opens it in a floating window; **⌖ Show all** zooms to all the aircraft. Each aircraft is drawn pointing along its heading, with its track in red; a click opens its FlightAware page.

> [Tip] Ground stations send a squitter every 32 s. Choose a frequency where propagation is open towards the station and wait a few minutes: only some messages carry a position.

# 10. FLDIGI: RTTY, SITOR, PSK, Olivia and the others

## 10.1 One decoder, fourteen variants

The **FLDIGI** button opens a single decoder that covers the modes of the fldigi software. The **Variant** menu chooses the family; the panel title changes accordingly (FSK / RTTY, PSK31, Olivia, Packet, APRS…).

| Variant | Use |
| Maritime FSK / SITOR | NAVTEX, SITOR maritime warnings, NBDP |
| Weather RTTY | Weather bulletins in RTTY (DWD) |
| Amateur RTTY | Amateur radio RTTY |
| PSK31 (BPSK) | Amateur keyboard conversation |
| Olivia | Very robust text in difficult conditions |
| MFSK16 · 32 · 64 | Robust text, copes well with fading |
| DominoEX | Text, resistant to drift and multipath |
| THOR | DominoEX with error correction |
| THROB / THROBX | Slow multi-tone mode |
| Hellschreiber | Text sent as an image (character facsimile) |
| MT63 | Wide, very robust mode, often used for emergencies |
| Packet (AX.25) | Packet radio traffic |
| APRS | APRS positions and messages |

> [Tip] While running, this decoder takes control of the mode and the IF filter. First choose a known frequency, then fine-tune until the text settles.

## 10.2 Common controls

![FLDIGI decoder, maritime FSK / SITOR variant.](images/en_p20_0.jpg){w=204,side}
- **Known frequency** then **Tune** — tunes to a reference frequency for the variant.
- **Next Broadcasts · UTC** — broadcast times for the variants that have them (NAVTEX, DWD stations).
- **⇒ Set IF Band-Pass** — sets the IF filter to the width of the mode.
- **⟳ Auto-tune Center** — finds the signal and centres the decoder on it.
- **Clear** — clears the text; a button **saves the text**.
- The header shows the decoder status; “waiting for lock…” as long as no signal is caught.

## 10.3 RTTY and SITOR (FSK)

The three FSK variants share the same settings:

- **Center audio (Hz)** — audio frequency of the centre of the signal.
- **Shift (Hz)** — spacing between the mark and space tones.
- **Baud** — speed.
- **Framing** — 5N1, 5N1.5, 5N2, 7N1, 7E1, 7O1, 8N1.
- **Encoding** — CCIR-476 (SITOR), ITA2 / Baudot (RTTY), ASCII.
- **Invert mark / space** — swaps the two tones.
- **Auto shift detect** — measures the shift automatically.
- **Squelch (SNR)** — stops noise from being printed. Noise alone reads about −12 to −15 dB; RTTY stays readable down to about −4 dB. Slider fully left: squelch off (“off”).

| Variant | Centre | Shift | Baud | Code | Invert |
| Maritime FSK / SITOR | 500 Hz | 170 Hz | 100 | CCIR-476, 7N1 | no |
| Weather RTTY | 1,000 Hz | 450 Hz | 50 | ITA2, 5N1.5 | **yes** |
| Amateur RTTY | 1,000 Hz | 170 Hz | 45.45 | ITA2, 5N1.5 | no |

Indicators: **Mark** and **Space** (measured frequencies of the two tones), **Tones**, **SNR**, lock and timing.

**Known frequencies:**

- *Maritime* — 518 kHz (international NAVTEX), 490 kHz (national NAVTEX), 2,174.5 kHz (NBDP), 4,209.5 kHz (HF NAVTEX), SITOR MSI on 4,210, 6,314, 8,416.5, 12,579, 16,806.5, 19,680.5, 22,376 and 26,100.5 kHz.
- *Weather* — DWD Pinneberg: 4,583 (DDK2), 7,646 (DDH7), 10,100.8 (DDK9), 11,039 (DDH9), 14,467.3 (DDH8) and 147.3 kHz (DDH47, longwave, 85 Hz shift).
- *Amateur* — RTTY on 3,590, 7,043, 10,143, 14,083, 21,083 and 28,083 kHz.

> [Tip] DWD weather RTTY arrives with the mark tone at the bottom: leave **Invert mark / space** ticked. For amateur RTTY and SITOR, leave it unticked.

## 10.4 PSK31

- **Center audio** — put the decoder on the signal's trace (a thin line 31 Hz wide on the waterfall), or use **⟳ Auto-tune Center**.
- Indicators: **Carrier** (carrier frequency), **IMD** (transmission quality: −25 dB or below is clean, above −20 dB the transmitter is overdriven), **DCD** (● when a signal is detected), **Audio** (level).
- Known frequencies: 3,580.15 · 7,040.15 · 10,142.15 · 14,070.15 · 18,100.15 · 21,080.15 · 24,920.15 · 28,120.15 kHz.

## 10.5 Olivia

- **Mode** — number of tones / width: 8/250, 16/500, 32/1000, 16/1000. It must match the station being received.
- **Squelch (FEC S/N)** — below 3.5 noise starts printing; a good signal reads 8 to 9.
- Known frequencies: 20 m 14,072.5 (8/250) and 14,108.5 (32/1000), 80 m 3,583, 40 m 7,040 and 7,072.5, 12 m 24,922.5, 10 m 28,122.5 kHz…

## 10.6 MFSK, DominoEX, THOR, THROB, Hellschreiber, MT63

These modes all have two settings: a **Mode** (sub-mode, chosen to match the station being received) and a **Squelch** specific to each family. The **Centre**, **Mode** and **Audio** indicators follow reception.

| Variant | Sub-modes | Default |
| MFSK | MFSK16, MFSK32, MFSK64 | MFSK16 |
| DominoEX | Micro, 4, 5, 8, 11, 16, 22, 44, 88 | DominoEX 11 |
| THOR | Micro, 4, 5, 8, 11, 16, 22, 25 x4, 50 x1, 50 x2, 100 | THOR 16 |
| THROB | THROB 1, 2, 4 · THROBX 1, 2, 4 | THROB 2 |
| Hellschreiber | Feld Hell, Slow Hell, Hell X5, Hell X9, FSK Hell 245, FSK Hell 105, Hell 80 | Feld Hell |
| MT63 | 500, 1000, 2000 (short or long interleave) | MT63-1000 long |

> [Tip] In Hellschreiber the text is not decoded but **drawn**: you read it by eye, like a tape. Double-height text is normal.

## 10.7 Packet and APRS

- **Speed** — 1,200 baud (VHF) or 300 baud (HF); 1,200 / 2,200 Hz tones on VHF.
- **Show raw packet** — also shows the raw AX.25 frame.
- Indicators: **Frames** (valid frames received), **Stations** (number of different stations), **DCD**, **Audio**.
- In APRS, stations sending a position can be **shown on the map**.
- Known frequencies: 144.800 MHz (APRS Europe), 144.390 (North America), 145.175 (Australia), 144.640 (China), 144.660 (Japan), 145.825 MHz (ISS digipeater) and 10,147.6 kHz (HF APRS, 300 baud).

> [Tip] The VHF frequencies can only be used if ORSAT's receiver covers the 2 m band.

# 11. RADE (FreeDV digital voice)

RADE v1 is FreeDV's neural-network digital voice mode. It is not started from the decoders row but from the **RADEL** (LSB, for 160, 80 and 40 m) and **RADEU** (USB, for 20, 17, 15 and 10 m) buttons of the mode selector. Decoding is done **on the server**.

- **Green** light: synced, with the SNR; **yellow**: searching for a signal; **red**: the server's decoding service cannot be reached.
- Bandwidth: 1,500 Hz; the voice is rebuilt by the FARGAN vocoder.
- **📡 FreeDV Reporter** shows the list of FreeDV stations active worldwide (qso.freedv.org).

# 12. Identification aids

## 12.1 Digital signal analysis

The module, at the head of the decoders row, **tries to recognise the mode** of the signal being received (FT8, WSPR, RTTY, PSK, Olivia, CW…) and suggests the matching decoder. This feature is **experimental**.

![The “Digital signal analysis” module.](images/new_analyse.jpg){w=380}

- **Automatic analysis: OFF / ON** — the mode is usually recognised in about fifteen seconds.
- **Current measurement** — width, tone spacing, speed, cadence, signal-to-noise ratio.
- **Recognised modes, by relevance** — **▶** opens the matching decoder (with its settings), the **i** icon shows the mode's entry.
- **Recentre & retry** — appears when the signal is too close to the edge of the filter.

## 12.2 Identify a signal (Artemis database)

The signal database button searches **583 reference signals** for those matching the current frequency, filter width and demodulation, ranked by match percentage. Each entry gives a spectrogram, an **audio sample** to compare, the modulation, the frequency range and a link to the Signal Identification Wiki.

![The “Identify a signal” window.](images/new_identifier.jpg){w=440}

# 13. Troubleshooting

| Symptom | Likely cause | Remedy |
| No FT8 / FT4 / WSPR decodes | Wrong frequency or band closed | Use **Known frequencies**; check on the waterfall that signals are present |
| Few FT8 decodes, scattered DT | Time sync | Tick **Auto** next to Sync offset |
| CW unreadable | Several signals in the filter | Narrow CW filter, a single signal |
| FAX image slanted | Line sync | **⇔ Auto-align** |
| FAX image in negative | Polarity | **⇅ Invert** |
| SSTV: wrong colours or nothing | Wrong sideband or wrong mode | Change sideband; try a forced mode then **⏺ Force** |
| NAVTEX silent | Outside the slot | Wait for the station's slot (broadcast table) |
| RTTY: random characters | Mark / space swapped | Tick or untick **Invert mark / space** |
| RTTY: nothing printed | Squelch too high | Lower the **Squelch** |
| PSK31 / Olivia: broken text | Decoder off-centre | **⟳ Auto-tune Center** |
| HFDL: no messages | Propagation to the ground station | Try another frequency or another station |
| RADE: red light | Server service stopped | Tell the ORSAT administrator |

> [Tip] For any decoder, first check by ear and on the waterfall that a signal is really there and well centred: most failures come from approximate tuning.
