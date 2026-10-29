#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_force_tablet_resources.py  -  forca os recursos de TABLET como unicos recursos do app

Rode na RAIZ do repositorio:   python3 02_force_tablet_resources.py [opcoes]

Problema: no Launcher2 o tablet e' decidido por qualificadores (sw600dp, xlarge) e o telefone
por port/land/sw340dp. Se so movessemos o sw600dp para o default, num celular os dirs
values-port, values-land e drawable-land-* continuariam ganhando do default.

Solucao: simulamos a resolucao de recursos do Android para um dispositivo
"smallestWidth = TARGET_SW dp, tela xlarge", separadamente em retrato e paisagem, e
reescrevemos res/ so com os vencedores, sem os qualificadores sw*/xlarge:

  layout-sw600dp/launcher.xml            -> layout/launcher.xml
  values-sw600dp/dimens.xml (+ values/)  -> values/dimens.xml (mesclado por nome)
  drawable-xlarge-hdpi/x.png             -> drawable-hdpi/x.png (substitui a versao de telefone)
  layout-sw600dp-port/ + -land/ diferentes -> layout-port/ + layout-land/

Tags exclusivas do AOSP (<add-resource>, <java-symbol>, <skip>, <eat-comment>) tambem saem
de values/: o merger do Gradle recusa essas tags.

O resultado nao depende mais do tamanho do aparelho. Sobra so orientacao e densidade.
Recursos que so valiam para telas maiores que TARGET_SW (sw720dp) sao descartados.

Tambem (a menos que --keep-unused):
  * poda layouts que o tablet nunca infla (hotseat, workspace_divider, ...), alcancabilidade
    calculada a partir de R.layout.* no Java e de @layout/ em todo o res/
  * cria values/ids_phone_compat.xml com os R.id.* que o Java usa mas que so existiam
    nos layouts podados (findViewById devolve null, como no tablet)

Opcoes:
  --dry-run          mostra o plano sem escrever
  --target-sw N      smallestWidth alvo em dp (padrao 600; o helper de escala usa o mesmo valor)
  --keep-unused      nao poda layouts sem uso

Backup: o res/ original fica em .backup_tablet/res_original (so na primeira execucao).
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {
    "xliff": "urn:oasis:names:tc:xliff:document:1.2",
    "android": "http://schemas.android.com/apk/res/android",
    "tools": "http://schemas.android.com/tools",
}
for _p, _u in NS.items():
    ET.register_namespace(_p, _u)

# Tags do aapt1/AOSP que o merger de recursos do Gradle (AGP) rejeita
# ("Can't determine type for tag"). Sao so metadados, sem valor: podem sair.
DROP_TAGS = {"eat-comment", "skip", "add-resource", "java-symbol"}

SIZE_ORDER = {"small": 0, "normal": 1, "large": 2, "xlarge": 3}
TARGET_SIZE = "xlarge"
DENSITIES = {"ldpi", "mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi", "tvdpi", "nodpi", "anydpi"}
ORIENTS = ("port", "land")
APACHE_HDR = '<?xml version="1.0" encoding="utf-8"?>\n'


# ----------------------------------------------------------------------------------------
# qualificadores
# ----------------------------------------------------------------------------------------
class Qual:
    __slots__ = ("locale", "sw", "size", "orient", "density")

    def __init__(self):
        self.locale = ""
        self.sw = None
        self.size = None
        self.orient = None
        self.density = None

    def rank(self):
        return (self.sw if self.sw is not None else -1,
                SIZE_ORDER[self.size] if self.size else -1,
                1 if self.orient else 0)


def parse_dir(name):
    parts = name.split("-")
    rtype, toks = parts[0], parts[1:]
    q = Qual()
    loc = []
    for t in toks:
        m = re.fullmatch(r"sw(\d+)dp", t)
        if m:
            q.sw = int(m.group(1))
        elif t in SIZE_ORDER:
            q.size = t
        elif t in ORIENTS:
            q.orient = t
        elif t in DENSITIES:
            q.density = t
        elif not loc and re.fullmatch(r"[a-z]{2,3}", t):
            loc.append(t)
        elif loc and re.fullmatch(r"r[A-Z]{2}", t):
            loc.append(t)
        elif not loc and t.startswith("b+"):
            loc.append(t)
        else:
            raise ValueError(f"qualificador desconhecido '{t}' em '{name}'")
    q.locale = "-".join(loc)
    return rtype, q


