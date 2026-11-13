package com.mergewindow.app

import android.os.SystemClock
import android.view.ViewGroup
import android.webkit.WebView
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.json.JSONTokener
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Checks the packaged offline map and native bridge without requesting a live route. */
@RunWith(AndroidJUnit4::class)
class NavigationRenderingTest {
    @Test fun offlineNavigationLoadsWithoutNetworkPermission() {
        ActivityScenario.launch(MainActivity::class.java).use { activity ->
            val deadline=SystemClock.elapsedRealtime()+30000
            var seen=JSONObject()
            while(SystemClock.elapsedRealtime()<deadline) {
                val done=CountDownLatch(1)
                val result=AtomicReference("null")
                activity.onActivity { a ->
                    val web=a.findViewById<ViewGroup>(android.R.id.content).getChildAt(0) as WebView
                    assertTrue("WebView must block network loads", web.settings.blockNetworkLoads)
                    val permissions=a.packageManager.getPackageInfo(a.packageName, android.content.pm.PackageManager.GET_PERMISSIONS).requestedPermissions.orEmpty()
                    assertFalse("Offline app must not have INTERNET permission", permissions.contains("android.permission.INTERNET"))
                    web.evaluateJavascript("""
                        JSON.stringify({
                            connection:document.getElementById('connection')?.textContent,
                            marker:!!document.querySelector('.vehicle'),
                            mapLoaded:!!document.querySelector('.offline-map-image')?.naturalWidth,
                            tiles:document.querySelectorAll('.leaflet-tile').length,
                            externalImages:[...document.images].filter(i=>new URL(i.src).host!=='mergewindow.local').length,
                            settingsHidden:document.getElementById('drawer')?.hidden,
                            locked:!document.getElementById('lock')?.hidden,
                            bridge:typeof window.MergeWindow?.action === 'function'
                        })
                    """.trimIndent()) { value -> result.set(value);done.countDown() }
                }
                if(done.await(3,TimeUnit.SECONDS)) {
                    val value=JSONTokener(result.get()).nextValue()
                    if(value is String)seen=JSONObject(value)
                    if(seen.optBoolean("marker") && seen.optBoolean("mapLoaded") && seen.optString("connection")=="오프라인 시연")break
                }
                Thread.sleep(200)
            }
            assertEquals("오프라인 시연",seen.optString("connection"))
            assertTrue("Fictional demo vehicle is visible",seen.optBoolean("marker"))
            assertTrue("Packaged SVG must load in Android WebView",seen.optBoolean("mapLoaded"))
            assertEquals("No remote map tiles",0,seen.optInt("tiles"))
            assertEquals("All images are local",0,seen.optInt("externalImages"))
            assertTrue("Controls must be available to the packaged UI",seen.optBoolean("bridge"))
            assertTrue("Lab controls stay out of the main screen",seen.optBoolean("settingsHidden"))
            assertFalse("Stationary demo unlocked",seen.optBoolean("locked"))
        }
    }
}
