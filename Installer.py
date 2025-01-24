import sys
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import os
import urllib.request
import shutil
import platform
import threading
import ctypes

# ------------------------------------------------------------------------
# 0. Configuration & Constants
# ------------------------------------------------------------------------

BUILD_TOOLS_URL = "https://aka.ms/vs/17/release/vs_buildtools.exe"
BUILD_TOOLS_FILENAME = "vs_buildtools.exe"
BUILD_TOOLS_PATH = os.path.join(os.getcwd(), BUILD_TOOLS_FILENAME)

# Official Rust “rustup-init” endpoints
RUSTUP_EXE_64_WIN = "https://win.rustup.rs/x86_64"
RUSTUP_EXE_32_WIN = "https://win.rustup.rs/i686"
RUSTUP_INIT_EXE = "rustup-init.exe"

PACKAGES = [
    'pywin32',
    'pyminizip',
    'google-api-python-client',
    'google-auth-httplib2',
    'google-auth-oauthlib',
    'cryptography',
    'schedule'
]

VENV_DIR = 'env'
BACKUP_SCRIPT_NAME = 'backup_script.py'

SPECIFIC_SETUPTOOLS_VERSION = '68.0.0'

IS_WINDOWS = (platform.system().lower() == 'windows')

# ------------------------------------------------------------------------
# Helper: Check Admin on Windows
# ------------------------------------------------------------------------

def is_admin_windows():
    """Returns True if running with admin privileges on Windows; True on non-Windows by default."""
    if not IS_WINDOWS:
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# ------------------------------------------------------------------------
# Helper: Path to the venv's python.exe (Method #1)
# ------------------------------------------------------------------------

def get_venv_python():
    """
    Returns the full path to the venv's Python interpreter.
    We'll use it with '-m pip install' calls to ensure everything
    runs inside the virtual environment's Python process.
    """
    if platform.system().lower() == 'windows':
        return os.path.join(os.getcwd(), VENV_DIR, 'Scripts', 'python.exe')
    else:
        return os.path.join(os.getcwd(), VENV_DIR, 'bin', 'python')

# ------------------------------------------------------------------------
# 1. Windows-Specific: Build Tools
# ------------------------------------------------------------------------

def locate_vcvarsall_bat():
    candidate_paths = [
        r"C:\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
    ]
    for path in candidate_paths:
        if os.path.isfile(path):
            return path

    vswhere_path = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    if os.path.isfile(vswhere_path):
        try:
            cmd = [
                vswhere_path,
                "-products", "*",
                "-latest",
                "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-find", "**\\vcvarsall.bat"
            ]
            output = subprocess.check_output(cmd, text=True).strip()
            if output and os.path.isfile(output):
                return output
        except Exception:
            pass

    return None

def get_msvc_env(bitness="x64"):
    vcvarsall_path = locate_vcvarsall_bat()
    if not vcvarsall_path:
        append_output("[WARNING] Could not locate vcvarsall.bat. Some builds may fail.\n\n")
        return None

    cmd = f'cmd.exe /c "call \"{vcvarsall_path}\" {bitness} && set"'
    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
    except subprocess.CalledProcessError as e:
        append_output(f"[WARNING] Failed to call vcvarsall.bat:\n{e}\n\n")
        return None

    new_env = dict(os.environ)
    for line in output.splitlines():
        if '=' in line:
            key, val = line.split('=', 1)
            new_env[key.upper()] = val
    return new_env

def is_build_tools_installed():
    """Checks if Microsoft C++ Build Tools are installed by examining registry. Skip on non-Windows."""
    if not IS_WINDOWS:
        return True
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\VisualStudio\Installer\Products",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
    except FileNotFoundError:
        return False

    try:
        for i in range(winreg.QueryInfoKey(key)[0]):
            subkey_name = winreg.EnumKey(key, i)
            subkey_path = f"SOFTWARE\\Microsoft\\VisualStudio\\Installer\\Products\\{subkey_name}"
            subkey = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                subkey_path,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )
            try:
                product_id, _ = winreg.QueryValueEx(subkey, "ProductID")
                if "Microsoft.VisualStudio.Workload.VCTools" in product_id:
                    return True
            except FileNotFoundError:
                continue
    except Exception as e:
        append_output(f"Error checking Build Tools installation: {e}\n\n")
        return False

    return False

