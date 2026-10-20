package org.notifyiq.app

import android.content.Context
import android.content.SharedPreferences

/**
 * Manages local user settings, forwarding credentials, and package preferences for NotifyIQ companion app.
 */
class SettingsManager(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("notifyiq_prefs", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_CAPTURE_ENABLED = "capture_enabled"
        private const val KEY_FORWARDING_ENABLED = "forwarding_enabled"
        private const val KEY_SERVER_HOST = "server_host"
        private const val KEY_SERVER_PORT = "server_port"
        private const val KEY_API_KEY = "api_key"
        private const val KEY_EXCLUDED_PACKAGES = "excluded_packages"
        private const val KEY_INCLUDED_PACKAGES = "included_packages"
    }

    var isCaptureEnabled: Boolean
        get() = prefs.getBoolean(KEY_CAPTURE_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_CAPTURE_ENABLED, value).apply()

    var isForwardingEnabled: Boolean
        get() = prefs.getBoolean(KEY_FORWARDING_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_FORWARDING_ENABLED, value).apply()

    var serverHost: String
        get() = prefs.getString(KEY_SERVER_HOST, "192.168.1.100") ?: "192.168.1.100"
        set(value) = prefs.edit().putString(KEY_SERVER_HOST, value.trim()).apply()

    var serverPort: Int
        get() = prefs.getInt(KEY_SERVER_PORT, 8000)
        set(value) = prefs.edit().putInt(KEY_SERVER_PORT, value).apply()

    var apiKey: String
        get() = prefs.getString(KEY_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_API_KEY, value.trim()).apply()

    var excludedPackages: Set<String>
        get() = prefs.getStringSet(KEY_EXCLUDED_PACKAGES, emptySet()) ?: emptySet()
        set(value) = prefs.edit().putStringSet(KEY_EXCLUDED_PACKAGES, value).apply()

    var includedPackages: Set<String>
        get() = prefs.getStringSet(KEY_INCLUDED_PACKAGES, emptySet()) ?: emptySet()
        set(value) = prefs.edit().putStringSet(KEY_INCLUDED_PACKAGES, value).apply()

    /**
     * Determines whether a package should be captured and forwarded based on user filters.
     * Enforces package inclusion and exclusion rules strictly.
     */
    fun isPackageAllowed(packageName: String): Boolean {
        if (!isCaptureEnabled) return false
        val cleanPkg = packageName.trim()
        if (excludedPackages.contains(cleanPkg)) return false
        if (includedPackages.isNotEmpty() && !includedPackages.contains(cleanPkg)) return false
        return true
    }
}
