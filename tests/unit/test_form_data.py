import io

from atomhttp import AtomHTTP, FormData


class TestFormData:
    def test_basic_fields(self, base_url):
        form = FormData()
        form.append("username", "ada")
        form.append("age", 30)
        body, boundary = form.to_multipart()
        text = body.decode("utf-8")
        assert f'name="username"' in text
        assert "ada" in text
        assert boundary in text
        assert text.strip().endswith(f"--{boundary}--")

    def test_file_upload_roundtrip(self, base_url):
        with AtomHTTP(base_url=base_url, timeout=5) as client:
            form = FormData()
            form.append("field", "value")
            form.append("file", io.BytesIO(b"file-contents"), filename="test.txt", content_type="text/plain")
            response = client.post("/anything", data=form)
            assert response.status == 200
            assert 'name="field"' in response.data["data"]
            assert "file-contents" in response.data["data"]
            assert 'filename="test.txt"' in response.data["data"]
            assert response.data["headers"]["Content-Type"].startswith("multipart/form-data")

    def test_content_type_guessed_from_filename(self, base_url):
        form = FormData()
        form.append("img", b"\x89PNG", filename="pic.png")
        body, _ = form.to_multipart()
        assert b"Content-Type: image/png" in body

    def test_urlencoded(self):
        form = FormData()
        form.append("a", "1")
        form.append("b", "hello world")
        encoded = form.to_urlencoded()
        assert "a=1" in encoded
        assert "b=hello+world" in encoded

    def test_multiple_values_same_name(self):
        form = FormData()
        form.append("tag", "python")
        form.append("tag", "http")
        assert form.get_all("tag") == ["python", "http"]

    def test_set_replaces_existing_values(self):
        form = FormData()
        form.append("tag", "python")
        form.append("tag", "http")
        form.set("tag", "only-one")
        assert form.get_all("tag") == ["only-one"]

    def test_delete_and_has(self):
        form = FormData()
        form.append("a", "1")
        assert form.has("a") is True
        form.delete("a")
        assert form.has("a") is False

    def test_reading_a_file_object_twice_still_works(self):
        # Regression test: v1's FormData cached the boundary but not the
        # already-read file bytes, so calling to_multipart() twice on a
        # file-like value produced an empty body the second time.
        form = FormData()
        form.append("file", io.BytesIO(b"content"), filename="a.txt")
        body1, _ = form.to_multipart()
        body2, _ = form.to_multipart()
        assert b"content" in body1
        assert b"content" in body2
