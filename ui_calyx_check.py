import io
from pathlib import Path
import main
r=next(r for r in main.gallery().rows if r[1]=='45.jpg')
u=io.BytesIO(Path(r[2]).read_bytes());u.name='45.jpg'
main.st.file_uploader=lambda *args,**kwargs:u
main.main()
