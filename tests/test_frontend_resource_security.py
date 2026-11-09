from pathlib import Path

import pytest

import frontend.resource_security as resource_security

from frontend.resource_security import (
    PROJECT_ROOT,
    resolve_resource_path,
)


def test_valid_document_path_is_allowed():

    result = resolve_resource_path({
        "content_path": "data/documents/normalization.pdf"
    })

    expected = (
        PROJECT_ROOT
        / "data"
        / "documents"
        / "normalization.pdf"
    ).resolve()

    assert result == str(expected)


@pytest.mark.parametrize(
    "resource_path",
    [
        "../.env",
        "../../.env",
        "data/../.env",
        "data/documents/../../.env",
        "C:/Windows/win.ini",
        "",
        "..\\..\\.env",
        "data\\..\\..\\.env",
        "data/documents/../../../secret.pdf",
        "data/documents/file\x00.pdf",
    ],
)
def test_unsafe_paths_are_rejected(resource_path):

    result = resolve_resource_path({
        "content_path": resource_path
    })

    assert result == ""


def test_non_pdf_file_is_rejected():

    result = resolve_resource_path({
        "content_path": "data/documents/example.txt"
    })

    assert result == ""


def test_absolute_path_is_rejected():

    absolute_path = str(
        PROJECT_ROOT
        / "data"
        / "documents"
        / "normalization.pdf"
    )

    result = resolve_resource_path({
        "content_path": absolute_path
    })

    assert result == ""


def test_non_dictionary_resource_is_rejected():

    assert resolve_resource_path(None) == ""

    assert (
        resolve_resource_path(
            "data/documents/normalization.pdf"
        ) == ""
    )


def test_valid_pdf_file_exists():

    result = resolve_resource_path({
        "content_path": "data/documents/normalization.pdf"
    })

    assert result
    assert Path(result).is_file()


def test_missing_pdf_file_is_rejected():

    result = resolve_resource_path({
        "content_path": "data/documents/this_file_does_not_exist.pdf"
    })

    assert result == ""


# ============================================================
# SYMLINK SECURITY TESTS
# ============================================================

def test_documents_directory_symlink_escape_is_rejected(
    tmp_path,
    monkeypatch,
):

    project_root = tmp_path / "project"
    outside_directory = tmp_path / "outside"

    project_root.mkdir()
    outside_directory.mkdir()

    documents_parent = project_root / "data"
    documents_parent.mkdir()

    outside_pdf = outside_directory / "outside.pdf"
    outside_pdf.write_bytes(b"%PDF-1.4 test")

    documents_directory = documents_parent / "documents"

    try:
        documents_directory.symlink_to(
            outside_directory,
            target_is_directory=True,
        )

    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are not supported.")

    monkeypatch.setattr(
        resource_security,
        "PROJECT_ROOT",
        project_root,
    )

    result = resolve_resource_path({
        "content_path": "data/documents/outside.pdf"
    })

    assert result == ""


def test_pdf_symlink_escape_is_rejected(
    tmp_path,
    monkeypatch,
):

    project_root = tmp_path / "project"
    documents_directory = (
        project_root / "data" / "documents"
    )

    documents_directory.mkdir(parents=True)

    outside_pdf = tmp_path / "outside.pdf"
    outside_pdf.write_bytes(b"%PDF-1.4 test")

    linked_pdf = documents_directory / "linked.pdf"

    try:
        linked_pdf.symlink_to(outside_pdf)

    except (OSError, NotImplementedError):
        pytest.skip("File symlinks are not supported.")

    monkeypatch.setattr(
        resource_security,
        "PROJECT_ROOT",
        project_root,
    )

    result = resolve_resource_path({
        "content_path": "data/documents/linked.pdf"
    })

    assert result == ""


def test_symlink_inside_documents_directory_is_allowed(
    tmp_path,
    monkeypatch,
):

    project_root = tmp_path / "project"
    documents_directory = (
        project_root / "data" / "documents"
    )

    documents_directory.mkdir(parents=True)

    original_pdf = documents_directory / "original.pdf"
    original_pdf.write_bytes(b"%PDF-1.4 test")

    linked_pdf = documents_directory / "linked.pdf"

    try:
        linked_pdf.symlink_to(original_pdf)

    except (OSError, NotImplementedError):
        pytest.skip("File symlinks are not supported.")

    monkeypatch.setattr(
        resource_security,
        "PROJECT_ROOT",
        project_root,
    )

    result = resolve_resource_path({
        "content_path": "data/documents/linked.pdf"
    })

    assert result == str(original_pdf.resolve())


# ============================================================
# RESOURCE METADATA TESTS
# ============================================================

@pytest.mark.parametrize(
    "resource",
    [
        {},
        {"content_path": None},
        {"content_path": ""},
        {"content_path": 123},
        {"content_path": ["normalization.pdf"]},
        {"content_path": "\x00"},
    ],
)
def test_invalid_resource_metadata_is_rejected(resource):

    assert resolve_resource_path(resource) == ""


def test_file_path_fallback_is_supported():

    result = resolve_resource_path({
        "file_path": "data/documents/normalization.pdf"
    })

    expected = (
        PROJECT_ROOT
        / "data"
        / "documents"
        / "normalization.pdf"
    ).resolve()

    assert result == str(expected)


def test_path_fallback_is_supported():

    result = resolve_resource_path({
        "path": "data/documents/normalization.pdf"
    })

    expected = (
        PROJECT_ROOT
        / "data"
        / "documents"
        / "normalization.pdf"
    ).resolve()

    assert result == str(expected)