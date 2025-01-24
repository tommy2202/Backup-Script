import os
import shutil
import zipfile
import logging
import traceback
from datetime import datetime
from tkinter import (
    Tk, filedialog, messagebox, Button, Label,
    ttk, BooleanVar, Checkbutton, simpledialog
)
import threading
import schedule
import time
import platform
import pyminizip
import pickle

# Google Drive imports
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


##############################################################################
# CONFIGURE LOGGING
##############################################################################

logging.basicConfig(
    filename='backup.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

SCOPES = ['https://www.googleapis.com/auth/drive.file']


##############################################################################
# UTILITY & ERROR LOGGING
##############################################################################

def log_exception(e):
    """Logs the exception details including the traceback."""
    logging.error(f"Exception occurred: {e}")
    logging.error(traceback.format_exc())


##############################################################################
# GOOGLE DRIVE AUTH (MAIN THREAD)
##############################################################################

# We'll store the Google Drive credentials here once we authenticate
G_DRIVE_CREDS = None

def ensure_google_drive_credentials():
    """
    Checks if we already have valid Google Drive credentials (token.pickle).
    If not or expired, runs the OAuth flow in the main thread, which will:
      - Open a browser window
      - Let user sign in (with 2FA if enabled)
    Saves the token in token.pickle for future runs.
    Returns the credentials object or None on failure.
    """
    global G_DRIVE_CREDS

    # If we already have G_DRIVE_CREDS in memory and they're valid, just return
    if G_DRIVE_CREDS and G_DRIVE_CREDS.valid:
        logging.info("Reusing in-memory Google Drive credentials.")
        return G_DRIVE_CREDS

    creds = None
    # The file token.pickle stores the user's access and refresh tokens.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                log_exception(e)
                creds = None

        # If still no valid creds, run the login flow
        if not creds:
            if not os.path.exists('credentials.json'):
                messagebox.showerror(
                    "Credentials Missing",
                    "Google Drive credentials not found.\n"
                    "Please place 'credentials.json' in the script directory."
                )
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                # This starts a local server on some port and opens a browser for login
                creds = flow.run_local_server(port=0)
            except Exception as e:
                log_exception(e)
                messagebox.showerror("Authentication Error", f"Failed Google OAuth flow:\n{e}")
                return None

        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # If we reach here, we have valid creds
    G_DRIVE_CREDS = creds
    logging.info("Authenticated with Google Drive successfully.")
    return G_DRIVE_CREDS


##############################################################################
# FILE / FOLDER UTILS
##############################################################################

def get_folder_size(folder_path):
    """Calculates the total size of the folder in bytes."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
            except Exception as e:
                log_exception(e)
    return total_size

def get_available_space(destination):
    """Returns the available disk space in bytes for the destination."""
    try:
        total, used, free = shutil.disk_usage(destination)
        return free
    except Exception as e:
        log_exception(e)
        return 0

def confirm_space(source_folder, backup_destination):
    """Confirms if there's enough space in the backup destination."""
    source_size = get_folder_size(source_folder)
    available_space = get_available_space(backup_destination)
    logging.info(f"Source folder size: {source_size} bytes")
    logging.info(f"Available space at destination: {available_space} bytes")

    if available_space < source_size:
        messagebox.showerror(
            "Insufficient Space",
            f"Not enough space in the backup destination.\n\n"
            f"Required: {source_size / (1024**3):.2f} GB\n"
            f"Available: {available_space / (1024**3):.2f} GB"
        )
        return False
    else:
        user_confirm = messagebox.askyesno(
            "Confirm Backup",
            f"The backup will require approximately {source_size / (1024**3):.2f} GB of space.\n"
            f"Available space: {available_space / (1024**3):.2f} GB.\n\n"
            f"Do you want to proceed?"
        )
        return user_confirm

def is_different_drive(source, destination):
    """Checks if the source and destination are on different drives."""
    try:
        system = platform.system()
        if system == "Windows":
            source_drive = os.path.splitdrive(os.path.abspath(source))[0].lower()
            destination_drive = os.path.splitdrive(os.path.abspath(destination))[0].lower()
            return source_drive != destination_drive
        else:
            # On Unix-like systems, comparing root directories might not be sufficient
            return os.path.abspath(source).split(os.sep)[1] != os.path.abspath(destination).split(os.sep)[1]
    except Exception as e:
        log_exception(e)
        return False


##############################################################################
# ZIP & ENCRYPTION
##############################################################################

def create_zip_backup(source_folder, backup_destination, progress_callback=None):
    """
    Creates a non-encrypted ZIP backup of the source_folder in the backup_destination.
    progress_callback(current, total) can be used to update a progress bar.
    """
    folder_name = os.path.basename(source_folder.rstrip(os.sep))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{folder_name}_backup_{timestamp}.zip"
    zip_path = os.path.join(backup_destination, zip_filename)
    logging.info(f"Creating ZIP archive: {zip_path}")

    total_files = sum(len(files) for _, _, files in os.walk(source_folder))
    current_file = 0

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
        for root_dir, dirs, files in os.walk(source_folder):
            for f in files:
                file_path = os.path.join(root_dir, f)
                try:
                    backup_zip.write(file_path, os.path.relpath(file_path, source_folder))
                    logging.debug(f"Added {file_path} to ZIP.")
                except Exception as e:
                    log_exception(e)
                    logging.warning(f"Failed to add {file_path} to ZIP.")
                finally:
                    current_file += 1
                    if progress_callback:
                        progress_callback(current_file, total_files)

    logging.info(f"Backup created successfully at {zip_path}")
    return zip_path

def create_encrypted_zip(source_folder, backup_destination, password, progress_callback=None):
    """
    Creates an encrypted ZIP backup of the source_folder in the backup_destination using pyminizip.
    progress_callback(current, total) can be used to update a progress bar (pyminizip doesn't natively support progress).
    """
    folder_name = os.path.basename(source_folder.rstrip(os.sep))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{folder_name}_backup_{timestamp}.zip"
    zip_path = os.path.join(backup_destination, zip_filename)
    logging.info(f"Creating encrypted ZIP archive: {zip_path}")

    # Collect all file paths
    file_paths = []
    for root_dir, dirs, files in os.walk(source_folder):
        for f in files:
            file_paths.append(os.path.join(root_dir, f))

    # pyminizip doesn't have built-in progress callback, so we can only do a naive approach
    # or skip progress updates. We'll skip it here for simplicity.
    compression_level = 5
    pyminizip.compress_multiple(
        file_paths,
        [source_folder]*len(file_paths),
        zip_path,
        password,
        compression_level
    )

    logging.info(f"Encrypted backup created successfully at {zip_path}")
    return zip_path


##############################################################################
# GOOGLE DRIVE UPLOAD
##############################################################################

def upload_to_google_drive(creds, file_path, folder_id=None):
    """
    Uploads a file to Google Drive using existing OAuth credentials.
    If folder_id is specified, the file is placed in that Drive folder.
    """
    try:
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': os.path.basename(file_path)}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        media = MediaFileUpload(file_path, mimetype='application/zip')
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        logging.info(f"Uploaded {file_path} to Google Drive (File ID: {file.get('id')})")
    except Exception as e:
        log_exception(e)
        messagebox.showerror("Upload Error", f"Failed to upload {file_path} to Google Drive:\n{e}")


##############################################################################
# BACKGROUND THREAD: PERFORM BACKUP & UPLOAD
##############################################################################

def background_backup_task(
    source_folder, backup_destination,
    encrypt, password, do_upload, creds,
    update_progress, update_status
):
    """
    This function runs in a background thread:
      - Creates the ZIP (encrypted or not).
      - Optionally uploads to Google Drive using 'creds'.
    'update_progress(current, total)' and 'update_status(text)' are callbacks
    to update the GUI in a thread-safe manner (usually via root.after).
    """

    try:
        update_status("Creating Backup...")
        if encrypt and password:
            # create_encrypted_zip doesn't provide per-file callback, so no progress updates
            zip_path = create_encrypted_zip(
                source_folder, backup_destination, password
            )
        else:
            # We can pass a progress callback so we can update the progress bar
            def on_progress(current, total):
                update_progress(current, total)

            zip_path = create_zip_backup(
                source_folder, backup_destination, progress_callback=on_progress
            )

        update_status("Backup Completed")

        if do_upload and creds:
            update_status("Uploading to Google Drive...")
            upload_to_google_drive(creds, zip_path)
            update_status("Upload Completed")

        messagebox.showinfo("Success", f"Backup (and upload) finished.\n\n{zip_path}")
    except Exception as e:
        log_exception(e)
        messagebox.showerror("Error", f"An error occurred in the background backup:\n{e}")
        update_status("Error")


##############################################################################
# MAIN THREAD: USER INTERFACE / DIALOGS
##############################################################################

def on_backup_button(root, encrypt, upload, choose_storage):
    """
    Called on main thread when user clicks "Select Folder to Backup".
    1. All user interaction (folder dialogs, confirm dialogs, password prompts, drive auth) happens here.
    2. Then we start a background thread for the actual backup/zip/upload.
    """

    # 1. Ask user for source folder
    logging.info("Opening folder selection dialog.")
    source_folder = filedialog.askdirectory()
    if not source_folder:
        logging.warning("No folder was selected.")
        messagebox.showwarning("Selection Error", "No folder was selected.")
        return

    # 2. Confirm selection
    confirm = messagebox.askyesno(
        "Confirm Selection",
        f"Do you want to back up the folder:\n{source_folder}?"
    )
    if not confirm:
        logging.info("User canceled the folder selection.")
        return

    # 3. Decide how to pick backup destination
    if choose_storage:
        # let the user pick
        backup_destination = filedialog.askdirectory(title="Select Backup Destination")
        if not backup_destination:
            logging.warning("No backup destination was selected.")
            messagebox.showwarning("Selection Error", "No backup destination was selected.")
            return

        # Optional check if on same drive
        if not is_different_drive(source_folder, backup_destination):
            messagebox.showwarning(
                "Selection Warning",
                "The backup destination is on the same drive as the source folder.\n"
                "It's recommended to choose a different drive to prevent data loss."
            )
    else:
        # use default "backup_storage" folder
        backup_destination = os.path.join(os.getcwd(), "backup_storage")
        os.makedirs(backup_destination, exist_ok=True)
        logging.info(f"Using default backup location: {backup_destination}")

    # 4. Confirm enough space
    if not confirm_space(source_folder, backup_destination):
        return

    # 5. If encryption is checked, prompt for password (on main thread)
    password = None
    if encrypt:
        password = simpledialog.askstring("Password", "Enter a password for the backup ZIP file:", show='*')
        if not password:
            messagebox.showerror("Password Required", "A password is required to create an encrypted backup.")
            return

    # 6. If Google Drive upload is checked, ensure we have valid credentials
    creds = None
    if upload:
        creds = ensure_google_drive_credentials()
        if not creds:
            # user canceled or authentication failed
            return

    # 7. Start the background thread for the actual backup
    # We'll define a couple helper functions so we can safely update the GUI
    def update_progress(current, total):
        # use root.after to update the progress bar from the background
        def _set_progress():
            if total > 0:
                pct = (current / total) * 100
                root.progress['value'] = pct
        root.after(0, _set_progress)

    def update_status(text):
        def _set_status():
            root.status_label.config(text=f"Status: {text}")
        root.after(0, _set_status)

    root.status_label.config(text="Status: Starting background backup...")
    threading.Thread(
        target=background_backup_task,
        args=(
            source_folder, backup_destination,
            encrypt, password, upload, creds,
            update_progress, update_status
        ),
        daemon=True
    ).start()

def on_schedule_backup_button(root, encrypt, upload, choose_storage):
    """
    Similar to on_backup_button but for scheduling.
    We'll gather all info on main thread, then schedule a background job.
    """
    # 1. Ask user for source folder
    source_folder = filedialog.askdirectory()
    if not source_folder:
        return

    # 2. Confirm selection
    confirm = messagebox.askyesno(
        "Confirm Selection",
        f"Do you want to back up the folder:\n{source_folder}?"
    )
    if not confirm:
        return

    # 3. Decide backup destination
    if choose_storage:
        backup_destination = filedialog.askdirectory(title="Select Backup Destination")
        if not backup_destination:
            return
        if not is_different_drive(source_folder, backup_destination):
            messagebox.showwarning(
                "Selection Warning",
                "Destination is on the same drive as the source."
            )
    else:
        backup_destination = os.path.join(os.getcwd(), "backup_storage")
        os.makedirs(backup_destination, exist_ok=True)

    # 4. Confirm space
    if not confirm_space(source_folder, backup_destination):
        return

    # 5. Encryption password if needed
    password = None
    if encrypt:
        password = simpledialog.askstring("Password", "Enter a password for the backup ZIP file:", show='*')
        if not password:
            return

    # 6. Google Drive if needed
    creds = None
    if upload:
        creds = ensure_google_drive_credentials()
        if not creds:
            return

    # 7. Schedule the backup
    def scheduled_job():
        try:
            # no user prompts here (background)
            background_backup_task(
                source_folder, backup_destination,
                encrypt, password, upload, creds,
                lambda c, t: None,  # no progress updates in scheduled
                lambda txt: None
            )
        except Exception as e:
            log_exception(e)

    # For simplicity, schedule daily at 02:00
    schedule.every().day.at("02:00").do(scheduled_job)
    messagebox.showinfo("Scheduled", "Backup scheduled daily at 02:00.\nLeave this script running.")
    
    def run_schedule_loop():
        while True:
            schedule.run_pending()
            time.sleep(1)

    # Start a background thread that runs the schedule loop
    threading.Thread(target=run_schedule_loop, daemon=True).start()


##############################################################################
# GUI SETUP
##############################################################################

def setup_gui():
    """Sets up the GUI for the backup application."""
    logging.info("Setting up the GUI.")
    root = Tk()
    root.title("Backup System")
    root.geometry("600x600")
    root.resizable(False, False)

    label = Label(root, text="Backup System", font=("Helvetica", 16))
    label.pack(pady=10)

    # Checkboxes: Choose Storage, Encrypt, Upload
    choose_storage_var = BooleanVar(value=True)
    choose_storage_checkbox = Checkbutton(
        root,
        text="Choose Backup Storage Location",
        variable=choose_storage_var
    )
    choose_storage_checkbox.pack(pady=5)

    encrypt_var = BooleanVar()
    encrypt_checkbox = Checkbutton(
        root, text="Encrypt Backup with Password", variable=encrypt_var
    )
    encrypt_checkbox.pack(pady=5)

    upload_var = BooleanVar()
    upload_checkbox = Checkbutton(
        root, text="Upload Backup to Google Drive", variable=upload_var
    )
    upload_checkbox.pack(pady=5)

    progress = ttk.Progressbar(root, orient='horizontal', length=500, mode='determinate')
    progress.pack(pady=10)

    status_label = Label(root, text="Status: Idle", font=("Helvetica", 10))
    status_label.pack(pady=5)

    # Backup Button
    backup_button = Button(
        root,
        text="Select Folder to Backup",
        command=lambda: on_backup_button(
            root,
            encrypt_var.get(),
            upload_var.get(),
            choose_storage_var.get()
        ),
        width=25,
        height=2
    )
    backup_button.pack(pady=10)

    # Schedule Backup Button
    schedule_button = Button(
        root,
        text="Schedule Daily Backup",
        command=lambda: on_schedule_backup_button(
            root,
            encrypt_var.get(),
            upload_var.get(),
            choose_storage_var.get()
        ),
        width=25,
        height=2
    )
    schedule_button.pack(pady=10)

    # Attach references
    root.progress = progress
    root.status_label = status_label

    # Exit Button
    exit_button = Button(root, text="Exit", command=root.quit, width=10)
    exit_button.pack(pady=10)

    logging.info("GUI setup complete. Starting main loop.")
    root.mainloop()


##############################################################################
# MAIN ENTRY POINT
##############################################################################

if __name__ == "__main__":
    setup_gui()
