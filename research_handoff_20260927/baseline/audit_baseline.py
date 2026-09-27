"""Read-only baseline audit. Writes only this audit's result files.

This does not build, deploy, launch, inspect processes, or modify existing assets.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
import zipfile

OUT = Path(__file__).resolve().parent
REPO = Path(r"C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced")
OLD = Path(r"E:\File\Codes\0\26.9.1\HD2")
EXPECTED = "0e536c29908001513115dafdabe366f45d126b6bbf09e39377c045ee1d024783"
MOD = "Projectile-Collision-Filter-v0.3.0-preview.8-build25480438.zip"
TOOLKIT = "HD2-Projectile-Collision-Filter-Update-Toolkit-1.3.2-win-x64.zip"
GH = "https://api.github.com/repos/cainiao524/HD2-Projectile-Collision-Filter/releases/tags/v0.3.0-preview.8"
AYAKA = "https://ayakamods.com/mods/p-11-self-hit-healing-p-11-%E6%B2%BB%E7%99%82%E6%89%8B%E6%A7%8D%E8%87%AA%E7%99%82.4166/"


def digest(data):
    return sha256(data).hexdigest()


def record(path):
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha256": digest(data)}


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "HD2-Generation-ReadOnly-Audit"}), timeout=45) as response:
        data = response.read()
        final = urlsplit(response.url)
        final_url = urlunsplit((final.scheme, final.netloc, final.path, "", ""))
        return data, {"request_url": url, "final_url_without_query": final_url,
                      "status": response.status, "size": len(data), "sha256": digest(data)}


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def zip_entries(path):
    with zipfile.ZipFile(path) as archive:
        return {name: digest(archive.read(name)) for name in archive.namelist() if not name.endswith("/")}


def main():
    now = datetime.now(timezone.utc).isoformat()
    protected = [
        REPO / "dist/release" / MOD,
        REPO / "dist/release" / TOOLKIT,
        REPO / "dist" / MOD,
        REPO / "dist/candidates/v0.3.0-preview.8/Projectile-Collision-Filter-v0.3.0-preview.8-build25480438-CANDIDATE.zip",
        REPO / "dist/candidates/v0.3.0-preview.9/Projectile-Collision-Filter-v0.3.0-preview.9-candidate-build25480438.zip",
        REPO / "dist/candidates/v0.3.0-preview.9/candidate-manifest.json",
        REPO / "dist/candidates/filediver-maintenance/HD2-Projectile-Collision-Filter-Update-Toolkit-1.4.0-candidate-win-x64.zip",
        REPO / "dist/homing stim-performance-visual-fix-smooth-v2.zip",
        REPO / "vendor/homing-original.lua",
        REPO / "third-party/homing.json",
        OLD / "_pcf_assets" / MOD,
        OLD / "_pcf_assets" / TOOLKIT,
        OLD / "_pcf_checkout/HD2-Projectile-Collision-Filter-main/dist" / MOD,
    ]
    for subdir in ("mods/projectile_collision_filter", "mods/projectile_collision_filter_candidate"):
        protected.extend(p for p in (REPO / subdir).rglob("*")
                         if p.is_file() and "__pycache__" not in p.parts)
    inventory = [record(path) for path in sorted(set(protected))]
    save("protected-assets.before.json", {"observed_at_utc": now, "repo": str(REPO), "files": inventory})

    ayaka_bytes, ayaka_http = fetch(AYAKA)
    html = ayaka_bytes.decode("utf-8")
    h1 = re.search(r"<h1>.*?</h1>", html, re.S)
    version = re.search(r"<dt>Version</dt>\s*<dd>(.*?)</dd>", html)
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    advertised = re.search(r"<b>v0\.3\.0-preview\.8 is a four-choice integrated prerelease\.</b>", html)
    if not all((h1, version, canonical, advertised)):
        raise RuntimeError("Required visible AyakaMods version evidence is absent")
    ayaka = {"observed_at_utc": now, **ayaka_http,
             "canonical_url": canonical.group(1),
             "visible_h1_html": h1.group(0), "visible_version_html": version.group(0),
             "visible_version": version.group(1), "body_version_excerpt_html": advertised.group(0),
             "interpretation": "The visible site version is 0.5 while its description advertises v0.3.0-preview.8. No AyakaMods download fingerprint has been established; use the GitHub fingerprinted baseline."}
    save("ayakamods-version.json", ayaka)

    gh_bytes, gh_http = fetch(GH)
    release = json.loads(gh_bytes)
    assets = [{k: asset.get(k) for k in ("id", "name", "size", "digest", "browser_download_url", "updated_at")}
              for asset in release["assets"]]
    selected = next(asset for asset in assets if asset["name"] == MOD)
    zip_bytes, download = fetch(selected["browser_download_url"])
    if digest(zip_bytes) != EXPECTED:
        raise RuntimeError("Downloaded release mod differs from the required fingerprint")
    # The remote archive is hashed in memory; no duplicate mod ZIP is generated here.
    github = {"observed_at_utc": now, **gh_http,
              "html_url": release["html_url"], "tag_name": release["tag_name"],
              "target_commitish": release["target_commitish"], "prerelease": release["prerelease"],
              "published_at": release["published_at"], "assets": assets,
              "mod_download": download, "expected_mod_sha256": EXPECTED,
              "download_matches_expected": True}
    save("github-preview8.json", github)

    baseline = OLD / "_pcf_assets" / MOD
    rebuild = OLD / "_pcf_checkout/HD2-Projectile-Collision-Filter-main/dist" / MOD
    a, b = zip_entries(baseline), zip_entries(rebuild)
    comparison = {"baseline": record(baseline), "local_same_name": record(rebuild),
                  "only_baseline": sorted(a.keys() - b.keys()),
                  "only_local_same_name": sorted(b.keys() - a.keys()),
                  "different_contents": [{"entry": name, "baseline_sha256": a[name], "local_sha256": b[name]}
                                         for name in sorted(a.keys() & b.keys()) if a[name] != b[name]],
                  "same_entry_contents": a == b}
    save("same-name-archive-comparison.json", comparison)

    after = [record(Path(item["path"])) for item in inventory]
    if after != inventory:
        raise RuntimeError("A protected asset changed during the baseline audit")
    save("protected-assets.after.json", {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
                                        "matches_before": True, "files": after})
    print(json.dumps({"protected_files": len(inventory), "protected_unchanged": True,
                      "ayakamods_visible_version": ayaka["visible_version"],
                      "github_download_sha256": download["sha256"],
                      "same_name_archive_differences": len(comparison["different_contents"]),
                      "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1:] == ["--verify-preserved"]:
        original = json.loads((OUT / "protected-assets.before.json").read_text(encoding="utf-8"))["files"]
        current = [record(Path(item["path"])) for item in original]
        if current != original:
            raise RuntimeError("A protected asset differs from the audit baseline")
        print(f"PASS: {len(original)} protected files retain their recorded fingerprints")
    elif sys.argv[1:]:
        raise SystemExit("usage: audit_baseline.py [--verify-preserved]")
    else:
        main()
