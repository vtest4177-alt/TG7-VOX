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
        if "sharedOkHttpClient" in text and "retryOnConnectionFailure(true)" not in text:
            if "import java.util.concurrent.TimeUnit" not in text:
                text = re.sub(
                    r"(import java\.io\.File\n)",
                    r"\1import java.io.FileOutputStream\nimport java.util.concurrent.TimeUnit\n",
                    text,
                )
            if "import kotlinx.coroutines.NonCancellable" not in text:
                text = re.sub(
                    r"(import kotlinx\.coroutines\.withContext\n)",
                    r"import kotlinx.coroutines.NonCancellable\nimport kotlinx.coroutines.delay\n\1",
                    text,
                )
            text = re.sub(
                r"private val client =\s*\n\s*sharedOkHttpClient\s*\n\s*\.newBuilder\(\)\s*\n\s*\.build\(\)",
                "private val client =\n        sharedOkHttpClient\n            .newBuilder()\n            .connectTimeout(30, TimeUnit.SECONDS)\n            .readTimeout(90, TimeUnit.SECONDS)\n            .writeTimeout(30, TimeUnit.SECONDS)\n            .callTimeout(0, TimeUnit.MILLISECONDS)\n            .retryOnConnectionFailure(true)\n            .build()",
                text,
            )
            if "userCanceled" not in text:
                text = re.sub(
                    r"(@Volatile private var activeDownload: Call\? = null)",
                    r"\1\n    @Volatile private var userCanceled = false",
                    text,
                )
            dl_pat = re.compile(
                r'    @SuppressLint\("UsableSpace"\)\s*\n\s*private suspend fun downloadOnce\([\s\S]*?\n    fun cancelDownload\(\)\s*\{\s*\n\s*activeDownload\?\.cancel\(\)\s*\n\s*\}'
            )
            if dl_pat.search(text):
                replacement_dl = (
                    '    @SuppressLint("UsableSpace")\n'
                    '    private suspend fun downloadOnce(\n'
                    '        context: Context,\n'
                    '        release: GitHubRelease,\n'
                    '        crashRecovery: Boolean,\n'
                    '        skipVerification: Boolean,\n'
                    '    ) = withContext(Dispatchers.IO + NonCancellable) {\n'
                    '        var packageMismatch = false\n'
                    '        operationMutex.withLock {\n'
                    '            when (val active = mutableState.value) {\n'
                    '                is AppUpdateState.Downloading -> if (active.release.updateKey == release.updateKey) return@withLock\n'
                    '                is AppUpdateState.Downloaded -> if (active.release.updateKey == release.updateKey && active.file.isFile) return@withLock\n'
                    '                else -> Unit\n'
                    '            }\n'
                    '            val asset = release.apk\n'
                    '            if (asset == null) {\n'
                    '                mutableState.value = AppUpdateState.Error(UpdateFailure.NO_APK, release)\n'
                    '                return@withLock\n'
                    '            }\n'
                    '            userCanceled = false\n'
                    '            runCatching {\n'
                    '                check(asset.size in 1..MAX_APK_BYTES) { "Invalid update size" }\n'
                    '                val updateDir = File(context.cacheDir, "updates").apply { mkdirs() }\n'
                    '                updateDir.listFiles()?.forEach(File::delete)\n'
                    f'                val partial = File(updateDir, "{safe_slug}-${{release.version}}.apk.part")\n'
                    f'                val output = File(updateDir, "{safe_slug}-${{release.version}}.apk")\n'
                    '                check(updateDir.usableSpace > asset.size + MIN_FREE_SPACE_BYTES) { "Insufficient space for update" }\n'
                    '                var downloaded = 0L\n'
                    '                var lastError: Throwable? = null\n'
                    '                for (attempt in 0 until 4) {\n'
                    '                    if (userCanceled) error("Download canceled")\n'
                    '                    val resumeFrom = if (partial.isFile) partial.length().coerceIn(0L, asset.size) else 0L\n'
                    '                    downloaded = resumeFrom\n'
                    '                    if (downloaded == asset.size) {\n'
                    '                        lastError = null\n'
                    '                        break\n'
                    '                    }\n'
                    '                    val attemptResult =\n'
                    '                        runCatching {\n'
                    '                            val reqBuilder =\n'
                    '                                Request\n'
                    '                                    .Builder()\n'
                    '                                    .url(asset.downloadUrl)\n'
                    f'                                    .header("User-Agent", "{safe_agent}/${{BuildConfig.VERSION_NAME}}")\n'
                    '                                    .header("Accept-Encoding", "identity")\n'
                    '                            if (resumeFrom > 0L) {\n'
                    '                                reqBuilder.header("Range", "bytes=$resumeFrom-")\n'
                    '                            }\n'
                    '                            val call = client.newCall(reqBuilder.build()).also { activeDownload = it }\n'
                    '                            call.execute().use { response ->\n'
                    '                                check(response.isSuccessful) { "Download returned ${response.code}" }\n'
                    '                                val append = response.code == 206 && resumeFrom > 0L\n'
                    '                                if (!append) downloaded = 0L\n'
                    '                                val body = checkNotNull(response.body)\n'
                    '                                val responseLength = body.contentLength()\n'
                    '                                val expectedRemaining = if (append) asset.size - downloaded else asset.size\n'
                    '                                if (responseLength >= 0 && responseLength != expectedRemaining) {\n'
                    '                                    packageMismatch = true\n'
                    '                                    error("Update response size mismatch")\n'
                    '                                }\n'
                    '                                val total = asset.size\n'
                    '                                body.byteStream().use { input ->\n'
                    '                                    FileOutputStream(partial, append).buffered().use { target ->\n'
                    '                                        val buffer = ByteArray(32 * 1024)\n'
                    '                                        while (true) {\n'
                    '                                            if (userCanceled) error("Download canceled")\n'
                    '                                            val count = input.read(buffer)\n'
                    '                                            if (count < 0) break\n'
                    '                                            if (downloaded + count > asset.size) packageMismatch = true\n'
                    '                                            check(downloaded + count <= asset.size && downloaded + count <= MAX_APK_BYTES) {\n'
                    '                                                "Update exceeded the expected size"\n'
                    '                                            }\n'
                    '                                            check(updateDir.usableSpace > count + MIN_FREE_SPACE_BYTES) { "Insufficient space for update" }\n'
                    '                                            target.write(buffer, 0, count)\n'
                    '                                            downloaded += count\n'
                    '                                            val progress = if (total > 0) ((downloaded * 100) / total).toInt().coerceIn(0, 100) else 0\n'
                    '                                            mutableState.value = AppUpdateState.Downloading(release, progress)\n'
                    '                                        }\n'
                    '                                        target.flush()\n'
                    '                                    }\n'
                    '                                }\n'
                    '                            }\n'
                    '                        }\n'
                    '                    if (attemptResult.isSuccess && downloaded == asset.size) {\n'
                    '                        lastError = null\n'
                    '                        break\n'
                    '                    }\n'
                    '                    lastError = attemptResult.exceptionOrNull()\n'
                    '                    if (userCanceled || packageMismatch) break\n'
                    '                    if (attempt < 3) delay((attempt + 1) * 900L)\n'
                    '                }\n'
                    '                lastError?.let { throw it }\n'
                    '                if (downloaded != asset.size || (!skipVerification && !verifyDigest(partial, asset.digest))) {\n'
                    '                    packageMismatch = true\n'
                    '                    partial.delete()\n'
                    '                    mutableState.value = AppUpdateState.Error(UpdateFailure.DIGEST, release)\n'
                    '                    return@runCatching\n'
                    '                }\n'
                    '                check(partial.renameTo(output)) { "Could not finalize update" }\n'
                    '                if (!skipVerification && !verifyApkIdentity(context, output)) {\n'
                    '                    output.delete()\n'
                    '                    mutableState.value = AppUpdateState.Error(UpdateFailure.DIGEST, release)\n'
                    '                    return@runCatching\n'
                    '                }\n'
                    '                if (!crashRecovery) Settings.shared.pendingUpdateReleaseJson = json.encodeToString(release)\n'
                    '                mutableState.value = AppUpdateState.Downloaded(release, output, verified = !skipVerification)\n'
                    '            }.onFailure {\n'
                    '                mutableState.value =\n'
                    '                    if (userCanceled || activeDownload?.isCanceled() == true) {\n'
                    '                        AppUpdateState.Available(release)\n'
                    '                    } else {\n'
                    '                        AppUpdateState.Error(UpdateFailure.DOWNLOAD, release)\n'
                    '                    }\n'
                    '            }\n'
                    '            activeDownload = null\n'
                    '        }\n'
                    '        packageMismatch\n'
                    '    }\n\n'
                    '    fun cancelDownload() {\n'
                    '        userCanceled = true\n'
                    '        activeDownload?.cancel()\n'
                    '    }'
                )
                text = dl_pat.sub(lambda _m: replacement_dl, text, count=1)
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


