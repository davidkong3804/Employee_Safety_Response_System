import base64, glob, os, re
logos = {}
for f in glob.glob("logos/*.svg"):
    name = os.path.splitext(os.path.basename(f))[0]
    b64 = base64.b64encode(open(f,"rb").read()).decode()
    logos[name] = f"data:image/svg+xml;base64,{b64}"

# token: @@name@@  or  @@name|WIDTH@@
def repl(m):
    name = m.group(1); w = m.group(2) or "38"
    if name not in logos:
        return m.group(0)
    return (f"<img src='{logos[name]}' width='{w}' "
            f"style='vertical-align:middle;margin:0 2px' alt='{name}'/>")

pat = re.compile(r"@@([a-z0-9]+)(?:\|(\d+))?@@")
for src in glob.glob("src/*.mmd"):
    out = os.path.join("build", os.path.basename(src))
    txt = open(src,encoding="utf-8").read()
    open(out,"w",encoding="utf-8").write(pat.sub(repl, txt))
    print("built", out)
