Backup System with Installation Script

This repository contains two main scripts:

Installation Script (installation_script.py):

Prepares the environment by installing necessary dependencies and tools.

Creates a virtual environment.

Installs required Python packages.

Optionally installs the Microsoft C++ Build Tools (on Windows) and Rust compiler (cross-platform) if needed.

Generates a convenience batch file (run_backup.bat) to launch the backup application easily (Windows only).

Backup Script (backup_script.py):

Provides a graphical user interface (GUI) to select or schedule folder backups.

Creates either an encrypted or unencrypted ZIP file of your chosen folder.

(Optional) Uploads the backup ZIP file to Google Drive.

(Optional) Schedules daily automatic backups.

Table of Contents

Prerequisites

Installation

Usage

Additional Notes

Contributing

License

Prerequisites

Windows Users:

Run the installation script as Administrator if you need the Microsoft C++ Build Tools.

Ensure you have an active internet connection (the installer might download external tools such as Build Tools and Rust).

macOS / Linux Users:

Python 3.6+ required.

The script will attempt to install Rust via rustup if needed.

If you already have Rust installed (and a suitable C++ toolchain), you can skip those parts.

Installation

Clone or Download this repository (see Usage > Cloning from GitHub).

Run the Installation Script First:

Open a terminal (or Command Prompt / PowerShell on Windows) in the directory containing installation_script.py.

On Windows:

Right-click and Run as Administrator if you plan to install the Microsoft C++ Build Tools.

Then run:

python installation_script.py

On macOS / Linux:

python3 installation_script.py

Follow the On-Screen Prompts:

The script will create a Python virtual environment in a folder called env.

It will install required packages:

pywin32, pyminizip, google-api-python-client, google-auth-httplib2, google-auth-oauthlib, cryptography, schedule

If on Windows and you do not already have the Microsoft C++ Build Tools installed, it will download and attempt to install them.

It will also check for Rust installation; if not found, it will download and install Rust (across platforms).

Finally, it creates a run_backup.bat file (on Windows) which you can use to quickly start the backup script.

Usage

Starting the Backup Application
After the installation completes, you have two primary ways to run the backup script:

On Windows (batch file)

Double-click run_backup.bat.

This batch file automatically activates the virtual environment and runs backup_script.py.

On Any OS (manually)

Navigate to the repository folder.

Activate the virtual environment manually:

Windows:

.\env\Scripts\activate

macOS / Linux:

source env/bin/activate

Run backup_script.py inside the activated virtual environment:

python backup_script.py

Using the Backup Script GUI
When the backup application (backup_script.py) starts:

Choose Options (checkboxes):

Choose Backup Storage Location: Lets you pick a destination folder for the backup.

Encrypt Backup with Password: If enabled, you’ll be prompted for a password to encrypt the resulting ZIP file.

Upload Backup to Google Drive: If enabled, you must supply Google Drive credentials (credentials.json) and/or authenticate via a browser.

Select Folder to Backup:

The script opens a folder selection dialog. Pick the folder you want to back up.

Backup Process:

The script confirms enough disk space.

Creates a ZIP file (encrypted or unencrypted, depending on your choice).

Optionally uploads to Google Drive.

A progress bar and status label keep you informed.

Schedule Daily Backup (optional):

The “Schedule Daily Backup” button schedules a backup every day at 02:00.

Keep this script (or a terminal session) running so that the scheduled backup can execute.

Additional Notes

If you plan to use Google Drive uploads, you must place a credentials.json file (OAuth client credentials for the Google Drive API) in the same directory as the scripts.

The script will create (or update) token.pickle after your first sign-in, so subsequent backups won’t require re-authentication unless the token expires or is revoked.

On Windows, if you see any prompts from the Microsoft Visual C++ Build Tools installer, follow them, or let the script proceed with a silent install.

You can safely remove the vs_buildtools.exe installer or rustup-init.exe after everything finishes, if space is a concern.