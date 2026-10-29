import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def report_error(error):
    """Show startup failures even when Tk or a package cannot import."""
    import os
    import traceback
    frozen = getattr(sys, 'frozen', False)
    missing = getattr(error, 'name', '') if isinstance(error, ImportError) else ''
    if isinstance(error, ImportError):
        reason = 'A required component is missing' + (': ' + missing if missing else '.')
        fix = ('Download a fresh complete EXE release; Python is already bundled.'
               if frozen else 'From the project folder, run: python -m pip install -r src/requirements.txt. For tkinter, reinstall Python with Tcl/Tk enabled.')
    elif isinstance(error, PermissionError):
        reason = 'Windows denied access to a required file or setting.'
        fix = 'Use a folder you can write to and check Windows Security protection history. Retry after correcting access.'
    else:
        reason = 'The app could not start or complete an action (' + type(error).__name__ + ').'
        fix = 'Try the current release from a writable local folder. If it persists, send the diagnostic log to the maintainer.'
    from netcroc.core import data_folder
    folder = data_folder()
    log = folder / 'startup-error.log'
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        frames = traceback.extract_tb(error.__traceback__)
        log.write_text(type(error).__name__ + (' module=' + missing if missing else '') + '\n' +
                       '\n'.join(f'{Path(f.filename).name}:{f.lineno} in {f.name}' for f in frames), encoding='utf-8')
        location = '\n\nDiagnostic log: ' + str(log)
    except OSError:
        location = '\n\nA diagnostic log could not be written.'
    message = reason + '\n\nHow to fix:\n' + fix + location
    if os.name == 'nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'NetCroc', 0x10)
    else:
        print(message, file=sys.stderr)


def health_status():
    """Read-only DNS helper, dispatched before any UI or singleton mutex."""
    import socket
    import queue
    import threading
    import time
    from netcroc.dns import DOMAINS
    answers = queue.Queue()
    def check(domain):
        try:
            answers.put(bool(socket.getaddrinfo(domain, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)))
        except OSError:
            answers.put(False)
    for domain in DOMAINS:
        threading.Thread(target=check,args=(domain,),daemon=True).start()
    successes = 0
    deadline = time.monotonic() + 12
    for _ in DOMAINS:
        try:
            successes += answers.get(timeout=max(.01,deadline-time.monotonic()))
        except queue.Empty:
            break
        if successes >= 2:
            break
    return 0 if successes >= 2 else 2

if __name__ == '__main__':
    try:
        if '--after-exit' in sys.argv:
            from netcroc.platforms import wait_for_process_exit
            index = sys.argv.index('--after-exit')
            wait_for_process_exit(int(sys.argv[index+1]), float(sys.argv[index+2]))
        if '--routing-watch' in sys.argv:
            from netcroc.tun_service import worker
            worker()
            raise SystemExit(0)
        if '--native-control' in sys.argv:
            from netcroc.platforms import native_control
            native_control(sys.argv[sys.argv.index('--native-control')+1])
            raise SystemExit(0)
        if '--child-watch' in sys.argv:
            from netcroc.platforms import watch_child
            i=sys.argv.index('--child-watch')
            watch_child(int(sys.argv[i+1]),float(sys.argv[i+2]),int(sys.argv[i+3]))
            raise SystemExit(0)
        if '--dns-health' in sys.argv:
            import os
            status = health_status()
            if '--dns-health-report' in sys.argv:
                index = sys.argv.index('--dns-health-report')
                Path(sys.argv[index+1]).write_text(str(status),encoding='ascii')
            # This child owns no UI or persistent state. Exit without waiting
            # for any outstanding Windows resolver call in a daemon thread.
            os._exit(status)
        if '--dns-watch' in sys.argv:
            from netcroc.dns import watchdog
            index = sys.argv.index('--dns-watch')
            watchdog(sys.argv[index+1], sys.argv[index+2] if len(sys.argv)>index+2 else None)
            raise SystemExit(0)
        import tkinter as tk
        tk.Tk.report_callback_exception = lambda self, kind, value, tb: report_error(value.with_traceback(tb))
        from netcroc.ui import main
        main()
    except Exception as error:
        report_error(error)
        raise SystemExit(1)
