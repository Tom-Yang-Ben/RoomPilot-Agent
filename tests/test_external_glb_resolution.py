import zipfile

from backend.server import main


def _write_glb_zip(zip_path, entry_name):
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(entry_name, b"glTF-test-payload")


def test_external_furniture_zip_entry_uses_furniture_download_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "local")
    zip_path = tmp_path / "downloaded-files(furniture)-sample.zip"
    entry_name = "downloaded-files(furniture)/ABO/ABO-test/001 - Sample chair.glb"
    _write_glb_zip(zip_path, entry_name)

    monkeypatch.setattr(main, "_EXTERNAL_GLB_ZIP_SEARCH_DIRS", (tmp_path,))
    main._external_zip_entry_lookup.cache_clear()

    item = {"zip_entry": "downloaded-files/ABO/ABO-test/001 - Sample chair.glb"}

    assert main._model_status(item)[0] is True
    assert main._external_glb_bytes(item) == b"glTF-test-payload"

    main._external_zip_entry_lookup.cache_clear()


def test_external_furniture_zip_entry_uses_home_appliance_download_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "local")
    zip_path = tmp_path / "downloaded-files(home apppliances)-sample.zip"
    entry_name = "downloaded-files(home apppliances)/sf-electric-fans/001 - Fan.glb"
    _write_glb_zip(zip_path, entry_name)

    monkeypatch.setattr(main, "_EXTERNAL_GLB_ZIP_SEARCH_DIRS", (tmp_path,))
    main._external_zip_entry_lookup.cache_clear()

    item = {"zip_entry": "sf-electric-fans/001 - Fan.glb"}

    assert main._model_status(item)[0] is True
    assert main._external_glb_bytes(item) == b"glTF-test-payload"

    main._external_zip_entry_lookup.cache_clear()


def test_catalog_relative_glb_path_can_resolve_from_an_external_zip(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "local")
    zip_path = tmp_path / "downloaded-files-catalog.zip"
    entry_name = "downloaded-files/tw/tw-beds/01 - Sample bed.glb"
    _write_glb_zip(zip_path, entry_name)

    monkeypatch.setattr(main, "_EXTERNAL_GLB_ZIP_SEARCH_DIRS", (tmp_path,))
    main._external_zip_entry_lookup.cache_clear()

    item = {"glb_relative_path": entry_name}

    assert main._model_status(item)[0] is True
    assert main._external_glb_bytes(item) == b"glTF-test-payload"

    main._external_zip_entry_lookup.cache_clear()


def test_explicit_backup_zip_does_not_scan_default_downloads(tmp_path, monkeypatch):
    explicit_zip = tmp_path / "ikea抓取家具glb_中文命名版-explicit.zip"
    default_dir = tmp_path / "downloads"
    default_dir.mkdir()
    default_zip = default_dir / "downloaded-files-default.zip"
    _write_glb_zip(explicit_zip, "IKEA/explicit.glb")
    _write_glb_zip(default_zip, "downloaded-files/default.glb")

    monkeypatch.setenv("ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS", str(explicit_zip))
    monkeypatch.setattr(main, "_EXTERNAL_GLB_ZIP_SEARCH_DIRS", (default_dir,))

    assert main._iter_external_zip_paths() == [explicit_zip]