def patch_splash(cfg: dict) -> None:
    if not cfg.get("enablePremiumSplash", True):
        return
    safe_app = escape_kt(cfg.get("appName") or "TG VOX")
    required_imports = [
        "import android.graphics.Bitmap",
        "import androidx.compose.animation.core.Animatable",
        "import androidx.compose.animation.core.FastOutSlowInEasing",
        "import androidx.compose.animation.core.LinearEasing",
        "import androidx.compose.animation.core.tween",
        "import androidx.compose.foundation.Canvas",
        "import androidx.compose.foundation.Image",
        "import androidx.compose.foundation.background",
        "import androidx.compose.foundation.border",
        "import androidx.compose.foundation.clickable",
        "import androidx.compose.foundation.interaction.MutableInteractionSource",
        "import androidx.compose.foundation.layout.padding",
        "import androidx.compose.foundation.layout.size",
        "import androidx.compose.foundation.shape.RoundedCornerShape",
        "import androidx.compose.runtime.Composable",
        "import androidx.compose.runtime.LaunchedEffect",
        "import androidx.compose.runtime.saveable.rememberSaveable",
        "import androidx.compose.ui.draw.clip",
        "import androidx.compose.ui.geometry.Offset",
        "import androidx.compose.ui.graphics.Brush",
        "import androidx.compose.ui.graphics.Color",
        "import androidx.compose.ui.graphics.asImageBitmap",
        "import androidx.compose.ui.graphics.drawscope.Stroke",
        "import androidx.compose.ui.graphics.graphicsLayer",
        "import androidx.compose.ui.layout.ContentScale",
        "import androidx.compose.ui.platform.LocalContext",
        "import androidx.compose.ui.text.font.FontWeight",
        "import androidx.compose.ui.unit.sp",
        "import androidx.compose.ui.zIndex",
        "import androidx.core.content.ContextCompat",
        "import kotlin.math.PI",
        "import kotlin.math.cos",
        "import kotlin.math.sin",
    ]
    for p in ROOT.rglob("MainActivity.kt"):
        text = p.read_text(encoding="utf-8")
        orig = text
        missing = [imp for imp in required_imports if imp not in text]
        if missing:
            text = re.sub(
                r"(import androidx\.activity\.ComponentActivity\n)",
                lambda m, block="\n".join(missing): f"{m.group(1)}{block}\n",
                text,
                count=1,
            )
        if "TgVoxPremiumSplashOverlay" in text:
            text = re.sub(
                r'(TgVoxPremiumSplashOverlay\(\s*\n\s*appName\s*=\s*)"[^"]*"',
                rf'\1"{safe_app}"',
                text,
            )
            if text != orig:
                p.write_text(text, encoding="utf-8")
                print(f"Patched {p.relative_to(ROOT)}")
            continue
        state_anchor = r"(var onboardingComplete by remember \{ mutableStateOf\(app\.onboardingManager\.isComplete\) \})"
        box_anchor = r"(\n\s*onboardingComplete = true\n\s*\},\n\s*\)\n\s*\}\n\s*\}\n\s*\}\n)(\s*\}\n\s*\}\n\s*\}\n\s*\}\n\s*\n\s*private fun endStartupTrace)"
        if re.search(state_anchor, text) and re.search(box_anchor, text):
            text = re.sub(
                state_anchor,
                r"\1\n                var showPremiumSplash by rememberSaveable { mutableStateOf(true) }",
                text,
                count=1,
            )
            overlay_call = (
                "                    if (showPremiumSplash) {\n"
                "                        TgVoxPremiumSplashOverlay(\n"
                f'                            appName = "{safe_app}",\n'
                "                            onFinished = { showPremiumSplash = false },\n"
                "                        )\n"
                "                    }\n"
            )
            text = re.sub(box_anchor, lambda m, oc=overlay_call: f"{m.group(1)}{oc}{m.group(2)}", text, count=1)
            splash_fn = """

@Composable
private fun TgVoxPremiumSplashOverlay(
    appName: String,
    onFinished: () -> Unit,
) {
    val context = LocalContext.current
    val logoBitmap =
        remember(context) {
            runCatching {
                val drawable =
                    ContextCompat.getDrawable(context, R.mipmap.ic_launcher)
                        ?: context.packageManager.getApplicationIcon(context.packageName)
                val sizePx = 384
                val bitmap = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.ARGB_8888)
                val androidCanvas = android.graphics.Canvas(bitmap)
                drawable.setBounds(0, 0, sizePx, sizePx)
                drawable.draw(androidCanvas)
                bitmap.asImageBitmap()
            }.getOrNull()
        }

    val progress = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        progress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 2650, easing = LinearEasing),
        )
        onFinished()
    }

    val t = progress.value
    val dotAppear = FastOutSlowInEasing.transform((t / 0.16f).coerceIn(0f, 1f))
    val spreadIn = FastOutSlowInEasing.transform(((t - 0.04f) / 0.18f).coerceIn(0f, 1f))
    val spinEase = FastOutSlowInEasing.transform(((t - 0.08f) / 0.66f).coerceIn(0f, 1f))
    val converge = FastOutSlowInEasing.transform(((t - 0.52f) / 0.24f).coerceIn(0f, 1f))
    val logoReveal = FastOutSlowInEasing.transform(((t - 0.62f) / 0.20f).coerceIn(0f, 1f))
    val labelReveal = FastOutSlowInEasing.transform(((t - 0.72f) / 0.14f).coerceIn(0f, 1f))
    val exitEase = FastOutSlowInEasing.transform(((t - 0.90f) / 0.10f).coerceIn(0f, 1f))

    val overlayAlpha = 1f - exitEase
    val overlayScale = 1f + 0.03f * exitEase
    val burstProgress = ((t - 0.60f) / 0.26f).coerceIn(0f, 1f)
    val burstEase = FastOutSlowInEasing.transform(burstProgress)

    val dotAlpha = dotAppear * (1f - FastOutSlowInEasing.transform(((t - 0.64f) / 0.12f).coerceIn(0f, 1f)))
    val orbitAngleDeg = spinEase * 540f
    val logoScale =
        if (logoReveal <= 0f) {
            0.52f
        } else {
            0.52f + 0.48f * logoReveal + 0.035f * sin(logoReveal * PI.toFloat())
        }

    val interactionSource = remember { MutableInteractionSource() }

    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .zIndex(99f)
                .graphicsLayer {
                    alpha = overlayAlpha
                    scaleX = overlayScale
                    scaleY = overlayScale
                }.background(
                    Brush.radialGradient(
                        colors = listOf(Color(0xFF0D1833), Color(0xFF060A16), Color(0xFF03050B)),
                    ),
                ).clickable(
                    interactionSource = interactionSource,
                    indication = null,
                    onClick = {},
                ),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val center = Offset(size.width / 2f, size.height / 2f)
            val maxOrbitPx = 42.dp.toPx()
            val orbitPx = maxOrbitPx * spreadIn * (1f - converge)
            val baseDotPx = (8.5.dp.toPx() * (0.4f + 0.6f * dotAppear)) * (1f - 0.35f * converge)

            val ambientGlowRadius =
                (150.dp.toPx() * (0.65f + 0.35f * dotAppear.coerceAtLeast(logoReveal))).coerceAtLeast(1f)
            drawCircle(
                brush =
                    Brush.radialGradient(
                        colors = listOf(Color(0x3338BDF8), Color(0x1834D399), Color.Transparent),
                        center = center,
                        radius = ambientGlowRadius,
                    ),
                radius = ambientGlowRadius,
                center = center,
            )

            if (orbitPx > 2f && dotAlpha > 0.01f) {
                drawCircle(
                    color = Color(0xFF94A3B8).copy(alpha = 0.14f * dotAlpha * (1f - converge)),
                    radius = orbitPx,
                    center = center,
                    style = Stroke(width = 1.2.dp.toPx()),
                )
            }

            if (dotAlpha > 0.01f) {
                val dotColors = listOf(Color(0xFF38BDF8), Color(0xFF34D399), Color(0xFF818CF8))
                for (i in 0 until 3) {
                    val dotColor = dotColors[i]
                    for (trail in 2 downTo 0) {
                        val trailFade = if (trail == 0) 1f else if (trail == 1) 0.32f else 0.14f
                        val angleRad = ((orbitAngleDeg + i * 120f - trail * 13f) * PI / 180.0)
                        val pos =
                            Offset(
                                x = center.x + (orbitPx * cos(angleRad)).toFloat(),
                                y = center.y + (orbitPx * sin(angleRad)).toFloat(),
                            )
                        val r = (baseDotPx * (1f - trail * 0.22f)).coerceAtLeast(1f)
                        val haloR = (r * 3.4f).coerceAtLeast(1f)
                        drawCircle(
                            brush =
                                Brush.radialGradient(
                                    colors =
                                        listOf(
                                            dotColor.copy(alpha = 0.42f * dotAlpha * trailFade),
                                            dotColor.copy(alpha = 0.14f * dotAlpha * trailFade),
                                            Color.Transparent,
                                        ),
                                    center = pos,
                                    radius = haloR,
                                ),
                            radius = haloR,
                            center = pos,
                        )
                        drawCircle(
                            color = dotColor.copy(alpha = 0.92f * dotAlpha * trailFade),
                            radius = r,
                            center = pos,
                        )
                        if (trail == 0) {
                            drawCircle(
                                color = Color.White.copy(alpha = 0.72f * dotAlpha),
                                radius = (r * 0.42f).coerceAtLeast(0.5f),
                                center = pos,
                            )
                        }
                    }
                }
            }

            if (burstProgress > 0.01f && burstProgress < 0.99f) {
                val ringRadius = (18.dp.toPx() + 86.dp.toPx() * burstEase).coerceAtLeast(1f)
                val ringAlpha = (1f - burstEase) * 0.55f
                drawCircle(
                    color = Color(0xFF38BDF8).copy(alpha = ringAlpha),
                    radius = ringRadius,
                    center = center,
                    style = Stroke(width = (2.5.dp.toPx() * (1f - burstEase * 0.6f)).coerceAtLeast(0.5f)),
                )
            }
        }

        Box(
            modifier =
                Modifier
                    .size(106.dp)
                    .graphicsLayer {
                        alpha = logoReveal
                        scaleX = logoScale
                        scaleY = logoScale
                    }.clip(RoundedCornerShape(28.dp))
                    .background(Color(0xFF0B1222))
                    .border(
                        width = 1.dp,
                        brush =
                            Brush.linearGradient(
                                colors = listOf(Color(0x8838BDF8), Color(0x5534D399), Color(0x66818CF8)),
                            ),
                        shape = RoundedCornerShape(28.dp),
                    ),
            contentAlignment = Alignment.Center,
        ) {
            if (logoBitmap != null) {
                Image(
                    bitmap = logoBitmap,
                    contentDescription = appName,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize().clip(RoundedCornerShape(28.dp)),
                )
            }
        }

        Text(
            text = appName.uppercase(),
            color = Color(0xFFF8FAFC).copy(alpha = labelReveal),
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 5.sp,
            modifier =
                Modifier
                    .align(Alignment.Center)
                    .padding(top = 160.dp)
                    .graphicsLayer {
                        alpha = labelReveal
                        translationY = (1f - labelReveal) * 10.dp.toPx()
                    },
        )
    }
}
"""
            text = text.rstrip() + splash_fn
        if text != orig:
            p.write_text(text, encoding="utf-8")
            print(f"Patched {p.relative_to(ROOT)}")


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    target_mode = cfg.get("targetMode", "both")
    if target_mode != "ios-only":
        patch_gradle(cfg)
        patch_manifest(cfg)
        patch_splash(cfg)
    patch_strings(cfg)
    patch_about(cfg)
    patch_updater(cfg)
    if target_mode != "android-only":
        patch_ios(cfg)
    if target_mode != "ios-only":
        clean_conflicting_icons()


if __name__ == "__main__":
    main()
