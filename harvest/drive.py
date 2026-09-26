"""정책문서 폴더 읽기·업로드."""

from __future__ import annotations

import mimetypes

FOLDER_ID = "1-VLB42YhmZZIMxoR48J2qeIYgMYMdAK5"  # Policy Fit 정책문서 폴더(비밀 아님)

MIME = {
    "pdf": "application/pdf",
    "hwp": "application/x-hwp",
    "hwpx": "application/haansofthwpx",
}


def list_names(svc, folder_id: str = FOLDER_ID) -> list[dict]:
    files, token = [], None
    while True:
        res = (
            svc.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,size)",
                pageSize=1000,
                pageToken=token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files += res.get("files", [])
        token = res.get("nextPageToken")
        if not token:
            return files


def upload(svc, path: str, name: str, folder_id: str = FOLDER_ID) -> dict:
    """같은 이름이 있으면 올리지 않고 예외를 낸다."""
    from googleapiclient.http import MediaFileUpload

    if any(f["name"] == name for f in list_names(svc, folder_id)):
        raise FileExistsError(name)
    ext = name.rsplit(".", 1)[-1].lower()
    mime = MIME.get(ext) or mimetypes.guess_type(name)[0] or "application/octet-stream"
    media = MediaFileUpload(path, mimetype=mime, resumable=True)
    return (
        svc.files()
        .create(
            body={"name": name, "parents": [folder_id]},
            media_body=media,
            fields="id,name,webViewLink,owners(emailAddress)",
            supportsAllDrives=True,
        )
        .execute()
    )


def delete(svc, file_id: str) -> None:
    svc.files().delete(fileId=file_id, supportsAllDrives=True).execute()
