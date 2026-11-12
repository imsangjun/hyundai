package com.mergewindow.app

import android.content.Context
import android.graphics.*
import android.view.View

/** Schematic, never a map, lane detector or representation of real nearby vehicles. */
class LaneView(context: Context) : View(context) {
    var advice = Advice(AdviceState.WAITING, "", "")
        set(value) { field = value; invalidate() }
    private val p = Paint(Paint.ANTI_ALIAS_FLAG)
    private val laneDash = DashPathEffect(floatArrayOf(14f,14f),0f)
    private val arrow = Path().apply { moveTo(344f,115f); lineTo(344f,98f); lineTo(465f,98f) }
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val sx = width / 560f
        val sy = height / 400f
        canvas.save()
        canvas.scale(sx, sy)
        fun rect(l: Float, t: Float, r: Float, b: Float, c: String, radius: Float = 14f) {
            p.color = Color.parseColor(c); p.style = Paint.Style.FILL
            canvas.drawRoundRect(l,t,r,b,radius,radius,p)
        }
        fun text(s: String, x: Float, y: Float, size: Float, c: String) {
            p.color=Color.parseColor(c); p.textSize=size; p.typeface=Typeface.create("sans-serif",Typeface.NORMAL)
            canvas.drawText(s,x,y,p)
        }
        rect(20f,15f,540f,385f,"#152630",22f)
        text("가상 차선 개념도",42f,48f,18f,"#9FB3C1")
        rect(80f,70f,400f,360f,"#263C48")
        rect(80f,70f,510f,120f,"#263C48")
        p.color=Color.parseColor("#6B808C"); p.strokeWidth=3f; p.pathEffect=laneDash
        canvas.drawLine(185f,130f,185f,350f,p); canvas.drawLine(290f,130f,290f,350f,p)
        p.pathEffect=null
        val visibleQueue = advice.upper != null && advice.state !in listOf(AdviceState.WAITING,AdviceState.RESTRICTED,AdviceState.EXPIRED)
        if (visibleQueue) {
            val count = if ((advice.upper ?: 0) > 400) 5 else 2
            repeat(count) { i -> rect(321f,132f+i*34f,367f,158f+i*34f,"#F3B875",7f) }
        }
        p.color=Color.parseColor("#6DE4C4");p.style=Paint.Style.STROKE;p.strokeWidth=7f
        canvas.drawPath(arrow,p);canvas.drawLine(449f,83f,466f,98f,p);canvas.drawLine(449f,113f,466f,98f,p)
        p.style=Paint.Style.FILL
        rect(111f,292f,159f,340f,"#6DE4C4",9f)
        text("나",123f,324f,21f,"#101A22")
        text("직진",110f,374f,15f,"#9FB3C1");text("직진",215f,374f,15f,"#9FB3C1");text("우회전",318f,374f,15f,"#9FB3C1")
        if (advice.state == AdviceState.PREPARE) {
            p.color=Color.parseColor("#6DE4C4");p.strokeWidth=3f
            canvas.drawLine(90f,310f,390f,310f,p)
            text("준비 구간",412f,311f,17f,"#6DE4C4")
        }
        if (!visibleQueue) text("후미 위치 표시 보류",407f,180f,12f,"#9FB3C1")
        canvas.restore()
    }
}
