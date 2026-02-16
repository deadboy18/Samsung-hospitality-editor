<img width="1536" height="1024" alt="SamsungEditorLogo" src="https://github.com/user-attachments/assets/342f9428-fb6c-40d6-81f1-3341759cf45a" />

# Samsung Hospitality TV Channel Editor

A powerful, open-source tool to reverse engineer and manage channel lists for Samsung Hospitality TVs. This tool allows IT managers and administrators to sort, rename, and bulk-edit channel maps via CSV, bypassing the tedious on-screen menu editing process.

It also includes a guide and backup files for using a USB/Type-C IR Blaster to automate the hidden "Hotel Menu" access code.

---

## Screenshots

| Main Interface | CSV Export Example |
|:--:|:--:|
| <img src="https://github.com/user-attachments/assets/104b122b-7550-4a8f-9a0e-db87ff320674" width="520" alt="Main GUI" /> | <img src="https://github.com/user-attachments/assets/f16f822c-8070-40b1-b00e-cea5b0d1da61" width="260" alt="CSV Excel" /> |
| *The Channel Editor Dashboard* | *Bulk Editing in Excel* |

---

## Features

* **Parse & Edit Binary Maps:** Decodes the proprietary `map-AirD` (Digital) and `map-AirA` (Analog) binary files.
* **CSV Import/Export:** Export your channel list to Excel, use "Flash Fill" to renumber/rename 500+ channels instantly, and import it back.
* **Automatic Backup:** Creates a timestamped `.bak` file before saving any changes to prevent data loss.
* **Hardware Detection:** Auto-detects TV Model, Firmware Version, and Panel Type from `ProductCloneInfo` and `FADAT` files.
* **Safe Mode:** Validates channel data to prevent corrupting the channel list.

---

## Tested Models

This tool has been verified to work on the following Samsung Hospitality models:

