package io.rownd.android

import io.rownd.android.models.network.SignInLinkApi
import java.net.URI
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MauiLoginOwnershipTest {
    @Test
    fun `managed rejected ownership vectors really reach pinned native login`() {
        val urls = listOf(
            "testapp://user@account/login",
            "testapp://account:444/login",
            "testapp://account///login///",
            "https://user@hub.example.test/account/login",
            "https://hub.example.test:444/account/login",
            "https://rownd-hub.supertokens.com/account/login",
            "https://tenant.rownd-hub.supertokens.com/account/login",
            "https://staging.supertokens-rownd-hub.pages.dev/account/login",
            "https://supertokens-rownd-hub.pages.dev/account/login",
        )
        for (url in urls) {
            val uri = URI(url)
            val custom = uri.scheme == "testapp"
            assertEquals(if (custom) "account" else url.substringAfter("//").substringBefore('/').substringAfter('@').substringBefore(':'), uri.host)
            assertEquals(if (url.contains("///")) "///login///" else if (custom) "/login" else "/account/login", uri.rawPath)
            assertEquals(url, "https://hub.example.test/account/login?code=%2f%2B#token=%252F+",
                SignInLinkApi.toHubUrl("$url?code=%2f%2B#token=%252F+", "testapp", "https://hub.example.test"))
        }
    }

    @Test
    fun `lookalike hosts and encoded path are not native login callbacks`() {
        for (url in listOf(
            "https://evilrownd-hub.supertokens.com/account/login",
            "https://rownd-hub.supertokens.com.evil.test/account/login",
            "testapp://account/%6cogin",
            "testapp://elsewhere/login",
            "http://hub.example.test/account/login",
        )) {
            assertNull(url, SignInLinkApi.toHubUrl(url, "testapp", "https://hub.example.test"))
        }
    }
}
