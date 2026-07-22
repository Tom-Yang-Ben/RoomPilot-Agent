import zipfile

from backend.server.services import glb_assets


def _write_glb_zip(zip_path, entry_name):
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(entry_name, b"glTF-test-payload")


def test_external_furniture_zip_entry_uses_furniture_download_prefix(tmp_path, monkeypatch):
    zip_path = tmp_path / "downloaded-files(furniture)-sample.zip"
    entry_name = "downloaded-files(furniture)/ABO/ABO-test/001 - Sample chair.glb"
    _write_glb_zip(zip_path, entry_name)

    monkeypatch.setattr(glb_assets, "_EXTERNAL_GLB_ZIP_SEARCH_DIRS", (tmp_path,))
    glb_assets._external_zip_entry_lookup.cache_clear()

    item = {"zip_entry": "downloaded-files/ABO/ABO-test/001 - Sample chair.glb"}

    assert glb_assets._model_status(item)[0] is True
    assert glb_assets._external_glb_bytes(item) == b"glTF-test-payload"

    glb_assets._external_zip_entry_lookup.cache_clear()


def test_external_furniture_zip_entry_uses_home_appliance_download_prefix(tmp_path, monkeypatch):
    zip_path = tmp_path / "downloaded-files(home apppliances)-sample.zip"
    entry_name = "downloaded-files(home apppliances)/sf-electric-fans/001 - Fan.glb"
    _write_glb_zip(zip_path, entry_name)

    monkeypatch.setattr(glb_assets, "_EXTERNAL_GLB_ZIP_SEARCH_DIRS", (tmp_path,))
    glb_assets._external_zip_entry_lookup.cache_clear()

    item = {"zip_entry": "sf-electric-fans/001 - Fan.glb"}

    assert glb_assets._model_status(item)[0] is True
    assert glb_assets._external_glb_bytes(item) == b"glTF-test-payload"

    glb_assets._external_zip_entry_lookup.cache_clear()
