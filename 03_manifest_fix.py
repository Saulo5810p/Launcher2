#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_manifest_fix.py  -  AndroidManifest.xml do Launcher2 para SDK 34 / AGP 8

Rode na RAIZ do repositorio:   python3 03_manifest_fix.py [--dry-run] [--keep-ids]

  * remove package="..." (agora vem do namespace do build.gradle) e <original-package>
  * android:exported="true" em activity/receiver/provider com intent-filter (obrigatorio no SDK 31+)
  * remove a activity RocketLauncher (a classe e' removida pelo script 04)
  * remove permissionGroup="android.permission-group.SYSTEM_TOOLS" (grupo nao existe mais)
  * remove o atributo 'style' invalido da activity WallpaperChooser
  * adiciona EXPAND_STATUS_BAR (abrir notificacoes) e QUERY_ALL_PACKAGES (listar apps no SDK 30+)
  * troca o namespace XML http://schemas.android.com/apk/res/com.android.launcher por res-auto
  * IDs unicos (evita INSTALL_FAILED_CONFLICTING_PROVIDER / DUPLICATE_PERMISSION com outro launcher):
      permissoes com.android.launcher.permission.*  -> com.xaulinxs.launcher2.permission.*
      authority   com.android.launcher2.settings    -> com.xaulinxs.launcher2.settings
    (use --keep-ids para manter os nomes originais)

Idempotente.
"""
import argparse
import re
import sys
from pathlib import Path

APP_ID = "com.xaulinxs.launcher2"
MANIFEST = Path("AndroidManifest.xml")
PROVIDER_JAVA = Path("src/com/android/launcher2/LauncherProvider.java")
CHANGED, WARN = [], []
DRY = False


def log_change(msg):
    CHANGED.append(msg)


def sub(txt, pattern, repl, desc, flags=0, count=0):
    new, n = re.subn(pattern, repl, txt, count=count, flags=flags)
    if n:
        log_change(f"{desc} ({n}x)")
    return new


def fix_manifest(txt, keep_ids):
    # 1) package="..." e <original-package>
    txt = sub(txt, r'\s+package="[^"]*"', "", "remove package=", count=1)
    txt = sub(txt, r'\n[ \t]*<original-package[^>]*/>[ \t]*', "", "remove <original-package>")

    # 2) RocketLauncher
    txt = sub(txt, r'\n[ \t]*<activity android:name="com\.android\.launcher2\.RocketLauncher".*?</activity>',
              "", "remove activity RocketLauncher", flags=re.S)

    # 3) permissionGroup e style invalido
    txt = sub(txt, r'\n[ \t]*android:permissionGroup="[^"]*"', "", "remove permissionGroup")
    txt = sub(txt, r'\n[ \t]*style="@style/Theme\.WallpaperPicker"', "", "remove style= invalido (WallpaperChooser)")

    # 4) exported
    def add_exported(m):
        tag = m.group(0)
        if "android:exported" in tag:
            return tag
        log_change("android:exported em " + re.search(r'android:name="([^"]*)"', tag).group(1).split(".")[-1])
        return re.sub(r'(android:name="[^"]*")', r'\1\n            android:exported="true"', tag, count=1)

    txt = re.sub(r'<(?:activity|receiver|provider)\b[^>]*>', add_exported, txt)

    # 5) permissoes extras
    anchor = '<uses-permission android:name="android.permission.VIBRATE" />'
    for perm in ("android.permission.EXPAND_STATUS_BAR", "android.permission.QUERY_ALL_PACKAGES"):
        if perm not in txt:
            if anchor in txt:
                txt = txt.replace(anchor, anchor + f'\n    <uses-permission android:name="{perm}" />', 1)
                anchor = f'<uses-permission android:name="{perm}" />'
                log_change(f"uses-permission {perm.split('.')[-1]}")
            else:
                WARN.append(f"ancora VIBRATE nao encontrada; adicione {perm} manualmente")

    # 6) ids unicos
    if not keep_ids:
        txt = sub(txt, r'com\.android\.launcher\.permission\.', f"{APP_ID}.permission.",
                  "permissoes -> " + APP_ID)
        txt = sub(txt, r'android:authorities="com\.android\.launcher2\.settings"',
                  f'android:authorities="{APP_ID}.settings"', "authority -> " + APP_ID)
    return txt


def main():
    global DRY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-ids", action="store_true")
    a = ap.parse_args()
    DRY = a.dry_run

    if not MANIFEST.exists() or not Path("res").is_dir():
        sys.exit("ERRO: rode na raiz do repo Launcher2 (AndroidManifest.xml e res/).")

    print("== 03: manifest e namespaces ==")

    old = MANIFEST.read_text(encoding="utf-8")
    new = fix_manifest(old, a.keep_ids)
    if new != old and not DRY:
        MANIFEST.write_text(new, encoding="utf-8")

    # authority no Java (precisa casar com o manifest)
    if not a.keep_ids and PROVIDER_JAVA.exists():
        j = PROVIDER_JAVA.read_text(encoding="utf-8")
        j2 = j.replace('AUTHORITY = "com.android.launcher2.settings"', f'AUTHORITY = "{APP_ID}.settings"')
        if j2 != j:
            log_change("LauncherProvider.AUTHORITY -> " + APP_ID + ".settings")
            if not DRY:
                PROVIDER_JAVA.write_text(j2, encoding="utf-8")

    # namespace xml
    n_files = 0
    for f in Path("res").rglob("*.xml"):
        t = f.read_text(encoding="utf-8")
        t2 = t.replace("http://schemas.android.com/apk/res/com.android.launcher",
                       "http://schemas.android.com/apk/res-auto")
        if t2 != t:
            n_files += 1
            if not DRY:
                f.write_text(t2, encoding="utf-8")
    if n_files:
        log_change(f"namespace res/com.android.launcher -> res-auto em {n_files} arquivos")

    print(f"  alteracoes: {len(CHANGED)}")
    for c in CHANGED:
        print(f"    + {c}")
    for w in WARN:
        print(f"    ! {w}")
    print("== 03 concluido ==" + (" (dry-run)" if DRY else ""))


if __name__ == "__main__":
    main()
