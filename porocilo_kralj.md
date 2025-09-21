# KPOV Judge

Kot dodatno nalogo pri predmetu KPOV sem moral popraviti aplikacijo KPOV Judge. Aplikacija je napisana v programskem jeziku Python. Popravljena aplikacija je objavljena kot »vilica« na mojem Github profilu: https://github.com/gigibu5/kpov-judge

Odpravljene so bile naslednje napake:
- Knjižnjica `flask.ext.babel` se je preimenovala v `flask_babel`
- Dekorator `@babel.localeselector` je bil depreciran
- Dekorator nadomesti `babel.init_app(app, locale_selector=get_locale)` tik pred metodo `app.run`

Za lažjo namestitev in razvoj aplikacije sem dodal nekaj konfiguracijskih datotek v `.gitignore` ter ustvaril datoteko `requirements.txt`. Datoteka requirements.txt se v Python projektih uporablja zato, da na enem mestu zabeleži vse zunanje knjižnice in njihove različice, ki jih tvoj projekt potrebuje. Vse knjižnjice se namestijo z uporabo ukaza `pip install -r requirements.txt`.
