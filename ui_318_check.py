"""Streamlit AppTest harness using the actual query 318."""
import io
from pathlib import Path
import main

row = next(r for r in main.gallery().rows if r[1] == '318.jpg')
upload = io.BytesIO(Path(row[2]).read_bytes())
upload.name = '318.jpg'
main.st.file_uploader = lambda *args, **kwargs: upload
main.main()
