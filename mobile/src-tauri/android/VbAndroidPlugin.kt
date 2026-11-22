package dev.vibebuilder.ide.mobile

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import app.tauri.annotation.Command
import app.tauri.annotation.InvokeArg
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.JSObject
import app.tauri.plugin.Plugin
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

@InvokeArg
class TokenKeyArg {
    var server: String = ""
}

@InvokeArg
class TokenPairArg {
    var server: String = ""
    var token: String = ""
}

@InvokeArg
class TunnelServiceArg {
    var active: Boolean = false
}

@TauriPlugin
class VbAndroidPlugin(private val activity: Activity) : Plugin(activity) {
    companion object {
        private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
        private const val KEY_ALIAS = "VibeBuilderDeviceTokenKey"
        private const val PREFS_NAME = "vb_keystore_tokens"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val IV_LEN = 12
    }

    private fun getOrCreateKey(): SecretKey {
        val ks = KeyStore.getInstance(KEYSTORE_PROVIDER).apply { load(null) }
        ks.getKey(KEY_ALIAS, null)?.let { return it as SecretKey }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE_PROVIDER)
        gen.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return gen.generateKey()
    }

    private fun encrypt(plain: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val iv = cipher.iv
        val ct = cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        val combined = ByteArray(iv.size + ct.size)
        System.arraycopy(iv, 0, combined, 0, iv.size)
        System.arraycopy(ct, 0, combined, iv.size, ct.size)
        return Base64.encodeToString(combined, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String): String {
        val raw = Base64.decode(encoded, Base64.NO_WRAP)
        val iv = raw.copyOfRange(0, IV_LEN)
        val ct = raw.copyOfRange(IV_LEN, raw.size)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
        return String(cipher.doFinal(ct), Charsets.UTF_8)
    }

    private fun prefs() = activity.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    @Command
    fun tokenGet(invoke: Invoke) {
        val args = invoke.parseArgs(TokenKeyArg::class.java)
        val enc = prefs().getString(args.server, null)
        val res = JSObject()
        if (enc == null) {
            res.put("token", null)
        } else {
            try {
                res.put("token", decrypt(enc))
            } catch (_: Exception) {
                prefs().edit().remove(args.server).apply()
                res.put("token", null)
            }
        }
        invoke.resolve(res)
    }

    @Command
    fun tokenSet(invoke: Invoke) {
        val args = invoke.parseArgs(TokenPairArg::class.java)
        val enc = encrypt(args.token)
        prefs().edit().putString(args.server, enc).apply()
        invoke.resolve(JSObject())
    }

    @Command
    fun tokenDelete(invoke: Invoke) {
        val args = invoke.parseArgs(TokenKeyArg::class.java)
        prefs().edit().remove(args.server).apply()
        invoke.resolve(JSObject())
    }

    @Command
    fun deviceName(invoke: Invoke) {
        val mfg = Build.MANUFACTURER?.trim().orEmpty()
        val model = Build.MODEL?.trim().orEmpty()
        val label = when {
            model.isEmpty() -> mfg.ifEmpty { "Android Phone" }
            mfg.isEmpty() || model.startsWith(mfg, ignoreCase = true) -> model
            else -> "$mfg $model"
        }
        val res = JSObject()
        res.put("name", label)
        invoke.resolve(res)
    }

    @Command
    fun setTunnelService(invoke: Invoke) {
        val args = invoke.parseArgs(TunnelServiceArg::class.java)
        val intent = Intent(activity, TunnelForegroundService::class.java)
        if (args.active) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                activity.startForegroundService(intent)
            } else {
                activity.startService(intent)
            }
        } else {
            activity.stopService(intent)
        }
        invoke.resolve(JSObject())
    }
}
