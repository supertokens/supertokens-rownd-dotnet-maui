package io.rownd.android

import io.rownd.android.models.domain.AuthState
import io.rownd.android.models.repos.GlobalState
import io.rownd.android.util.ServerException
import io.rownd.android.util.SuperTokensSessionBridge
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first

/** Called after configure returns; cache hydration alone is not session readiness. */
suspend fun RowndClient.awaitMauiSessionReady() {
    val context = checkNotNull(config.applicationContext)
    awaitMauiSessionReady(
        state = state,
        bootstrap = ::checkMauiBootstrap,
        migrate = { authRepo.migrateLegacySessionIfNeeded(context) },
        reconcile = { SuperTokensSessionBridge.resolveAuthState(context, stateRepo.getStore()) },
    )
}

internal fun checkMauiBootstrap() {
    SuperTokensSessionBridge.initializationFailure?.let { throw it }
    check(SuperTokensSessionBridge.isInitialized.get()) { "Session SDK did not initialize" }
}

internal suspend fun awaitMauiSessionReady(
    state: StateFlow<GlobalState>,
    bootstrap: () -> Unit,
    migrate: suspend () -> Unit,
    reconcile: suspend () -> AuthState?,
) {
    bootstrap()
    state.first { it.isInitialized }
    state.first { it.appConfig.id.isNotEmpty() && !it.appConfig.isLoading }
    migrate()
    val resolved = reconcile()
    // Native reconciliation intentionally preserves pending legacy credentials. They must
    // not be advertised as a usable native session if migration failed or was deferred.
    if (state.value.auth.isAuthenticated && resolved == null) {
        throw ServerException("Native session reconciliation is incomplete; retry after configuration")
    }
}