def build_dirname(rtype, locale, orient, density):
    parts = [rtype]
    if locale:
        parts.append(locale)
    if orient:
        parts.append(orient)
    if density:
        parts.append(density)
    return "-".join(parts)


def matches(q, orient, target_sw):
    if q.sw is not None and q.sw > target_sw:
        return False
    if q.size is not None and SIZE_ORDER[q.size] > SIZE_ORDER[TARGET_SIZE]:
        return False
    if q.orient is not None and q.orient != orient:
        return False
    return True


def resolve(cands, orient, target_sw):
    """Elimina candidatos na ordem de precedencia do Android: sw > tamanho > orientacao.
    Os sobreviventes diferem apenas pela densidade (que nao eliminamos)."""
    c = [x for x in cands if matches(x.q, orient, target_sw)]
    have = [x for x in c if x.q.sw is not None]
    if have:
        best = max(x.q.sw for x in have)
        c = [x for x in have if x.q.sw == best]
    have = [x for x in c if x.q.size is not None]
    if have:
        best = max(SIZE_ORDER[x.q.size] for x in have)
        c = [x for x in have if SIZE_ORDER[x.q.size] == best]
    have = [x for x in c if x.q.orient is not None]
    if have:
        c = have
    return c


def signature(group):
    return frozenset((x.q.density, x.digest) for x in group)


# ----------------------------------------------------------------------------------------
# leitura do res/
# ----------------------------------------------------------------------------------------
class Cand:
    __slots__ = ("dirname", "rtype", "q", "digest", "src", "fname", "comments", "text", "order", "header")


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def read_header(raw):
    i = raw.find("<resources")
    head = raw[:i] if i >= 0 else APACHE_HDR
    if "<?xml" not in head:
        head = APACHE_HDR + head
    return head


def strip_ns_decl(text):
    for p, u in NS.items():
        text = text.replace(f' xmlns:{p}="{u}"', "")
    return text


def parse_values_file(path):
    raw = path.read_text(encoding="utf-8")
    header = read_header(raw)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(raw.encode("utf-8"), parser=parser)
    out, pending = [], []
    for ch in root:
        if ch.tag is ET.Comment:
            pending.append(ch.text)
            continue
        if not isinstance(ch.tag, str):
            continue
        name = ch.get("name")
        if ch.tag in DROP_TAGS or name is None:
            pending = []
            continue
        key = (ch.tag, name, ch.get("type") if ch.tag == "item" else None)
        ch.tail = None
        text = strip_ns_decl(ET.tostring(ch, encoding="unicode"))
        out.append((key, pending, text))
        pending = []
    return header, out


def collect(res):
    """Retorna dict chave -> [Cand]. Chave: (rtype, locale, nome)."""
    cands = defaultdict(list)
    for d in sorted(p for p in res.iterdir() if p.is_dir()):
        try:
            rtype, q = parse_dir(d.name)
        except ValueError as e:
            sys.exit(f"ERRO: {e}. Ajuste parse_dir() do script para esse qualificador.")
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            if rtype == "values":
                if f.suffix != ".xml":
                    print(f"  aviso: ignorando arquivo nao-xml em values: {f}")
                    continue
                header, elems = parse_values_file(f)
                for order, (key, comments, text) in enumerate(elems):
                    c = Cand()
                    c.dirname, c.rtype, c.q = d.name, rtype, q
                    c.digest = sha1(text.encode("utf-8"))
                    c.src, c.fname, c.comments, c.text, c.order, c.header = f, f.name, comments, text, order, header
                    cands[(rtype, q.locale, key)].append(c)
            else:
                name = f.name if rtype == "raw" else f.name.split(".")[0]
                c = Cand()
                c.dirname, c.rtype, c.q = d.name, rtype, q
                c.digest = sha1(f.read_bytes())
                c.src, c.fname, c.comments, c.text, c.order, c.header = f, f.name, None, None, 0, None
                cands[(rtype, q.locale, name)].append(c)
    return cands


