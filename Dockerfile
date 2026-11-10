FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-tested.txt /app/
RUN pip install -r requirements-tested.txt && useradd --uid 10001 --create-home quote && mkdir /data && chown quote:quote /data
COPY --chown=quote:quote quotepilot/ /app/quotepilot/
COPY --chown=quote:quote integration/rfq_native.yaml /app/integration/rfq_native.yaml
COPY --chown=quote:quote web/ /app/web/
COPY --chown=quote:quote workspace/samples/ /app/workspace/samples/
COPY --chown=quote:quote server.py /app/
COPY --chown=quote:quote deploy/entrypoint.py /app/entrypoint.py
ENV QUOTEPILOT_DB=/data/quotepilot.db
USER quote
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8765')+'/healthz',timeout=4)"
CMD ["python", "entrypoint.py"]
