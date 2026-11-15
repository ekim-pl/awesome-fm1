"""Build the dependency-free multilingual GitHub Pages site."""
import json
import hashlib
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


def icon_link(url, label, icon, cls=''):
    return f'<a class="{cls}" href="{escape(url, quote=True)}" aria-label="{escape(label, quote=True)}" title="{escape(label, quote=True)}"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{icon}</svg></a>'


ICONS = {
    'GitHub': '<path d="M9 19c-4 1-4-2-6-2m12 4v-3c0-1 .1-1.5-.5-2 3-.3 6-1.5 6-6a4.5 4.5 0 0 0-1.2-3.1A4 4 0 0 0 19.2 3S18 2.6 15 4.5a14 14 0 0 0-6 0C6 2.6 4.8 3 4.8 3a4 4 0 0 0-.1 3.9A4.5 4.5 0 0 0 3.5 10c0 4.5 3 5.7 6 6-.5.5-.6 1-.5 2v3"/>',
    'home': '<path d="M3 11 12 3l9 8M5 10v10h14V10M9 20v-6h6v6"/>',
    'YouTube': '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
    'Instagram': '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".8" fill="currentColor"/>',
    'TikTok': '<path d="M14 3h3a5 5 0 0 0 5 5v3a8 8 0 0 1-5-1.7V16a6 6 0 1 1-6-6v3a3 3 0 1 0 3 3Z"/>',
    'Discord': '<path d="M7 5a19 19 0 0 1 10 0l1-2m-11 2L6 3M7 5C4 6 2 11 2 17l5 3 2-3m8-12c3 1 5 6 5 12l-5 3-2-3M6 16a15 15 0 0 0 12 0"/><circle cx="8" cy="12" r="1"/><circle cx="16" cy="12" r="1"/>',
}


def build():
    locales = json.loads((ROOT / 'website/locales.json').read_text())
    OUT.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'website/style.css', OUT / 'style.css')
    shutil.copyfile(ROOT / 'catalog.json', OUT / 'catalog.json')
    for asset in ('logo.svg', 'favicon.ico'):
        shutil.copyfile(ROOT / 'assets/branding' / asset, OUT / asset)
    style_version = hashlib.sha256((OUT / 'style.css').read_bytes()).hexdigest()[:12]
    logo_version = hashlib.sha256((OUT / 'logo.svg').read_bytes()).hexdigest()[:12]
    favicon_version = hashlib.sha256((OUT / 'favicon.ico').read_bytes()).hexdigest()[:12]
    (OUT / '.nojekyll').touch()
    for lang, t in locales.items():
        flags = {'en': '🇬🇧', 'pl': '🇵🇱', 'zh-CN': '🇨🇳'}
        nav = ''.join(f'<a lang="{code}" hreflang="{code}" href="../{code}/"' + (' aria-current="page"' if code == lang else '') + f' aria-label="{escape(data["label"], quote=True)}" title="{escape(data["label"], quote=True)}">{flags[code]}</a>' for code, data in locales.items())
        alternates = ''.join(f'<link rel="alternate" hreflang="{code}" href="{BASE}/{code}/">' for code in locales)
        html = f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Awesome FM-1 — {escape(t['directory'])}</title><meta name="description" content="{escape(t['intro'], quote=True)}"><link rel="canonical" href="{BASE}/{lang}/">{alternates}<link rel="icon" href="../favicon.ico?v={favicon_version}" sizes="any"><link rel="stylesheet" href="../style.css?v={style_version}"><meta name="theme-color" content="#121817"></head>
<body><a class="skip" href="#main">{t['skip']}</a><header><a class="brand" href="./"><img src="../logo.svg?v={logo_version}" alt="" width="48" height="48"><span class="brand-name">AWESOME <span>FM-1</span></span></a><nav aria-label="Language">{nav}</nav>{icon_link(REPO, 'GitHub', ICONS['GitHub'], 'github')}</header>
<main id="main"><section class="hero"><div><p class="kicker">{t['eyebrow']}</p><h1>{t['title']}</h1><p class="intro">{t['intro']}</p><div class="actions">{link('#contribute', t['contribute'], 'button')}</div></div><div class="synth" aria-hidden="true"><div class="synth-top">AWESOME FM-1 <span>COMMUNITY / 001</span></div><div class="display"><span>FIND YOUR NEXT SOUND</span><svg viewBox="0 0 400 120"><path d="M0 60H25L45 12 70 108 95 12 120 108 145 12 170 108 195 12 220 108 245 12 270 108 295 12 320 108 345 12 370 60H400"/></svg><b>FM—1</b></div><div class="knobs"><i></i><i></i><i></i><span>EXPLORE<br>CREATE<br>CONTRIBUTE</span></div></div></section>
<section class="companion"><p class="kicker">01 / FM-1 FLASHER</p><h2>{t['flasherTitle']}</h2><p>{t['flasherText']}</p><div class="links">{link(FLASHER + '/' + lang + '/', t['flasherLink'])}{link('https://github.com/ekim-pl/android-fm1-flasher', t['flasherRepo'])}</div></section>
<section id="contribute" class="contribute"><div><p class="kicker">02 / PULL REQUEST</p><h2>{t['joinTitle']}</h2><p>{t['joinText']}</p>{link(REPO + '/blob/main/README.md#contributing', t['guidelines'], 'button')}</div><div><ol>{''.join('<li>' + escape(step) + '</li>' for step in t['steps'])}</ol><p class="note">{t['rules']}</p></div></section>
<section class="catalog"><h2>{t['catalogTitle']}</h2><p>{t['catalogText']}</p><div class="links">{link('../catalog.json', t['catalogLink'])}{link(REPO + '/blob/main/schema/catalog.schema.json', t['schema'])}</div></section></main><footer><span class="footer-brand"><img src="../logo.svg?v={logo_version}" alt="" width="28" height="28">Awesome FM-1</span><p>{t['footer']}</p><nav class="footer-links" aria-label="{t['socialLabel']}">{icon_link('https://ekim-pl.github.io/', t['home'], ICONS['home'])}{icon_link('https://github.com/ekim-pl', t['githubProfile'], ICONS['GitHub'])}{icon_link('https://www.youtube.com/@ekim-pl', 'YouTube', ICONS['YouTube'])}{icon_link('https://www.instagram.com/ekimpl/', 'Instagram', ICONS['Instagram'])}{icon_link('https://www.tiktok.com/@ekim_pl', 'TikTok', ICONS['TikTok'])}{icon_link('https://discord.com/users/1422549758785880215', 'Discord', ICONS['Discord'])}</nav></footer></body></html>'''
        target = OUT / lang
        target.mkdir(exist_ok=True)
        (target / 'index.html').write_text(html)
    (OUT / 'index.html').write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="icon" href="favicon.ico?v={favicon_version}" sizes="any"><meta http-equiv="refresh" content="0;url=en/"><title>Awesome FM-1</title></head><body><a href="en/">English</a> · <a href="pl/">Polski</a> · <a href="zh-CN/">简体中文</a></body></html>')
    print('Built English, Polish and Simplified Chinese pages in _site/')


if __name__ == '__main__':
    build()
