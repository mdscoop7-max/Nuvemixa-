import base64
import importlib

def test_admin_user_management_local(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_DB", str(tmp_path / "users.sqlite3"))
    monkeypatch.setenv("TRENDMIX_ADMIN_USER", "qaowner")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD", "UniqueLocalQASecret12345!")
    import admin_accounts
    importlib.reload(admin_accounts)
    from app import app
    app.config["TESTING"] = True
    def auth(user, password):
        return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}
    with app.test_client() as client:
        assert client.get("/beheer/accounts").status_code == 401
        assert client.get("/beheer/accounts", headers=auth("qaowner", "UniqueLocalQASecret12345!")).status_code == 200
        with client.session_transaction() as sess:
            sess["admin_csrf"] = "test-csrf"
            sess["_tm_csrf"] = "form-csrf"
        created = client.post("/beheer/accounts", headers=auth("qaowner", "UniqueLocalQASecret12345!"),
            data={"_csrf_token":"form-csrf", "csrf": "test-csrf", "action": "create", "username": "qaeditor", "password": "StrongEditorSecret123!", "role": "manager"})
        assert created.status_code == 200
        assert client.get("/beheer", headers=auth("qaeditor", "StrongEditorSecret123!")).status_code == 200
        assert client.get("/beheer/accounts", headers=auth("qaeditor", "StrongEditorSecret123!")).status_code == 403
        assert client.post("/beheer/accounts", headers=auth("qaowner", "UniqueLocalQASecret12345!"),
            data={"_csrf_token":"form-csrf", "csrf": "incorrect", "action": "delete", "username": "qaeditor"}).status_code == 403
        with client.session_transaction() as sess:
            sess["admin_csrf"] = "test-csrf"
            sess["_tm_csrf"] = "form-csrf"
        changed = client.post("/beheer/accounts", headers=auth("qaowner", "UniqueLocalQASecret12345!"),
            data={"_csrf_token":"form-csrf", "csrf": "test-csrf", "action": "password", "current_password": "UniqueLocalQASecret12345!", "new_password": "UniqueNewOwnerSecret789!"})
        assert changed.status_code == 200
        assert client.get("/beheer", headers=auth("qaowner", "UniqueLocalQASecret12345!")).status_code == 401
        assert client.get("/beheer", headers=auth("qaowner", "UniqueNewOwnerSecret789!")).status_code == 200
