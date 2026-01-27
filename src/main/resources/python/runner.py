import os
import sys

runtime = os.environ.get("PYJAVABRIDGE_RUNTIME")
script_path = os.environ.get("PYJAVABRIDGE_SCRIPT")
if runtime and runtime not in sys.path:
    sys.path.insert(0, runtime)
if script_path:
    script_dir = os.path.dirname(script_path)
    if script_dir and script_dir not in sys.path:
        sys.path.insert(0, script_dir)

import bridge

if __name__ == "__main__":
    if not script_path:
        raise SystemExit("PYJAVABRIDGE_SCRIPT not set")
    bridge._bootstrap(script_path)