1. **Samsung HG32AB670** (HB670 Series)
* [Official Support Page](https://www.samsung.com/my/support/model/HG32AB670BWXXM/)


2. **Samsung HG32AC470** (HC470 Series)
* [Official Support Page](https://www.samsung.com/au/support/model/HG32AC470GWXXY/)



*Note: It likely works on most Samsung TVs that use the `T-NT14L` or similar firmware structure (Clone.dat file system).*

---

## Installation & Usage

### 1. Requirements

* A PC with **Python 3.x** installed.
* A USB Flash Drive (FAT32 formatted recommended).
* Samsung Hospitality TV.

### 2. Extracting Files from TV (Cloning)

To edit the channels, you first need to dump the TV's system files to a USB drive.

1. Turn the TV **ON**.
2. Insert your USB Drive.
3. Enter the **Hidden Hotel Menu** by pressing this sequence on the remote:
`[MUTE] -> [1] -> [1] -> [9] -> [ENTER]`
4. Select **"Clone TV to USB"** and press Enter.
5. Wait for the "Success" message, then remove the USB.

<img width="688" height="652" alt="image" src="https://github.com/user-attachments/assets/f09f2a2b-69f5-4d84-a31a-5f5c8c8036c6" />



### 3. Editing on PC

1. Clone this repository:
```bash
git clone https://github.com/your-username/samsung-hospitality-editor.git
cd samsung-hospitality-editor

```


2. Run the script:
```bash
python SamsungEditor.py

```


3. Click **Open Map** and navigate to your USB drive.
* Go to: `T-NT14LDEUCB\Clone` (Folder name varies by model).
* Select **`map-AirD`** (This is the Digital Channel Map).


4. **Edit your channels:**
* Double-click to rename or renumber single channels.
* **Recommended:** Click **Export CSV**, edit the list in Excel, save it, and click **Import CSV**.


5. Click **Save Map**.

### 4. Flashing Back to TV

1. Insert the modified USB drive back into the TV.
2. Enter the Hotel Menu again (`Mute 1 1 9 Enter`).
3. Select **"Clone USB to TV"**.
4. The TV will apply the new channel list and reboot.

---

## IR Blaster Automation (Easy Access)

Entering `Mute+1+1+9+Enter` manually on every TV is slow. I use a Type-C IR Blaster with a custom macro to do this instantly.

### Setup

* **Hardware:** Tiqiaa / Type-C USB IR Blaster.
* **Software:** [IR Blaster TV Universal Remote](https://play.google.com/store/apps/details?id=org.nslabs.ir_blaster) (Android).
* **App Source:** [GitHub - android-ir-blaster](https://github.com/iodn/android-ir-blaster).

### How to use the Profile

I have uploaded my custom IR backup file (`IR_Blaster_Backup`) to this repo.

1. Download the app on your Android phone.
2. Import my backup file.
3. Use the **"Hotel Menu"** macro button.
* *Action:* Sends `MUTE` + `1` + `1` + `9` + `ENTER` in a rapid sequence.


4. For PC/Windows usage of this IR blaster, check my other repo: [Tiqiaa-USB-IR-Windows](https://github.com/deadboy18/Tiqiaa-USB-IR-Windows).

---

## Technical Deep Dive & Reverse Engineering Guide

For developers looking to adapt this tool for other Samsung TV models (e.g., Tizen-based H-Browser models), here is the methodology we used to reverse-engineer the `T-NT14L` firmware format.

### 1. The "Binary Diff" Method

To find where specific settings (like Channel Names) were stored, we used the "Difference" technique:

1. **Baseline:** We exported a "Clone" to USB with a channel named "BBC World".
2. **Modification:** On the TV, we renamed that single channel to "BBC News" and exported a second Clone.
3. **Comparison:** We compared the two `map-AirD` files in a Hex Editor.
* *Result:* The only bytes that changed were at offset `65` inside a block. This confirmed the location of the Name String.



### 2. Identifying Record Structures

We noticed the file size was perfectly divisible by the number of channels.

* *Total File Size:* 32,000 bytes.
* *Total Channels:* 100.
* *Calculated Record Size:* 320 bytes per channel.

By viewing the file in a Hex Editor with a **row width of 320**, patterns emerged vertically. We could clearly see the "Channel Number" (Byte 0) incrementing by 1 in every row, confirming the structure.

### 3. The Checksum "Gatekeeper"

Initially, the TV rejected our modified files with an "Invalid File" error. This indicated a checksum protection.

* **Hypothesis:** Samsung often uses a simple `Sum Modulo 256` or `CRC32` at the end of a record.
* **Test:** We summed the values of the first 319 bytes of a valid record.
* **Result:** The sum (modulo 256) perfectly matched the value at Byte 319.
* **Fix:** The script now automatically recalculates and writes this byte before saving, allowing the TV to accept the modified file.

### 4. Hardware Detection Logic

To automatically detect the TV Model and Panel Type, the tool parses two auxiliary files found in the Clone folder:

* **`ProductCloneInfo`**: A simple text file containing the Model Number and Firmware Version.
* **`FADAT`**: A binary file containing Factory Adjustment Data. We found the Panel Code (e.g., `32S6` for 32-inch, Series 6) stored as an ASCII string within this binary blob.

### 5. File Protocol Specification (`map-AirD`)

If you are writing your own parser, here is the structure for the `T-NT14L` firmware:

| Offset | Length | Type | Description |
| --- | --- | --- | --- |
| **0x00** | 2 Bytes | `uint16_le` | **Channel Number** (e.g., 101 = `65 00`) |
| **0x02** | 2 Bytes | `uint16_le` | **Major Number** (DTV) |
| **0x04** | 2 Bytes | `uint16_le` | **Minor Number** (DTV) |
| **0x41** | 100 Bytes | `utf16_le` | **Channel Name** (Padded with `00`) |
| **0x13F** | 1 Byte | `uint8` | **Checksum** (Sum of 0x00 to 0x13E % 256) |

*Note: Offsets 0x06 to 0x40 contain frequency, bandwidth, and PLP IDs, which we left untouched to ensure signal stability.*

---

## Disclaimer

This software is provided "as is", without warranty of any kind. I am not responsible for any damage to your TV. Always use the **Clone TV to USB** feature to make a full backup before editing files.

---

## License

MIT License. Feel free to fork and improve!
