---
pdf: guideDiversiteEN.pdf
pdf_title: PhantomSDR-ORSAT — Receive diversity guide
title: Receive diversity
subtitle: Detailed guide — the principle, choosing a partner, reading the indicators
url: https://orsat.ddns.net
cover: div_principe_en.png
cover_caption: Two distant receivers do not hear the same fades: ORSAT switches, moment by moment, to the better of the two.
summary: This guide explains why a shortwave signal fades, how a second receiver located elsewhere lets you ride through those fades, and how to use ORSAT's “Receive Diversity” panel step by step.
edition: English version — October 2026 edition — ORSAT 1.0
credits: Receive diversity method inspired by **AetherSDR**, adapted and documented by **F1NSK** for ORSAT.
header_left: ORSAT — Receive diversity
header_right: ORSAT 1.0
page: Page
toc: Contents
cover_note: The screenshots show the interface in French; the button names in the text are those of the English interface.
---

# 1. The problem: QSB

## 1.1 Why a signal fades

On shortwave, the signal of a distant station does not reach you in a straight line: it bounces off the **ionosphere**, a layer of the atmosphere that never stops moving. It often arrives by **several slightly different paths at once**. Those paths add up, sometimes reinforcing each other, sometimes cancelling out.

The result: the signal **rises and falls** every few seconds. This is **QSB**, or fading. At the bottom of a fade the station can vanish completely for a second or two, just long enough to lose a callsign or a report.

## 1.2 What a single receiver cannot do

Turning up the volume, changing the filter or switching on noise reduction changes nothing: when the signal cancels out **where the antenna is**, there is nothing left to amplify. The only remedy is to listen **somewhere else**.

# 2. The solution: listen in two places

## 2.1 The principle

![Two distant receivers hear the same station over two different paths. Their fades do not happen at the same moment: ORSAT follows, moment by moment, whichever of the two receives better.](images/div_principe_en.png){w=482}

Two receivers several hundred kilometres apart hear the same station over **two different ionospheric paths**. Their fades are **independent**: when the signal dips at ORSAT, it is usually fine at the other receiver, and the other way round.

Receive diversity connects ORSAT to **a second web receiver located elsewhere**, on the **same frequency**, and lets you hear **the better of the two** at every moment. The dips of one are filled in by the other: the station stays readable where, with a single receiver, it would have disappeared.

> [Tip] The gain is measured in **continuity** rather than strength: diversity does not make the signal louder, it stops it from disappearing.

## 2.2 Why choose rather than add

You might think adding the two sounds together would be even better. In fact the two paths have different phase and a slightly different frequency offset: added together, the two sounds give a **hollow, metallic** voice, as if spoken down a pipe. Clean adding would need two receivers locked to the same clock, which is impossible between two sites linked over the internet.

ORSAT therefore **chooses** between the two (this is called *selection combining*). When it switches from one to the other, it makes a **30-millisecond crossfade**, too short to be heard: there is no audible break.

## 2.3 How ORSAT decides

- It continuously measures the **signal-to-noise ratio (SNR)** of both receivers.
- It only switches if the other receiver is **better by at least 2.5 dB**, and only if the current one has held for **at least 0.4 second**. This avoids jumping back and forth on every syllable.
- If the current receiver **collapses** (below 6 dB for half a second), it switches without waiting.
- If the remote receiver **stops responding** for 1.5 seconds, ORSAT falls straight back on itself. **Diversity never cuts the sound**: at worst you hear ORSAT alone, as usual.

# 3. The delay between the two receivers

## 3.1 Why alignment is needed

The remote receiver's audio does not reach you at the same moment as ORSAT's: each receiver has its own buffers, and the internet path adds its own delay. The gap is usually between a few tenths of a second and 1.5 seconds, and can be up to 4 seconds.

Without correction, switching from one receiver to the other would **skip or repeat** part of a sentence. ORSAT must therefore first measure that exact delay.

## 3.2 How it is measured

ORSAT compares the **rhythm of speech** in the two sounds: the sequence of syllables and pauses, which stays recognisable despite the different paths and audio compression. It looks for the offset that makes the two rhythms line up.

- It first searches a **±1.5-second** window (about 9 seconds of listening), which is nearly always enough, then widens to **±4 seconds** if needed.
- It waits for **two successive measurements to agree** within 40 milliseconds before declaring itself aligned.
- Once aligned, it **re-checks the delay every minute**, since the clocks of the two sites drift very slowly.

Allow **10 to 20 seconds** between pressing **▶ Start** and diversity being operational. **Someone must be talking** during that time: on a bare carrier or an empty frequency there is no rhythm to compare.

> [Tip] Once aligned, the sound you hear is about **0.3 second behind** ORSAT alone. That is the price of the margin that allows smooth switching; when listening, you do not notice it.

# 4. Using the panel step by step

## 4.1 The panel

The **Diversity reception** panel is in the middle column, below fine tuning. Its gold bar shows the state in plain words; click **Open ▸** to unfold it.

![The panel bar, folded: title, state and Open button.](images/en_div_ferme.jpg){w=330}

![The unfolded panel: the partners offered and the start button.](images/en_div_ouvert.jpg){w=330}

## 4.2 Starting

1. **Tune ORSAT first** to the station you want to hear, in the right mode.
2. **Choose a partner receiver** by clicking its card: it gets a gold outline. Preferably the one carrying the **★ Recommended** badge (section 5).
3. Click the large green **▶ Start with…** button.
4. Wait: the state goes from **Synchronising…** to **Running** when diversity is operational.

**There is nothing to set on the partner.** ORSAT tunes it automatically to the same frequency, mode and filter, and follows every tuning change.

