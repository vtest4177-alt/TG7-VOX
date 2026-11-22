#!/usr/bin/env python3
"""Deterministic TG VOX re-branding script executed during autonomous upstream sync."""
import json
import re
import xml.sax.saxutils as xmlutils
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / ".github" / "tgvox-config.json"


def escape_kt(val: str) -> str:
    return val.replace("\\", "\\\\").replace('"', '\\"')


def escape_xml(val: str) -> str:
    return xmlutils.escape(val, {'"': "&quot;", "'": "&apos;"})


def patch_gradle(cfg: dict) -> None:
    app_id = cfg["applicationId"]
    app_name = cfg["appName"].replace('"', '\\"')
    for rel in ("androidApp/build.gradle.kts", "app/build.gradle.kts", "composeApp/build.gradle.kts"):
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        orig = text
        text = re.sub(
            r'(applicationId\s*=\s*System\.getenv\([^)]+\)\s*\?:\s*)"[^"]+"',
            rf'\1"{app_id}"',
            text,
        )
        if text == orig:
            text = re.sub(r'(applicationId\s*=\s*)"[^"]+"', rf'\1"{app_id}"', text)
        text = re.sub(r'(manifestPlaceholders\["appLabel"\]\s*=\s*)"[^"]+"', rf'\1"{app_name}"', text)
        if text != orig:
            p.write_text(text, encoding="utf-8")
            print(f"Patched {rel}")


def patch_strings(cfg: dict) -> None:
    app_name = cfg["appName"]
    dev_name = cfg["developerName"]
    esc_app = escape_xml(app_name)
    primary_candidates = {
        (ROOT / "shared/src/commonMain/composeResources/values/strings.xml").resolve(),
        (ROOT / "androidApp/src/main/res/values/strings.xml").resolve(),
        (ROOT / "app/src/main/res/values/strings.xml").resolve(),
    }
    all_string_files: list[Path] = []
    for base_rel in (
        "shared/src/commonMain/composeResources",
        "androidApp/src/main/res",
        "app/src/main/res",
        "composeApp/src/commonMain/composeResources",
    ):
        base = ROOT / base_rel
        if base.exists():
            all_string_files.extend(sorted(base.glob("values*/strings.xml")))

    replacements = [
        ("app_name", app_name),
        ("credits_creator", f"Creator of {app_name}"),
        ("credits_creator_section", "Developer"),
        ("credits_license_desc", f"{app_name} by {dev_name} · Licensed under GPL-3.0"),
        ("account_menu_license", f"GPL-3.0 {dev_name}"),
        ("equalizer_usage_warning", f"{app_name} assumes no responsibility for your use of MetroEQ."),
        ("settings_check_releases_summary", f"Check GitHub for a newer {app_name} release"),
        ("crash_imminent_title", f"{app_name} is about to crash"),
        ("discord_error_gateway_configuration", f"Discord rejected the connection configuration. Update {app_name} before trying again."),
    ]
    for p in all_string_files:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        orig = text
        is_primary = p.resolve() in primary_candidates
        if is_primary:
            for key, val in replacements:
                esc = escape_xml(val)
                text = re.sub(
                    rf'(<string\s+name=["\']{key}["\'][^>]*>)[\s\S]*?(</string>)',
                    lambda m, e=esc: f"{m.group(1)}{e}{m.group(2)}",
                    text,
                )

        def _scrub_tag(m: re.Match) -> str:
            open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
            if 'name="backup_filename_prefix"' in open_tag or "name='backup_filename_prefix'" in open_tag:
                return m.group(0)
            new_body = re.sub(
                r'(\\[nt]|(?<![A-Za-z/]))Metro[Ll]ist(?:-KMP)?(?!Group)',
                lambda mm, e=esc_app: f"{mm.group(1)}{e}",
                body,
            )
            return f"{open_tag}{new_body}{close_tag}"

        text = re.sub(r'(<string\s+[^>]*>)([\s\S]*?)(</string>)', _scrub_tag, text)
        if text != orig:
            p.write_text(text, encoding="utf-8")
            print(f"Patched {p.relative_to(ROOT)}")


def patch_manifest(cfg: dict) -> None:
    for rel in ("androidApp/src/main/AndroidManifest.xml", "app/src/main/AndroidManifest.xml"):
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        orig = text
        text = re.sub(r'android:icon="[^"]*"', 'android:icon="@mipmap/ic_launcher"', text)
        text = re.sub(r'android:roundIcon="[^"]*"', 'android:roundIcon="@mipmap/ic_launcher_round"', text)
        if text != orig:
            p.write_text(text, encoding="utf-8")
            print(f"Patched {rel}")


