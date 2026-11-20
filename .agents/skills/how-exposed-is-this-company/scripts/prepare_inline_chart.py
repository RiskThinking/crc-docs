"""Embed an existing PNG and print its final-answer reference for ChatGPT Work Mode."""

import argparse
import base64
import html
import json
import struct
from pathlib import Path
from uuid import uuid4

MAX_FRAGMENT_BYTES = 1_000_000
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


def prepare_chart(png: Path, workspace: Path, alt: str) -> str:
    data = png.read_bytes()
    if len(data) < 33 or not data.startswith(PNG_HEADER):
        raise ValueError("Expected a PNG chart.")
    width, height = struct.unpack(">II", data[16:24])
    if not width or not height or not alt.strip():
        raise ValueError("Provide a nonempty chart and description.")

    name = f"crc-damage-chart-{uuid4().hex}"
    encoded = base64.b64encode(data).decode("ascii")
    fragment = (
        f'<figure id="{name}" style="margin:0">\n'
        f'  <img alt="{html.escape(alt, quote=True)}" width="{width}" height="{height}" '
        f'style="display:block;width:100%;height:auto" src="data:image/png;base64,{encoded}">\n'
        "</figure>\n"
    ).encode()
    if len(fragment) >= MAX_FRAGMENT_BYTES:
        raise ValueError("Chart is too large for this renderer. Export a smaller PNG.")

    path = workspace.resolve() / f"{name}.html"
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_bytes(fragment)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    descriptor = json.dumps({"path": str(path)}, separators=(",", ":"))
    return "visualize" + descriptor + ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", type=Path)
    parser.add_argument("--alt", required=True, help="An accessible chart description.")
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    args = parser.parse_args()
    try:
        print(prepare_chart(args.png, args.workspace, args.alt))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
