"""Promote the latest successful private main build to a public Release."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
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
    if os.environ["GITHUB_EVENT_NAME"] == "push" and Path(".github/release-request").read_text().strip() != tag:
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
    if code == "26112302" and digest != FIRST:
        raise ValueError("Initial APK digest mismatch")
    if code != "26112302":
        notes, = [a for a in artifacts if a["name"] == "public-notes-" + code]
        read_archive(notes, token, "notes.json")
    print(f"Verified {name} sha256:{digest}")


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
    if current["draft"]:
        body = current.get("body") or ""
        if (TMP / "notes.json").exists():
            notes = json.loads((TMP / "notes.json").read_text())
            if code not in notes:
                raise ValueError("Missing release notes for the selected build")
            body = "\n\n".join(notes[key].strip() for key in sorted(notes, key=int, reverse=True)
                              if previous < int(key) <= int(code))
        if not body.strip():
            raise ValueError("Release notes are empty")
        write(f"/releases/{current['id']}", "PATCH", dict(draft=False, prerelease=False, make_latest="true", body=body))
    latest = json.loads(api(PUBLIC + "/releases/latest", token))
    if latest["tag_name"] != tag or not any(a["name"] == apk.name and a["digest"] == digest for a in latest["assets"]):
        raise ValueError("Published release not found in latest feed")
    print(latest["html_url"])


if __name__ == "__main__":
    {"retrieve": retrieve, "publish": publish}[sys.argv[1]]()
