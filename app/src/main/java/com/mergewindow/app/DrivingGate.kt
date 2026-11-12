package com.mergewindow.app

import android.car.Car
import android.car.drivingstate.CarUxRestrictions
import android.car.drivingstate.CarUxRestrictionsManager
import android.content.Context
import android.os.Handler
import android.os.Looper

/** Fail closed until AAOS confirms that the stationary demo UI is allowed. */
class DrivingGate(context: Context, private val changed: (Boolean) -> Unit) {
    private var manager: CarUxRestrictionsManager? = null
    private var closed = false
    private val listener = CarUxRestrictionsManager.OnUxRestrictionsChangedListener { apply(it) }
    private val car = try {
        Car.createCar(context, Handler(Looper.getMainLooper()), Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT) { vehicle, ready ->
            if (!closed) {
                if (ready) {
                    try {
                        manager = vehicle.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE) as CarUxRestrictionsManager
                        manager?.registerListener(listener)
                        manager?.currentCarUxRestrictions?.let { apply(it) } ?: changed(false)
                    } catch (_: Exception) { changed(false) }
                } else changed(false)
            }
        }
    } catch (_: Exception) { changed(false); null }

    private fun apply(restrictions: CarUxRestrictions) {
        if (!closed) changed(!restrictions.isRequiresDistractionOptimization)
    }
    fun close() {
        closed = true
        try { manager?.unregisterListener() } catch (_: Exception) { }
        car?.disconnect()
    }
}
