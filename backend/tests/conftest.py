import os
import sys

if sys.platform == "win32":
    for path in [r"E:\msys64\ucrt64\bin", r"C:\msys64\ucrt64\bin"]:
        if os.path.exists(path):
            try:
                os.add_dll_directory(path)
                os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
            except Exception:
                pass
