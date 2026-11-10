import asyncio
from io import BytesIO
from email import policy
from email.parser import BytesParser
import hashlib
from fastapi import UploadFile
import pytest
from fastapi import HTTPException
from openpyxl import Workbook
from quotepilot.rfq_upload import read_rfq
from quotepilot.parsing import parse_eml


def test_standalone_xlsx_preserves_bytes_customer_and_identity():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['RFQ No', 'Part Number', 'Quantity', 'Unit Of Measure', 'Condition'])
    sheet.append(['ROUND-1', 'PN-0001', 500, 'EA', 'FN'])
    file = BytesIO()
    workbook.save(file)
    raw = file.getvalue()

    def receive(sender):
        return asyncio.run(read_rfq(UploadFile(BytesIO(raw), filename='order.xlsx'), sender))

    first, name = receive('buyer@example.invalid')
    assert receive('buyer@example.invalid')[0] == first
    assert receive('another@example.invalid')[0] != first
    message = BytesParser(policy=policy.default).parsebytes(first)
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == 'order.xlsx'
    assert hashlib.sha256(attachment.get_payload(decode=True)).digest() == hashlib.sha256(raw).digest()
    parsed = parse_eml(first, name)
    assert parsed['lines'][0]['quantity'] == 500
    with pytest.raises(HTTPException) as exc:
        receive('')
    assert exc.value.status_code == 422
