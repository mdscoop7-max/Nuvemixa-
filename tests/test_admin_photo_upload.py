import base64
from io import BytesIO
from PIL import Image

def _basic(user,password):
    return {"Authorization":"Basic "+base64.b64encode(f"{user}:{password}".encode()).decode()}

def test_private_upload_and_staff_restrictions(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_DB",str(tmp_path/"accounts.sqlite"))
    monkeypatch.setenv("TRENDMIX_ADMIN_USER","testowner")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD","VeryLongLocalOwnerSecret1!")
    from app import app
    app.config["TESTING"]=True
    with app.test_client() as c:
        a=_basic("testowner","VeryLongLocalOwnerSecret1!")
        page=c.get("/beheer/productconcepten",headers=a)
        assert page.status_code==200
        assert b'Foto uploaden' in page.data
        with c.session_transaction() as ss:
            ss["_tm_csrf"]="upload-csrf"
        photo=BytesIO()
        Image.new("RGB",(100,80),"blue").save(photo,"PNG")
        photo.seek(0)
        sent=c.post("/beheer/foto/upload",headers=a,data={"_csrf_token":"upload-csrf","image":(photo,"test.png")},content_type="multipart/form-data")
        assert sent.status_code==303
        photo_url=sent.headers["Location"].split("photo=",1)[-1]
        assert photo_url
        assert c.get("/beheer/foto/"+"0"*32+".jpg").status_code==401
        assert c.post("/beheer/foto/upload",headers=a,data={"_csrf_token":"wrong"},content_type="multipart/form-data").status_code==403
