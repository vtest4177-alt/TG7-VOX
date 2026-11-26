package com.metrolist.android

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.os.Trace
import android.util.Log
import androidx.activity.ComponentActivity
import android.graphics.Bitmap
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.zIndex
import androidx.core.content.ContextCompat
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.displayCutout
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.union
import androidx.compose.material3.CircularWavyProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.platform.LocalViewConfiguration
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.platform.ViewConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.lifecycleScope
import com.metrolist.android.deviceconnect.AndroidDeviceConnect
import com.metrolist.android.listentogether.AndroidListenTogetherManager
import com.metrolist.android.locale.AppLocale
import com.metrolist.android.onboarding.OnboardingDestination
import com.metrolist.android.onboarding.OnboardingScreen
import com.metrolist.android.playback.PlayerConnection
import com.metrolist.android.playback.playbackAudioQuality
import com.metrolist.android.playback.prefetchIncomingAudio
import com.metrolist.android.playback.resolveIncomingPlaybackSong
import com.metrolist.android.playback.toAndroidContentHints
import com.metrolist.android.ui.IncomingDestination
import com.metrolist.android.ui.MetrolistApp
import com.metrolist.android.ui.screens.settings.DiscordLoginFlow
import com.metrolist.android.ui.theme.MetrolistTheme
import com.metrolist.android.ui.toIncomingDestination
import com.metrolist.android.utils.CrashHandler
import com.metrolist.android.utils.isAndroidTv
import com.metrolist.innertubex.extraction.TokenProvider
import com.metrolist.shared.model.SongItem
import com.metrolist.shared.settings.LibraryFilterType
import com.metrolist.shared.settings.Settings
import com.metrolist.shared.settings.defaultOpenTabRoot
import com.metrolist.shared.state.GlobalYouTube
import com.metrolist.shared.state.GlobalYouTubeRepository
import com.metrolist.shared.state.applyContentRegion
import com.metrolist.shared.ui.LocalIsInPipMode
import com.metrolist.shared.ui.LocalIsTv
import com.metrolist.shared.ui.theme.appearanceDensity
import com.metrolist.shared.youtube.playback.AndroidTokenProvider
import com.metrolist.shared.youtube.playback.PlaybackNetworkStateStore
import com.metrolist.shared.youtube.playback.StreamResolver
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import org.koin.android.ext.android.get
import java.util.UUID

internal class NavigationRestorationViewModel(
    private val savedState: SavedStateHandle,
) : ViewModel() {
    val saveKey: String =
        savedState.get<String>("navigationSaveKey") ?: UUID.randomUUID().toString().also {
            savedState["navigationSaveKey"] = it
        }

    fun shouldResetLibraryFilter(defaultOpenTab: String): Boolean {
        val freshStart = savedState.get<Boolean>("contentStarted") != true
        savedState["contentStarted"] = true
        return freshStart && defaultOpenTabRoot(defaultOpenTab) == "LIBRARY"
    }
}

class MainActivity : ComponentActivity() {
    companion object {
        const val ACTION_SEARCH = "com.metrolist.music.action.SEARCH"
        const val ACTION_PLAYLIST_IMPORT = "com.metrolist.music.action.PLAYLIST_IMPORT"
        const val EXTRA_IMPORT_RESULT_MESSAGE = "import_result_message"
        const val ACTION_DOWNLOADS = "com.metrolist.music.action.DOWNLOADS"
        const val ACTION_LISTEN_TOGETHER = "com.metrolist.music.action.LISTEN_TOGETHER"
        const val ACTION_LIBRARY = "com.metrolist.music.action.LIBRARY"
        const val ACTION_UPDATES = "com.metrolist.music.action.UPDATES"
        const val ACTION_LOGIN = "com.metrolist.music.action.LOGIN"
        const val ACTION_BACKUP_RESTORE = "com.metrolist.music.action.BACKUP_RESTORE"
        const val ACTION_RECOGNITION = "com.metrolist.music.action.RECOGNITION"
        const val ACTION_LASTFM = "com.metrolist.music.action.LASTFM"
        const val ACTION_OPEN_WIDGET_TARGET = "com.metrolist.music.action.OPEN_WIDGET_TARGET"
        const val EXTRA_WIDGET_TARGET_TYPE = "widget_target_type"
        const val EXTRA_WIDGET_TARGET_ID = "widget_target_id"
    }

    override fun attachBaseContext(newBase: Context) {
        val recovery = (newBase.applicationContext as App).recovery
        var context = newBase
        recovery.run { context = AppLocale.wrap(newBase) }
        super.attachBaseContext(context)
    }

    private val incomingIntentState = mutableStateOf<Intent?>(null)
    private var incomingPlaybackSong: Deferred<SongItem>? = null
    private val isInPipModeState = mutableStateOf(false)
    private val navigationRestoration: NavigationRestorationViewModel by viewModels()
    private lateinit var startupPresentation: StartupPresentation
    private var startupTraceOpen = false