def patch_about(cfg: dict) -> None:
    dev = escape_kt(cfg["developerName"])
    gh = escape_kt(cfg["developerGithub"])
    repo = escape_kt(cfg["forkRepo"])
    branch = escape_kt(cfg.get("forkBranch") or "main")
    solo = bool(cfg.get("soloDeveloperMode", True))
    for p in ROOT.rglob("AboutContent.kt"):
        text = p.read_text(encoding="utf-8")
        orig = text
        new_lead = (
            'val lead: AboutContributor =\n'
            '        AboutContributor(\n'
            f'            name = "{dev}",\n'
            '            role = AboutContributorRole.CREATOR,\n'
            f'            githubHandle = "{gh}",\n'
            '            avatarShape = AboutAvatarShape.COOKIE_9_SIDED,\n'
            '        )\n'
        )
        text = re.sub(r'val lead:\s*AboutContributor\s*=[\s\S]*?(?=\n\s*val leads:)', new_lead, text)
        if solo:
            text = re.sub(r'val leads:\s*List<AboutContributor>\s*=[\s\S]*?(?=\n\s*val collaborators:)', 'val leads: List<AboutContributor> = emptyList()\n', text)
            text = re.sub(r'val collaborators:\s*List<AboutContributor>\s*=[\s\S]*?(?=\n\s*val all:)', 'val collaborators: List<AboutContributor> = emptyList()\n', text)
        text = text.replace("MetrolistGroup/Metrolist", repo)
        text = re.sub(r'(AboutCommunityLink\(AboutCommunityLinkKind\.LICENSE,\s*)"https://github\.com/[^"]+"', rf'\1"https://github.com/{repo}/blob/{branch}/LICENSE"', text)
        if text != orig:
            p.write_text(text, encoding="utf-8")
            print(f"Patched {p.relative_to(ROOT)}")

    for p in ROOT.rglob("AboutScreen.kt"):
        text = p.read_text(encoding="utf-8")
        orig = text
        text = text.replace("MetrolistGroup/Metrolist", repo)
        text = re.sub(r'"https://metrolist\.app/?[^"]*"', f'"https://github.com/{repo}"', text)
        text = re.sub(r'"Metrolist"', f'"{dev}"', text)
        if text != orig:
            p.write_text(text, encoding="utf-8")
            print(f"Patched {p.relative_to(ROOT)}")


def patch_updater(cfg: dict) -> None:
    if not cfg.get("enableInAppForkUpdater", True):
        return
    repo = cfg["forkRepo"]
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", cfg["appName"]) or "TG-VOX"
    safe_agent = re.sub(r"[^a-zA-Z0-9_-]+", "", cfg["appName"]) or "TGVOX"
    safe_lower = re.sub(r"[^a-z0-9]+", "-", cfg["appName"].lower()).strip("-") or "tg-vox"
    safe_apk = f"{safe_slug}.apk"
    for p in ROOT.rglob("LatestRelease.kt"):
        text = p.read_text(encoding="utf-8")
        next_text = text.replace(
            "https://api.github.com/repos/MetrolistGroup/Metrolist/releases/latest",
            f"https://api.github.com/repos/{repo}/releases/latest",
        )
        if next_text != text:
            p.write_text(next_text, encoding="utf-8")
            print(f"Patched {p.relative_to(ROOT)}")

    for p in ROOT.rglob("AppUpdateManager.kt"):
        text = p.read_text(encoding="utf-8")
        orig = text
        text = text.replace(
            "https://api.github.com/repos/MetrolistGroup/Metrolist/",
            f"https://api.github.com/repos/{repo}/",
        )
        text = text.replace(
            "https://github.com/MetrolistGroup/Metrolist/",
            f"https://github.com/{repo}/",
        )
        if f'"{safe_apk}"' not in text:
            text = re.sub(
                r'(private val PREFERRED_APK_NAMES\s*=\s*listOf\()',
                rf'\1\n        "{safe_apk}",',
                text,
            )
        text = text.replace('"Metrolist/${BuildConfig.VERSION_NAME}"', f'"{safe_agent}/${{BuildConfig.VERSION_NAME}}"')
        text = text.replace('"Metrolist-${release.version}.apk.part"', f'"{safe_slug}-${{release.version}}.apk.part"')
        text = text.replace('"Metrolist-${release.version}.apk"', f'"{safe_slug}-${{release.version}}.apk"')
        if text != orig:
            p.write_text(text, encoding="utf-8")
            print(f"Patched {p.relative_to(ROOT)}")

    for p in ROOT.rglob("UpdatesScreen.kt"):
        text = p.read_text(encoding="utf-8")
        next_text = text.replace('"metrolist-"', f'"{safe_lower}-"')
        if next_text != text:
            p.write_text(next_text, encoding="utf-8")
            print(f"Patched {p.relative_to(ROOT)}")


