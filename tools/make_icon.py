"""开发用：把 assets/logo.png 生成为多尺寸的 assets/logo.ico。

Windows 任务栏/标题栏/资源管理器在不同缩放下会挑不同的尺寸，
单一尺寸的图片放大缩小都会糊；多尺寸 ICO 每个尺寸都是单独缩放的。

不需要额外依赖（用 Qt 自己缩放 + 手写 ICO 头，PNG-in-ICO 是 Vista 之后的格式）。

运行：<项目>/.venv/Scripts/python.exe tools/make_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QSize, Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

SOURCE = ROOT / "assets" / "logo.png"
TARGET = ROOT / "assets" / "logo.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(image: QImage) -> bytes:
    # 注意：不要写 QBuffer(QByteArray())——那个临时 QByteArray 会被回收，
    # PySide6 会在编码时直接崩掉。无参 QBuffer 自带缓冲区。
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def main() -> int:
    app = QApplication([])
    source = QImage(str(SOURCE))
    if source.isNull():
        print(f"读不到源图片：{SOURCE}")
        return 1

    # 先裁成正方形（源图是方的，这里只是防御性处理）
    side = min(source.width(), source.height())
    source = source.copy(
        (source.width() - side) // 2, (source.height() - side) // 2, side, side
    )

    entries: list[tuple[int, bytes]] = []
    for size in SIZES:
        scaled = source.scaled(
            QSize(size, size),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ).convertToFormat(QImage.Format.Format_ARGB32)
        entries.append((size, png_bytes(scaled)))

    offset = 6 + 16 * len(entries)
    header = struct.pack("<HHH", 0, 1, len(entries))
    directory = b""
    payload = b""
    for size, data in entries:
        dimension = 0 if size >= 256 else size
        directory += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset
        )
        payload += data
        offset += len(data)

    TARGET.write_bytes(header + directory + payload)
    print(f"已生成 {TARGET}（{len(entries)} 个尺寸：{', '.join(str(s) for s in SIZES)}）")
    print(f"文件大小：{TARGET.stat().st_size / 1024:.1f} KB")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