def download_build_tools():
    if os.path.exists(BUILD_TOOLS_PATH):
        append_output("Build Tools installer already downloaded.\n\n")
        return True
    try:
        append_output("Downloading Microsoft C++ Build Tools...\n")
        with urllib.request.urlopen(BUILD_TOOLS_URL) as response, open(BUILD_TOOLS_FILENAME, 'wb') as out_file:
            total_length = response.getheader('content-length')
            if total_length:
                total_length = int(total_length)
                downloaded = 0
                chunk_size = 8192
                while True:
                    data = response.read(chunk_size)
                    if not data:
                        break
                    out_file.write(data)
                    downloaded += len(data)
                    percent = downloaded * 100 / total_length
                    progress_var.set(percent)
                    append_output(f"Downloaded {percent:.2f}%\r")
                    root.update_idletasks()
            else:
                shutil.copyfileobj(response, out_file)
        append_output("\nDownload completed successfully.\n\n")
        return True
    except Exception as e:
        append_output(f"Failed to download Build Tools. Error:\n{e}\n\n")
        messagebox.showerror("Download Error", f"Failed to download Build Tools.\nError: {e}")
        return False

def install_build_tools():
    """Installs Build Tools silently with the required workloads. No-op on non-Windows."""
    if not IS_WINDOWS:
        return True

    try:
        append_output("Installing Microsoft C++ Build Tools...\n")
        cmd = [
            BUILD_TOOLS_PATH,
            "--quiet",
            "--wait",
            "--norestart",
            "--nocache",
            "--installPath", "C:\\BuildTools",
            "--add", "Microsoft.VisualStudio.Workload.NativeDesktop",
            "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "--add", "Microsoft.VisualStudio.Component.Windows10SDK.19041",
            "--includeRecommended"
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in iter(process.stdout.readline, ''):
            append_output(line)
        process.stdout.close()
        stderr = process.stderr.read()
        process.stderr.close()
        process.wait()

        if process.returncode != 0:
            append_output(f"Build Tools installation failed.\nError: {stderr}\n\n")
            messagebox.showerror("Installation Error", f"Failed to install Build Tools.\nError: {stderr}")
            return False

        append_output("Microsoft C++ Build Tools installed successfully.\n\n")
        append_output("You may need to reboot or open a new terminal so 'cl.exe' is on PATH.\n\n")
        return True

    except Exception as e:
        append_output(f"An error occurred during Build Tools installation.\nError: {e}\n\n")
        messagebox.showerror("Installation Error", f"An error occurred during Build Tools installation.\nError: {e}")
        return False

# ------------------------------------------------------------------------
# 2. Virtual Environment
# ------------------------------------------------------------------------

def create_virtual_environment():
    try:
        append_output("Creating virtual environment...\n")
        subprocess.check_call([sys.executable, '-m', 'venv', VENV_DIR])
        append_output("Virtual environment created successfully.\n\n")
        return True
    except subprocess.CalledProcessError as e:
        append_output(f"Failed to create virtual environment. Error:\n{e}\n\n")
        messagebox.showerror("Virtual Environment Error", f"Failed to create virtual environment.\nError: {e}")
        return False
    except Exception as e:
        append_output(f"An unexpected error occurred while creating virtual environment.\nError: {e}\n\n")
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred while creating virtual environment.\nError: {e}")
        return False

# ------------------------------------------------------------------------
# 3. Rust Installation (Cross-Platform)
# ------------------------------------------------------------------------

def is_rust_installed():
    try:
        subprocess.check_output(["rustc", "--version"], text=True)
        return True
    except Exception:
        return False

def install_rust_windows():
    arch = platform.architecture()[0]
    rustup_url = RUSTUP_EXE_64_WIN if arch == "64bit" else RUSTUP_EXE_32_WIN

    try:
        append_output("Downloading rustup-init.exe...\n")
        with urllib.request.urlopen(rustup_url) as response, open(RUSTUP_INIT_EXE, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        append_output("Downloaded rustup-init.exe successfully.\n")

        cmd = [os.path.join(os.getcwd(), RUSTUP_INIT_EXE), "-y", "--default-toolchain", "stable"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in iter(process.stdout.readline, ''):
            append_output(line)
        process.stdout.close()
        stderr = process.stderr.read()
        process.stderr.close()
        process.wait()

        if process.returncode != 0:
            append_output(f"Rust installation failed.\nError: {stderr}\n\n")
            return False

        append_output("Rust installed successfully. (Windows)\n\n")
        return True
    except Exception as e:
        append_output(f"Failed to download or install Rust on Windows. Error:\n{e}\n\n")
        return False

def install_rust_unix():
    try:
        append_output("Installing Rust via rustup (macOS/Linux)...\n")
        cmd = ['sh', '-c', "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)
        for line in iter(process.stdout.readline, ''):
            append_output(line)
        process.stdout.close()
        stderr = process.stderr.read()
        process.stderr.close()
        process.wait()

        if process.returncode != 0:
            append_output(f"Rust installation failed on macOS/Linux.\nError: {stderr}\n\n")
            return False

        append_output("Rust installed successfully. (macOS/Linux)\n\n")
        return True
    except Exception as e:
        append_output(f"Failed to download or install Rust on macOS/Linux. Error:\n{e}\n\n")
        return False

def download_and_install_rust():
    append_output("Attempting to install Rust...\n")
    if IS_WINDOWS:
        return install_rust_windows()
    else:
        return install_rust_unix()

# ------------------------------------------------------------------------
# 4. Package Installation (Method #1: Call venv's python -m pip)
# ------------------------------------------------------------------------

def upgrade_pip_setuptools_wheel(_unused, specific_setuptools_version=None, env_vars=None):
    """
    Instead of using pip_executable, we get the venv python and call it with -m pip.
    _unused parameter is just to keep the same signature.
    """
    venv_python = get_venv_python()
    try:
        if specific_setuptools_version:
            # Install pinned setuptools
            append_output(f"Installing setuptools=={specific_setuptools_version}...\n")
            subprocess.check_call(
                [venv_python, '-m', 'pip', 'install', f'setuptools=={specific_setuptools_version}'],
                env=env_vars
            )
            append_output(f"setuptools=={specific_setuptools_version} installed successfully.\n\n")

            # Then upgrade pip
            append_output("Upgrading pip...\n")
            subprocess.check_call(
                [venv_python, '-m', 'pip', 'install', '--upgrade', 'pip'],
                env=env_vars
            )
            append_output("Successfully upgraded pip, and installed the correct setuptools.\n\n")

        else:
            # If no pinned version, upgrade setuptools and wheel
            append_output("Upgrading setuptools...\n")
            subprocess.check_call(
                [venv_python, '-m', 'pip', 'install', '--upgrade', 'setuptools'],
                env=env_vars
            )

            append_output("Upgrading wheel...\n")
            subprocess.check_call(
                [venv_python, '-m', 'pip', 'install', '--upgrade', 'wheel'],
                env=env_vars
            )
            append_output("setuptools and wheel have been upgraded successfully.\n\n")
        return True
    except subprocess.CalledProcessError as e:
        append_output(f"Failed to upgrade/install setuptools/pip. Error:\n{e}\n\n")
        messagebox.showerror("Upgrade Error", f"Failed to upgrade/install setuptools/pip.\nError: {e}")
        return False
    except Exception as e:
        append_output(f"An unexpected error occurred during upgrades.\nError: {e}\n\n")
        messagebox.showerror("Unexpected Error", "An unexpected error occurred during upgrades.")
        return False

def install_packages(_unused, env_vars=None):
    """
    Installs PACKAGES by calling the venv python with -m pip in real-time.
    """
    venv_python = get_venv_python()
    for package in PACKAGES:
        if package.lower() == 'cryptography':
            if install_cryptography_with_fallback(venv_python, env_vars):
                continue
            else:
                messagebox.showerror(
                    "Installation Error",
                    "Failed to install cryptography (and fallback), even after Rust installation attempts."
                )
                return
        else:
            if not try_install_package_realtime(venv_python, package, env_vars=env_vars):
                return

    # Re-upgrade setuptools after all packages
    append_output("Re-upgrading setuptools to the latest version...\n")
    if upgrade_pip_setuptools_wheel(None, env_vars=env_vars):
        append_output("All packages have been installed successfully.\n\n")
        messagebox.showinfo("Installation Complete", "All packages have been installed successfully.")
    else:
        append_output("Failed to re-upgrade setuptools.\n\n")
        messagebox.showwarning("Partial Installation", "Packages installed, but failed to re-upgrade setuptools.")

def try_install_package_realtime(venv_python, package, env_vars=None):
    """
    Calls: venv_python -m pip install package
    Streams output in real-time.
    """
    try:
        append_output(f"Installing {package}...\n")
        process = subprocess.Popen(
            [venv_python, '-m', 'pip', 'install', package],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env_vars
        )
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                append_output(output)
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            append_output(f"Successfully installed {package}.\n\n")
            return True
        else:
            append_output(f"Failed to install {package}. Error:\n{stderr}\n\n")
            messagebox.showerror("Installation Error", f"Failed to install {package}. Check console for details.")
            return False
    except subprocess.CalledProcessError as e:
        append_output(f"Failed to install {package}. Error:\n{e}\n\n")
        messagebox.showerror("Installation Error", f"Failed to install {package}. Check console.")
        return False
    except Exception as e:
        append_output(f"Unexpected error installing {package}.\nError: {e}\n\n")
        messagebox.showerror("Installation Error", f"Unexpected error installing {package}.")
        return False

def install_cryptography_with_fallback(venv_python, env_vars=None):
    """
    1) Try cryptography
    2) If fail, try cryptography<38
    3) If still fail, install Rust and re-try
    """
    if try_install_package_realtime(venv_python, 'cryptography', env_vars):
        return True

    append_output("[WARNING] cryptography installation failed. Attempting fallback...\n")
    if try_install_package_realtime(venv_python, 'cryptography<38', env_vars):
        append_output("Fallback cryptography installed successfully.\n\n")
        return True

    append_output("[WARNING] Fallback cryptography also failed. Checking Rust...\n")
    if not is_rust_installed():
        if not download_and_install_rust():
            append_output("[WARNING] Rust installation attempt failed. cryptography cannot be built from source.\n")
            return False

        append_output("Re-trying cryptography install now that Rust is installed...\n")
        if try_install_package_realtime(venv_python, 'cryptography', env_vars):
            return True

    return False

# ------------------------------------------------------------------------
# 5. Batch File Generator
# ------------------------------------------------------------------------

def generate_run_backup_batch():
    try:
        batch_content = f"""@echo off
cd /d "%~dp0"
call {VENV_DIR}\\Scripts\\activate
python {BACKUP_SCRIPT_NAME}
pause
"""
        batch_filename = "run_backup.bat"
        with open(batch_filename, 'w') as bf:
            bf.write(batch_content)
        append_output(f"Batch file '{batch_filename}' created successfully.\n\n")
        messagebox.showinfo("Batch File Created", f"Batch file '{batch_filename}' has been created.")
    except Exception as e:
        append_output(f"Failed to create batch file. Error:\n{e}\n\n")
        messagebox.showerror("Batch File Error", f"Failed to create batch file.\nError: {e}")

# ------------------------------------------------------------------------
# 6. Tkinter GUI
# ------------------------------------------------------------------------

root = tk.Tk()
root.title("Cross-Platform Python Installer")
root.geometry("800x600")
root.resizable(False, False)

progress_var = tk.DoubleVar()

def append_output(text):
    output_console.configure(state='normal')
    output_console.insert(tk.END, text)
    output_console.see(tk.END)
    output_console.configure(state='disabled')

def enable_install_button():
    install_button.config(state='normal')

def run_installation_process():
    # Check admin on Windows
    if IS_WINDOWS and not is_admin_windows():
        msg = (
            "This script should be run as Administrator on Windows to install "
            "the C++ Build Tools (and possibly Rust). "
            "Please re-run as Administrator."
        )
        append_output(msg + "\n\n")
        messagebox.showerror("Admin Rights Required", msg)
        enable_install_button()
        return

    # 1. On Windows, check Build Tools
    if not is_build_tools_installed():
        if IS_WINDOWS:
            if not download_build_tools():
                enable_install_button()
                return
            if not install_build_tools():
                enable_install_button()
                return
        else:
            append_output("Non-Windows detected; skipping MS C++ Build Tools step.\n\n")

    # 2. Create Venv
    if not create_virtual_environment():
        enable_install_button()
        return

    # 3. If Windows, capture MSVC environment; if non-Windows, skip
    x64_env = None
    if IS_WINDOWS:
        if platform.architecture()[0] == '64bit':
            append_output("Python is 64-bit. Attempting x64 MSVC environment...\n")
            x64_env = get_msvc_env("x64")
            if x64_env:
                append_output("Captured x64 MSVC environment vars.\n\n")
            else:
                append_output("[WARNING] Could not capture x64 environment.\n\n")
        else:
            append_output("Python is 32-bit. Attempting x86 MSVC environment...\n")
            x64_env = get_msvc_env("x86")
            if x64_env:
                append_output("Captured x86 MSVC environment vars.\n\n")
            else:
                append_output("[WARNING] Could not capture x86 environment.\n\n")
    else:
        append_output("Non-Windows detected; skipping MSVC environment setup.\n\n")

    # 4. Install specific setuptools version (which also upgrades pip)
    if not upgrade_pip_setuptools_wheel(None, specific_setuptools_version=SPECIFIC_SETUPTOOLS_VERSION, env_vars=x64_env):
        enable_install_button()
        return

    # 5. Install packages
    install_packages(None, env_vars=x64_env)

    # 6. Generate batch file
    generate_run_backup_batch()

    enable_install_button()

def install_all():
    install_button.config(state='disabled')
    threading.Thread(target=run_installation_process, daemon=True).start()

label = tk.Label(
    root,
    text="Click the button below to set up the required packages.\nBackup script will need a new python).",
    font=("Arial", 12)
)
label.pack(pady=10)

install_button = tk.Button(
    root,
    text="Install",
    command=install_all,
    width=20,
    height=2,
    bg="blue",
    fg="white"
)
install_button.pack(pady=10)

progress_bar = ttk.Progressbar(root, orient='horizontal', length=700, mode='determinate', variable=progress_var)
progress_bar.pack(pady=10)

output_console = scrolledtext.ScrolledText(root, width=100, height=20, wrap=tk.WORD, state='disabled', font=("Courier", 10))
output_console.pack(pady=10)
append_output("Installation Output:\n\n")

root.mainloop()
