"""AppTest harness; component input and persistence are mocked, never user data."""
import main
import organ_review_ui

organ_review_ui.editor=lambda **kwargs:{'polygons':{'calyx':[], 'stem':[[[154,220],[177,218],[182,253],[165,253]]]}}
def fake_save(image_id,key,payload,note):
    main.st.session_state['review_save_stub']={'image_id':image_id,'image_key':key,'payload':payload,'note':note}
    return ['60.jpg (test only)']
organ_review_ui.save_review=fake_save
main.main()
