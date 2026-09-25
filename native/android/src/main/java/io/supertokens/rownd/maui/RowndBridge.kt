package io.supertokens.rownd.maui

import android.content.Intent
import androidx.fragment.app.FragmentActivity
import io.rownd.android.Rownd
import io.rownd.android.RowndConfigureOptions
import io.rownd.android.awaitMauiSessionReady
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout
import java.net.URI

fun interface Completion { fun complete(error: String?) }
fun interface TokenCompletion { fun complete(token: String?, error: String?) }
fun interface StateListener { fun changed(ready: Boolean, authenticated: Boolean, userId: String?) }

/** Disposing releases observers, not the native session. */
class RowndBridge {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var listener: StateListener? = null
    private var configured = false
    private var ready = false

    fun configure(activity: FragmentActivity, appKey: String, apiDomain: String,
                  apiBasePath: String, hubUrl: String, scheme: String, completion: Completion) {
        scope.launch {
            try {
                check(!configured) { "Rownd is already configured" }
                val api = URI(apiDomain)
                val hub = URI(hubUrl)
                require(appKey.isNotBlank()) { "appKey is required" }
                require(api.scheme in listOf("https", "http") && api.host != null &&
                    api.userInfo == null && api.query == null && api.fragment == null &&
                    api.path in listOf("", "/")) { "apiDomain must be an HTTP(S) origin" }
                require(hub.scheme in listOf("https", "http") && hub.host != null &&
                    hub.userInfo == null && hub.fragment == null) { "hubUrl must be HTTP(S)" }
                require(apiBasePath.startsWith('/') && !apiBasePath.contains('?') &&
                    !apiBasePath.contains('#')) { "apiBasePath must be an absolute path" }
                require(scheme.matches(Regex("[A-Za-z][A-Za-z0-9+.-]*")) &&
                    scheme.lowercase() !in listOf("http", "https")) { "Use a custom scheme" }
                configured = true
                Rownd.configure(activity, RowndConfigureOptions(appKey = appKey,
                    apiDomain = apiDomain, apiBasePath = apiBasePath, hubUrl = hubUrl,
                    deepLinkScheme = scheme))
                withTimeout(30000) { Rownd.awaitMauiSessionReady() }
                ready = true
                scope.launch {
                    Rownd.state.collect { state ->
                        listener?.changed(ready, state.auth.isAuthenticated,
                            Rownd.user.get("user_id") as? String)
                    }
                }
                completion.complete(null)
            } catch (error: Exception) {
                completion.complete(error.javaClass.simpleName)
            }
        }
    }
    fun setStateListener(value: StateListener?) { listener = value }
    fun requestSignIn() { check(ready); Rownd.requestSignIn() }
    fun signOut() { check(ready); Rownd.signOut() }
    fun getAccessToken(completion: TokenCompletion) {
        scope.launch {
            try {
                check(ready)
                completion.complete(Rownd.getAccessToken(), null)
            } catch (error: Exception) {
                completion.complete(null, error.javaClass.simpleName)
            }
        }
    }
    // MAUI ComponentActivity already participates in native intent dispatch.
    // Only call this for hosts outside that lifecycle; never forward twice.
    fun handleIntent(intent: Intent): Boolean { check(ready); return Rownd.handleIntent(intent) }
    fun close() { listener = null; scope.cancel() }
}
