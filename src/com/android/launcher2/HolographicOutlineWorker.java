/*
 * [10] Gera contornos holograficos (blur + linha, estilo Launcher2 Honeycomb) numa thread de
 * fundo unica e guarda os resultados num cache LRU. Portado do PagedViewIcon/PagedViewWidget
 * do Honeycomb, centralizado aqui.
 */
package com.android.launcher2;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.Process;
import android.util.Log;

import java.util.LinkedHashMap;
import java.util.Map;

final class HolographicOutlineWorker {
    private static final String TAG = "HolographicOutlineWorker";
    private static final int CACHE_MAX = 160;

    interface Callback {
        /** Chamado na thread principal. */
        void onOutline(Bitmap outline);
    }

    private static Handler sWorker;
    private static Handler sMain;
    private static HolographicOutlineHelper sHelper; // usado so na thread de fundo

    private static final LinkedHashMap<String, Bitmap> sCache =
            new LinkedHashMap<String, Bitmap>(32, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, Bitmap> eldest) {
                    return size() > CACHE_MAX;
                }
            };

    private HolographicOutlineWorker() {}

    static Bitmap getCached(String key) {
        if (key == null) return null;
        synchronized (sCache) {
            return sCache.get(key);
        }
    }

    private static synchronized void ensureStarted() {
        if (sWorker == null) {
            HandlerThread t = new HandlerThread("holographic-outline",
                    Process.THREAD_PRIORITY_BACKGROUND);
            t.start();
            sWorker = new Handler(t.getLooper());
            sMain = new Handler(Looper.getMainLooper());
        }
    }

    /**
     * Pede um contorno para "src" (o bitmap NAO e modificado). Se "key" != null o resultado
     * entra no cache. "src" nao pode ser reciclado enquanto a tarefa roda (passe uma copia se
     * o dono puder recicla-lo).
     */
    static void request(final Bitmap src, final String key, final int blurColor,
            final int outlineColor, final Callback cb) {
        if (src == null || src.isRecycled()) return;
        ensureStarted();
        sWorker.post(new Runnable() {
            @Override
            public void run() {
                try {
                    if (src.isRecycled()) return;
                    if (sHelper == null) sHelper = new HolographicOutlineHelper();
                    final Bitmap out = Bitmap.createBitmap(src.getWidth(), src.getHeight(),
                            Bitmap.Config.ARGB_8888);
                    Canvas c = new Canvas(out);
                    c.drawBitmap(src, 0, 0, null);
                    sHelper.applyThickExpensiveOutlineWithBlur(out, c, blurColor, outlineColor);
                    if (key != null) {
                        synchronized (sCache) {
                            sCache.put(key, out);
                        }
                    }
                    if (cb != null) {
                        sMain.post(new Runnable() {
                            @Override
                            public void run() {
                                cb.onOutline(out);
                            }
                        });
                    }
                } catch (Throwable t) {
                    Log.w(TAG, "falha ao gerar contorno holografico", t);
                }
            }
        });
    }
}
