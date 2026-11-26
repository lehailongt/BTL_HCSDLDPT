"""Local, reviewable correction screen; no network or model dependency."""
import base64
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from pymysql import MySQLError
from organ_annotations import image_key,read_annotation
from organ_review_service import preview,save_review
from similarity import GROUPS,Descriptor

editor=components.declare_component('organ_mask_editor',path=str(Path(__file__).parent/'ui_components'/'organ_mask_editor'))
CHOICES={'Có — dùng vùng đã vẽ':'present','Giữ tự động':'unknown',
         'Không có — tôi xác nhận':'absent','Không quan sát được':'unobservable'}


def review_screen(catalog,on_save):
    st.title('Hiệu chỉnh vùng đài và cuống')
    st.caption('Khoanh vùng, xem trước phép đo rồi lưu. Các xác nhận này được lưu riêng với 133 thuộc tính.')
    subset=st.radio('Danh sách ảnh',['Còn thiếu cuống','Còn thiếu đài','Tất cả ảnh'],horizontal=True)
    group='stem' if subset=='Còn thiếu cuống' else 'calyx'
    rows=[r for r in catalog.rows if subset=='Tất cả ảnh' or not np.isfinite(r[3].values[GROUPS[group]]).any()]
    if not rows:st.info('Không còn ảnh trong danh sách này.');return
    name=st.selectbox('Chọn ảnh',[r[1] for r in rows],key='review_image')
    selected=next(r for r in rows if r[1]==name)
    image=cv2.imdecode(np.frombuffer(Path(selected[2]).read_bytes(),np.uint8),1)
    key=image_key(image);saved=read_annotation(image)
    initial={g:(saved or {}).get('organs',{}).get(g,{}).get('polygons',[]) for g in ('calyx','stem')}
    token=key+hashlib.sha256(json.dumps(saved,sort_keys=True).encode()).hexdigest()
    left,right=st.columns([2,1])
    with left:
        png=cv2.imencode('.png',image)[1].tobytes()
        value=editor(image='data:image/png;base64,'+base64.b64encode(png).decode(),width=image.shape[1],height=image.shape[0],
                     polygons=initial,token=token,key='organ_canvas_'+key,default={'polygons':initial})
    with right:
        changed={g:st.checkbox('Hiệu chỉnh '+label,value=g=='stem',key='change_'+g+'_'+key)
                 for g,label in (('calyx','đài'),('stem','cuống'))}
        states={}
        for g,label in (('calyx','đài'),('stem','cuống')):
            if changed[g]:
                choice=st.selectbox('Trạng thái '+label,list(CHOICES),key='state_'+g+'_'+key)
                states[g]=CHOICES[choice]
        note=st.text_area('Căn cứ kiểm tra',value=(saved or {}).get('note',''),key='review_note_'+key,
                          placeholder='Ví dụ: cuống nghiêng sang trái, bị bộ dò bỏ sót.')
        st.caption('Màu vàng: đài. Màu xanh lam: cuống. Chọn Giữ tự động để bỏ hiệu chỉnh của bộ phận đó.')
    payload={'version':1,'image_key':key,'organs':dict((saved or {}).get('organs',{}))}
    polygons=(value or {}).get('polygons',initial)
    for g,state in states.items():
        payload['organs'][g]={'status':state,'polygons':polygons.get(g,[]) if state=='present' else []}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    if st.button('Xem trước vùng và số đo',disabled=not any(changed.values())):
        try:
            prep,features=preview(image,payload,{g:getattr(selected[3],g+'_status') for g in ('calyx','stem')})
            st.session_state['organ_preview']={'digest':digest,'prep':prep,'features':features}
        except (ValueError,cv2.error) as exc:st.error(str(exc))
    shown=st.session_state.get('organ_preview')
    ready=bool(shown and shown['digest']==digest)
    if ready:
        prep=shown['prep'];overlay=image.copy()
        for g,color in (('calyx',[0,255,255]),('stem',[255,255,0])):
            selected_pixels=prep[g+'_mask']>0
            overlay[selected_pixels]=(overlay[selected_pixels]*.35+np.array(color)*.65).astype(np.uint8)
        st.image(overlay,channels='BGR',width=360,caption='Vùng thực sự dùng để đo sau khi loại bông và biên lặp')
        descriptor=Descriptor.from_extracted(shown['features'])
        st.dataframe([{'Bộ phận':g,'Trạng thái':descriptor.organ_state(g),
                       'Pixel':cv2.countNonZero(prep[g+'_mask']),
                       'Giá trị':str(shown['features'][g])} for g in ('calyx','stem')],hide_index=True)
        st.caption('Khi lưu, các bản ảnh có nội dung pixel giống hệt cũng được đồng bộ. Ảnh khác tên nhưng khác nội dung không dùng chung vùng.')
    if st.button('Lưu vùng đã kiểm tra',type='primary',disabled=not ready or not note.strip()):
        try:
            aliases=save_review(selected[0],key,payload,note)
            on_save();st.session_state.pop('organ_preview',None)
            st.success('Đã lưu vùng và cập nhật CSDL: '+', '.join(aliases))
        except (ValueError,RuntimeError,OSError,cv2.error,MySQLError) as exc:st.error(str(exc))
