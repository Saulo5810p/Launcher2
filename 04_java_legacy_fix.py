#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_java_legacy_fix.py  -  Launcher2 (ICS) -> Java que compila e roda no Android moderno (SDK 34)

Rode na RAIZ do repositorio:   python3 04_java_legacy_fix.py [--dry-run]

Forca o layout de tablet:
  * LauncherApplication.isScreenLarge() passa a devolver sempre true

Corrige o que nao compila contra o SDK publico:
  * com.android.internal.util.XmlUtils      -> src/.../XmlUtils.java local
  * com.android.internal.R.id.tabs/tabcontent -> android.R.id.*
  * com.android.internal.R.dimen.default_app_widget_padding_* -> dimens proprios (8dp)
  * com.android.internal.R.mipmap.sym_def_app_icon -> getIdentifier + fallback publico
  * android.os.SystemProperties, com.android.common.Search -> removidos / literal
  * View.setFastScaleX/Y/Alpha/Translation*/RotationY, fastInvalidate -> setScaleX... / invalidate
  * ViewGroup.setChildrenLayersEnabled (oculto) -> setLayerType nos filhos
  * ValueAnimator.clearAllAnimations(), StatusBarManager.expand() (ocultos)
  * new Vibrator() -> getSystemService(VIBRATOR_SERVICE)
  * Launcher.closeSystemDialogs() (conflita com Context) -> closeLauncherDialogs()
  * Workspace.onViewAdded: protected -> public ; BubbleTextView.mLayout -> getLayout()
  * RocketLauncher (usa android.support.v13.dreams, que nao existe mais) -> removido
  * campos herdados que o SDK publico nao expoe (mScrollX/Y, mPadding*, mLeft/Right/Top/Bottom,
    mParent, mContext) -> getScrollX(), getPaddingLeft(), getLeft(), getParent(), getContext()...
  * ClipData.getIcon(), AccessibilityManager.getInstance() e TableMaskFilter (ocultos)
  * registerReceiver(...) -> Utilities.registerReceiverCompat (flag RECEIVER_EXPORTED no Android 13+)

Corrige o que compilava mas falha em runtime:
  * bindAppWidgetId (oculto desde o 4.1) -> bindAppWidgetIdIfAllowed + ACTION_APPWIDGET_BIND
  * configuracao de widget -> AppWidgetHost.startAppWidgetConfigureActivityForResult

