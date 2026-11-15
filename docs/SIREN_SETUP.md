# The Siren: setup and test sheet

The Siren is a Chrome extension. It shows FaZe lore on YouTube and Twitch videos and lets a fan collect relics.

## Before you start
- The API must be running on http://127.0.0.1:8080 (`bash setup/dev.sh` on macOS/Linux, `setup\dev.ps1` on Windows).
- Use Google Chrome (or any Chromium browser that supports side panels).

## Install (once)
1. Open `chrome://extensions`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and choose the `extension` folder in the repo.
4. Pin **The Siren** from the puzzle icon so the side panel button is visible.

## Check the settings
1. Open the Siren side panel and click the ⚙ icon.
2. API base should be `http://127.0.0.1:8080`. Web base should be `http://localhost:3000`.
3. Fan should be `demo_odysseus` (the seeded demo fan).
4. Click **Save**.

## Test the flow
1. Open a FaZe video on YouTube.
2. The side panel should show the lore for the current moment and the era.
3. Click **Collect Relic**. A toast shows "Relic collected" and the Drachmae reward.
4. Click **Collect Relic** again. It should say you already hold it.
5. Under the relic, the hint "Next to find" should show a relic you don't have yet.
6. Click **Ask the Bard about this** to open the Hub's Bard page.

## If something is wrong
- **Side panel is empty:** the API isn't running. Check http://127.0.0.1:8080/health.
- **No lore for a FaZe video:** the video isn't in the lore data yet. The team has to add its video ID.
- **Collect does nothing:** check the settings (fan and API base), then reload the extension from `chrome://extensions`.
- **Changes don't show:** after editing the extension files, click the reload icon on the extension card.

## Twitch (optional)
- Open a FaZe Twitch channel. The side panel uses the same lore check.
- For the Bow Trial overlay in OBS, add a **Browser Source** with the URL `http://127.0.0.1:8080/twitch/overlay`, set it to transparent.
