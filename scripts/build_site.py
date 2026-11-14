"""Build the dependency-free GitHub Pages site from local catalog metadata."""
import json
import shutil
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
REPO = 'https://github.com/ekim-pl/awesome-fm1'
FLASHER = 'https://ekim-pl.github.io/android-fm1-flasher'
BASE = 'https://ekim-pl.github.io/awesome-fm1'


def link(url, label, cls=''):
    return f'<a class="{cls}" href="{escape(url, quote=True)}">{escape(label)}</a>'


def build():
    locales = json.loads((ROOT / 'website/locales.json').read_text())
    catalog = json.loads((ROOT / 'catalog.json').read_text())
    OUT.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'website/style.css', OUT / 'style.css')
    shutil.copyfile(ROOT / 'catalog.json', OUT / 'catalog.json')
    (OUT / '.nojekyll').touch()
    for lang, t in locales.items():
        nav = ''.join(f'<a lang="{code}" hreflang="{code}" href="../{code}/"' + (' aria-current="page"' if code == lang else '') + f'>{data["label"]}</a>' for code, data in locales.items())
        cards = []
        for fw in catalog['firmwares']:
            description = t.get(fw['id'], fw.get('what', ''))
            links = []
            if fw.get('site'):
                links.append(link(fw['site'], t['source']))
            if fw.get('repo'):
                links.append(link('https://github.com/' + fw['repo'], t['repo']))
            if (fw.get('pkg') or '').startswith('https://'):
                links.append(link(fw['pkg'], t['package']))
            status = t['unknown'] if fw.get('chip', 'unknown') == 'unknown' else t['verified']
            cards.append(f'''<article class="firmware"><div class="tile" aria-hidden="true">{escape(fw['name'][:1])}<span>FM—1</span></div><div><p class="kicker">{escape(t['project'])} / {escape(fw['id'])}</p><h3>{escape(fw['name'])}</h3><p>{escape(description)}</p><dl><div><dt>{t['publisher']}</dt><dd>{escape(fw.get('author', '—'))}</dd></div><div><dt>{t['version']}</dt><dd>{escape(fw.get('version', '—'))} {'· ' + t['beta'] if fw.get('beta') else ''}</dd></div></dl><p class="status">● {status}</p><div class="links">{''.join(links)}{link(REPO + '/blob/main/docs/verification.md', t['evidence'])}</div></div></article>''')
        alternates = ''.join(f'<link rel="alternate" hreflang="{code}" href="{BASE}/{code}/">' for code in locales)
        html = f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Awesome FM-1 — {escape(t['directory'])}</title><meta name="description" content="{escape(t['intro'], quote=True)}"><link rel="canonical" href="{BASE}/{lang}/">{alternates}<link rel="stylesheet" href="../style.css"><meta name="theme-color" content="#121817"></head>
<body><a class="skip" href="#main">{t['skip']}</a><header><a class="brand" href="./">AWESOME <span>FM-1</span></a><nav aria-label="Language">{nav}</nav>{link(REPO, 'GitHub ↗', 'github')}</header>
<main id="main"><section class="hero"><div><p class="kicker">{t['eyebrow']}</p><h1>{t['title']}</h1><p class="intro">{t['intro']}</p><div class="actions">{link('#firmware', t['browse'], 'button')}{link('#contribute', t['contribute'], 'text-link')}</div></div><div class="synth" aria-hidden="true"><div class="synth-top">AWESOME FM-1 <span>COMMUNITY / 001</span></div><div class="display"><span>FIND YOUR NEXT SOUND</span><svg viewBox="0 0 400 120"><path d="M0 60H25L45 12 70 108 95 12 120 108 145 12 170 108 195 12 220 108 245 12 270 108 295 12 320 108 345 12 370 60H400"/></svg><b>FM—1</b></div><div class="knobs"><i></i><i></i><i></i><span>EXPLORE<br>CREATE<br>CONTRIBUTE</span></div></div></section>
<section id="firmware"><p class="kicker">01 / {t['directory']}</p><h2>{t['directoryText']}</h2>{''.join(cards)}<p class="note">{t['notice']}</p></section>
<section class="companion"><p class="kicker">02 / FM-1 FLASHER</p><h2>{t['flasherTitle']}</h2><p>{t['flasherText']}</p><div class="links">{link(FLASHER + '/' + lang + '/', t['flasherLink'])}{link('https://github.com/ekim-pl/android-fm1-flasher', t['flasherRepo'])}</div></section>
<section id="contribute" class="contribute"><div><p class="kicker">03 / PULL REQUEST</p><h2>{t['joinTitle']}</h2><p>{t['joinText']}</p>{link(REPO + '/blob/main/README.md#contributing', t['guidelines'], 'button')}</div><div><ol>{''.join('<li>' + escape(step) + '</li>' for step in t['steps'])}</ol><p class="note">{t['rules']}</p></div></section>
<section class="catalog"><h2>{t['catalogTitle']}</h2><p>{t['catalogText']}</p><div class="links">{link('../catalog.json', t['catalogLink'])}{link(REPO + '/blob/main/schema/catalog.schema.json', t['schema'])}</div></section></main><footer><span>Awesome FM-1</span><p>{t['footer']}</p>{link(REPO, 'GitHub ↗')}</footer></body></html>'''
        target = OUT / lang
        target.mkdir(exist_ok=True)
        (target / 'index.html').write_text(html)
    (OUT / 'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=en/"><title>Awesome FM-1</title></head><body><a href="en/">English</a> · <a href="pl/">Polski</a> · <a href="zh-CN/">简体中文</a></body></html>')
    print('Built English, Polish and Simplified Chinese pages in _site/')


if __name__ == '__main__':
    build()
