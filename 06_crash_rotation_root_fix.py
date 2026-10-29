#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_crash_rotation_root_fix.py - Launcher2: crash no toque longo, rotacao e brilho (TableMaskFilter)

Rode na RAIZ do repositorio (depois do 05):
    python3 06_crash_rotation_root_fix.py [--dry-run]

1) CRASH AO SEGURAR UM ICONE
   "IllegalArgumentException: Invalid Region.Op - only INTERSECT and DIFFERENCE are allowed"
   (BubbleTextView.drawWithPadding). Region.Op.REPLACE/UNION/XOR/REVERSE_DIFFERENCE foram
   removidos no Android 9+.
     * BubbleTextView: o canvas e' novo (bitmap proprio) -> clipRect(rect) equivale ao REPLACE.
     * CellLayout (brilho do drop com escala > 1): usa Utilities.clipRectExpand(), que so usa
       REPLACE onde ainda existe (API < 28) e nos demais mantem o clip atual.

2) ROTACAO (retrato <-> paisagem)
   O Launcher era recriado a cada rotacao (Activity destruida + modelo recarregado em paralelo)
   e acabava em tela preta. Agora a Activity trata a mudanca sozinha (configChanges no
   manifest) e so re-mede: workspace (celulas esticam), gaveta (recalcula colunas/linhas) e
   realinha a pagina atual.

3) BRILHO DOS ICONES (TableMaskFilter, API oculta)
   Ordem de tentativas, tudo transparente para o usuario:
     a) reflexao (funciona sem root em muitos aparelhos; no seu A35 o log mostra "allowed");
     b) se a reflexao falhar: pede root UMA vez (su) e liga a politica de APIs ocultas
        (settings put global hidden_api_policy 1). A politica so vale para processos novos,
        entao o Launcher se reinicia uma unica vez;
     c) sem root (ou se negarem): ClipTableCallback avisa e o brilho e' reproduzido em Java puro
        (Utilities.applyClipTable, criado no 04b), com a mesma tabela de alpha do TableMaskFilter.
   O pedido de root nunca se repete (flag em SharedPreferences "launcher2_glow").
   ATENCAO: hidden_api_policy e' uma configuracao GLOBAL do Android (afeta todos os apps).

