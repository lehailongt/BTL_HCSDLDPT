"""AppTest harness: a query with a slanted stalk, without changing app logic."""
import io
from pathlib import Path
import main

row=next(r for r in main.gallery().rows if r[1]=='114.jpg')
upload=io.BytesIO(Path(row[2]).read_bytes());upload.name='114.jpg'
main.st.file_uploader=lambda *args,**kwargs:upload
main.main()
