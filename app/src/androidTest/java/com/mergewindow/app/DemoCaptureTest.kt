package com.mergewindow.app

import android.view.ViewGroup
import android.webkit.WebView
import android.graphics.Bitmap
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONTokener
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.io.File

/** Records actual app scenarios for a captioned, offline demonstration. */
@RunWith(AndroidJUnit4::class)
class DemoCaptureTest {
 @Test fun captureScenarios() {
  val instrumentation=InstrumentationRegistry.getInstrumentation()
  ActivityScenario.launch(MainActivity::class.java).use { activity ->
   fun js(script:String):String {
    val latch=CountDownLatch(1);var value=""
    activity.onActivity { a ->
     val web=a.findViewById<ViewGroup>(android.R.id.content).getChildAt(0) as WebView
     web.evaluateJavascript(script) { value=it;latch.countDown() }
    }
    assertTrue(latch.await(3,TimeUnit.SECONDS));return JSONTokener(value).nextValue().toString()
   }
   fun shot(name:String) {
    val bitmap=instrumentation.uiAutomation.takeScreenshot()
    File(instrumentation.targetContext.filesDir,"demo-$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG,100,it) }
   }
   val deadline=System.currentTimeMillis()+30000
   while(js("typeof state !== 'undefined' && state.parked")!="true" && System.currentTimeMillis()<deadline) Thread.sleep(250)
   assertTrue(js("state.parked")=="true")
   val recording=instrumentation.uiAutomation.executeShellCommand("screenrecord --time-limit 44 --bit-rate 6000000 /data/local/tmp/mergewindow-demo.mp4")
   Thread.sleep(2000)
   js("document.querySelector('[data-scenario=BOTH_BLOCKS]').click(); true")
   Thread.sleep(1500);shot("both");Thread.sleep(5500)
   js("document.querySelector('[data-scenario=NEXT_BLOCK_CLEAR]').click(); true")
   Thread.sleep(1500);shot("next");Thread.sleep(5500)
   js("document.querySelector('[data-direction=LEFT]').click(); document.querySelector('[data-scenario=BOTH_BLOCKS]').click(); true")
   Thread.sleep(1500);shot("left");Thread.sleep(5500)
   js("document.getElementById('video-replay').click(); document.getElementById('settings').click(); true")
   Thread.sleep(8000)
   js("document.getElementById('v2x-status').scrollIntoView({block:'center'}); true")
   Thread.sleep(1000);shot("vision")
   assertTrue(js("state.v2xStatus.includes('차량 밀집 후보')")=="true")
   Thread.sleep(13000)
   recording.close()
  }
 }
}