# ----------------------------------------------------------------------------------------
# plano
# ----------------------------------------------------------------------------------------
def plan_resources(cands, target_sw):
    files = {}      # (dirname, fname) -> Path
    values = defaultdict(list)   # (dirname, fname) -> [(rank, order, comments, text, header)]
    expected = {}   # chave -> (sigPort, sigLand)
    for key, cl in cands.items():
        rtype, locale, _ = key
        res_by_o = {o: resolve(cl, o, target_sw) for o in ORIENTS}
        sigs = {o: signature(res_by_o[o]) for o in ORIENTS}
        expected[key] = (sigs["port"], sigs["land"])
        gp, gl = res_by_o["port"], res_by_o["land"]
        if sigs["port"] == sigs["land"]:
            emit = [(None, gp)]                      # igual nas duas orientacoes
        elif not gp or not gl:
            emit = [(o, res_by_o[o]) for o in ORIENTS if res_by_o[o]]   # so existe em uma
        else:
            emit = [(None, gp), ("land", gl)]        # base (retrato) + override de paisagem
        for orient, group in emit:
            for c in group:
                out_dir = build_dirname(rtype, locale, orient, c.q.density)
                if rtype == "values":
                    values[(out_dir, c.fname)].append((c.q.rank(), c.order, c.comments, c.text, c.header))
                else:
                    files[(out_dir, c.fname)] = c.src
    return files, values, expected


def referenced_layouts_and_ids(files, values, src_dir, manifest):
    """Le os textos necessarios para poda de layouts."""
    java = ""
    for p in src_dir.rglob("*.java"):
        java += p.read_text(encoding="utf-8", errors="replace") + "\n"
    man = manifest.read_text(encoding="utf-8", errors="replace") if manifest.exists() else ""
    return java, man


def prune_layouts(files, values, java, man):
    layout_names = defaultdict(list)   # nome -> [(dirname, fname)]
    for (d, f) in files:
        if d.split("-")[0] == "layout":
            layout_names[f.split(".")[0]].append((d, f))

    # arestas e raizes
    edges = defaultdict(set)
    roots = set(re.findall(r"(?<![\w.])R\.layout\.(\w+)", java))
    roots |= set(re.findall(r"@layout/(\w+)", man))
    for (d, f), src in files.items():
        if not f.endswith(".xml"):
            continue
        txt = src.read_text(encoding="utf-8", errors="replace")
        refs = set(re.findall(r"@layout/(\w+)", txt))
        if d.split("-")[0] == "layout":
            edges[f.split(".")[0]] |= refs
        else:
            roots |= refs
    for items in values.values():
        for (_, _, _, text, _) in items:
            roots |= set(re.findall(r"@layout/(\w+)", text))

    reach, stack = set(), [r for r in roots if r in layout_names]
    while stack:
        n = stack.pop()
        if n in reach:
            continue
        reach.add(n)
        stack.extend(x for x in edges[n] if x in layout_names and x not in reach)

    dropped = sorted(n for n in layout_names if n not in reach)
    for n in dropped:
        for k in layout_names[n]:
            files.pop(k, None)
    return dropped


def compute_missing_ids(files, values, java):
    defined, referenced = set(), set(re.findall(r"(?<![\w.])R\.id\.(\w+)", java))
    for (d, f), src in files.items():
        if d.split("-")[0] == "values" or not f.endswith(".xml"):
            continue
        txt = src.read_text(encoding="utf-8", errors="replace")
        defined |= set(re.findall(r"@\+id/(\w+)", txt))
        referenced |= set(re.findall(r"@id/(\w+)", txt))
    for items in values.values():
        for (_, _, _, text, _) in items:
            m = re.match(r'<item\b[^>]*', text)
            if m and 'type="id"' in m.group(0):
                n = re.search(r'name="(\w+)"', m.group(0))
                if n:
                    defined.add(n.group(1))
    # ids definidos em arquivos de values (item type=id) ja contados acima
    return sorted(referenced - defined)


# ----------------------------------------------------------------------------------------
# escrita
# ----------------------------------------------------------------------------------------
def render_values(items):
    items = sorted(items, key=lambda t: (t[0], t[1]))
    header = items[0][4]
    used_x = any("xliff:" in t[3] for t in items)
    root = "<resources" + (f' xmlns:xliff="{NS["xliff"]}"' if used_x else "") + ">\n"
    body = []
    for (_, _, comments, text, _) in items:
        for c in comments or []:
            body.append(f"    <!--{c}-->\n")
        body.append(f"    {text}\n")
    return header + root + "".join(body) + "</resources>\n"


