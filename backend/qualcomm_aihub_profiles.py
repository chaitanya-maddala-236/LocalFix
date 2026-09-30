"""List Qualcomm AI Hub Snapdragon Windows target profiles without saving credentials."""

from __future__ import annotations

import getpass
import sys


def main() -> int:
    try:
        import qai_hub as hub
    except ImportError:
        print("Install qai-hub in a separate Python 3.11+ environment before using this helper.")
        return 2

    token = getpass.getpass("Qualcomm AI Hub API token (input hidden): ").strip()
    if not token:
        print("No token entered.")
        return 2
    try:
        client = hub.Client(hub.ClientConfig(api_token=token, verbose=False))
        devices = client.get_devices()
    except Exception as error:
        print(f"AI Hub authentication/device lookup failed ({type(error).__name__}).")
        return 1
    finally:
        token = ""

    target_names = sorted({
        str(getattr(device, "name", "")) for device in devices
        if any(part in str(getattr(device, "name", "")).casefold()
               for part in ("snapdragon x elite", "snapdragon x plus", "snapdragon x2"))
    })
    print(f"AI Hub account access: available; device profiles returned: {len(devices)}")
    print("Snapdragon Windows reference profiles:")
    for name in target_names:
        print(f"- {name}")
    print("These are AI Hub target profiles, not measurements from the physical HP laptop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
