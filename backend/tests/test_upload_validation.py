import pytest

from services.upload_service import FileData, UploadService, UploadSource

service = UploadService()


def make_file(filename="20250704_OMEGA_ELEKTRO_Mueller.pdf", size=1024, content_type="application/pdf",
              source=UploadSource.DRAG_DROP):
    return FileData(content=b"%PDF" + b"0" * (size - 4), filename=filename, content_type=content_type,
                    file_size=size, source=source)


@pytest.mark.parametrize("raw, expected", [
    ("../../etc/passwd", "passwd.pdf"),
    ("rechnung<script>.pdf", "rechnung_script_.pdf"),
    ("a..b.pdf", "a.b.pdf"),
    ("", "unknown.pdf"),
])
def test_sanitize_filename(raw, expected):
    assert service.sanitize_filename(raw) == expected


def test_sanitize_filename_caps_length():
    assert len(service.sanitize_filename("x" * 400 + ".pdf")) <= 255


def test_valid_file_passes():
    assert service.validate_file(make_file()) == (True, None)


@pytest.mark.parametrize("kwargs, message_part", [
    ({"size": 0}, "leer"),
    ({"size": UploadService.MAX_FILE_SIZE + 1}, "zu groß"),
    ({"content_type": "image/png"}, "PDF"),
    ({"filename": "rechnung.pdf"}, "EINGANGSDATUM"),
    ({"filename": "2025074_OMEGA_ELEKTRO_Mueller.pdf"}, "EINGANGSDATUM"),
])
def test_invalid_files_are_rejected(kwargs, message_part):
    if kwargs.get("size") == 0:
        file_data = make_file()
        file_data.file_size = 0
    else:
        file_data = make_file(**kwargs)
    ok, error = service.validate_file(file_data)
    assert not ok
    assert message_part in error


def test_folder_watcher_upload_blocked_without_database():
    """Without the DB we can't rule out duplicates, so automated imports must stop."""
    ok, error = service.validate_file(make_file(source=UploadSource.FOLDER_WATCHER))
    assert not ok
    assert "Datenbank" in error


@pytest.mark.parametrize("source, expected", [
    (UploadSource.DRAG_DROP, "x.pdf"),
    (UploadSource.FOLDER_WATCHER, "folder_watcher/x.pdf"),
    (UploadSource.MANUAL, "manual/x.pdf"),
])
def test_storage_path_by_source(source, expected):
    assert service.generate_storage_path("x.pdf", source) == expected