def patch_ios(cfg: dict) -> None:
    app_name = cfg["appName"]
    safe_prod = re.sub(r"[^a-zA-Z0-9_-]+", "", app_name) or "TGVOX"
    bundle = cfg["iosBundleId"]
    xcconfig = ROOT / "iosApp/Configuration/Config.xcconfig"
    if xcconfig.exists():
        text = xcconfig.read_text(encoding="utf-8")
        orig = text
        text = re.sub(r'^PRODUCT_NAME\s*=.*$', f'PRODUCT_NAME = {safe_prod}', text, flags=re.M)
        text = re.sub(r'^PRODUCT_BUNDLE_IDENTIFIER\s*=.*$', f'PRODUCT_BUNDLE_IDENTIFIER = {bundle}', text, flags=re.M)
        if text != orig:
            xcconfig.write_text(text, encoding="utf-8")
            print("Patched iosApp/Configuration/Config.xcconfig")

    plist = ROOT / "iosApp/Configuration/Info.plist"
    if plist.exists():
        text = plist.read_text(encoding="utf-8")
        orig = text
        esc_app = escape_xml(app_name)
        text = re.sub(
            r'(<key>CFBundleDisplayName</key>\s*<string>)[\s\S]*?(</string>)',
            lambda m: f"{m.group(1)}{esc_app}{m.group(2)}",
            text,
        )
        scheme = re.sub(r"[^a-z0-9]+", "", app_name.lower()) or "tgvox"
        if "<key>CFBundleURLSchemes</key>" in text and f"<string>{scheme}</string>" not in text:
            text = re.sub(
                r'(<key>CFBundleURLSchemes</key>\s*<array>)',
                rf'\1\n                <string>{scheme}</string>',
                text,
            )
        if bundle and "com.metrolist.automatic-backup" in text:
            text = text.replace("com.metrolist.automatic-backup", f"{bundle}.automatic-backup")
        if text != orig:
            plist.write_text(text, encoding="utf-8")
            print("Patched iosApp/Configuration/Info.plist")

    build_sh = ROOT / "scripts/build_ios.sh"
    if build_sh.exists():
        text = build_sh.read_text(encoding="utf-8")
        next_text = re.sub(r'^bundle_id="[^"]+"', f'bundle_id="{bundle}"', text, flags=re.M)
        if next_text != text:
            build_sh.write_text(next_text, encoding="utf-8")
            print("Patched scripts/build_ios.sh")


def clean_conflicting_icons() -> None:
    for res_base in ("androidApp/src/main/res", "app/src/main/res"):
        base = ROOT / res_base
        if not base.exists():
            continue
        for pat in (
            "mipmap-mdpi/ic_launcher*.webp",
            "mipmap-hdpi/ic_launcher*.webp",
            "mipmap-xhdpi/ic_launcher*.webp",
            "mipmap-xxhdpi/ic_launcher*.webp",
            "mipmap-xxxhdpi/ic_launcher*.webp",
            "mipmap-mdpi/ic_launcher*.xml",
            "mipmap-hdpi/ic_launcher*.xml",
            "mipmap-xhdpi/ic_launcher*.xml",
            "mipmap-xxhdpi/ic_launcher*.xml",
            "mipmap-xxxhdpi/ic_launcher*.xml",
            "mipmap-anydpi/ic_launcher*.xml",
        ):
            for f in base.glob(pat):
                f.unlink()
                print(f"Removed conflicting icon: {f.relative_to(ROOT)}")


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    target_mode = cfg.get("targetMode", "both")
    if target_mode != "ios-only":
        patch_gradle(cfg)
        patch_manifest(cfg)
    patch_strings(cfg)
    patch_about(cfg)
    patch_updater(cfg)
    if target_mode != "android-only":
        patch_ios(cfg)
    if target_mode != "ios-only":
        clean_conflicting_icons()


if __name__ == "__main__":
    main()
