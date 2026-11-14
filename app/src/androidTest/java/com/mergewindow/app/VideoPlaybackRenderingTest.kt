package com.mergewindow.app

import android.view.ViewGroup
import android.webkit.WebView
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONTokener
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(AndroidJUnit4::class)
class VideoPlaybackRenderingTest {
    @Test fun installedYoloReplayReachesNativeNavigation() {
        val context = androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().targetContext
        VideoReplay(java.io.File(context.filesDir,"vision-replay.json").readText(),0)
        ActivityScenario.launch(MainActivity::class.java).use { activity ->
            fun js(script: String): String {
                val latch = CountDownLatch(1)
                var result = ""
                activity.onActivity { a ->
                    val web = a.findViewById<ViewGroup>(android.R.id.content).getChildAt(0) as WebView
                    web.evaluateJavascript(script) { result = it; latch.countDown() }
                }
                assertTrue(latch.await(3, TimeUnit.SECONDS))
                return JSONTokener(result).nextValue().toString()
            }
            fun waitFor(script: String) {
                val deadline = System.currentTimeMillis() + 45000
                while (System.currentTimeMillis() < deadline) {
                    if (js(script) == "true") return
                    Thread.sleep(250)
                }
                throw AssertionError("Condition not reached: $script; snapshot=" + js("JSON.stringify(state)"))
            }
            waitFor("typeof state !== 'undefined' && state.parked")
            js("document.getElementById('video-replay').click(); true")
            waitFor("state.videoReplay && state.v2xStatus.includes('V4 → V3 → V2 → V1 → EGO') && state.v2xStatus.includes('VEHICLES_DETECTED')")
            assertTrue(js("state.prepareAt === null && state.high === null") == "true")
            assertTrue(js("document.querySelector('.demo-tag').textContent === 'YOLO 영상 관측'") == "true")
        }
    }
}
