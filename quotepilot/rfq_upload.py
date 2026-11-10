"""Preserve standalone RFQ originals and reuse the same MIME attachment parser."""
import hashlib
import re
from email.message import EmailMessage
from pathlib import Path

from fastapi import HTTPException, UploadFile


async def read_rfq(file: UploadFile, customer_email: str):
    name = Path((file.filename or 'upload').replace('\\', '/')).name
    suffix = Path(name).suffix.lower()
    if suffix not in {'.eml', '.xlsx', '.pdf'}:
        raise HTTPException(415, '请选择 EML、XLSX 或 PDF 文件')
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, '询价文件超过 10 MB 上限')
    if not data:
        raise HTTPException(422, '文件为空')
    if suffix == '.eml':
        return data, name

    if suffix == '.pdf':
        sample = Path(__file__).resolve().parents[1] / 'web/guide/samples/suppliers.pdf'
        if sample.is_file() and data == sample.read_bytes():
            raise HTTPException(422, '这是第三步的供应商示例报价单，请在「供应商比价与报价」上传。第一步请选择客户询价邮件。')

    sender = customer_email.strip().lower()
    if len(sender) > 254 or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', sender):
        raise HTTPException(422, '请填写此独立附件所属的客户邮箱，再预览或导入')
    if any(ord(c) < 32 for c in name) or len(name) > 200:
        raise HTTPException(422, '文件名含控制字符或过长')
    digest = hashlib.sha256(sender.encode() + b'\0' + name.encode() + b'\0' + data).hexdigest()
    env = EmailMessage()
    env['From'] = sender
    env['Subject'] = name
    env['Message-ID'] = f'<file-{digest}@quotepilot.invalid>'
    env.set_content('Standalone attachment. Customer email supplied by the operator.')
    subtype = 'pdf' if suffix == '.pdf' else 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    env.add_attachment(data, maintype='application', subtype=subtype, filename=name)
    env.set_boundary('qp-' + digest)
    return env.as_bytes(), name + '.eml'
