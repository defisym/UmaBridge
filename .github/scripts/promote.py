"""Promote the latest successful private main build to a public Release."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PRIVATE = "https://api.github.com/repos/defisym/UmaBridgeDev"
PUBLIC = "https://api.github.com/repos/defisym/UmaBridge"
UPLOAD = "https://uploads.github.com/repos/defisym/UmaBridge"
TMP = Path(os.environ["RUNNER_TEMP"]) / "verified-release"
APK = r"UmaBridge-(\d+(?:\.\d+){1,3})-([1-9]\d*)-arm64\.apk"
TAG = r"v(\d+(?:\.\d+){1,3})-([1-9]\d*)"
CERT = "78ee0f8e264cce5f297ced94f11c419e340384ca3126a1f067ce33efee5b5697"
FIRST = "f02602f98eaa4780d1e001076eaa9296dbb545c244eda02eea9a797394a1c26d"


def api(url, token, *args):
    # curl strips Authorization on redirects to a different host.
    return subprocess.check_output(["curl", "--silent", "--show-error", "--fail",
        "--location", "--proto", "=https", "-H", "Authorization: Bearer " + token,
        "-H", "Accept: application/vnd.github+json", *args, url])


def read_archive(artifact, token, filename):
    if artifact["expired"]:
        raise ValueError("The requested artifact has expired")
    path = TMP / "artifact.zip"
    api(f"{PRIVATE}/actions/artifacts/{artifact['id']}/zip", token, "-o", str(path))
    if "sha256:" + hashlib.file_digest(path.open("rb"), "sha256").hexdigest() != artifact["digest"]:
        raise ValueError("Artifact archive digest mismatch")
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != [filename]:
            raise ValueError("Unexpected artifact contents")
        with archive.open(filename) as src, (TMP / filename).open("wb") as dst:
            shutil.copyfileobj(src, dst)


def retrieve():
    token = os.environ["ARTIFACT_TOKEN"]
    if not token:
        raise ValueError("Configure UMABRIDGE_DEV_ARTIFACTS_READ on the public repository")
    TMP.mkdir()
    runs = json.loads(api(PRIVATE + "/actions/workflows/release-apk.yml/runs?branch=main&status=success&per_page=1", token))
    run = runs["workflow_runs"][0]
    if run["head_repository"]["full_name"] != "defisym/UmaBridgeDev" or run["event"] not in ("push", "workflow_dispatch"):
        raise ValueError("Unexpected build origin")
    artifacts = json.loads(api(f"{PRIVATE}/actions/runs/{run['id']}/artifacts", token))["artifacts"]
    artifact, = [a for a in artifacts if re.fullmatch(APK, a["name"])]
    name = artifact["name"]
    version, code = re.fullmatch(APK, name).groups()
    tag = f"v{version}-{code}"
    request = Path(".github/release-request").read_text().split() if os.environ["GITHUB_EVENT_NAME"] == "push" else []
    if request and request[0] != tag:
        raise ValueError("Latest signed build does not match the requested tag")
    read_archive(artifact, token, name)
    apk = TMP / name
    sdk = Path(os.environ["ANDROID_HOME"]) / "build-tools/35.0.0"
    cert = subprocess.check_output([sdk / "apksigner", "verify", "--print-certs", apk], text=True)
    if re.findall(r"^Signer #\d+ certificate SHA-256 digest: (\w+)$", cert, re.M) != [CERT]:
        raise ValueError("Unexpected APK signer")
    badging = subprocess.check_output([sdk / "aapt", "dump", "badging", apk], text=True)
    if (f"package: name='local.umabridge.notify' versionCode='{code}' versionName='{version}'" not in badging
            or "native-code: 'arm64-v8a'" not in badging.splitlines() or "application-debuggable" in badging):
        raise ValueError("APK manifest does not match artifact")
    digest = hashlib.file_digest(apk.open("rb"), "sha256").hexdigest()
    if len(request) > 1 and request[1:] != [digest]:
        raise ValueError("Signed build differs from the APK approved for publication")
    if code == "26112302" and digest != FIRST:
        raise ValueError("Initial APK digest mismatch")
    if code != "26112302":
        notes, = [a for a in artifacts if a["name"] == "public-notes-" + code]
        read_archive(notes, token, "notes.json")
    print(f"Verified {name} sha256:{digest}")


def merge_notes(notes, previous, code):
    entries = {"中文": {}, "English": {}}
    for key in sorted(notes, key=int, reverse=True):
        if not previous < int(key) <= code:
            continue
        parts = re.split(r"(?m)^### (中文|English)[ \t]*$", notes[key].strip())
        if len(parts) != 5 or parts[0].strip() or set(parts[1::2]) != entries.keys():
            raise ValueError(f"Expected Chinese and English release notes for build {key}")
        for language, section in zip(parts[1::2], parts[2::2]):
            for block in re.split(r"(?m)(?=^- )", section.strip()):
                block = block.strip()
                if block:
                    # Older generated notes may be a single paragraph.
                    item = block if block.startswith("- ") else "- " + block
                    entries[language][item] = None
    return "\n\n".join(f"### {language}\n\n" + "\n".join(items)
                       for language, items in entries.items() if items)


def publish():
    token = os.environ["RELEASE_TOKEN"]
    apk, = TMP.glob("*.apk")
    version, code = re.fullmatch(APK, apk.name).groups()
    tag = f"v{version}-{code}"
    releases = []
    for page in range(1, 1000):
        batch = json.loads(api(f"{PUBLIC}/releases?per_page=100&page={page}", token))
        releases.extend(batch)
        if len(batch) < 100:
            break
    current = next((r for r in releases if r["tag_name"] == tag), None)
    previous = max((int(m[2]) for r in releases if not r["draft"] and not r["prerelease"]
                    and (m := re.fullmatch(TAG, r["tag_name"])) and r["tag_name"] != tag), default=0)
    if int(code) <= previous:
        raise ValueError("A newer build is already public")
    def write(path, method, data):
        return json.loads(api(PUBLIC + path, token, "-X", method, "-H", "Content-Type: application/json",
                              "--data-binary", json.dumps(data)))
    if not current:
        current = write("/releases", "POST", dict(tag_name=tag, target_commitish=os.environ["GITHUB_SHA"],
                        name=f"UmaBridge {version} ({code})", draft=True))
    digest = "sha256:" + hashlib.file_digest(apk.open("rb"), "sha256").hexdigest()
    asset = next((a for a in current["assets"] if a["name"] == apk.name), None)
    if not asset:
        if not current["draft"]:
            raise ValueError("Existing public release has no matching APK")
        url = f"{UPLOAD}/releases/{current['id']}/assets?name={apk.name}"
        asset = json.loads(api(url, token, "-H", "Content-Type: application/vnd.android.package-archive",
                               "--data-binary", "@" + str(apk)))
    if asset["digest"] != digest or asset["size"] != apk.stat().st_size or asset["state"] != "uploaded":
        raise ValueError("Release asset failed verification")
    body = current.get("body") or ""
    if current["draft"] and (TMP / "notes.json").exists():
        notes = json.loads((TMP / "notes.json").read_text())
        if code not in notes:
            raise ValueError("Missing release notes for the selected build")
        body = merge_notes(notes, previous, int(code))
    if not body.strip():
        raise ValueError("Release notes are empty")
    if int(code) >= 26112304:
        # GitHub can assign an untagged download URL while the release is a draft.
        public_asset = {key: asset[key] for key in ("name", "size", "digest")}
        public_asset["browser_download_url"] = f"https://github.com/defisym/UmaBridge/releases/download/{tag}/{apk.name}"
        manifest = dict(tag_name=tag, draft=False, prerelease=False, body=body, assets=[public_asset])
        path = TMP / "update.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        companion = next((a for a in current["assets"] if a["name"] == "update.json"), None)
        if companion is None:
            companion = json.loads(api(f"{UPLOAD}/releases/{current['id']}/assets?name=update.json", token,
                "-H", "Content-Type: application/json", "--data-binary", "@" + str(path)))
        if companion["digest"] != expected or companion["state"] != "uploaded":
            raise ValueError("Update manifest digest mismatch")
    if current["draft"]:
        write(f"/releases/{current['id']}", "PATCH", dict(draft=False, prerelease=False, make_latest="true", body=body))
    latest = json.loads(api(PUBLIC + "/releases/latest", token))
    if latest["tag_name"] != tag or not any(a["name"] == apk.name and a["digest"] == digest for a in latest["assets"]):
        raise ValueError("Published release not found in latest feed")
    print(latest["html_url"])


def public_check():
    def download(url, *args):
        return subprocess.check_output(["curl", "--silent", "--show-error", "--fail", "--location",
            "--proto", "=https", "--retry", "3", "--retry-all-errors", "--max-time", "75",
            "-A", "UmaBridge-Android", "-H", "Accept: application/octet-stream", *args, url])

    apk, = TMP.glob("*.apk")
    version, code = re.fullmatch(APK, apk.name).groups()
    tag = f"v{version}-{code}"
    base = "https://github.com/defisym/UmaBridge/releases"
    apk_url = f"{base}/download/{tag}/{apk.name}"
    with apk.open("rb") as original:
        digest = "sha256:" + hashlib.file_digest(original, "sha256").hexdigest()
    if int(code) >= 26112304:
        expected = json.loads((TMP / "update.json").read_bytes())
        for attempt in range(6):
            public = json.loads(download(base + "/latest/download/update.json"))
            if public == expected:
                break
            if attempt == 5:
                raise ValueError("Public manifest does not match the verified release")
            time.sleep(5)
    copy = TMP / "public-download.bin"
    download(apk_url, "-o", str(copy))
    with copy.open("rb") as downloaded:
        if copy.stat().st_size != apk.stat().st_size or "sha256:" + hashlib.file_digest(downloaded, "sha256").hexdigest() != digest:
            raise ValueError("Public APK download mismatch")

    # The optional legacy client check is separate from the current, API-independent path.
    req = urllib.request.Request(PUBLIC + "/releases/latest",
            headers={"User-Agent": "UmaBridge-Android", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            legacy = json.load(response)
    except urllib.error.HTTPError as exc:
        limited = exc.code in (403, 429) and (exc.code == 429 or exc.headers.get("X-RateLimit-Remaining") == "0"
                  or "rate limit" in exc.read(8192).decode(errors="replace").lower())
        if int(code) < 26112304 or not limited:
            raise
        print("The legacy anonymous API was rate-limited. The current public manifest and APK passed without the API.")
    else:
        asset, = [a for a in legacy["assets"] if a["name"] == apk.name]
        if (legacy["tag_name"] != tag or legacy["draft"] or legacy["prerelease"] or asset["browser_download_url"] != apk_url
                or asset["digest"] != digest or asset["size"] != apk.stat().st_size):
            raise ValueError("Legacy API metadata mismatch")
    print(f"Anonymous update check and APK download passed for {tag}")


if __name__ == "__main__":
    {"retrieve": retrieve, "publish": publish, "public-check": public_check}[sys.argv[1]]()