To stop, click **■ Stop diversity**: you are instantly back to ORSAT alone. Your browser remembers your last partner for next time.

## 4.3 While listening

Below the button, the **3. Listen** part shows what is happening:

- **🎧 You are hearing: ORSAT** (green) or **the partner's name** (blue) — the receiver you hear at this moment.
- **The state in plain words** — “Synchronising the two receivers…”, then “Synchronised ✓ — the best signal is picked continuously”; in red, “The partner does not answer” with the reason.
- **Two signal quality bars**, ORSAT and partner, with their signal-to-noise ratio in dB; the green bar is the receiver being used.
- **The share of time** spent on the partner and the **number of switches** since starting.

## 4.4 The state in the panel bar

| State | Meaning |
| ● Off (grey) | Diversity stopped |
| ● Synchronising… (amber) | Connecting or aligning |
| ● Running, green dot | Aligned, you are hearing **ORSAT** |
| ● Running, blue dot | Aligned, you are hearing **the partner** |
| ● Error (red) | The partner no longer answers: you hear ORSAT alone |

Listening to a fluctuating station, you will see the dot switch between green and blue with the fades: that is diversity at work.

## 4.5 Technical details

While listening, **▸ Technical details** unfolds a table for the curious:

| Indicator | What it says |
| link | State of the connection to the partner (connecting, ready, closed, error) and the reason for a disconnection |
| delay | Measured offset between the two sounds, in seconds; “searching” until it is found |
| correlation | Similarity of the two sounds once aligned: the higher, the surer the alignment |
| remote audio | Amount of sound received from the partner and its sample rate; “none” means it sends nothing |
| ORSAT SNR / partner SNR | Signal-to-noise ratio of each receiver, in dB, on which the choice is made |
| trim | Correction added to the partner's SNR, set by the sysop (see section 6) |
| switches | Number of changes from one receiver to the other since starting |

If the message **“This partner does not receive this frequency”** appears, choose another one.

# 5. The recommended partner

## 5.1 What the badges say

Each card carries a badge that applies **to the band you are tuned to**; it changes when you change band.

| Badge | Meaning |
| ★ Recommended on 40m | The best partner right now on this band |
| Possible · 41 % | Partly useful: it hears about this percentage of the area ORSAT hears |
| Of little use on 40m | It does not hear the same stations as ORSAT on this band right now |
| Offline | The receiver does not answer; its card is greyed out |

Hover a badge to read the full explanation. No badge means the server has no advice yet (at start-up, or a partner without a known locator).

## 5.2 How the advice is computed

A good partner is not necessarily the one receiving the loudest: it is the one hearing **the same stations as ORSAT, along another path**. A receiver that hears another region very well brings nothing.

- Every 10 minutes, the ORSAT server computes, from **ionosondes** worldwide (KC2G network), the area ORSAT hears on each band, up to 3000 km.
- It makes the same computation **from each partner's locator**, and measures the share of ORSAT's area that the partner hears too: that is the badge percentage.
- It takes the **distance** between the two receivers into account: under 100 km their fades are linked and diversity is useless; from 300 km they are independent.
- Every 10 minutes it also checks that each partner **answers**: an offline receiver is never recommended.

Example: on 40 m in daytime, ORSAT mostly hears France, within 900 km. A partner in Belgium then hears another area and will be “Of little use”; in the evening, when 40 m opens to long distance, it becomes an excellent partner again.

> [Note] This advice is computed separately: it never enters ORSAT's **performance index** shown above the waterfall.

# 6. The partners offered

The partners are **chosen by the ORSAT sysop** in the administration panel: reliable receivers at a good distance, each with the **SNR correction** that balances the comparison (a receiver that compresses its sound heavily seems noisier than it is). So there is no address to type and nothing to set.

Each card shows the country **flag**, the receiver's **name** and **callsign**, its **place** and **distance** from ORSAT, its **locator** and its **bearing** from ORSAT.

Some receivers (often KiwiSDRs) can only be reached over **http**, which a browser refuses from a secure https page. In that case the connection goes automatically through the **ORSAT server**, acting as a relay: there is nothing to do. The partner then sees the ORSAT server's address, not yours.

# 7. What diversity does not do

- **It only feeds the speaker.** The decoders (FT8, CW, RTTY…) keep using **ORSAT alone**: a change of receiver mid-slot would break decoding that needs continuous audio.
- **It does not replace a good antenna.** If neither receiver hears the station, diversity cannot help.
- **It does not mix the two sounds**, except during the 30 ms crossfades (see section 2.2).
- **It cannot align on an unmodulated signal**: it needs a voice, Morse or any signal that varies over time.

# 8. Troubleshooting

| Symptom | Probable cause | Remedy |
| Stays on “Synchronising…” | Nobody is talking, or the partner does not hear the station | Wait for a transmission; try the recommended partner |
| “Error” state, “The partner does not answer” | Receiver offline or full | Choose another partner; avoid “Offline” cards |
| remote audio: none | The partner accepts the connection but sends no sound | Try another partner |
| “does not receive this frequency” | The partner does not cover this band | Choose another partner |
| Always on ORSAT, 0 switches | ORSAT is better right now | Normal: diversity only uses the partner when it does better |
| Constant switching | The two receivers are equivalent | Harmless to listening |
| A word repeated or skipped at a switch | Alignment being readjusted | Corrects itself at the next check (one minute at most) |
| No badge on the cards | The server has not computed yet, or the partner has no locator | Wait a few minutes; you can still choose without a badge |

> [Tip] When in doubt, click **■ Stop diversity**: the sound returns immediately to ORSAT alone, with no consequence.