def write_tree(new_res, files, values):
    for (d, f), src in files.items():
        dst = new_res / d / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for (d, f), items in values.items():
        dst = new_res / d / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(render_values(items), encoding="utf-8")


def verify(new_res, expected, pruned_names, target_sw):
    cands = collect(new_res)
    bad = 0
    for key, (sp, sl) in expected.items():
        rtype, locale, name = key
        if rtype == "layout" and name in pruned_names:
            continue
        cl = cands.get(key, [])
        got = tuple(signature(resolve(cl, o, target_sw)) for o in ORIENTS)
        if got != (sp, sl):
            bad += 1
            if bad <= 10:
                print(f"  VERIFICACAO FALHOU: {key}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--target-sw", type=int, default=600)
    ap.add_argument("--keep-unused", action="store_true")
    a = ap.parse_args()

    res = Path("res")
    if not (res.is_dir() and Path("src").is_dir()):
        sys.exit("ERRO: rode na raiz do repo Launcher2 (precisa de res/ e src/).")

    print("== 02: forcando recursos de tablet ==")
    orig_dirs = sorted(p.name for p in res.iterdir() if p.is_dir())
    cands = collect(res)
    files, values, expected = plan_resources(cands, a.target_sw)

    java, man = referenced_layouts_and_ids(files, values, Path("src"), Path("AndroidManifest.xml"))
    pruned = []
    if not a.keep_unused:
        pruned = prune_layouts(files, values, java, man)
    missing = compute_missing_ids(files, values, java)
    if missing:
        note = " ids usados pelo Java que so existiam nos layouts de telefone (findViewById -> null, como no tablet) "
        items = [((9999, 0), i, [note] if i == 0 else [], f'<item name="{n}" type="id" />', APACHE_HDR)
                 for i, n in enumerate(missing)]
        values[("values", "ids_phone_compat.xml")] = items

    new_dirs = sorted({d for (d, _) in files} | {d for (d, _) in values})
    removed = [d for d in orig_dirs if d not in new_dirs]
    created = [d for d in new_dirs if d not in orig_dirs]
    dropped_big = sorted({c.dirname for cl in cands.values() for c in cl
                          if c.q.sw is not None and c.q.sw > a.target_sw})

    print(f"  dirs originais: {len(orig_dirs)}  ->  dirs finais: {len(new_dirs)}")
    print(f"  dirs removidos: {len(removed)}")
    for d in removed:
        if not re.match(r"values-[a-z]{2,3}(-r[A-Z]{2})?-(sw600dp|land)$", d):
            print(f"    - {d}")
    print(f"    (+ {sum(1 for d in removed if re.match(r'values-[a-z]{2,3}(-r[A-Z]{2})?-(sw600dp|land)$', d))} dirs de traducao -sw600dp mesclados em values-<idioma>)")
    if created:
        print(f"  dirs criados: {', '.join(created)}")
    if dropped_big:
        print(f"  descartados por serem para telas > {a.target_sw}dp: {', '.join(dropped_big)}")
    if pruned:
        print(f"  layouts podados (so telefone / sem uso): {', '.join(pruned)}")
    if missing:
        print(f"  ids de compatibilidade criados ({len(missing)}): {', '.join(missing)}")

    if a.dry_run:
        print("== 02 (dry-run) nada foi escrito ==")
        return

    backup = Path(".backup_tablet/res_original")
    if not backup.exists():
        backup.parent.mkdir(exist_ok=True)
        shutil.copytree(res, backup)
        print("  backup do res/ original em .backup_tablet/res_original")

    new_res = Path("res.__new")
    if new_res.exists():
        shutil.rmtree(new_res)
    write_tree(new_res, files, values)

    bad = verify(new_res, expected, set(pruned), a.target_sw)
    if bad:
        shutil.rmtree(new_res)
        sys.exit(f"ERRO: {bad} recursos divergem apos a reescrita. res/ NAO foi alterado.")

    shutil.rmtree(res)
    new_res.rename(res)

    Path(".tablet_config.json").write_text(
        json.dumps({"target_sw": a.target_sw}, indent=2) + "\n", encoding="utf-8")
    print(f"  verificacao ok (todos os recursos resolvem igual ao tablet original)")
    print("== 02 concluido ==")


if __name__ == "__main__":
    main()
