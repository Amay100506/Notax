package org.notifyiq.app

import android.content.Context
import android.content.SharedPreferences

/**
 * Manages local user settings and package preferences for NotifyIQ companion app.
 */
class SettingsManager(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("notifyiq_prefs", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_CAPTURE_ENABLED = "capture_enabled"
        private const val KEY_EXCLUDED_PACKAGES = "excluded_packages"
    }

    var isCaptureEnabled: Boolean
        get() = prefs.getBoolean(KEY_CAPTURE_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_CAPTURE_ENABLED, value).apply()

    var excludedPackages: Set<String>
        get() = prefs.getStringSet(KEY_EXCLUDED_PACKAGES, emptySet()) ?: emptySet()
        set(value) = prefs.edit().putStringSet(KEY_EXCLUDED_PACKAGES, value).apply()

    fun isPackageAllowed(packageName: String): Boolean {
        return isCaptureEnabled && !excludedPackages.contains(packageName)
    }
}
