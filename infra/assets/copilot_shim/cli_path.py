import logging
import os
import platform
import shutil


def get_copilot_cli_path() -> str:
    """
    Get the path to the Copilot CLI executable.

    Priority:
    1. COPILOT_CLI_PATH environment variable
    2. Bundled npm package (current platform-specific binary only)
    3. SDK-bundled binary (copilot Python package bin/)
    4. Azure Functions known deployment path
    5. System PATH (via `which copilot`) - fallback for local development
    6. Default 'copilot' (assumes it's in PATH)
    """
    env_path = os.environ.get("COPILOT_CLI_PATH")
    if env_path:
        logging.info(f"Using COPILOT_CLI_PATH: {env_path}")
        return env_path

    # Bundled npm platform-specific binary
    function_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    system = platform.system().lower()
    machine = platform.machine().lower()

    platform_map = {
        ("darwin", "arm64"): "copilot-darwin-arm64",
        ("darwin", "x86_64"): "copilot-darwin-x64",
        ("linux", "x86_64"): "copilot-linux-x64",
        ("linux", "aarch64"): "copilot-linux-arm64",
        ("windows", "amd64"): "copilot-win32-x64",
        ("windows", "x86_64"): "copilot-win32-x64",
    }
    platform_pkg = platform_map.get((system, machine))

    if platform_pkg:
        ext = ".exe" if system == "windows" else ""
        binary_path = os.path.join(
            "/home/site/wwwroot", "node_modules", "@github", platform_pkg, f"copilot{ext}"
        )
        if os.path.exists(binary_path):
            logging.info(f"Using bundled Copilot CLI for {system}/{machine}: {binary_path}")
            return binary_path
        logging.debug(f"Platform binary not found: {binary_path}")

    # SDK-bundled binary (works locally and on Azure)
    try:
        import copilot as _copilot_pkg
        pkg_dir = os.path.dirname(os.path.abspath(_copilot_pkg.__file__))
        sdk_binary = os.path.join(pkg_dir, "bin", "copilot")
        if os.path.exists(sdk_binary):
            if os.access(sdk_binary, os.X_OK):
                logging.info(f"Using SDK-bundled Copilot CLI: {sdk_binary}")
                return sdk_binary
            # Binary exists but not executable — copy to writable location
            try:
                import shutil as _shutil
                tmp_binary = os.path.join("/tmp", "copilot-cli")
                if not os.path.exists(tmp_binary):
                    _shutil.copy2(sdk_binary, tmp_binary)
                    os.chmod(tmp_binary, 0o755)
                if os.access(tmp_binary, os.X_OK):
                    logging.info(f"Using SDK-bundled Copilot CLI (copied to /tmp): {tmp_binary}")
                    return tmp_binary
            except OSError as e:
                logging.warning(f"Cannot make SDK CLI binary executable: {e}")
    except ImportError:
        pass

    # Azure Functions known path
    bundled_cli = os.path.join("/home", "site", "wwwroot", ".python_packages", "lib", "site-packages", "copilot", "bin", "copilot")
    if os.path.exists(bundled_cli):
        if os.access(bundled_cli, os.X_OK):
            logging.info(f"Using Azure-deployed Copilot CLI: {bundled_cli}")
            return bundled_cli
        try:
            tmp_binary = os.path.join("/tmp", "copilot-cli")
            if not os.path.exists(tmp_binary):
                import shutil as _shutil
                _shutil.copy2(bundled_cli, tmp_binary)
                os.chmod(tmp_binary, 0o755)
            if os.access(tmp_binary, os.X_OK):
                logging.info(f"Using Azure-deployed Copilot CLI (copied to /tmp): {tmp_binary}")
                return tmp_binary
        except OSError as e:
            logging.warning(f"Cannot make Azure CLI binary executable: {e}")

    system_copilot = shutil.which("copilot")
    if system_copilot:
        logging.info(f"Using copilot from system PATH: {system_copilot}")
        return system_copilot

    logging.warning("No copilot CLI found, falling back to 'copilot' command")
    return "copilot"