    override fun onCreate(savedInstanceState: Bundle?) {
        val app = application as App
        val recovery = app.recovery
        val startedAt = SystemClock.elapsedRealtime()
        startupPresentation = StartupPresentation(startedAt)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            Trace.beginAsyncSection("Metrolist.startup.firstFrame", hashCode())
            startupTraceOpen = true
        }
        var splashReleased = false
        try {
            installSplashScreen().setKeepOnScreenCondition {
                val now = SystemClock.elapsedRealtime()
                val keep = startupPresentation.keepSplash(now, app.startup.isReady, recovery.isRecovering, app.restoringBackup)
                if (!keep && !splashReleased) {
                    splashReleased = true
                    endStartupTrace()
                    Log.i(
                        "MetrolistStartup",
                        "splash released elapsedMs=${now - startedAt} home=${startupPresentation.homeRequired} " +
                            "cacheReady=${startupPresentation.homeCacheReady} avatarReady=${startupPresentation.avatarReady} " +
                            "recovery=${recovery.isRecovering} restore=${app.restoringBackup}",
                    )
                }
                keep
            }
        } catch (error: Throwable) {
            recovery.capture(error)
        }
        super.onCreate(savedInstanceState)
        lifecycleScope.launch {
            recovery.report.collect { id -> if (id != null) showStartupRecovery() }
        }
        recovery.run { initializeActivity(savedInstanceState) }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) showStartupRecovery()
    }

    private fun showStartupRecovery() {
        val id = (application as App).recovery.claimReport(window.decorView.hasWindowFocus()) ?: return
        CrashHandler.launch(this, id, terminateAfterHandoff = true)
        finish()
    }

    private fun initializeActivity(savedInstanceState: Bundle?) {
        val app = application as App
        val waitingForRestore = app.restoringBackup

        @Suppress("DEPRECATION")
        val pendingIntent =
            if (savedInstanceState?.containsKey("incomingIntent") == true) {
                savedInstanceState.getParcelable<Intent>("incomingIntent")
            } else {
                intent
            }
        incomingIntentState.value = pendingIntent
        setIntent(pendingIntent ?: Intent(this, MainActivity::class.java))
        isInPipModeState.value = isInPictureInPictureMode
        WindowCompat.enableEdgeToEdge(window)
        val lightSystemBars = resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK != Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = lightSystemBars
            isAppearanceLightNavigationBars = lightSystemBars
        }
        if (waitingForRestore) {
            setContent {
                MaterialTheme {
                    Surface(Modifier.fillMaxSize()) {
                        Column(
                            modifier = Modifier.fillMaxSize().padding(24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(24.dp, Alignment.CenterVertically),
                        ) {
                            @OptIn(ExperimentalMaterial3ExpressiveApi::class)
                            CircularWavyProgressIndicator()
                            Text(stringResource(R.string.restore_in_progress))
                        }
                    }
                }
            }
        }
        // Main.immediate can deadlock Compose resource loading inside the startup completion event loop.
        lifecycleScope.launch(Dispatchers.Main) {
            if (!awaitStartup()) return@launch
            app.recovery.run {
                if (waitingForRestore) {
                    recreate()
                    return@run
                }
                consumeDiscordCallback(intent)
                app.restoreDeviceConnectIfEnabled()
                prepareIncomingPlayback()
                showContent()
            }
        }
    }

    private fun prepareIncomingPlayback() {
        if (!(application as App).onboardingManager.isComplete) return
        val destination = incomingIntentState.value?.toIncomingDestination() as? IncomingDestination.PlayVideo ?: return
        GlobalYouTube.applyContentRegion(
            contentCountry = Settings.shared.contentCountry,
            contentLanguage = Settings.shared.contentLanguage,
            systemLocale = AppLocale.systemLocale(this),
        )
        lifecycleScope.launch {
            (get<TokenProvider>() as? AndroidTokenProvider)?.prewarm()
        }
        get<PlayerConnection>().ensureConnected()
        incomingPlaybackSong =
            lifecycleScope.async(Dispatchers.IO) {
                val song =
                    resolveIncomingPlaybackSong(
                        videoId = destination.videoId,
                        fallbackArtist = getString(R.string.youtube_music),
                        loadMetadata = GlobalYouTubeRepository.instance::getSongMetadata,
                        loadPlayerInformation = GlobalYouTubeRepository.instance::getSongPlayerInformation,
                    )
                prefetchIncomingAudio(
                    song = song,
                    wantVideo = Settings.shared.videoViewerVisible,
                    canPlayLocally =
                        PlaybackNetworkStateStore.current.connected &&
                            !AndroidListenTogetherManager.isGuestPlaybackLocked && !AndroidDeviceConnect.manager.remote.isActive,
                ) { source ->
                    get<StreamResolver>().resolve(
                        source.id,
                        source.toAndroidContentHints(wantVideo = false),
                        playbackAudioQuality(),
                        sourceSong = source,
                    )
                }
                song
            }
    }

    private fun showContent() {
        if (navigationRestoration.shouldResetLibraryFilter(Settings.shared.defaultOpenTab)) {
            Settings.shared.libraryFilter = LibraryFilterType.DEFAULT
        }
        setContent {
            val systemDensity = LocalDensity.current
            val windowSize = LocalWindowInfo.current.containerDpSize
            val safeInsets = WindowInsets.navigationBars.union(WindowInsets.displayCutout)
            val direction = LocalLayoutDirection.current
            val contentWidth =
                windowSize.width.value -
                    (safeInsets.getLeft(systemDensity, direction) + safeInsets.getRight(systemDensity, direction)) / systemDensity.density
            val density =
                appearanceDensity(
                    systemDensity = systemDensity,
                    smallestDimensionDp = minOf(windowSize.width, windowSize.height).value,
                    enableLandscapeScaling = Settings.shared.enableLandscapeScaling,
                    userDensityScale = Settings.shared.densityScaleFactor,
                    availableWidthDp = contentWidth,
                )
            val systemViewConfiguration = LocalViewConfiguration.current
            val touchTargetScale = (systemDensity.density / density.density).coerceAtLeast(1f)
            val viewConfiguration =
                remember(systemViewConfiguration, touchTargetScale) {
                    object : ViewConfiguration by systemViewConfiguration {
                        override val minimumTouchTargetSize = systemViewConfiguration.minimumTouchTargetSize * touchTargetScale
                    }
                }
            CompositionLocalProvider(
                LocalStartupPresentation provides startupPresentation,
                LocalViewConfiguration provides viewConfiguration,
                LocalMinimumInteractiveComponentSize provides LocalMinimumInteractiveComponentSize.current * touchTargetScale,
                LocalIsInPipMode provides isInPipModeState.value,
                LocalDensity provides density,
            ) {
                val app = application as App
                var onboardingComplete by remember { mutableStateOf(app.onboardingManager.isComplete) }
                var showPremiumSplash by rememberSaveable { mutableStateOf(true) }
                Box(Modifier.fillMaxSize().onGloballyPositioned { startupPresentation.contentLaidOut = true }) {
                    if (onboardingComplete) {
                        MetrolistApp(
                            navigationSaveKey = navigationRestoration.saveKey,
                            incomingIntent = incomingIntentState.value,
                            incomingPlaybackSong = incomingPlaybackSong,
                            onExitApp = ::exitApp,
                            onIncomingIntentConsumed = { consumed ->
                                if (incomingIntentState.value === consumed) {
                                    incomingIntentState.value = null
                                    setIntent(Intent(this@MainActivity, MainActivity::class.java))
                                }
                            },
                        )
                    } else {
                        val tvDevice = remember { isAndroidTv() }
                        CompositionLocalProvider(LocalIsTv provides tvDevice) {
                            MetrolistTheme {
                                OnboardingScreen(
                                    migration = app.legacyInstallMigration,
                                    hasLegacyInstallationOverride = app.hadLegacyInstallationAtStartup,
                                    onComplete = { sendCrashReports, destination ->
                                        app.completeOnboarding(sendCrashReports)
                                        incomingIntentState.value =
                                            when (destination) {
                                                OnboardingDestination.HOME -> incomingIntentState.value
                                                OnboardingDestination.LOGIN -> Intent(ACTION_LOGIN)
                                                OnboardingDestination.BACKUP_RESTORE -> Intent(ACTION_BACKUP_RESTORE)
                                            }
                                        prepareIncomingPlayback()
                                        onboardingComplete = true
                                    },
                                )
                            }
                        }
                    }
                    if (showPremiumSplash) {
                        TgVoxPremiumSplashOverlay(
                            appName = "TG VOX",
                            onFinished = { showPremiumSplash = false },
                        )
                    }
                }
            }
        }
    }

    private fun endStartupTrace() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && startupTraceOpen) {
            Trace.endAsyncSection("Metrolist.startup.firstFrame", hashCode())
            startupTraceOpen = false
        }
    }

    override fun onDestroy() {
        endStartupTrace()
        super.onDestroy()
    }

    override fun onPictureInPictureModeChanged(
        isInPictureInPictureMode: Boolean,
        newConfig: Configuration,
    ) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        isInPipModeState.value = isInPictureInPictureMode
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putParcelable("incomingIntent", incomingIntentState.value)
        super.onSaveInstanceState(outState)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        incomingPlaybackSong?.cancel()
        incomingPlaybackSong = null
        setIntent(intent)
        incomingIntentState.value = intent
        lifecycleScope.launch {
            if (!awaitStartup()) return@launch
            (application as App).recovery.run { consumeDiscordCallback(intent) }
        }
    }

    private suspend fun awaitStartup(): Boolean {
        val app = application as App
        if (app.recovery.isRecovering) return false
        return try {
            app.startup.await()
            !app.recovery.isRecovering
        } catch (error: Throwable) {
            if (error !is CancellationException) app.recovery.capture(error)
            false
        }
    }

    private fun consumeDiscordCallback(callback: Intent) {
        if (DiscordLoginFlow.handleCallback(callback) && intent === callback) {
            incomingIntentState.value = null
            setIntent(Intent(this, MainActivity::class.java))
        }
    }
}

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
