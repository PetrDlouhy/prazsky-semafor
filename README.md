# Pražský semafor

Hlídač pražských projektů a slibů: dokumentuje, co si Praha schválila,
co skutečně vzniklo a co se cestou změnilo. Statický web bez JavaScriptu,
generovaný z otevřených dat a odkazovaných zdrojů.

## Jak se web staví

```bash
python3 build.py
```

Bez závislostí (stačí Python 3.9+). Výstup jde do `dist/`, včetně
`preview.html` (celý web v jednom souboru pro rychlé sdílení).

## Struktura dat

- `data/projects/*.json`: spisy projektů (události, hlasování, karta, odkazy)
- `data/promises.json`: doslovné sliby z programů a koaličních dokumentů
- `data/ramce.json`: strategie a koncepce, kterými se město měří
- `data/persons.json`: ruční doplňky k osobám (role, poznámky)
- `data/rolls/*.json`: jmenovitá hlasování městských částí, přepsaná
  z úředních exportů (Praha 1: TXT v cp1250, Praha 8: HTML v UTF-16LE)
- `data/cache/`: stažené odpovědi veřejného rozhraní praha.eu
  (jmenovitá hlasování ZHMP, kluby, zastupitelé); build je offline
  reprodukovatelný

Metodika výběru projektů, stupňů doloženosti a hodnocení slibů je popsaná
přímo na webu na stránce Metodika.

## Opravy a doplnění

Každé tvrzení na webu má odkazovaný zdroj. Opravy a doplnění se zdrojem
jsou vítané, ideálně jako issue nebo pull request nad soubory v `data/`.
