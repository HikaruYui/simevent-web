# Fungsi file: Pembuatan gambar QR di memori dari token tiket tanpa menyisipkan identitas peserta.

from io import BytesIO

import qrcode
from qrcode.image.pil import PilImage


def render_ticket_qr(token):
    """Encode only the opaque token; never persist private QR images in media."""
    buffer = BytesIO()
    image = qrcode.make(str(token), image_factory=PilImage, box_size=8, border=4)
    image.save(buffer, format="PNG")
    return buffer.getvalue()
