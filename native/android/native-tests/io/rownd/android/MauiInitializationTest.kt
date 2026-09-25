package io.rownd.android

import io.rownd.android.models.domain.AppConfigState
import io.rownd.android.models.domain.AuthState
import io.rownd.android.models.repos.GlobalState
import io.rownd.android.util.ServerException
import io.rownd.android.util.SuperTokensSessionBridge
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class MauiInitializationTest {
    private fun state(auth: AuthState = AuthState()) = MutableStateFlow(GlobalState(
        isInitialized = true,
        appConfig = AppConfigState(id = "test-app", isLoading = false),
        auth = auth,
    ))

    @Test
    fun `cache loaded cannot hide bootstrap failure`() = runBlocking {
        val failure = IllegalStateException("bootstrap failed")
        var reconciled = false
        val previousFailure = SuperTokensSessionBridge.initializationFailure
        val previousInitialized = SuperTokensSessionBridge.isInitialized.get()
        try {
            SuperTokensSessionBridge.initializationFailure = failure
            SuperTokensSessionBridge.isInitialized.set(false)
            val result = runCatching {
                awaitMauiSessionReady(state(AuthState(accessToken = "cached")),
                    bootstrap = ::checkMauiBootstrap, migrate = {},
                    reconcile = { reconciled = true; null })
            }
            assertSame(failure, result.exceptionOrNull())
            assertFalse(reconciled)
        } finally {
            SuperTokensSessionBridge.initializationFailure = previousFailure
            SuperTokensSessionBridge.isInitialized.set(previousInitialized)
        }
    }

    @Test
    fun `cached authentication is reconciled before success when native session is absent`() = runBlocking {
        val state = state(AuthState(accessToken = "cached"))
        val release = CompletableDeferred<Unit>()
        val ready = async(start = CoroutineStart.UNDISPATCHED) {
            awaitMauiSessionReady(state, bootstrap = {}, migrate = {}, reconcile = {
                release.await()
                state.value = state.value.copy(auth = AuthState())
                null
            })
        }
        assertFalse(ready.isCompleted)
        assertTrue(state.value.auth.isAuthenticated)
        release.complete(Unit)
        ready.await()
        assertFalse(state.value.auth.isAuthenticated)
    }

    @Test
    fun `signed out succeeds without a token`() = runBlocking {
        var reconciled = false
        awaitMauiSessionReady(state(), bootstrap = {}, migrate = {}, reconcile = {
            reconciled = true
            null
        })
        assertTrue(reconciled)
    }

    @Test
    fun `transient reconciliation failure is not signed out success`() = runBlocking {
        val state = state(AuthState(accessToken = "cached"))
        val failure = ServerException("refresh transport failure")
        val result = runCatching {
            awaitMauiSessionReady(state, bootstrap = {}, migrate = {}, reconcile = { throw failure })
        }
        assertSame(failure, result.exceptionOrNull())
        assertTrue(state.value.auth.isAuthenticated)
    }

    @Test
    fun `pending legacy credentials cannot escape as ready authentication`() = runBlocking {
        val result = runCatching {
            awaitMauiSessionReady(state(AuthState(accessToken = "legacy")),
                bootstrap = {}, migrate = {}, reconcile = { null })
        }
        assertTrue(result.exceptionOrNull() is ServerException)
    }

    @Test
    fun `cache and app configuration both gate reconciliation`() = runBlocking {
        val state = MutableStateFlow(GlobalState())
        var reconciled = false
        val ready = async(start = CoroutineStart.UNDISPATCHED) {
            awaitMauiSessionReady(state, bootstrap = {}, migrate = {}, reconcile = {
                reconciled = true
                null
            })
        }
        assertFalse(ready.isCompleted)
        state.value = state.value.copy(isInitialized = true)
        kotlinx.coroutines.yield()
        assertFalse(reconciled)
        state.value = state.value.copy(appConfig = AppConfigState(id = "test-app", isLoading = false))
        ready.await()
        assertTrue(reconciled)
    }
}