Tambem cria res/values/dimens_modern_compat.xml (dimens usados no lugar dos internos).
Idempotente. Pontos nao encontrados sao listados no final como AVISO.
"""
import argparse
import re
import sys
from pathlib import Path

SRC = Path("src/com/android/launcher2")
WARN = []
CHANGED = []
DRY = False


def rd(p):
    return p.read_text(encoding="utf-8")


def wr(p, txt):
    if not DRY:
        p.write_text(txt, encoding="utf-8")


def edit(fname, old, new, regex=False, flags=0, desc=None, count=0):
    """Edita SRC/fname. Idempotente: se 'old' nao existe mas 'new' existe, considera aplicado."""
    p = SRC / fname
    tag = f"{fname}: {desc or old[:50].strip()!r}"
    if not p.exists():
        WARN.append(f"{tag} (arquivo inexistente)")
        return
    txt = rd(p)
    if regex:
        if re.search(old, txt, flags):
            wr(p, re.sub(old, new, txt, count=count, flags=flags))
            CHANGED.append(tag)
        return
    if old in txt:
        if old in new and new in txt:
            return                  # ja aplicado (o novo trecho contem o antigo)
        wr(p, txt.replace(old, new) if count == 0 else txt.replace(old, new, count))
        CHANGED.append(tag)
    elif new and new in txt:
        return                      # ja aplicado
    elif not new:
        return
    else:
        WARN.append(tag + " (trecho nao encontrado)")


XMLUTILS = '''/*
 * Copyright (C) 2006 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.android.launcher2;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserException;

import java.io.IOException;

/**
 * Copia minima de com.android.internal.util.XmlUtils (classe interna do framework,
 * inacessivel para apps comuns).
 */
final class XmlUtils {
    private XmlUtils() {}

    public static final void beginDocument(XmlPullParser parser, String firstElementName)
            throws XmlPullParserException, IOException {
        int type;
        while ((type = parser.next()) != XmlPullParser.START_TAG
                && type != XmlPullParser.END_DOCUMENT) {
            ;
        }
        if (type != XmlPullParser.START_TAG) {
            throw new XmlPullParserException("No start tag found");
        }
        if (!parser.getName().equals(firstElementName)) {
            throw new XmlPullParserException("Unexpected start tag: found " + parser.getName()
                    + ", expected " + firstElementName);
        }
    }

    public static final void nextElement(XmlPullParser parser)
            throws XmlPullParserException, IOException {
        int type;
        while ((type = parser.next()) != XmlPullParser.START_TAG
                && type != XmlPullParser.END_DOCUMENT) {
            ;
        }
    }
}
'''

DIMENS_COMPAT = '''<?xml version="1.0" encoding="utf-8"?>
<!-- generated by 04_java_legacy_fix.py
     Substitui com.android.internal.R.dimen.default_app_widget_padding_* (valores AOSP: 8dp). -->
<resources>
    <dimen name="default_app_widget_padding_left">8dp</dimen>
    <dimen name="default_app_widget_padding_right">8dp</dimen>
    <dimen name="default_app_widget_padding_top">8dp</dimen>
    <dimen name="default_app_widget_padding_bottom">8dp</dimen>
</resources>
'''

SHOW_NOTIFICATIONS_OLD = '''    private void showNotifications() {
        final StatusBarManager statusBar = (StatusBarManager) getSystemService(STATUS_BAR_SERVICE);
        if (statusBar != null) {
            statusBar.expand();
        }
    }'''

SHOW_NOTIFICATIONS_NEW = '''    private void showNotifications() {
        // StatusBarManager e' oculto no SDK publico: usa reflexao (precisa de EXPAND_STATUS_BAR).
        try {
            final Object statusBar = getSystemService("statusbar");
            if (statusBar != null) {
                final Class<?> sbm = Class.forName("android.app.StatusBarManager");
                sbm.getMethod("expandNotificationsPanel").invoke(statusBar);
            }
        } catch (Throwable t) {
            Log.w(TAG, "Nao foi possivel abrir o painel de notificacoes", t);
        }
    }'''

BIND_OLD = '''        int appWidgetId = getAppWidgetHost().allocateAppWidgetId();
        AppWidgetManager.getInstance(this).bindAppWidgetId(appWidgetId, info.componentName);
        addAppWidgetImpl(appWidgetId, info);'''

BIND_NEW = '''        int appWidgetId = getAppWidgetHost().allocateAppWidgetId();
        if (AppWidgetManager.getInstance(this).bindAppWidgetIdIfAllowed(
                appWidgetId, info.componentName)) {
            addAppWidgetImpl(appWidgetId, info);
        } else {
            // Sem a permissao BIND_APPWIDGET (so apps de sistema): pede autorizacao ao usuario.
            mPendingBindInfo = info;
            mPendingBindAppWidgetId = appWidgetId;
            Intent bind = new Intent(AppWidgetManager.ACTION_APPWIDGET_BIND);
            bind.putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId);
            bind.putExtra(AppWidgetManager.EXTRA_APPWIDGET_PROVIDER, info.componentName);
            startActivityForResultSafely(bind, REQUEST_BIND_APPWIDGET);
        }'''

BIND_RESULT_ANCHOR = '''        boolean delayExitSpringLoadedMode = false;
        mWaitingForResult = false;
'''

BIND_RESULT_NEW = BIND_RESULT_ANCHOR + '''
        if (requestCode == REQUEST_BIND_APPWIDGET) {
            final PendingAddWidgetInfo bindInfo = mPendingBindInfo;
            final int bindId = (data != null)
                    ? data.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, mPendingBindAppWidgetId)
                    : mPendingBindAppWidgetId;
            mPendingBindInfo = null;
            mPendingBindAppWidgetId = -1;
            if (resultCode == RESULT_OK && bindInfo != null && bindId != -1) {
                addAppWidgetImpl(bindId, bindInfo);
            } else {
                if (bindId != -1) {
                    mAppWidgetHost.deleteAppWidgetId(bindId);
                }
                exitSpringLoadedDragModeDelayed(false, false);
            }
            return;
        }
'''

CONFIG_OLD = '''            startActivityForResultSafely(intent, REQUEST_CREATE_APPWIDGET);
        } else {
            // Otherwise just add it'''

CONFIG_NEW = '''            // A activity de configuracao pode nao ser exportada: o host precisa abri-la pelo sistema.
            boolean hasConfigData = info != null && info.mimeType != null
                    && !info.mimeType.isEmpty();
            boolean started = false;
            if (!hasConfigData) {
                try {
                    mAppWidgetHost.startAppWidgetConfigureActivityForResult(
                            this, appWidgetId, 0, REQUEST_CREATE_APPWIDGET, null);
                    mWaitingForResult = true;
                    started = true;
                } catch (Exception e) {
                    Log.w(TAG, "Configuracao via host falhou; tentando intent direta", e);
                }
            }
            if (!started) {
                startActivityForResultSafely(intent, REQUEST_CREATE_APPWIDGET);
            }
        } else {
            // Otherwise just add it'''

CELL_FAST_ALPHA = '''    public void setFastAlpha(float alpha) {
        setFastChildrenAlpha(alpha);
        super.setFastAlpha(alpha);
    }

'''

CELL_FAST_CHILDREN = '''    private void setFastChildrenAlpha(float alpha) {
        final int childCount = getChildCount();
        for (int i = 0; i < childCount; i++) {
            getChildAt(i).setFastAlpha(alpha);
        }
    }

'''

CHILD_LAYERS_HELPER = '''    private static void setChildrenLayers(ViewGroup parent, boolean enabled) {
        // Substitui ViewGroup.setChildrenLayersEnabled (oculto): camada de hardware nos filhos.
        final int type = enabled ? View.LAYER_TYPE_HARDWARE : View.LAYER_TYPE_NONE;
        final int count = parent.getChildCount();
        for (int i = 0; i < count; i++) {
            parent.getChildAt(i).setLayerType(type, null);
        }
    }

    protected void onWallpaperTap(MotionEvent ev) {'''

ICON_OLD = '''    public Drawable getFullResDefaultActivityIcon() {
        return getFullResIcon(Resources.getSystem(),
                com.android.internal.R.mipmap.sym_def_app_icon);
    }'''

ICON_NEW = '''    public Drawable getFullResDefaultActivityIcon() {
        final Resources sys = Resources.getSystem();
        int id = sys.getIdentifier("sym_def_app_icon", "mipmap", "android");
        if (id == 0) {
            id = android.R.drawable.sym_def_app_icon;
        }
        return getFullResIcon(sys, id);
    }'''


CLIP_TABLE_HELPER = '''
    /** TableMaskFilter e' oculta no SDK publico: tenta por reflexao e, se falhar, segue sem o filtro. */
    static MaskFilter createClipTable(int min, int max) {
        try {
            Class<?> c = Class.forName("android.graphics.TableMaskFilter");
            return (MaskFilter) c.getMethod("CreateClipTable", int.class, int.class)
                    .invoke(null, min, max);
        } catch (Throwable t) {
            return null;
        }
    }

    /** Android 13+ exige informar a flag de exportacao ao registrar receivers em runtime. */
    static void registerReceiverCompat(android.content.Context context,
            android.content.BroadcastReceiver receiver, android.content.IntentFilter filter) {
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            context.registerReceiver(receiver, filter, android.content.Context.RECEIVER_EXPORTED);
        } else {
            context.registerReceiver(receiver, filter);
        }
    }
'''

# campo herdado oculto -> (expressao publica, arquivos onde aparece)
HIDDEN_FIELDS = [
    ("mScrollX", "getScrollX()", ["BubbleTextView", "CachedTextView", "CellLayout", "PagedView", "Workspace"]),
    ("mScrollY", "getScrollY()", ["BubbleTextView", "CellLayout", "PagedView", "SmoothPagedView", "Workspace"]),
    ("mPaddingLeft", "getPaddingLeft()", ["CellLayout", "PagedView", "PagedViewCellLayout"]),
    ("mPaddingRight", "getPaddingRight()", ["CellLayout", "PagedView", "PagedViewCellLayout"]),
    ("mPaddingTop", "getPaddingTop()", ["CellLayout", "PagedView", "PagedViewCellLayout", "PagedViewIcon", "Workspace"]),
    ("mPaddingBottom", "getPaddingBottom()", ["CellLayout", "PagedView", "PagedViewCellLayout", "Workspace"]),
    ("mLeft", "getLeft()", ["BubbleTextView", "CachedTextView", "PagedView"]),
    ("mRight", "getRight()", ["BubbleTextView", "CachedTextView", "PagedView"]),
    ("mTop", "getTop()", ["BubbleTextView", "PagedView"]),
    ("mBottom", "getBottom()", ["BubbleTextView", "PagedView"]),
    ("mParent", "getParent()", ["LauncherAppWidgetHostView"]),
    ("mContext", "getContext()", ["AppsCustomizePagedView", "AppsCustomizeTabHost", "Folder",
                                  "PagedView", "Workspace"]),
]


def main():
    global DRY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    DRY = a.dry_run
    if not SRC.is_dir():
        sys.exit("ERRO: rode na raiz do repo Launcher2 (src/com/android/launcher2 nao encontrado).")

    print("== 04: corrigindo Java legado ==")

    # ---- forca tablet -------------------------------------------------------------------
    edit("LauncherApplication.java", "        return sIsScreenLarge;",
         "        // Launcher2 modificado: layout de tablet forcado em qualquer tela\n        return true;",
         desc="isScreenLarge() sempre true")

    # ---- arquivos novos / removidos -----------------------------------------------------
    xu = SRC / "XmlUtils.java"
    if not xu.exists():
        wr(xu, XMLUTILS)
        CHANGED.append("XmlUtils.java criado")
    dc = Path("res/values/dimens_modern_compat.xml")
    if not dc.exists():
        if Path("res/values").is_dir():
            wr(dc, DIMENS_COMPAT)
            CHANGED.append("res/values/dimens_modern_compat.xml criado")
        else:
            WARN.append("res/values nao existe; dimens_modern_compat.xml nao criado")
    rl = SRC / "RocketLauncher.java"
    if rl.exists():
        if not DRY:
            rl.unlink()
        CHANGED.append("RocketLauncher.java removido")

    # ---- LauncherProvider ---------------------------------------------------------------
    edit("LauncherProvider.java", "import com.android.internal.util.XmlUtils;\n", "")
    edit("LauncherProvider.java", r"\.bindAppWidgetId\(", ".bindAppWidgetIdIfAllowed(", regex=True,
         desc="bindAppWidgetId -> IfAllowed")

    # ---- Launcher -----------------------------------------------------------------------
    for imp in ("import android.os.SystemProperties;\n", "import com.android.common.Search;\n",
                "import android.app.StatusBarManager;\n"):
        edit("Launcher.java", imp, "")
    edit("Launcher.java", 'SystemProperties.getInt("debug.launcher2.dumpstate", 0) != 0', "false",
         desc="SystemProperties.getInt")
    edit("Launcher.java", "Search.SOURCE", '"source"', desc="Search.SOURCE")
    edit("Launcher.java", r"com\.android\.internal\.\s*R\.dimen\.", "R.dimen.", regex=True,
         desc="dimens internos -> proprios")
    edit("Launcher.java", r"\bcloseSystemDialogs\(\)", "closeLauncherDialogs()", regex=True,
         desc="closeSystemDialogs -> closeLauncherDialogs")
    edit("Launcher.java", "\n        ValueAnimator.clearAllAnimations();\n", "\n",
         desc="ValueAnimator.clearAllAnimations")
    edit("Launcher.java", SHOW_NOTIFICATIONS_OLD, SHOW_NOTIFICATIONS_NEW, desc="showNotifications")
    # widgets
    edit("Launcher.java", "    private static final int REQUEST_PICK_WALLPAPER = 10;\n",
         "    private static final int REQUEST_PICK_WALLPAPER = 10;\n"
         "    private static final int REQUEST_BIND_APPWIDGET = 11;\n", desc="REQUEST_BIND_APPWIDGET")
    edit("Launcher.java", "    private boolean mWaitingForResult;\n",
         "    private boolean mWaitingForResult;\n"
         "    private PendingAddWidgetInfo mPendingBindInfo;\n"
         "    private int mPendingBindAppWidgetId = -1;\n", desc="campos do bind pendente")
    edit("Launcher.java", BIND_OLD, BIND_NEW, desc="addAppWidgetFromDrop: bind")
    edit("Launcher.java", BIND_RESULT_ANCHOR, BIND_RESULT_NEW, desc="onActivityResult: bind")
    edit("Launcher.java", CONFIG_OLD, CONFIG_NEW, desc="addAppWidgetImpl: configure via host")
    # propriedades "fast" (ocultas)
    fast = [(r"\.setFastScaleX\(", ".setScaleX("), (r"\.setFastScaleY\(", ".setScaleY("),
            (r"\.setFastAlpha\(", ".setAlpha("), (r"\.setFastTranslationX\(", ".setTranslationX("),
            (r"\.setFastTranslationY\(", ".setTranslationY("),
            (r"\.setFastRotationY\(", ".setRotationY("), (r"\bfastInvalidate\(\)", "invalidate()")]

    # ---- CellLayout (precisa vir antes do rename de setFastAlpha) ------------------------
    edit("CellLayout.java", CELL_FAST_ALPHA, "", desc="remove override setFastAlpha")
    edit("CellLayout.java", CELL_FAST_CHILDREN, "", desc="remove setFastChildrenAlpha")
    for f in ("Launcher.java", "Workspace.java", "CellLayout.java"):
        for pat, rep in fast:
            edit(f, pat, rep, regex=True, desc=f"{pat} -> {rep}")

    # ---- Workspace ----------------------------------------------------------------------
    edit("Workspace.java", "    protected void onViewAdded(View child) {",
         "    public void onViewAdded(View child) {", desc="onViewAdded publico")
    edit("Workspace.java",
         "((ViewGroup)getChildAt(i)).setChildrenLayersEnabled(enableChildrenLayers);",
         "setChildrenLayers((ViewGroup) getChildAt(i), enableChildrenLayers);",
         desc="setChildrenLayersEnabled")
    edit("Workspace.java", "    protected void onWallpaperTap(MotionEvent ev) {", CHILD_LAYERS_HELPER,
         desc="helper setChildrenLayers")

    # ---- Vibrator -----------------------------------------------------------------------
    edit("DragController.java", "    private final Vibrator mVibrator = new Vibrator();",
         "    private Vibrator mVibrator;", desc="Vibrator campo")
    edit("DragController.java", "        mHandler = new Handler();\n        mScrollZone",
         "        mHandler = new Handler();\n"
         "        mVibrator = (Vibrator) launcher.getSystemService(Context.VIBRATOR_SERVICE);\n"
         "        mScrollZone", desc="Vibrator no construtor")

    # ---- BubbleTextView -----------------------------------------------------------------
    edit("BubbleTextView.java", "if (mLayout == null) {", "if (getLayout() == null) {",
         desc="mLayout -> getLayout()")

    # ---- IconCache / FocusHelper / AppsCustomizeTabHost ---------------------------------
    edit("IconCache.java", ICON_OLD, ICON_NEW, desc="sym_def_app_icon")
    for f in ("FocusHelper.java", "AppsCustomizeTabHost.java"):
        edit(f, r"com\.android\.internal\.R\.id\.", "android.R.id.", regex=True,
             desc="internal R.id -> android.R.id")


    # ---- campos herdados ocultos --------------------------------------------------------
    # atribuicoes diretas (so no PagedView, overscroll): vira super.scrollTo (sem recursao)
    edit("PagedView.java", r"(?m)^(\s*)mScrollX = (.+);$", r"\1super.scrollTo(\2, getScrollY());",
         regex=True, desc="mScrollX = ... -> super.scrollTo")
    for field, expr, files in HIDDEN_FIELDS:
        for f in files:
            edit(f + ".java", r"(?<![\w.])" + field + r"\b(?!\s*=[^=])", expr, regex=True,
                 desc=f"{field} -> {expr}")

    # ---- APIs ocultas restantes ---------------------------------------------------------
    edit("Workspace.java", r"\bdata\.getIcon\(\)", "null", regex=True, desc="ClipData.getIcon()")
    edit("PagedView.java", "AccessibilityManager.getInstance(getContext()).isEnabled()",
         "((AccessibilityManager) getContext().getSystemService(Context.ACCESSIBILITY_SERVICE))\n"
         "                    .isEnabled()", desc="AccessibilityManager.getInstance")
    for f in ("AppsCustomizePagedView.java", "HolographicOutlineHelper.java"):
        edit(f, "import android.graphics.TableMaskFilter;\n", "")
    edit("Utilities.java", "import android.graphics.TableMaskFilter;\n",
         "import android.graphics.MaskFilter;\n", desc="import MaskFilter")
    for f in ("AppsCustomizePagedView.java", "HolographicOutlineHelper.java", "Utilities.java"):
        edit(f, r"\bTableMaskFilter\.CreateClipTable\(", "Utilities.createClipTable(", regex=True,
             desc="TableMaskFilter.CreateClipTable")
    up = SRC / "Utilities.java"
    if up.exists() and "registerReceiverCompat(" not in rd(up):
        txt = rd(up)
        m = re.search(r"(?m)^(?:public )?(?:final )?class Utilities\s*\{\n", txt)
        if m:
            wr(up, txt[:m.end()] + CLIP_TABLE_HELPER + txt[m.end():])
            CHANGED.append("Utilities.java: helper createClipTable")
        else:
            WARN.append("Utilities.java: declaracao da classe nao encontrada (helper createClipTable)")


    # ---- receivers em runtime (Android 13/14) -------------------------------------------
    edit("LauncherApplication.java", r"(?<![\w.])registerReceiver\((\w+), (\w+)\);",
         r"Utilities.registerReceiverCompat(this, \1, \2);", regex=True, desc="registerReceiver (Application)")
    edit("Launcher.java", r"(?<![\w.])registerReceiver\((\w+), (\w+)\);",
         r"Utilities.registerReceiverCompat(this, \1, \2);", regex=True, desc="registerReceiver (Launcher)")

    print(f"  alteracoes: {len(CHANGED)}")
    for c in CHANGED:
        print(f"    + {c}")
    if WARN:
        print(f"  AVISOS ({len(WARN)}) - me envie esta saida:")
        for w in WARN:
            print(f"    ! {w}")
    print("== 04 concluido ==" + (" (dry-run)" if DRY else ""))


if __name__ == "__main__":
    main()