Idempotente. Pontos nao encontrados sao listados no final como AVISO.
"""
import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
SRC = Path("src/com/android/launcher2")
CHANGED, WARN = [], []


def rd(p):
    return Path(p).read_text(encoding="utf-8")


def wr(p, t):
    if not DRY:
        Path(p).write_text(t, encoding="utf-8")


def edit(path, old, new, marker=None, desc=None):
    p = Path(path)
    tag = f"{p.name}: {desc or old.strip()[:50]!r}"
    if not p.exists():
        WARN.append(tag + " (arquivo inexistente)")
        return
    t = rd(p)
    if marker is not None and marker in t:
        return
    if old not in t:
        if marker is None and new in t:
            return
        WARN.append(tag + " (trecho nao encontrado)")
        return
    wr(p, t.replace(old, new, 1))
    CHANGED.append(tag)


# ------------------------------------------------------------------ 1) Region.Op
edit(SRC / "BubbleTextView.java",
     "        destCanvas.clipRect(clipRect, Op.REPLACE);",
     "        destCanvas.clipRect(clipRect);   // canvas novo: INTERSECT == REPLACE (REPLACE foi removido)",
     marker="INTERSECT == REPLACE", desc="Region.Op.REPLACE -> clipRect(rect)")

edit(SRC / "CellLayout.java",
     "                    canvas.clipRect(-marginX, -marginY,\n"
     "                            getWidth() + marginX, getHeight() + marginY, Region.Op.REPLACE);",
     "                    Utilities.clipRectExpand(canvas, -marginX, -marginY,\n"
     "                            getWidth() + marginX, getHeight() + marginY);",
     marker="Utilities.clipRectExpand(canvas", desc="Region.Op.REPLACE -> clipRectExpand")

# ------------------------------------------------------------------ 3) Utilities: clip + root
UTIL = '''
    /** Region.Op.REPLACE foi removido (API 28+): onde nao da para ampliar o clip, mantem o atual. */
    static void clipRectExpand(Canvas canvas, int l, int t, int r, int b) {
        if (android.os.Build.VERSION.SDK_INT < 28) {
            canvas.clipRect(l, t, r, b, android.graphics.Region.Op.REPLACE);
        }
    }

    // ---------------------------------------------------------------------------------------
    // Brilho real (TableMaskFilter oculto): reflexao -> root (hidden_api_policy) -> emulacao Java
    // ---------------------------------------------------------------------------------------

    /** Avisado uma vez, quando se sabe se o TableMaskFilter real esta disponivel. */
    interface ClipTableCallback {
        /** @param realFilter true = TableMaskFilter real; false = brilho emulado em Java */
        void onClipTableResolved(boolean realFilter, boolean usedRoot);
    }

    private static final String GLOW_PREFS = "launcher2_glow";
    private static final String KEY_ROOT_TRIED = "root_hidden_api_tried";

    static void resolveClipTable(final android.content.Context context, final ClipTableCallback cb) {
        if (hasClipTable()) {
            if (cb != null) cb.onClipTableResolved(true, false);
            return;
        }
        final android.content.SharedPreferences sp =
                context.getSharedPreferences(GLOW_PREFS, android.content.Context.MODE_PRIVATE);
        if (sp.getBoolean(KEY_ROOT_TRIED, false)) {
            // ja pedimos root antes (negado, sem root ou sem efeito): usa o brilho emulado
            if (cb != null) cb.onClipTableResolved(false, false);
            return;
        }
        sp.edit().putBoolean(KEY_ROOT_TRIED, true).commit();   // nunca pergunta duas vezes

        final android.os.Handler main = new android.os.Handler(android.os.Looper.getMainLooper());
        new Thread(new Runnable() {
            public void run() {
                final boolean ok = enableHiddenApisWithRoot();
                if (ok) {
                    main.post(new Runnable() {
                        public void run() {
                            android.widget.Toast.makeText(context,
                                    "Brilho dos icones ativado. Reiniciando o Launcher...",
                                    android.widget.Toast.LENGTH_SHORT).show();
                        }
                    });
                    try { Thread.sleep(1200); } catch (InterruptedException e) { }
                    // A politica de APIs ocultas so vale para processos novos.
                    android.os.Process.killProcess(android.os.Process.myPid());
                } else {
                    main.post(new Runnable() {
                        public void run() {
                            if (cb != null) cb.onClipTableResolved(false, false);
                        }
                    });
                }
            }
        }, "Launcher2-RootGlow").start();
    }

    /** Pede root (o gerenciador de root mostra o dialogo) e libera as APIs ocultas. */
    private static boolean enableHiddenApisWithRoot() {
        try {
            final Process p = Runtime.getRuntime().exec(new String[] { "su", "-c",
                    "settings put global hidden_api_policy 1; "
                    + "settings put global hidden_api_policy_p_apps 1; "
                    + "settings put global hidden_api_policy_pre_p_apps 1" });
            // espera ate 30s (tempo do usuario responder ao pedido de root)
            for (int i = 0; i < 300; i++) {
                try {
                    return p.exitValue() == 0;
                } catch (IllegalThreadStateException running) {
                    try { Thread.sleep(100); } catch (InterruptedException e) { return false; }
                }
            }
            p.destroy();
            return false;
        } catch (Throwable t) {
            return false;   // sem su / sem permissao
        }
    }
'''
edit(SRC / "Utilities.java",
     "    /** Android 13+ exige informar a flag de exportacao",
     UTIL + "\n    /** Android 13+ exige informar a flag de exportacao",
     marker="static void resolveClipTable(", desc="root + callback do brilho")

edit(SRC / "LauncherApplication.java",
     "        sScreenDensity = getResources().getDisplayMetrics().density;\n",
     "        sScreenDensity = getResources().getDisplayMetrics().density;\n\n"
     "        // Brilho dos icones: TableMaskFilter real (reflexao/root) ou emulado em Java\n"
     "        Utilities.resolveClipTable(this, new Utilities.ClipTableCallback() {\n"
     "            public void onClipTableResolved(boolean realFilter, boolean usedRoot) {\n"
     "                android.util.Log.i(\"Launcher2\", realFilter\n"
     "                        ? \"Brilho: TableMaskFilter real\"\n"
     "                        : \"Brilho: efeito emulado em Java (sem TableMaskFilter)\");\n"
     "            }\n"
     "        });\n",
     marker="Utilities.resolveClipTable(this", desc="resolve o brilho no start")

# ------------------------------------------------------------------ 2) rotacao
edit("AndroidManifest.xml",
     '            android:launchMode="singleTask"\n',
     '            android:launchMode="singleTask"\n'
     '            android:configChanges="orientation|screenSize|smallestScreenSize|screenLayout|keyboard|keyboardHidden|navigation"\n',
     marker="android:configChanges", desc="Launcher trata a rotacao (configChanges)")

edit(SRC / "Launcher.java",
     "    @Override\n    protected void onRestoreInstanceState(Bundle savedInstanceState) {",
     "    /** Rotacao: a Activity nao e recriada (configChanges); so re-mede e realinha. */\n"
     "    @Override\n"
     "    public void onConfigurationChanged(android.content.res.Configuration newConfig) {\n"
     "        super.onConfigurationChanged(newConfig);\n"
     "        if (mAppsCustomizeContent != null) {\n"
     "            mAppsCustomizeContent.onConfigurationRefresh();\n"
     "        }\n"
     "        if (mWorkspace != null) {\n"
     "            mWorkspace.post(new Runnable() {\n"
     "                public void run() {\n"
     "                    mWorkspace.setCurrentPage(mWorkspace.getCurrentPage());\n"
     "                }\n"
     "            });\n"
     "        }\n"
     "    }\n\n"
     "    @Override\n    protected void onRestoreInstanceState(Bundle savedInstanceState) {",
     marker="public void onConfigurationChanged(", desc="onConfigurationChanged")

edit(SRC / "AppsCustomizeTabHost.java",
     "    @Override\n    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {\n"
     "        boolean remeasureTabWidth",
     "    /** Rotacao: refaz a largura das abas a partir da nova largura do conteudo. */\n"
     "    void onConfigurationRefresh() {\n"
     "        if (mTabs != null && mTabsContainer != null) {\n"
     "            mTabs.getLayoutParams().width = ViewGroup.LayoutParams.MATCH_PARENT;\n"
     "            mTabsContainer.setAlpha(0f);   // reaparece quando a largura for recalculada\n"
     "            requestLayout();\n"
     "        }\n"
     "    }\n\n"
     "    @Override\n    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {\n"
     "        boolean remeasureTabWidth",
     marker="void onConfigurationRefresh()", desc="abas recalculam na rotacao")

edit(SRC / "Launcher.java",
     "        if (mAppsCustomizeContent != null) {\n"
     "            mAppsCustomizeContent.onConfigurationRefresh();\n"
     "        }\n",
     "        if (mAppsCustomizeContent != null) {\n"
     "            mAppsCustomizeContent.onConfigurationRefresh();\n"
     "        }\n"
     "        if (mAppsCustomizeTabHost != null) {\n"
     "            mAppsCustomizeTabHost.onConfigurationRefresh();\n"
     "        }\n",
     marker="mAppsCustomizeTabHost.onConfigurationRefresh()", desc="onConfigurationChanged: abas")

# ------------------------------------------------------------------ resumo
print("== 06: toque longo + rotacao + brilho/root ==" + ("  (dry-run)" if DRY else ""))
for c in CHANGED:
    print("  ok  ", c)
if not CHANGED and not WARN:
    print("  nada a fazer (ja aplicado)")
if WARN:
    print("AVISOS:")
    for w in WARN:
        print("  !!  ", w)
